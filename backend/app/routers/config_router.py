from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ModelConfig
from ..models import ModelConnection, ModelProfile, RoleBinding
from ..services.model_config import MASK, redact, resolve, restore
from ..services.provider_registry import REGISTRY, ROLES
from ..services.ai import OpenAICompatibleProvider, DeepSeekProvider, GLMProvider, FakeProvider

router = APIRouter(prefix="/api/config", tags=["config"])

class ConfigReq(BaseModel):
    key: str
    value: str

class TestReq(BaseModel):
    # 测试连接时可传入临时配置；不传则用已保存的配置
    provider: str = ""
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    kind: str = "chat"  # chat=语言模型, tts=语音模型


@router.post("")
def set_config(req: ConfigReq, db: Session = Depends(get_db)):
    row = db.query(ModelConfig).filter_by(key=req.key).first()
    if row:
        row.value = req.value
    else:
        db.add(ModelConfig(key=req.key, value=req.value))
    db.commit()
    return {"ok": True}

@router.get("")
def get_config(db: Session = Depends(get_db)):
    return {r.key: r.value for r in db.query(ModelConfig).all()}


# 语音合成相关模型的关键字（用于从 /models 列表里筛出 TTS 模型）
_TTS_KEYWORDS = ("speech", "tts", "audio", "voice", "say")
# 明显不是聊天模型的关键字（图像/视频/嵌入/向量等，从 chat 列表里剔除）
_NON_CHAT_KEYWORDS = (
    "image", "embedding", "video", "seedance", "seedream", "wan", "kling",
    "ltx", "bge", "rerank", "tts", "speech", "audio", "voice", "dance", "music",
)


@router.post("/models")
def list_models(req: TestReq):
    """用 base_url + api_key 调中转站 /models 接口，返回真实可用模型列表。

    kind=chat 返回语言模型（剔除图像/视频/语音/嵌入等），
    kind=tts 返回语音合成模型（speech/tts/audio 相关）。
    """
    if req.provider == "openai":
        from ..services.ai import OpenAICompatibleProvider
        p = OpenAICompatibleProvider(model="", api_key=req.api_key, base_url=req.base_url)
        try:
            all_models = p.list_models()
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}
        if req.kind == "tts":
            models = [m for m in all_models if any(k in m.lower() for k in _TTS_KEYWORDS)]
        else:
            models = [m for m in all_models if not any(k in m.lower() for k in _NON_CHAT_KEYWORDS)]
        return {"ok": True, "models": models}
    # 非中转站：返回内置固定列表
    fixed = {
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "glm": ["glm-4-plus", "glm-4-flash"],
    }.get(req.provider, [])
    return {"ok": True, "models": fixed}


@router.post("/test")
def test_config(req: TestReq, db: Session = Depends(get_db)):
    """用当前（或临时）配置真实调用一次模型，返回成功/失败与响应片段。"""
    cfg = {r.key: r.value for r in db.query(ModelConfig).all()}
    provider_name = req.provider or cfg.get("ai_provider", "fake")
    model = req.model or cfg.get("ai_model", "")
    api_key = req.api_key or cfg.get("ai_key", "")
    base_url = req.base_url or cfg.get("ai_base_url", "")

    if provider_name == "openai":
        p = OpenAICompatibleProvider(model=model, api_key=api_key, base_url=base_url)
    elif provider_name == "deepseek":
        p = DeepSeekProvider(model=model, api_key=api_key)
    elif provider_name == "glm":
        p = GLMProvider(model=model, api_key=api_key)
    else:
        p = FakeProvider(model=model, api_key=api_key)

    try:
        reply = p.generate(prompt="请回复「连接成功」四个字，不要其他内容。", system="你是连通性测试助手。")
        return {"ok": True, "provider": provider_name, "model": model, "sample": reply[:200]}
    except Exception as e:
        return {"ok": False, "provider": provider_name, "model": model, "error": str(e)[:300]}


# ---------------- 模型与服务（7 角色）----------------

def _dump_catalog(db) -> dict:
    conns = db.query(ModelConnection).order_by(ModelConnection.id).all()
    out_conns = [
        {"id": c.id, "provider": c.provider, "name": c.name,
         "base_url": c.base_url, "api_key": c.api_key,
         "extra_headers": c.extra_headers}
        for c in conns
    ]
    index_of = {c["id"]: i for i, c in enumerate(out_conns)}

    services = {}
    for role in ROLES:
        binding = db.get(RoleBinding, role)
        prof = db.get(ModelProfile, binding.profile_id) if binding and binding.profile_id else None
        resolved = resolve(db, role)
        services[role] = {
            "connection_id": prof.connection_id if prof else None,
            "connection_index": index_of.get(prof.connection_id if prof else None),
            "model": prof.model if prof else "",
            "options": prof.options if prof else "",
            "mode": binding.mode if binding else "inherit",
            "effective": {
                "provider": resolved.provider,
                "model": resolved.model,
                "source": resolved.source,
            },
        }
    return {
        "registry": {
            role: [
                {"id": s.id, "label": s.label,
                 "needs_base_url": s.needs_base_url,
                 "default_model": s.default_model}
                for s in specs
            ]
            for role, specs in REGISTRY.items()
        },
        "connections": redact(out_conns),
        "services": services,
    }


@router.get("/catalog")
def get_catalog(db: Session = Depends(get_db)):
    return _dump_catalog(db)


@router.put("/catalog")
def put_catalog(req: dict, db: Session = Depends(get_db)):
    old_conns = [{"id": c.id, "api_key": c.api_key}
                 for c in db.query(ModelConnection).all()]
    incoming = restore(old_conns, req.get("connections") or [])

    by_id = {c.id: c for c in db.query(ModelConnection).all()}
    kept_ids = set()
    ordered_ids = []
    for row in incoming:
        rid = row.get("id")
        conn = by_id[rid] if rid and rid in by_id else ModelConnection()
        if conn.id is None:
            db.add(conn)
        conn.provider = row.get("provider") or "openai"
        conn.name = row.get("name") or ""
        conn.base_url = row.get("base_url") or ""
        conn.api_key = row.get("api_key") or ""
        conn.extra_headers = row.get("extra_headers") or ""
        db.flush()
        kept_ids.add(conn.id)
        ordered_ids.append(conn.id)

    # 删除未回传的连接：引用它的档位置 NULL，不级联删档位
    for cid, conn in by_id.items():
        if cid not in kept_ids:
            db.query(ModelProfile).filter_by(connection_id=cid).update(
                {"connection_id": None}, synchronize_session=False
            )
            db.delete(conn)
    db.flush()

    for role, svc in (req.get("services") or {}).items():
        if role not in ROLES:
            continue
        binding = db.get(RoleBinding, role) or RoleBinding(role=role)
        db.add(binding)
        binding.mode = svc.get("mode") or "inherit"

        idx = svc.get("connection_index")
        conn_id = ordered_ids[idx] if isinstance(idx, int) and 0 <= idx < len(ordered_ids) else None
        model = svc.get("model") or ""
        options = svc.get("options") or ""

        if conn_id is None and not model:
            binding.profile_id = None
            continue

        prof = db.get(ModelProfile, binding.profile_id) if binding.profile_id else None
        if prof is None:
            prof = ModelProfile(role=role)
            db.add(prof)
            db.flush()
        prof.connection_id = conn_id
        prof.model = model
        prof.options = options
        binding.profile_id = prof.id

    db.commit()
    return {"ok": True}
