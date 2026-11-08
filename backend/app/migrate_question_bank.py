"""一次性迁移：给存量 questions 表补题库列、放宽 lesson_id 非空、回填 qtype_category/qtype。

`create_all` 是「不存在才建」，不会给已存在的表补列/删 NOT NULL 约束，所以部署到
已有库（dev SQLite / prod MySQL）必须手动跑本脚本。

幂等：列已存在则跳过；qtype 已在 taxonomy 里则跳过回填。

运行方式：cd backend && python -m app.migrate_question_bank
"""
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .database import engine, SessionLocal
from .models import Question
from .core.question_types import CATEGORY_OF_QTYPE, LEGACY_QTYPE_MAP


def _longtext() -> str:
    return "MEDIUMTEXT" if engine.url.get_backend_name() == "mysql" else "TEXT"


# 需要补的 (列名, 类型, 默认值)；bank_id 是外键列，单独处理
_NEW_COLUMNS = [
    ("qtype_category", "VARCHAR(16)", "subjective"),
    ("answer_json", _longtext(), ""),
    ("options", _longtext(), ""),
    ("analysis", _longtext(), ""),
    ("difficulty", "VARCHAR(16)", "medium"),
    ("tags", _longtext(), ""),
]


def migrate(db: Session) -> None:
    backend = engine.url.get_backend_name()
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("questions")}

    # 1) 补列（缺哪个加哪个；bank_id 单独加，不建 FK，对齐「可独立成题」）
    if "bank_id" not in cols:
        db.execute(text("ALTER TABLE questions ADD COLUMN bank_id INTEGER"))
    for name, ctype, default in _NEW_COLUMNS:
        if name in cols:
            continue
        d = f" DEFAULT '{default}'" if isinstance(default, str) else f" DEFAULT {default}"
        db.execute(text(f"ALTER TABLE questions ADD COLUMN {name} {ctype}{d}"))
    db.commit()

    # 2) 放宽 lesson_id 非空
    if backend == "mysql":
        db.execute(text("ALTER TABLE questions MODIFY lesson_id INTEGER NULL"))
        db.commit()
    else:
        # SQLite 不支持 DROP NOT NULL；dev 库由 create_all 重建即可，这里仅提示。
        print("[warn] SQLite 不支持直接删 NOT NULL；若需独立成题，请删库后用 create_all 重建，或改用 MySQL。")

    # 3) 回填 qtype_category 与 qtype（旧 4 粗粒度值 → taxonomy 最近项）
    rows = db.query(Question).all()
    for q in rows:
        if q.qtype in LEGACY_QTYPE_MAP:
            q.qtype = LEGACY_QTYPE_MAP[q.qtype]
        q.qtype_category = CATEGORY_OF_QTYPE.get(q.qtype, "subjective")
    db.commit()


if __name__ == "__main__":
    db = SessionLocal()
    try:
        migrate(db)
        print("迁移完成")
    finally:
        db.close()
