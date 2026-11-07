#!/bin/sh
# 构建 student-app（需解压 Flutter SDK）前若报 No space left on device，在服务器上执行：
#   sh scripts/docker-free-disk.sh
set -eu
echo "=== 磁盘 ==="
df -h /
echo "=== Docker 占用 ==="
docker system df 2>/dev/null || true
echo "=== 清理未用镜像/构建缓存（不删命名卷）==="
docker system prune -af
docker builder prune -af
echo "=== 清理后 ==="
df -h /
docker system df 2>/dev/null || true
