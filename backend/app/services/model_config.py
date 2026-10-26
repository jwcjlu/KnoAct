"""模型与服务：统一解析出口 + 密钥掩码。"""
import copy
import json
from dataclasses import dataclass, field, replace as dc_replace

from sqlalchemy.orm import Session

from ..models import ModelConfig, ModelConnection, ModelProfile, RoleBinding
from .provider_registry import find

MASK = "***"


@dataclass(frozen=True)
class Resolved:
    role: str
    provider: str
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    extra_headers: dict = field(default_factory=dict)
    options: dict = field(default_factory=dict)
    source: str = "default"


def _json_dict(raw: str) -> dict:
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}


def _cfg(db: Session) -> dict:
    return {r.key: r.value for r in db.query(ModelConfig).all()}


def _legacy(db: Session, role: str) -> Resolved | None:
    """老键降级。没有可用老键时返回 None。"""
    cfg = _cfg(db)
    if role == "llm":
        provider = cfg.get("ai_provider", "")
        if provider in ("", "fake"):
            return None
        return Resolved(
            role="llm",
            provider=provider,
            model=cfg.get("ai_model", ""),
            base_url=cfg.get("ai_base_url", ""),
            api_key=cfg.get("ai_key", ""),
            options={"vision_model": cfg["vision_model"]} if cfg.get("vision_model") else {},
            source="legacy",
        )
    if role == "tts":
        provider = cfg.get("tts_provider", "")
        if provider in ("", "fake"):
            return None
        opts = {}
        if cfg.get("tts_voice"):
            opts["voice"] = cfg["tts_voice"]
        if cfg.get("tts_speed"):
            opts["speed"] = cfg["tts_speed"]
        if cfg.get("tts_repeat"):
            opts["repeat"] = cfg["tts_repeat"]
        return Resolved(
            role="tts",
            provider=provider,
            model=cfg.get("tts_model", ""),
            base_url=cfg.get("tts_base_url", ""),
            api_key=cfg.get("tts_key", ""),
            options=opts,
            source="legacy",
        )
    if role == "task":
        return None  # task 另外处理：继承 llm
    # embedding / search / stt / imagegen 没有专属老键，退回 llm
    return None


def resolve(db: Session, role: str) -> Resolved:
    """三级降级：binding → legacy → default。绝不抛异常。"""
    binding = db.get(RoleBinding, role)

    # task 默认跟随 llm
    if role == "task" and (binding is None or binding.mode == "inherit"):
        inherited = resolve(db, "llm")
        return dc_replace(inherited, role="task", source=inherited.source)

    if binding is not None and binding.profile_id:
        prof = db.get(ModelProfile, binding.profile_id)
        if prof is not None:
            conn = db.get(ModelConnection, prof.connection_id) if prof.connection_id else None
            if conn is not None:
                return Resolved(
                    role=role,
                    provider=conn.provider,
                    model=prof.model or find(conn.provider, role).default_model,
                    base_url=conn.base_url,
                    api_key=conn.api_key,
                    extra_headers=_json_dict(conn.extra_headers),
                    options=_json_dict(prof.options),
                    source="binding",
                )

    legacy = _legacy(db, role)
    if legacy is not None:
        return legacy

    if role in ("embedding", "search", "stt", "imagegen"):
        inherited = resolve(db, "llm")
        if inherited.source != "default":
            return dc_replace(inherited, role=role, source="legacy")

    return Resolved(role=role, provider="fake", source="default")


def redact(obj):
    """深拷贝并把非空 api_key 换成 MASK。"""
    out = copy.deepcopy(obj)
    if isinstance(out, dict):
        if out.get("api_key"):
            out["api_key"] = MASK
        for v in out.values():
            if isinstance(v, (dict, list)):
                redact(v)
    elif isinstance(out, list):
        for item in out:
            redact(item)
    return out


def restore(old_rows: list[dict], new_rows: list[dict]) -> list[dict]:
    """密钥掩码往返：新值为 MASK 时沿用已存 key，否则按新值处理。

    - MASK + 有 id 且老行存在 → 用老 key
    - MASK + 无 id（新建）     → 视为空，避免把字面量 "***" 存进库
    - 空串                     → 清空
    - 其它                     → 视为新 key
    """
    by_id = {r.get("id"): r for r in (old_rows or []) if r.get("id")}
    out = []
    for row in (new_rows or []):
        row = dict(row)
        if row.get("api_key") == MASK:
            rid = row.get("id")
            row["api_key"] = by_id[rid]["api_key"] if rid in by_id else ""
        out.append(row)
    return out
