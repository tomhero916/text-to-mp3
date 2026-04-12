"""
tts_providers.py
────────────────
OpenAI と Google Cloud TTS の両方に対応するTTSプロバイダー。

メルマガスクリプトで動作確認済みの分割ロジック（チャンク分割・文長制限対策）
をそのまま流用しています。
"""

import io
import re
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional


# ══════════════════════════════════════════
# テキスト前処理（メルマガスクリプトから流用）
# ══════════════════════════════════════════

def clean_text(text: str) -> str:
    """テキストをTTS向けにクリーニングする。"""
    # URL・メールアドレスを除去
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[\w.+-]+@[\w-]+\.[a-zA-Z]+', '', text)

    # 装飾用罫線を除去
    text = re.sub(r'[─━\-=＝]{3,}', '', text)

    # BMP外の文字を全て除去
    text = ''.join(c for c in text if ord(c) <= 0xFFFF)

    # TTSが読める文字だけを残すホワイトリスト方式
    def _is_tts_safe(c):
        cp = ord(c)
        if cp <= 0x007F:                      return True
        if 0x3000 <= cp <= 0x303F:            return True
        if 0x3040 <= cp <= 0x309F:            return True
        if 0x30A0 <= cp <= 0x30FF:            return True
        if 0x4E00 <= cp <= 0x9FFF:            return True
        if 0xFF01 <= cp <= 0xFF5E:            return True
        if 0xFF61 <= cp <= 0xFF9F:            return True
        if 0x3400 <= cp <= 0x4DBF:            return True
        if cp in (0x2015, 0x2026, 0x2018, 0x2019, 0x201C, 0x201D,
                  0x00D7, 0x00F7, 0x2013, 0x2014, 0x2025, 0x2030,
                  0x2103, 0x301C, 0xFF5E):    return True
        return False
    text = ''.join(c if _is_tts_safe(c) else '' for c in text)

    # 読み上げ不要な記号を除去
    blocked = {
        chr(0xFF3E), chr(0xFF3F), chr(0xFFE3), chr(0xFF5C), chr(0xFF40),
        '^', '_', '~', '|', '`', '{', '}', '<', '>', '[', ']', '\\',
    }
    text = ''.join('' if c in blocked else c for c in text)

    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _byte_len(s: str) -> int:
    return len(s.encode('utf-8'))


def split_text_for_tts(text: str, max_bytes: int = 2000) -> list:
    """テキストをmax_bytes以下のチャンクに分割する。"""
    paragraphs = text.split('\n\n')
    chunks = []
    current = ''

    for para in paragraphs:
        separator = '\n\n' if current else ''
        candidate = current + separator + para
        if _byte_len(candidate) <= max_bytes:
            current = candidate
        else:
            if current:
                chunks.append(current)
                current = ''
            if _byte_len(para) > max_bytes:
                chunks.extend(_split_paragraph(para, max_bytes))
            else:
                current = para

    if current:
        chunks.append(current)
    return chunks


def _split_paragraph(para: str, max_bytes: int) -> list:
    sentences = re.split(r'(?<=。)', para)
    chunks = []
    current = ''
    for sent in sentences:
        candidate = current + sent
        if _byte_len(candidate) <= max_bytes:
            current = candidate
        else:
            if current:
                chunks.append(current)
                current = ''
            if _byte_len(sent) > max_bytes:
                chunks.extend(_force_split(sent, max_bytes))
            else:
                current = sent
    if current:
        chunks.append(current)
    return chunks


def _force_split(text: str, max_bytes: int) -> list:
    chunks = []
    current = ''
    for ch in text:
        if _byte_len(current + ch) <= max_bytes:
            current += ch
        else:
            chunks.append(current)
            current = ch
    if current:
        chunks.append(current)
    return chunks


def prepare_for_tts(text: str, max_sentence_len: int = 100) -> str:
    """
    APIに送る直前のテキスト整形。
    - HTMLの折り返し改行を修復
    - 長すぎる文を読点位置で句点に置換して分割
    """
    sentence_end_chars = set(chr(0x3002) + '.!?' + chr(0xFF01) + chr(0xFF1F))

    lines = text.split('\n')
    merged = ''
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if merged and merged[-1] not in sentence_end_chars:
            merged += line
        else:
            if merged:
                merged += ' '
            merged += line
    text = merged

    parts = re.split('(' + chr(0x3002) + ')', text)
    result = []
    for part in parts:
        if part == chr(0x3002):
            result.append(part)
            continue
        if len(part) <= max_sentence_len:
            result.append(part)
            continue
        segments = part.split(chr(0x3001))
        rebuilt = ''
        current = ''
        for j, seg in enumerate(segments):
            sep = chr(0x3001) if j < len(segments) - 1 else ''
            candidate = current + seg + sep
            if len(candidate) <= max_sentence_len:
                current = candidate
            else:
                if current:
                    rebuilt += current.rstrip(chr(0x3001)) + chr(0x3002)
                current = seg + sep
        if current:
            rebuilt += current.rstrip(chr(0x3001))
        result.append(rebuilt)

    return ''.join(result)


# ══════════════════════════════════════════
# TTSプロバイダー（共通インターフェース）
# ══════════════════════════════════════════

class TTSProvider(ABC):
    @abstractmethod
    def synthesize_chunk(self, text: str) -> bytes:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


# ══════════════════════════════════════════
# OpenAI TTS
# ══════════════════════════════════════════

OPENAI_MODELS = ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"]

# 全ボイス（モデルに応じて使えるものが違う）
OPENAI_VOICES_ALL = [
    "alloy", "ash", "ballad", "coral", "echo", "fable",
    "nova", "onyx", "sage", "shimmer", "verse",
]

# 日本語に比較的適しているボイス
OPENAI_VOICES_JA = ["nova", "shimmer", "alloy", "sage", "coral"]

# 英語ネイティブのボイス
OPENAI_VOICES_EN = OPENAI_VOICES_ALL


def get_openai_voices(language: str = "ja") -> list:
    """言語に応じた推奨ボイス一覧を返す。"""
    if language == "ja":
        return OPENAI_VOICES_JA
    return OPENAI_VOICES_EN


class OpenAITTS(TTSProvider):
    def __init__(self, api_key: str, voice: str = "alloy",
                 model: str = "tts-1", speed: float = 1.0,
                 instructions: str = ""):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.voice = voice
        self.model = model
        self.speed = speed  # 0.25〜4.0
        self.instructions = instructions  # gpt-4o-mini-tts のみ対応

    @property
    def name(self) -> str:
        return f"OpenAI ({self.model}, {self.voice}, x{self.speed})"

    def synthesize_chunk(self, text: str) -> bytes:
        # gpt-4o-mini-tts のみ instructions に対応
        kwargs = dict(
            model=self.model,
            voice=self.voice,
            input=text,
            response_format="mp3",
            speed=self.speed,
        )
        if self.model == "gpt-4o-mini-tts" and self.instructions:
            kwargs["instructions"] = self.instructions

        response = self.client.audio.speech.create(**kwargs)
        return response.content


# ══════════════════════════════════════════
# Google Cloud TTS (Chirp 3 HD)
# ══════════════════════════════════════════

GOOGLE_VOICES_JA = [
    "ja-JP-Chirp3-HD-Autonoe",
    "ja-JP-Chirp3-HD-Charon",
    "ja-JP-Chirp3-HD-Kore",
    "ja-JP-Chirp3-HD-Puck",
]

GOOGLE_VOICES_EN = [
    "en-US-Chirp3-HD-Autonoe",
    "en-US-Chirp3-HD-Charon",
    "en-US-Chirp3-HD-Kore",
    "en-US-Chirp3-HD-Puck",
]


class GoogleCloudTTS(TTSProvider):
    def __init__(self, credentials_json: str,
                 voice: str = "ja-JP-Chirp3-HD-Autonoe",
                 speed: float = 1.0):
        import json
        from google.cloud import texttospeech
        from google.oauth2 import service_account

        creds_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(creds_dict)

        self.client = texttospeech.TextToSpeechClient(
            credentials=credentials,
            client_options={
                "api_endpoint": "asia-northeast1-texttospeech.googleapis.com"
            },
        )
        self.voice = voice
        self.speed = speed  # 後処理で適用
        self.language_code = '-'.join(voice.split('-')[:2])
        self._tts_module = texttospeech

    @property
    def name(self) -> str:
        return f"Google Cloud Chirp 3 HD ({self.voice}, x{self.speed})"

    def synthesize_chunk(self, text: str) -> bytes:
        # Chirp 3 HDはspeaking_rateに非対応のため、APIには等速で送る
        voice_params = self._tts_module.VoiceSelectionParams(
            language_code=self.language_code,
            name=self.voice,
        )
        audio_config = self._tts_module.AudioConfig(
            audio_encoding=self._tts_module.AudioEncoding.MP3,
        )
        response = self.client.synthesize_speech(
            input=self._tts_module.SynthesisInput(text=text),
            voice=voice_params,
            audio_config=audio_config,
        )
        return response.audio_content


# ══════════════════════════════════════════
# 統合変換関数
# ══════════════════════════════════════════

def convert_text_to_mp3(
    text: str,
    provider: TTSProvider,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    chunk_max_bytes: int = 2000,
    max_sentence_len: int = 100,
    chunk_silence_ms: int = 200,
) -> bytes:
    """
    テキストをMP3バイト列に変換する。

    Args:
        text: 変換するテキスト
        provider: TTSプロバイダー
        progress_callback: 進捗報告 (current, total, message)
    Returns:
        MP3バイト列
    """
    from pydub import AudioSegment

    if progress_callback:
        progress_callback(0, 1, "テキストをクリーニング中...")
    cleaned = clean_text(text)

    chunks = split_text_for_tts(cleaned, max_bytes=chunk_max_bytes)
    total = len(chunks)
    if progress_callback:
        progress_callback(0, total, f"{len(cleaned)}文字を{total}チャンクに分割しました")

    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=chunk_silence_ms)

    for i, chunk in enumerate(chunks, start=1):
        prepared = prepare_for_tts(chunk, max_sentence_len=max_sentence_len)

        if progress_callback:
            progress_callback(
                i, total,
                f"チャンク {i}/{total} を変換中 ({len(prepared)}文字)"
            )

        mp3_bytes = None
        last_error = None
        for attempt in range(3):
            try:
                mp3_bytes = provider.synthesize_chunk(prepared)
                break
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                if '400' in error_str or 'invalid' in error_str:
                    raise RuntimeError(
                        f"チャンク{i}でテキストエラー: {e}\n"
                        f"チャンク先頭: 「{prepared[:80]}...」"
                    )
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    time.sleep(wait)

        if mp3_bytes is None:
            raise RuntimeError(f"チャンク{i}の変換に3回失敗: {last_error}")

        segment = AudioSegment.from_file(io.BytesIO(mp3_bytes), format='mp3')
        if i > 1:
            combined += silence
        combined += segment

    if progress_callback:
        progress_callback(total, total, "MP3を生成中...")

    # Google CloudはAPI側で速度変更非対応なので、ここで後処理する
    # OpenAIは既にAPIで速度適用済みなのでスキップ
    speed = getattr(provider, 'speed', 1.0)
    if isinstance(provider, GoogleCloudTTS) and speed != 1.0:
        if progress_callback:
            progress_callback(total, total, f"再生速度を {speed}x に調整中...")
        # pydubのspeedupは1.0以上のみ対応。それ以外はframe_rate操作で実現
        if speed > 1.0:
            combined = combined.speedup(playback_speed=speed)
        else:
            # 遅くする場合: フレームレートを変えてから元に戻す
            new_frame_rate = int(combined.frame_rate * speed)
            combined = combined._spawn(
                combined.raw_data,
                overrides={'frame_rate': new_frame_rate}
            ).set_frame_rate(combined.frame_rate)

    output = io.BytesIO()
    combined.export(output, format='mp3', bitrate='128k')
    return output.getvalue()
