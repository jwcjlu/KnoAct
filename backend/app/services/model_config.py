"""模型与服务：统一解析出口 + 密钥掩码。"""
import copy
import json
from dataclasses import dataclass, field, replace as dc_replace

from sqlalchemy.orm import Session

from ..models import ModelConfig, ModelConnection, ModelProfile, RoleBinding, ChildConfig
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
        if cfg.get("tts_app_id"):
            opts["app_id"] = cfg["tts_app_id"]
        if cfg.get("tts_api_secret"):
            opts["api_secret"] = cfg["tts_api_secret"]
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


_CHILD_ROLE_PREFIXES = {
    "llm": "llm",
    "tts": "tts",
}


def _child_overlay(db: Session, child_id: int, role: str, base: Resolved) -> Resolved:
    """孩子覆盖层：用 ChildConfig 里的角色前缀键覆盖已解析的全局结果。

    只有当该孩子存在任一该角色前缀的键时才启用（否则原样返回 base，source 不变）。
    `llm` 的覆盖同时作用于 `task`/`embedding`/`search`/`stt`/`imagegen`（它们继承 llm），
    故继承类角色查的是 `llm_` 前缀键，并落在已继承 llm 的 base 上。
    """
    prefix = "llm" if role in ("llm", "task", "embedding", "search", "stt", "imagegen") else role
    if prefix not in _CHILD_ROLE_PREFIXES:
        return base
    rows = db.query(ChildConfig).filter(
        ChildConfig.user_id == child_id,
        ChildConfig.key.like(f"{prefix}_%"),
    ).all()
    if not rows:
        return base
    kv = {r.key: r.value for r in rows}

    provider = kv.get(f"{prefix}_provider") or base.provider
    model = kv.get(f"{prefix}_model") or base.model
    base_url = kv.get(f"{prefix}_base_url") or base.base_url
    api_key = kv.get(f"{prefix}_api_key") or base.api_key
    options = dict(base.options)
    if prefix == "llm":
        if kv.get("llm_vision_model"):
            options["vision_model"] = kv["llm_vision_model"]
    else:  # tts
        if kv.get("tts_voice"):
            options["voice"] = kv["tts_voice"]
        if kv.get("tts_speed"):
            options["speed"] = kv["tts_speed"]
        if kv.get("tts_repeat"):
            options["repeat"] = kv["tts_repeat"]
    return dc_replace(
        base,
        role=role,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        options=options,
        source="child",
    )


def _resolve_base(db: Session, role: str) -> Resolved:
    """三级降级：binding → legacy → default。绝不抛异常。（不含孩子覆盖层）"""
    binding = db.get(RoleBinding, role)

    # task 默认跟随 llm；reference 模式配了 profile 才用自己那份
    if role == "task":
        if binding is None or binding.mode == "inherit" or not binding.profile_id:
            inherited = _resolve_base(db, "llm")
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
        inherited = _resolve_base(db, "llm")
        if inherited.source != "default":
            return dc_replace(inherited, role=role, source="legacy")

    # task 永远不低于 llm：profile/连接坏了也退到 llm，不退 fake
    if role == "task":
        inherited = _resolve_base(db, "llm")
        return dc_replace(inherited, role="task", source=inherited.source)

    return Resolved(role=role, provider="fake", source="default")


def resolve(db: Session, role: str, child_id: int | None = None) -> Resolved:
    """三级降级：binding → legacy → default，child_id 非空时孩子覆盖层优先。绝不抛异常。"""
    base = _resolve_base(db, role)
    if child_id is None:
        return base
    return _child_overlay(db, child_id, role, base)


def _redact_inplace(obj):
    if isinstance(obj, dict):
        if obj.get("api_key"):
            obj["api_key"] = MASK
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _redact_inplace(v)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _redact_inplace(item)


def redact(obj):
    """深拷贝并把非空 api_key 换成 MASK（递归到嵌套 dict/list）。"""
    out = copy.deepcopy(obj)
    _redact_inplace(out)
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
