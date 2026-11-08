#!/bin/sh
# 腾出构建空间，但保住正在用的镜像层和命名卷（MySQL / uploads）。
#
# 用法（仓库根目录）：
#   sh scripts/docker-free-disk.sh
#
# 会删：悬空 <none> 镜像、已停容器、过期 BuildKit 缓存
# 不删：正在跑的 knoact-* / mysql:8.4 / python / nginx、knoact-mysql 等命名卷
#
# 不要改成 docker system prune -af 或 docker volume prune：
# 停掉 student-app 再 -af 会把 Flutter/pip 层一起清掉，下次构建又从零拉。
set -eu

echo "=== 磁盘 ==="
df -h /
echo
echo "=== Docker 占用 ==="
docker system df 2>/dev/null || true
echo
echo "=== 命名卷（将保留）==="
docker volume ls --format '{{.Name}}' 2>/dev/null || true

echo
echo "=== 清理：已停容器、悬空镜像、多余构建缓存 ==="
docker container prune -f
docker image prune -f
if docker builder prune --help 2>/dev/null | grep -q -- '--keep-storage'; then
  docker builder prune -f --keep-storage 4GB
else
  docker builder prune -f --filter until=24h
fi
docker network prune -f

echo
echo "=== 清理后 ==="
df -h /
docker system df 2>/dev/null || true
echo
echo "MySQL 数据在卷 knoact-mysql 里，本脚本不会删卷。"
echo "若仍 <10G：先只编 backend/parent-web；student-app 建议本机 docker build 后 docker load。"
