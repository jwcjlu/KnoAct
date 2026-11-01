# KnoAct 后端（FastAPI）
# 构建上下文为 backend/：docker build -t knoact-backend ./backend
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

# tzdata：每日任务调度（03:00）与 date.today() 按北京时间计算
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY migrate_model_catalog.py .
# uploads 存 PDF 与拆页图片，/data 存 SQLite 库；二者由 docker-compose 挂卷持久化
RUN mkdir -p uploads /data

ENV DATABASE_URL=sqlite:////data/zhixueban.db
EXPOSE 8010

# seed() 幂等：建表 + 补列迁移 + 空库时写入演示数据
CMD ["sh", "-c", "python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port 8010"]
