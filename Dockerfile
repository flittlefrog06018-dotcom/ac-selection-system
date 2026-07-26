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
ENV PORT=8000

# 4. 啟動 FastAPI 服務
CMD ["python", "backend/main.py"]
