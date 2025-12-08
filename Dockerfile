# Python イメージ（3.12 のスリム版を使用）
FROM python:3.12-slim

# 作業ディレクトリ
WORKDIR /app

# 依存関係ファイルをコピー
COPY requirements.txt .

# 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリ全体をコピー
COPY . .

# Bot 起動
CMD ["python", "bot.py"]
