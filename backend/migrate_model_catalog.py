"""把 ModelConfig 老键迁移成 ModelConnection/ModelProfile/RoleBinding。

幂等：已迁移过的角色跳过；老键保留不删，继续作为降级来源。

用法：
    cd backend && python migrate_model_catalog.py            # 执行迁移
    cd backend && python migrate_model_catalog.py --verify   # 只打印对照，不写库
"""
import json
import sys

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import ModelConfig, ModelConnection, ModelProfile, RoleBinding
from app.services.model_config import resolve
from app.services.provider_registry import ROLES


def _cfg(db: Session) -> dict:
    return {r.key: r.value for r in db.query(ModelConfig).all()}


def _upsert(db: Session, role: str, provider: str, model: str, api_key: str,
            base_url: str, options: dict) -> None:
    if db.get(RoleBinding, role):
        return  # 已迁移过
    conn = ModelConnection(provider=provider, name=f"{provider}（迁移）",
                           base_url=base_url, api_key=api_key)
    db.add(conn)
    db.flush()
    prof = ModelProfile(role=role, connection_id=conn.id, model=model,
                        options=json.dumps(options) if options else "")
    db.add(prof)
    db.flush()
    db.add(RoleBinding(role=role, profile_id=prof.id, mode="inherit"))
    db.flush()


def migrate(db: Session) -> None:
    cfg = _cfg(db)

    ai_provider = cfg.get("ai_provider", "")
    if ai_provider and ai_provider != "fake":
        opts = {}
        if cfg.get("vision_model"):
            opts["vision_model"] = cfg["vision_model"]
        _upsert(db, "llm", ai_provider, cfg.get("ai_model", ""),
                cfg.get("ai_key", ""), cfg.get("ai_base_url", ""), opts)

    tts_provider = cfg.get("tts_provider", "")
    if tts_provider and tts_provider != "fake":
        opts = {}
        for key, src in (("voice", "tts_voice"), ("speed", "tts_speed"),
                         ("repeat", "tts_repeat")):
            if cfg.get(src):
                opts[key] = cfg[src]
        _upsert(db, "tts", tts_provider, cfg.get("tts_model", ""),
                cfg.get("tts_key", ""), cfg.get("tts_base_url", ""), opts)

    db.commit()


def verify(db: Session) -> None:
    cfg = _cfg(db)
    print("老键:")
    for k in sorted(cfg):
        if k.startswith(("ai_", "tts_", "vision_")):
            print(f"  {k} = {cfg[k]!r}")
    print("\n解析结果:")
    for role in ROLES:
        r = resolve(db, role)
        print(f"  {role:10s} provider={r.provider:10s} "
              f"model={r.model or '-':24s} source={r.source}")


if __name__ == "__main__":
    # 建表是幂等的：已有库不会被动，空库则先把表补齐
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        if "--verify" in sys.argv:
            verify(s)
        else:
            migrate(s)
            print("迁移完成。")
            verify(s)
    finally:
        s.close()
