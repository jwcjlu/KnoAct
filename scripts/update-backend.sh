#!/usr/bin/env bash
# 更新 KnoAct 后端到最新 master（含思维训练接口 + 中文朗读兜底）。
#
# 用法（在服务器上、仓库根目录执行）：
#   bash scripts/update-backend.sh
#
# 做的事：
#   1. git pull 到最新 master
#   2. 只重建 backend 镜像并换容器（不连编前端，省时间省磁盘）
#   3. 等健康检查通过后，验证新增的两个端点
#
# 前置：服务器上已有本仓库 clone，且 .env 已配好（MySQL 密码等）。
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> 当前版本"
git log --oneline -1

echo "==> 拉取最新 master"
git pull --ff-only origin master

echo "==> 重建并重启 backend"
sh scripts/rebuild-backend.sh

echo "==> 等待 backend 就绪"
for i in $(seq 1 60); do
    if docker compose exec -T backend python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8010/docs',timeout=3)" >/dev/null 2>&1; then
        echo "backend 已就绪"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "ERROR: backend 60 秒内未就绪，请看 docker compose logs backend" >&2
        exit 1
    fi
    sleep 2
done

echo "==> 验证新端点已生效"
docker compose exec -T backend python - <<'PY'
import json, urllib.error, urllib.request

base = "http://127.0.0.1:8010"
ok = True

# 未带 token 应返回 401/403（而非 404）——说明路由已注册
for path in ("/api/brain-games/stats?user_id=1", "/api/tts/synthesize?text=x"):
    try:
        urllib.request.urlopen(base + path, timeout=5)
        print(f"[?] {path} 竟然 200（无鉴权？请检查）")
        ok = False
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[FAIL] {path} 仍 404，路由未注册")
            ok = False
        else:
            print(f"[OK] {path} -> {e.code}（路由已注册）")
    except Exception as e:
        print(f"[FAIL] {path} {e}")
        ok = False

raise SystemExit(0 if ok else 1)
PY

echo ""
echo "==> 完成"
echo "验证方式："
echo "  curl -s -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:\${KNOACT_STUDENT_PORT:-8082}/api/brain-games/stats"
echo "  （期望 401/403，不是 404）"
