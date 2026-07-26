FROM python:3.10-slim

WORKDIR /app

# 1. 安裝系統套件
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. 安裝 Python 依賴套件
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. 複製全套後端與靜態前端
COPY backend/ ./backend/

EXPOSE 8000

# 4. 使用 Production 級 Gunicorn + Uvicorn 啟動並綁定動態 $PORT
CMD gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} backend.main:app
