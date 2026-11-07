#!/bin/sh
# 配置 Docker daemon 的 registry-mirrors（可多个，按顺序尝试）。
# 国内示例：
#   MIRROR_URLS=https://xxxx.mirror.aliyuncs.com,https://docker.m.daocloud.io sh scripts/docker-registry-mirrors.sh
# 恢复官方：MIRROR_URLS= sh scripts/docker-registry-mirrors.sh  （见下方清空说明）
set -eu

MIRROR_URLS="${MIRROR_URLS:-}"

if [ -z "$MIRROR_URLS" ]; then
  cat <<'EOF'
设置一个或多个 Hub 加速地址（英文逗号分隔，不要空格）：

  MIRROR_URLS=https://你的ID.mirror.aliyuncs.com,https://docker.m.daocloud.io \
    sh scripts/docker-registry-mirrors.sh

阿里云专属加速：https://cr.console.aliyun.com/cn-hangzhou/instances/mirrors

写入后执行：systemctl daemon-reload && systemctl restart docker

若需改回仅直连 Hub：编辑 /etc/docker/daemon.json 删除 registry-mirrors 后重启 docker。
EOF
  exit 0
fi

DAEMON_JSON="/etc/docker/daemon.json"
mkdir -p /etc/docker
[ -f "$DAEMON_JSON" ] && cp "$DAEMON_JSON" "${DAEMON_JSON}.bak.$(date +%Y%m%d%H%M%S)"

# 生成 JSON 数组
json_mirrors=""
OLDIFS=$IFS
IFS=,
for url in $MIRROR_URLS; do
  url=$(echo "$url" | tr -d ' ')
  [ -z "$url" ] && continue
  json_mirrors="${json_mirrors}\"${url}\","
done
IFS=$OLDIFS
json_mirrors=$(echo "$json_mirrors" | sed 's/,$//')

cat >"$DAEMON_JSON" <<EOF
{
  "registry-mirrors": [${json_mirrors}]
}
EOF
echo "Wrote $DAEMON_JSON:"
cat "$DAEMON_JSON"
systemctl daemon-reload
systemctl restart docker
echo "Docker restarted."
