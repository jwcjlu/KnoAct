#!/usr/bin/env bash
# 校验数据库表结构是否与本轮代码要求的迁移一致（SQLite / MySQL 都支持）。
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

# 用 sh 执行时没有 pipefail（dash 会报 Illegal option），这里降级而非中断
if [ -n "${BASH_VERSION:-}" ]; then
    set -euo pipefail
else
    set -eu
fi

cd "$(dirname "$0")/.."

MODE="docker"
if [ "${1:-}" = "--local" ]; then
    MODE="local"
fi

# 检查逻辑：优先用 sqlalchemy（容器里一定有，能同时处理 SQLite 与 MySQL），
# 没有 sqlalchemy 时退回标准库 sqlite3（只支持 sqlite，用于排查机）。
CHECKER=$(cat <<'PY'
import os
import sys

url = os.environ.get("DATABASE_URL", "")
if not url:
    print("DATABASE_URL 未设置")
    raise SystemExit(1)

UQ = "uq_progress_user_document"
IX_DOC = "ix_learning_progress_document_id"
checks = []


def need(desc, ok):
    checks.append((desc, ok))


try:
    from sqlalchemy import create_engine, inspect, text
except ImportError:
    # ---- 标准库回退：只支持 sqlite ----
    if not url.startswith("sqlite"):
        print("这台机器没装 sqlalchemy，无法检查非 sqlite 的库：")
        print("  " + url)
        print("请在 backend 容器里跑（bash scripts/check-schema.sh），或 pip install sqlalchemy")
        raise SystemExit(2)

    import sqlite3

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

    T = tables()
    for t in ("practice_question_groups", "practice_import_pages"):
        need("表 " + t, t in T)

    qc = cols("questions")
    for col in ("group_id", "seq_in_group", "is_example", "work_mode"):
        need("questions." + col, col in qc)
    need("索引 ix_questions_group", "ix_questions_group" in indexes("questions"))

    need("learning_progress.document_id", "document_id" in cols("learning_progress"))
    need("唯一约束 " + UQ, UQ in ddl("learning_progress"))
    need("索引 " + IX_DOC, IX_DOC in indexes("learning_progress"))
    c.close()
else:
    # ---- sqlalchemy：SQLite / MySQL 通用 ----
    eng = create_engine(url)
    insp = inspect(eng)
    is_sqlite = eng.dialect.name == "sqlite"

    def tables():
        return set(insp.get_table_names())

    def cols(t):
        try:
            return {x["name"] for x in insp.get_columns(t)}
        except Exception:
            return set()

    def indexes(t):
        names = set()
        try:
            names |= {i["name"] for i in insp.get_indexes(t)}
        except Exception:
            pass
        # MySQL 的唯一键也会出现在索引里；把唯一约束名一并收进来
        try:
            names |= {u.get("name") or "" for u in insp.get_unique_constraints(t)}
        except Exception:
            pass
        return names

    def has_uq(t):
        try:
            if UQ in {u.get("name") or "" for u in insp.get_unique_constraints(t)}:
                return True
        except Exception:
            pass
        if is_sqlite:
            # SQLite 把约束写在建表语句里，某些版本 get_unique_constraints 读不全
            try:
                with eng.connect() as conn:
                    row = list(conn.execute(
                        text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"),
                        {"n": t}))
                if row and UQ in (row[0][0] or ""):
                    return True
            except Exception:
                pass
        return False

    print("==> 数据库：%s" % eng.dialect.name)

    T = tables()
    for t in ("practice_question_groups", "practice_import_pages"):
        need("表 " + t, t in T)

    qc = cols("questions")
    for col in ("group_id", "seq_in_group", "is_example", "work_mode"):
        need("questions." + col, col in qc)
    need("索引 ix_questions_group", "ix_questions_group" in indexes("questions"))

    need("learning_progress.document_id", "document_id" in cols("learning_progress"))
    need("唯一约束 " + UQ, has_uq("learning_progress"))
    need("索引 " + IX_DOC, IX_DOC in indexes("learning_progress"))

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
    # 容器里 DATABASE_URL 由 .env 提供（MySQL 或 sqlite），sqlalchemy 一定装好
    docker compose exec -T backend python -c "$CHECKER"
fi
