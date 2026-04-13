"""
app.py
──────
テキストをMP3に変換するStreamlit Webアプリ。

使い方:
  streamlit run app.py
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

from tts_providers import (
    OpenAITTS,
    GoogleCloudTTS,
    OPENAI_MODELS,
    OPENAI_VOICES_JA,
    OPENAI_VOICES_EN,
    GOOGLE_VOICES_JA,
    GOOGLE_VOICES_EN,
    convert_text_to_mp3,
)
from text_extractors import extract_from_url, extract_from_file, extract_from_pdf


# ══════════════════════════════════════════
# 設定ファイル管理
# ══════════════════════════════════════════

CONFIG_DIR = Path.home() / ".text_to_mp3_app"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: dict):
    CONFIG_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except Exception:
        pass



def reset_input_state():
    """新しいテキストを取り込む際に、前の状態をすべてクリアする。"""
    st.session_state.input_text = ""
    st.session_state.input_title = ""
    st.session_state.mp3_data = None
    st.session_state.mp3_filename = None
    # text_versionをインクリメントして、編集エリアのキーを変える
    st.session_state.text_version += 1


def sanitize_filename(s: str) -> str:
    s = re.sub(r'[\\/*?:"<>|]', '', s)
    s = s.strip()[:60]
    return s or "output"


# ══════════════════════════════════════════
# Streamlitアプリ本体
# ══════════════════════════════════════════

st.set_page_config(
    page_title="Text to MP3",
    page_icon="🎙",
    layout="wide",
)

st.title("🎙 Text to MP3")
st.caption("テキストを高品質な音声MP3に変換します")

# セッション状態の初期化
if 'config' not in st.session_state:
    st.session_state.config = load_config()
if 'input_text' not in st.session_state:
    st.session_state.input_text = ""
if 'input_title' not in st.session_state:
    st.session_state.input_title = ""
if 'mp3_data' not in st.session_state:
    st.session_state.mp3_data = None
if 'mp3_filename' not in st.session_state:
    st.session_state.mp3_filename = None
if 'text_version' not in st.session_state:
    st.session_state.text_version = 0


# ══════════════════════════════════════════
# サイドバー: TTS設定
# ══════════════════════════════════════════

with st.sidebar:
    st.header("⚙️ TTS設定")

    provider_type = st.radio(
        "TTSプロバイダー",
        options=["OpenAI", "Google Cloud"],
        index=0 if st.session_state.config.get("provider", "OpenAI") == "OpenAI" else 1,
        help="OpenAIは設定が簡単。Google Cloudは月100万文字まで無料で高音質。",
    )

    if provider_type == "OpenAI":
        st.markdown("**OpenAI 設定**")

        api_key = st.text_input(
            "API Key",
            value=st.session_state.config.get("openai_api_key", ""),
            type="password",
            placeholder="sk-...",
            help="https://platform.openai.com/api-keys で取得",
        )

        with st.expander("📖 APIキーの取得方法"):
            st.markdown("""
            1. [platform.openai.com](https://platform.openai.com/api-keys) にログイン
            2. 「Create new secret key」をクリック
            3. 表示された `sk-...` をコピーして上の欄に貼り付け
            4. クレジットカードの登録が必要（従量課金）

            **料金目安**: 1000文字あたり約$0.015〜$0.030（約2〜4円）
            メルマガ1本（3万文字）≒ 約60〜120円
            """)

        # 言語選択
        openai_language = st.radio(
            "言語",
            options=["日本語", "英語"],
            index=0 if st.session_state.config.get("openai_language", "ja") == "ja" else 1,
            horizontal=True,
            help="日本語の場合は推奨ボイスのみ表示されます",
        )
        lang_code = "ja" if openai_language == "日本語" else "en"

        # 日本語の場合は注意書き
        if lang_code == "ja":
            st.info(
                "💡 OpenAIの音声は英語に最適化されています。"
                "日本語の品質を重視する場合は、サイドバー上部で "
                "**Google Cloud Chirp 3 HD** を選ぶことを強くおすすめします。"
            )

        model = st.selectbox(
            "モデル",
            options=OPENAI_MODELS,
            index=OPENAI_MODELS.index(
                st.session_state.config.get("openai_model", "gpt-4o-mini-tts")
            ) if st.session_state.config.get("openai_model", "gpt-4o-mini-tts") in OPENAI_MODELS else 0,
            help=(
                "gpt-4o-mini-tts: 最新・多言語対応・日本語に強い（推奨）\n"
                "tts-1: 標準品質・速い・英語向け\n"
                "tts-1-hd: 高品質・やや遅い・英語向け"
            ),
        )

        # 言語に応じたボイス一覧
        available_voices = OPENAI_VOICES_JA if lang_code == "ja" else OPENAI_VOICES_EN
        default_voice = st.session_state.config.get("openai_voice", "nova")
        if default_voice not in available_voices:
            default_voice = available_voices[0]

        voice = st.selectbox(
            "音声",
            options=available_voices,
            index=available_voices.index(default_voice),
            help=(
                "日本語の場合: nova / shimmer / alloy が比較的自然です。"
                "音声によって品質が大きく異なるので、好みのものを試してください。"
            ),
        )

        # gpt-4o-mini-tts の場合のみ instructions 入力欄
        instructions = ""
        if model == "gpt-4o-mini-tts":
            instructions = st.text_area(
                "話し方の指示（任意）",
                value=st.session_state.config.get("openai_instructions", ""),
                placeholder="例: 落ち着いた口調でゆっくり話してください",
                height=80,
                help="gpt-4o-mini-tts のみ対応。話し方を自然言語で指定できます。",
            )

        if api_key:
            st.session_state.config.update({
                "provider": "OpenAI",
                "openai_api_key": api_key,
                "openai_language": lang_code,
                "openai_model": model,
                "openai_voice": voice,
                "openai_instructions": instructions,
            })
            save_config(st.session_state.config)

    else:  # Google Cloud
        st.markdown("**Google Cloud 設定**")

        creds_json = st.text_area(
            "サービスアカウントキー (JSON)",
            value=st.session_state.config.get("google_credentials", ""),
            height=150,
            placeholder='{"type": "service_account", ...}',
            help="JSONファイルの中身を全てコピーして貼り付け",
        )

        with st.expander("📖 サービスアカウントキーの取得方法"):
            st.markdown("""
            1. [Google Cloud Console](https://console.cloud.google.com/) にログイン
            2. 新規プロジェクトを作成（または既存のものを選択）
            3. 「Cloud Text-to-Speech API」を有効化
            4. 「IAMと管理」→「サービスアカウント」→「作成」
            5. ロールに「Cloud Text-to-Speech ユーザー」を選択
            6. 作成したアカウント →「キー」タブ →「鍵を追加」→ JSON形式
            7. ダウンロードしたJSONファイルの中身を全部コピーして上に貼り付け

            **料金**: 月100万文字まで無料（メルマガ4本/月なら完全無料）
            """)

        language = st.radio(
            "言語",
            options=["日本語", "英語"],
            horizontal=True,
        )

        voices = GOOGLE_VOICES_JA if language == "日本語" else GOOGLE_VOICES_EN
        default_voice = st.session_state.config.get(
            "google_voice", "ja-JP-Chirp3-HD-Autonoe"
        )
        if default_voice not in voices:
            default_voice = voices[0]

        voice = st.selectbox(
            "音声",
            options=voices,
            index=voices.index(default_voice),
        )

        if creds_json:
            st.session_state.config.update({
                "provider": "Google Cloud",
                "google_credentials": creds_json,
                "google_voice": voice,
            })
            save_config(st.session_state.config)

    st.divider()

    with st.expander("🔧 詳細設定"):
        speed = st.slider(
            "再生速度",
            min_value=0.5, max_value=2.0,
            value=st.session_state.config.get("speed", 1.0),
            step=0.05,
            help="1.0が等速。OpenAIはAPI側で、Google Cloudは生成後の後処理で適用。",
        )
        max_sentence_len = st.slider(
            "1文の最大文字数",
            min_value=50, max_value=200,
            value=st.session_state.config.get("max_sentence_len", 100),
            step=10,
            help="長すぎる文を読点で分割する閾値。エラーが出る場合は下げる。",
        )
        chunk_silence_ms = st.slider(
            "チャンク間の無音長（ミリ秒）",
            min_value=0, max_value=1000,
            value=st.session_state.config.get("chunk_silence_ms", 200),
            step=50,
        )
        st.session_state.config.update({
            "speed": speed,
            "max_sentence_len": max_sentence_len,
            "chunk_silence_ms": chunk_silence_ms,
        })
        save_config(st.session_state.config)


# ══════════════════════════════════════════
# メイン領域: 入力タブ
# ══════════════════════════════════════════

st.header("📝 テキスト入力")

tab_paste, tab_file, tab_url = st.tabs(["コピー&ペースト", "ファイル", "URL"])

with tab_paste:
    pasted = st.text_area(
        "テキストを貼り付けてください",
        height=300,
        placeholder="ここにテキストを貼り付けて、下の「テキストを取り込む」ボタンを押してください...",
        key="paste_area",
    )
    paste_title = st.text_input(
        "ファイル名（省略可）",
        placeholder="例: 朝のニュース",
        key="paste_title",
    )
    if st.button("📋 テキストを取り込む", key="paste_btn"):
        if pasted.strip():
            reset_input_state()
            st.session_state.input_text = pasted
            st.session_state.input_title = paste_title or ""
            st.success(f"✅ {len(pasted)}文字を取り込みました")
            st.rerun()
        else:
            st.warning("テキストが空です")

with tab_file:
    uploaded = st.file_uploader(
        "テキストファイルをアップロード",
        type=["txt", "md", "pdf"],
        help="対応形式: テキスト(UTF-8/Shift_JIS/EUC-JP)、Markdown、PDF",
    )
    if uploaded is not None:
        if st.button("📁 ファイルを取り込む", key="file_btn"):
            try:
                # 拡張子で処理を分岐
                if uploaded.name.lower().endswith(".pdf"):
                    title, text = extract_from_pdf(uploaded)
                else:
                    title, text = extract_from_file(uploaded)
                reset_input_state()
                st.session_state.input_text = text
                st.session_state.input_title = title
                st.success(f"✅ {len(text)}文字を取り込みました（{title}）")
                st.rerun()
            except Exception as e:
                st.error(f"❌ ファイル読み込みエラー: {e}")

with tab_url:
    url = st.text_input(
        "URL",
        placeholder="https://example.com/article",
        key="url_input",
    )
    if st.button("🌐 URLから取り込む", key="url_btn"):
        if url:
            with st.spinner("URLから本文を抽出中..."):
                try:
                    title, text = extract_from_url(url)
                    reset_input_state()
                    st.session_state.input_text = text
                    st.session_state.input_title = title
                    st.success(f"✅ {len(text)}文字を取り込みました（{title}）")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")
        else:
            st.warning("URLを入力してください")


# ══════════════════════════════════════════
# プレビュー & 変換
# ══════════════════════════════════════════

if st.session_state.input_text:
    st.divider()
    st.header("📄 プレビュー")

    char_count = len(st.session_state.input_text)

    col1, col2, col3 = st.columns(3)
    col1.metric("文字数", f"{char_count:,}")
    col2.metric("予想チャンク数", f"{max(1, char_count // 600)}")
    col3.metric("予想時間", f"約{char_count // 400 + 1}分")

    if st.session_state.input_title:
        st.text(f"タイトル: {st.session_state.input_title}")

    with st.expander("テキストを表示/編集", expanded=False):
        edited_text = st.text_area(
            "本文",
            value=st.session_state.input_text,
            height=400,
            key=f"edit_area_v{st.session_state.text_version}",
            label_visibility="collapsed",
        )
        if edited_text != st.session_state.input_text:
            st.session_state.input_text = edited_text

    st.divider()
    st.header("🎙 音声変換")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_name = (
        f"{timestamp}_{sanitize_filename(st.session_state.input_title)}"
        if st.session_state.input_title
        else f"output_{timestamp}"
    )
    output_filename = st.text_input(
        "出力ファイル名（.mp3は自動で付きます）",
        value=default_name,
    )

    convert_disabled = False
    config = st.session_state.config

    if config.get("provider") == "OpenAI":
        if not config.get("openai_api_key"):
            st.warning("⚠️ サイドバーでOpenAI APIキーを設定してください")
            convert_disabled = True
    else:
        if not config.get("google_credentials"):
            st.warning("⚠️ サイドバーでGoogle Cloud認証情報を設定してください")
            convert_disabled = True

    if st.button(
        "🎙 MP3に変換",
        type="primary",
        disabled=convert_disabled,
        use_container_width=True,
    ):
        try:
            if config.get("provider") == "OpenAI":
                provider = OpenAITTS(
                    api_key=config["openai_api_key"],
                    voice=config.get("openai_voice", "nova"),
                    model=config.get("openai_model", "gpt-4o-mini-tts"),
                    speed=config.get("speed", 1.0),
                    instructions=config.get("openai_instructions", ""),
                )
            else:
                provider = GoogleCloudTTS(
                    credentials_json=config["google_credentials"],
                    voice=config.get("google_voice", "ja-JP-Chirp3-HD-Autonoe"),
                    speed=config.get("speed", 1.0),
                )
        except Exception as e:
            st.error(f"❌ プロバイダー初期化エラー: {e}")
            st.stop()

        progress_bar = st.progress(0.0, text="準備中...")
        status = st.empty()

        def progress_callback(current, total, message):
            ratio = current / total if total > 0 else 0
            progress_bar.progress(ratio, text=message)
            status.info(message)

        try:
            mp3_bytes = convert_text_to_mp3(
                text=st.session_state.input_text,
                provider=provider,
                progress_callback=progress_callback,
                max_sentence_len=config.get("max_sentence_len", 100),
                chunk_silence_ms=config.get("chunk_silence_ms", 200),
            )
            st.session_state.mp3_data = mp3_bytes
            st.session_state.mp3_filename = f"{output_filename}.mp3"
            progress_bar.progress(1.0, text="完了！")
            status.success(f"✅ 変換完了！({len(mp3_bytes) / 1024 / 1024:.1f}MB)")
        except Exception as e:
            progress_bar.empty()
            status.empty()
            st.error(f"❌ 変換エラー: {e}")


# ══════════════════════════════════════════
# 結果の再生 & ダウンロード
# ══════════════════════════════════════════

if st.session_state.mp3_data:
    st.divider()
    st.header("🎧 結果")

    st.audio(st.session_state.mp3_data, format="audio/mp3")

    st.download_button(
        label="📥 MP3をダウンロード",
        data=st.session_state.mp3_data,
        file_name=st.session_state.mp3_filename,
        mime="audio/mp3",
        type="primary",
        use_container_width=True,
    )


# ══════════════════════════════════════════
# フッター
# ══════════════════════════════════════════

st.divider()
with st.expander("ℹ️ このアプリについて"):
    st.markdown("""
    **Text to MP3** はテキストを高品質な音声MP3に変換するローカルWebアプリです。

    **特徴**:
    - APIキーはお手元のPCにのみ保存（外部送信なし）
    - OpenAI と Google Cloud TTS の両方に対応
    - 長文を自動でチャンク分割し、シームレスに結合
    - 日本語の読み上げに最適化

    **料金の目安**:
    - OpenAI tts-1: 1000文字あたり約$0.015（約2円）
    - Google Cloud Chirp 3 HD: 月100万文字まで無料

    **設定ファイル**: `~/.text_to_mp3_app/config.json`
    """)
