#!/bin/sh
# 重新构建并重启家长端（parent-web）与运营后台（admin-web）两个静态前端服务。
#
# 用法：
#   sh scripts/rebuild-web.sh              # 两个都重建
#   sh scripts/rebuild-web.sh parent-web   # 只重建家长端
#   sh scripts/rebuild-web.sh admin-web    # 只重建运营后台
#
# 说明：两个前端都是纯静态页（nginx 托管 + 反代 /api、/uploads），
# 改 index.html / app.js / nginx.conf 后跑本脚本即可生效，无需重编后端。
set -eu

cd "$(dirname "$0")/.."

SERVICES="${1:-parent-web admin-web}"

echo "==> 重建服务：${SERVICES}"
docker compose build ${SERVICES}

echo "==> 重启服务（新镜像生效）"
docker compose up -d --no-deps ${SERVICES}

echo "==> 完成。当前状态："
docker compose ps ${SERVICES}
