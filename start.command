
#!/bin/bash

# Text to MP3 起動スクリプト

# このファイルをダブルクリックでアプリが起動します

# このスクリプトと同じディレクトリに移動

cd "$(dirname "$0")"

# 仮想環境を有効化

source venv/bin/activate

# Streamlit起動（ブラウザが自動で開く）

streamlit run app.py

# Streamlit終了後、ターミナルを開いたままにする

echo ""

echo "アプリを終了しました。このウィンドウは閉じて構いません。"

read -p "Press Enter to close..."

