# 校验数据库表结构是否与本轮代码要求的迁移一致。
#
# 用法（先重启一次后端，让启动钩子跑完迁移）：
#   powershell -File scripts/check-schema.ps1
#   powershell -File scripts/check-schema.ps1 -DbPath backend/zhixueban.db
#
# 退出码：0 = 全部就绪；1 = 有缺项（会逐条列出）。
#
# 为什么需要这一步：sync_schema 只补「列」，不补索引、也不改唯一约束。
# learning_progress 的唯一键从 (user_id, subject) 换成 (user_id, document_id)
# 是靠 migrate_progress_document.py 重建表完成的；没重启后端就还是旧结构，
# 新代码一访问 questions.group_id / learning_progress.document_id 就会报
# "no such column"。部署后跑一遍这个脚本能避免上线即 500。

param(
    [string]$DbPath = "",
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($DbPath)) {
    $DbPath = Join-Path $root "backend/zhixueban.db"
}

if (-not (Test-Path $DbPath)) {
    Write-Host "数据库不存在：$DbPath" -ForegroundColor Red
    Write-Host "先启动一次后端（会在 backend/ 下生成并迁移）"
    exit 1
}

$checker = Join-Path $env:TEMP "knoact_check_schema.py"
@'
import sqlite3
import sys

db = sys.argv[1]
c = sqlite3.connect(db)


def cols(t):
    try:
        return {r[1] for r in c.execute("PRAGMA table_info(%s)" % t)}
    except Exception:
        return set()


def idx(t):
    return {r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?", (t,))}


def ddl(t):
    row = list(c.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)))
    return row[0][0] if row else ""


tables = {r[0] for r in c.execute(
    "SELECT name FROM sqlite_master WHERE type='table'")}

checks = []


def need(desc, ok):
    checks.append((desc, ok))


for t in ("practice_question_groups", "practice_import_pages"):
    need("表 %s" % t, t in tables)

qc = cols("questions")
for col in ("group_id", "seq_in_group", "is_example", "work_mode"):
    need("questions.%s" % col, col in qc)
need("索引 ix_questions_group", "ix_questions_group" in idx("questions"))

lp = cols("learning_progress")
need("learning_progress.document_id", "document_id" in lp)
need("唯一约束 uq_progress_user_document",
     "uq_progress_user_document" in ddl("learning_progress"))
need("索引 ix_learning_progress_document_id",
     "ix_learning_progress_document_id" in idx("learning_progress"))

bad = [d for d, ok in checks if not ok]
for d, ok in checks:
    print(("  OK   " if ok else "  MISS ") + d)

if bad:
    print("")
    print("有 %d 项缺失。请重启一次后端让启动迁移跑完：" % len(bad))
    print("  powershell -File scripts/restart-backend.ps1")
    sys.exit(1)

print("")
print("表结构已就绪。")
c.close()
'@ | Set-Content -Path $checker -Encoding UTF8

& $PythonExe $checker $DbPath
$code = $LASTEXITCODE
Remove-Item $checker -Force -ErrorAction SilentlyContinue
exit $code
