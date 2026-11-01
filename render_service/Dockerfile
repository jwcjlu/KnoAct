# KnoAct 动画渲染服务（render_service）
# 构建上下文为仓库根目录（需要 backend/ 复用 AI/TTS provider 与数据库模型）：
#   docker build -f render_service/Dockerfile -t knoact-render .
# manim 代码统一转发到 sandbox-runner 容器执行（KNOACT_RENDER_SANDBOX=docker），
# 本镜像只需 ffmpeg 合成旁白音轨，不装 manim / LaTeX。
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/app backend/app
COPY render_service render_service
RUN mkdir -p render_service/media

ENV DATABASE_URL=sqlite:////data/zhixueban.db \
    KNOACT_RENDER_SANDBOX=docker \
    KNOACT_RENDER_RUNNER_URL=http://sandbox-runner:8901
EXPOSE 8011

# umask 0000：任务目录需对 sandbox-runner（非 root，uid 10001）可写
CMD ["sh", "-c", "umask 0000 && exec uvicorn render_service.app:app --host 0.0.0.0 --port 8011"]
