# Python イメージ（3.12 のスリム版を使用）
FROM python:3.12-slim

# 作業ディレクトリ
WORKDIR /app

# 依存関係ファイルを先にコピーし、インストール層をキャッシュ可能にする
COPY requirements.txt .

# 依存関係をインストール（--no-cache-dirでビルドイメージを小さくする）
# Python 3.12 イメージは pip が pip にリンクされているため、pip で実行
RUN pip install --no-cache-dir -r requirements.txt

# その他のBotコードをすべてコピー
COPY . .

# Bot 起動
# Python 3.12 イメージは python コマンドが python3 にリンクされているため、python で実行
CMD ["python", "bot.py"]
