# Text to MP3 セットアップガイド

このアプリは、テキストをMP3音声に変換するローカルWebアプリです。
セットアップは20〜30分程度で完了します。

---

## 必要なもの

- macOS / Windows / Linux（このガイドは macOS 中心）
- Python 3.10 以上
- インターネット接続
- 以下のいずれかのAPIキー:
  - **OpenAI APIキー**（推奨・5分で取得）
  - **Google Cloud TTS サービスアカウント**（無料枠あり・15分で取得）

---

## ステップ 1: Python と ffmpeg をインストール

### macOSの場合

[Homebrew](https://brew.sh/) を使うのが最も簡単です。

```bash
# Homebrewをまだ入れていない場合
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python と ffmpeg をインストール
brew install python@3.12 ffmpeg
```

### Windowsの場合

1. [python.org](https://www.python.org/downloads/) からPython 3.12をダウンロードしてインストール
   - インストール時に「Add Python to PATH」にチェック
2. [ffmpeg.org](https://ffmpeg.org/download.html) からffmpegをダウンロードしてPATHに追加

### Linuxの場合

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg
```

---

## ステップ 2: アプリのフォルダを準備

このアプリのフォルダ `text_to_mp3_app` を、好きな場所に配置してください。

```bash
# 例: ホームディレクトリ直下に置く
mv ~/Downloads/text_to_mp3_app ~/
cd ~/text_to_mp3_app
```

---

## ステップ 3: Python仮想環境を作成

```bash
cd ~/text_to_mp3_app
python3 -m venv venv
source venv/bin/activate
```

仮想環境が有効になると、プロンプトの先頭に `(venv)` が表示されます。

⚠️ アプリを起動するたびに `source venv/bin/activate` が必要です。

---

## ステップ 4: 必要なライブラリをインストール

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

数分かかります。完了したら次のステップへ。

---

## ステップ 5: アプリを起動

```bash
streamlit run app.py
```

ブラウザが自動で開き、`http://localhost:8501` でアプリが表示されます。

---

## ステップ 6: TTSプロバイダーの設定

サイドバーで OpenAI か Google Cloud のどちらかを選んで設定します。

### 🟢 オプションA: OpenAI（簡単・5分）

#### A-1. APIキーの取得

1. [platform.openai.com/api-keys](https://platform.openai.com/api-keys) にログイン
2. アカウントがなければ作成（クレジットカード登録が必要）
3. 「Create new secret key」をクリック
4. 適当な名前（例: `text-to-mp3`）を入力して作成
5. 表示された `sk-...` で始まる文字列をコピー（**この画面を閉じると二度と表示されない**ので注意）

#### A-2. アプリに設定

1. アプリのサイドバーで「TTSプロバイダー」を **OpenAI** に
2. 「API Key」欄に `sk-...` を貼り付け
3. モデルと音声を選択（デフォルト: tts-1 / alloy）

設定は自動で `~/.text_to_mp3_app/config.json` に保存され、次回起動時も覚えています。

#### A-3. 料金

- **tts-1**: 1000文字あたり $0.015（約2円）
- **tts-1-hd**: 1000文字あたり $0.030（約4円）

メルマガ1本（3万文字）≒ 約60円。月数本程度なら数百円で済みます。

---

### 🔵 オプションB: Google Cloud（高音質・月100万文字無料）

#### B-1. プロジェクト作成

1. [Google Cloud Console](https://console.cloud.google.com/) にログイン
2. 上部のプロジェクト選択メニュー →「新しいプロジェクト」
3. プロジェクト名: `text-to-mp3` など
4. 課金アカウントを設定（クレジットカード登録が必要だが、無料枠内なら請求は発生しない）

#### B-2. Text-to-Speech API を有効化

1. 検索バーで「Cloud Text-to-Speech API」を検索
2. 「有効にする」をクリック

#### B-3. サービスアカウント作成

1. ナビゲーションメニュー →「IAMと管理」→「サービスアカウント」
2. 「サービスアカウントを作成」
3. サービスアカウント名: `text-to-mp3` など
4. ロールに「**Cloud Text-to-Speech ユーザー**」を選択
5. 「完了」

#### B-4. キーの作成

1. サービスアカウント一覧から作成したアカウントをクリック
2. 「キー」タブ →「鍵を追加」→「新しい鍵を作成」
3. キーのタイプ: **JSON** を選択
4. 「作成」をクリック → JSONファイルがダウンロードされる

#### B-5. アプリに設定

1. アプリのサイドバーで「TTSプロバイダー」を **Google Cloud** に
2. ダウンロードしたJSONファイルをエディタで開き、**中身を全部コピー**
3. 「サービスアカウントキー (JSON)」欄に貼り付け
4. 言語と音声を選択

#### B-6. 料金

**月100万文字まで完全無料**。メルマガ用途ならまず無料枠を超えません。
超過後は100万文字あたり $30（約4500円）。

---

## ステップ 7: 使ってみる

1. 「テキスト入力」のタブから入力方法を選ぶ
   - **コピー&ペースト**: テキストエリアに貼り付け
   - **ファイル**: .txt や .md ファイルをアップロード
   - **URL**: ブログ記事やニュースのURLを入力（自動で本文抽出）
2. 「テキストを取り込む」ボタンを押す
3. プレビューを確認
4. 「🎙 MP3に変換」ボタンを押す
5. 進捗バーが進み、完了したら結果欄でプレビュー再生 & ダウンロード

---

## 日常運用

### 起動コマンド

```bash
cd ~/text_to_mp3_app
source venv/bin/activate
streamlit run app.py
```

毎回これを打つのが面倒なら、シェルスクリプトを作っておくと便利:

```bash
cat > ~/text_to_mp3_app/start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
streamlit run app.py
EOF
chmod +x ~/text_to_mp3_app/start.sh
```

以降は `~/text_to_mp3_app/start.sh` をダブルクリックするだけで起動できます。

### 停止方法

ターミナルで `Ctrl+C` を押すとアプリが停止します。

---

## トラブルシューティング

### `command not found: streamlit`

仮想環境を有効化していません:
```bash
source ~/text_to_mp3_app/venv/bin/activate
```

### `ModuleNotFoundError: No module named 'xxx'`

ライブラリのインストール忘れ:
```bash
cd ~/text_to_mp3_app
source venv/bin/activate
pip install -r requirements.txt
```

### `[Errno 2] No such file or directory: 'ffmpeg'`

ffmpeg未インストール:
```bash
brew install ffmpeg
```

### 「変換エラー: チャンクXでテキストエラー」

長すぎる文がエラーになっています。サイドバー →「🔧 詳細設定」→「1文の最大文字数」を100→80→60と下げてください。

### URL抽出に失敗する

サイトによっては自動抽出に対応していません。その場合はサイトを開いて、手動でテキストをコピーして「コピー&ペースト」タブを使ってください。

### APIキーをリセットしたい

```bash
rm ~/.text_to_mp3_app/config.json
```

その後アプリを再起動して設定し直してください。

### Google Cloudで「PERMISSION_DENIED」エラー

サービスアカウントに「Cloud Text-to-Speech ユーザー」ロールが付与されているか、またはText-to-Speech APIが有効になっているか確認してください。

---

## 仕組みの簡単な説明

1. **テキスト取得**: コピペ・ファイル・URLから本文を取得
2. **クリーニング**: URL・装飾文字・読み上げ不可文字を除去
3. **チャンク分割**: TTS APIの制限に合わせて分割（約2000バイトずつ）
4. **文長対策**: 100文字を超える長文を読点位置で句点に置換
5. **TTS変換**: 選択したプロバイダーで各チャンクをMP3生成
6. **結合**: pydubでチャンクを連結（200msの無音を挿入）
7. **ダウンロード**: ブラウザから直接MP3保存

---

## プライバシーについて

- **APIキーは外部に送信されません**。`~/.text_to_mp3_app/config.json` にのみ保存されます。
- **テキストは TTS API には送信されます**（OpenAI または Google Cloud のサーバー）。これがないと音声化できないためです。
- どちらのプロバイダーも「APIで送信されたデータをモデル学習には使用しない」と明言しています。

---

## ライセンス

自由に使用・改変・再配布できます。
