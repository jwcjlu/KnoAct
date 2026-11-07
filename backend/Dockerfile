# KnoAct 后端（FastAPI）
# 构建上下文为 backend/：docker build -t knoact-backend ./backend
# 构建参数由 docker-compose / .env 传入（默认官方源）；见 .env.example「构建加速」
FROM python:3.10-slim

ARG PIP_INDEX_URL=https://pypi.org/simple/
ARG PIP_TRUSTED_HOST=pypi.org
ARG APT_MIRROR=deb.debian.org

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST} \
    TZ=Asia/Shanghai

# tzdata：每日任务调度（03:00）与 date.today() 按北京时间计算
RUN set -eux; \
    if [ "$APT_MIRROR" != "deb.debian.org" ]; then \
      if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
      elif [ -f /etc/apt/sources.list ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list; \
      fi; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# requirements.txt 未变时 Docker 层缓存会跳过本步；勿加 docker/dockerfile 前端镜像（国内拉 Hub 很慢）
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    || ( [ "$PIP_INDEX_URL" = "https://pypi.org/simple/" ] && exit 1; \
        PIP_INDEX_URL=https://pypi.org/simple/ PIP_TRUSTED_HOST=pypi.org \
        pip install -r requirements.txt )

COPY app ./app
COPY migrate_model_catalog.py .
# uploads 存 PDF 与拆页图片，/data 存 SQLite 库；二者由 docker-compose 挂卷持久化
RUN mkdir -p uploads /data

ENV DATABASE_URL=sqlite:////data/zhixueban.db
EXPOSE 8010

# seed() 幂等：建表 + 补列迁移 + 空库时写入演示数据
CMD ["sh", "-c", "python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port 8010"]
