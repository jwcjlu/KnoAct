#!/bin/sh
# 广州/国内 ECS 拉 docker.io（mysql、nginx、python 等）很慢时，配置阿里云专属加速器。
# 用法：复制控制台地址后执行  MIRROR_URL=https://xxxx.mirror.aliyuncs.com sh scripts/docker-aliyun-mirror.sh
set -eu

MIRROR_URL="${MIRROR_URL:-}"
if [ -z "$MIRROR_URL" ]; then
  cat <<'EOF'
请先在阿里云控制台获取「镜像加速器」专属地址：
  https://cr.console.aliyun.com/cn-hangzhou/instances/mirrors
  （广州机房选华南/杭州节点均可，用控制台给出的 https://***.mirror.aliyuncs.com）

然后执行（把地址换成你的）：
  MIRROR_URL=https://你的ID.mirror.aliyuncs.com sh scripts/docker-aliyun-mirror.sh

或手工编辑 /etc/docker/daemon.json 后：
  systemctl daemon-reload && systemctl restart docker
EOF
  exit 0
fi

DAEMON_JSON="/etc/docker/daemon.json"
mkdir -p /etc/docker
if [ -f "$DAEMON_JSON" ]; then
  cp "$DAEMON_JSON" "${DAEMON_JSON}.bak.$(date +%Y%m%d%H%M%S)"
fi
cat >"$DAEMON_JSON" <<EOF
{
  "registry-mirrors": ["${MIRROR_URL}"]
}
EOF
echo "Wrote $DAEMON_JSON"
systemctl daemon-reload
systemctl restart docker
echo "Docker restarted. Test: docker pull mysql:8.4"
