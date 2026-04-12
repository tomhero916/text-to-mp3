# 🎙 Text to MP3

テキストを高品質な音声MP3に変換するローカルWebアプリ。

## 特徴

- **3つの入力方法**: コピー&ペースト / ファイルアップロード / URL自動抽出
- **2つのTTSプロバイダー**: OpenAI（簡単・有料）/ Google Cloud（高音質・月100万文字無料）
- **APIキーはローカル保存**: 外部送信なし、自分のPCにだけ保存
- **長文対応**: 自動でチャンク分割し、シームレスに結合
- **日本語最適化**: HTMLの折り返し改行や装飾文字を自動修復

## クイックスタート

詳しいセットアップは `SETUP.md` を参照してください。最短手順:

```bash
cd text_to_mp3_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg     # macOS（未インストールの場合）
streamlit run app.py
```

ブラウザが自動で開きます。サイドバーで OpenAI APIキー（または Google Cloud 認証情報）を設定すれば、すぐに使えます。

## ファイル構成

```
text_to_mp3_app/
├── app.py              # Streamlitメインアプリ
├── tts_providers.py    # OpenAI/Google両対応のTTSロジック
├── text_extractors.py  # URL本文抽出・ファイル読み込み
├── requirements.txt    # 依存ライブラリ
├── README.md           # このファイル
└── SETUP.md            # 詳細セットアップガイド
```

## 料金の目安

| プロバイダー | 料金 | メルマガ1本（3万文字） |
|---|---|---|
| OpenAI tts-1 | $0.015/1000文字 | 約60円 |
| OpenAI tts-1-hd | $0.030/1000文字 | 約120円 |
| Google Cloud Chirp 3 HD | 月100万文字まで無料 | 無料 |

## ライセンス

自由に使用・改変・再配布可能。
