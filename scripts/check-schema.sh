#!/usr/bin/env bash
# 校验数据库表结构是否与本轮代码要求的迁移一致。
#
# 用法（服务器上、仓库根目录）：
#   bash scripts/check-schema.sh              # 查运行中的 backend 容器（推荐）
#   bash scripts/check-schema.sh --local      # 不走 docker，直接查 backend/zhixueban.db
#
# 退出码：0 = 全部就绪；1 = 有缺项（逐条列出）。
#
# 为什么需要这一步：sync_schema 只补「列」，不补索引、也不改唯一约束。
# learning_progress 的唯一键从 (user_id, subject) 换成 (user_id, document_id)
# 是靠 migrate_progress_document.py 重建表完成的；没重启后端就还是旧结构，
# 新代码一访问 questions.group_id / learning_progress.document_id 就会报
# "no such column" —— 上线即 500。部署后跑一遍这个脚本能提前发现。
#
# 实现说明：只用标准库 sqlite3，不依赖 sqlalchemy —— 排查机器上常常没装
# 后端依赖，这时也能跑 --local 模式。容器模式用的是镜像里已有的环境。
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="docker"
if [ "${1:-}" = "--local" ]; then
    MODE="local"
fi

CHECKER=$(cat <<'PY'
"""逐个断言本轮迁移该有的表/列/索引/唯一约束。只用标准库。"""
import os
import sqlite3
import sys

url = os.environ.get("DATABASE_URL", "")
if not url.startswith("sqlite"):
    print("容器模式请用 sqlalchemy 版本；这里只处理 sqlite: %r" % url)
    raise SystemExit(2)

path = url.split("///")[-1]
if not os.path.exists(path):
    print("数据库不存在: %s" % path)
    raise SystemExit(1)

c = sqlite3.connect(path)


def tables():
    return {r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def cols(t):
    return {r[1] for r in c.execute("PRAGMA table_info(%s)" % t)}


def indexes(t):
    return {r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?", (t,))}


def ddl(t):
    row = list(c.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)))
    return row[0][0] if row else ""


UQ = "uq_progress_user_document"
checks = []


def need(desc, ok):
    checks.append((desc, ok))


T = tables()
for t in ("practice_question_groups", "practice_import_pages"):
    need("表 " + t, t in T)

qc = cols("questions")
for col in ("group_id", "seq_in_group", "is_example", "work_mode"):
    need("questions." + col, col in qc)
need("索引 ix_questions_group", "ix_questions_group" in indexes("questions"))

need("learning_progress.document_id", "document_id" in cols("learning_progress"))
need("唯一约束 " + UQ, UQ in ddl("learning_progress"))
need("索引 ix_learning_progress_document_id",
     "ix_learning_progress_document_id" in indexes("learning_progress"))

bad = [d for d, ok in checks if not ok]
for d, ok in checks:
    print(("  OK   " if ok else "  MISS ") + d)

if bad:
    print("")
    print("有 %d 项缺失。重启一次后端让启动迁移跑完：" % len(bad))
    print("  bash scripts/rebuild-backend.sh")
    raise SystemExit(1)

print("")
print("表结构已就绪。")
c.close()
PY
)

if [ "$MODE" = "local" ]; then
    DB_PATH="$(pwd)/backend/zhixueban.db"
    if [ ! -f "$DB_PATH" ]; then
        echo "数据库不存在：$DB_PATH" >&2
        echo "先启动一次后端（会在 backend/ 下生成并迁移）" >&2
        exit 1
    fi
    echo "==> 本地模式：$DB_PATH"
    DATABASE_URL="sqlite:///$DB_PATH" python3 -c "$CHECKER"
else
    echo "==> 容器模式：docker compose exec backend"
    # 容器里 DATABASE_URL 由 .env 提供；MySQL 的检查交给容器内的 sqlalchemy
    docker compose exec -T backend python -c "$CHECKER"
fi
