# 部署用 image(Google Cloud Run / 任何支援 container 嘅平台)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 先裝依賴(利用 layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再 copy 程式碼
COPY app ./app
COPY scripts ./scripts

# Cloud Run 會經 $PORT 傳入 port(預設 8080)
ENV PORT=8080
EXPOSE 8080

# 啟動前確保資料表存在 + 建立管理員,再開 web server
CMD ["sh", "-c", "python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
