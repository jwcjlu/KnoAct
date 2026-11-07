# KnoAct 后端（FastAPI）
# 构建上下文为 backend/：docker build -t knoact-backend ./backend
# 国内服务器默认走阿里云 PyPI 镜像；海外可：--build-arg PIP_INDEX_URL=https://pypi.org/simple
FROM python:3.10-slim

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_TRUSTED_HOST=mirrors.aliyun.com
ARG APT_MIRROR=mirrors.aliyun.com

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
    && pip install -r requirements.txt

COPY app ./app
COPY migrate_model_catalog.py .
# uploads 存 PDF 与拆页图片，/data 存 SQLite 库；二者由 docker-compose 挂卷持久化
RUN mkdir -p uploads /data

ENV DATABASE_URL=sqlite:////data/zhixueban.db
EXPOSE 8010

# seed() 幂等：建表 + 补列迁移 + 空库时写入演示数据
CMD ["sh", "-c", "python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port 8010"]
