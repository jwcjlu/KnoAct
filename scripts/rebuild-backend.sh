#!/bin/sh
# 重新构建并重启 backend（FastAPI）。
#
# 用法：
#   sh scripts/rebuild-backend.sh
#
# 只重建 backend 镜像并换上新容器，不连带重建前端。
# MySQL 没在跑时会先把它拉起来（backend 依赖它健康检查通过）。
set -eu

cd "$(dirname "$0")/.."

echo "==> 重建 backend"
docker compose build backend

echo "==> 重启 backend（新镜像生效）"
docker compose up -d --build backend

echo "==> 完成。当前状态："
docker compose ps backend
