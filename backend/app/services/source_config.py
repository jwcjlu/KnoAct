"""第三方题库凭证：ModelConfig（库内）优先，环境变量次之。"""
from __future__ import annotations

import os

from sqlalchemy.orm import Session

from ..core.tiku_cn_adapter import TikuCnAdapter
from ..core.xuekubao_adapter import XuekubaoAdapter
from ..models import ModelConfig
from .model_config import MASK

SOURCE_SECRET_KEYS = frozenset({"xuekubao_access_key", "tiku_cn_app_key"})


def _cfg(db: Session) -> dict[str, str]:
    return {r.key: r.value for r in db.query(ModelConfig).all()}


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _pick(cfg: dict[str, str], key: str, env_name: str, default: str = "") -> str:
    v = (cfg.get(key) or "").strip()
    if v:
        return v
    return _env(env_name, default)


def xuekubao_adapter(db: Session) -> XuekubaoAdapter:
    cfg = _cfg(db)
    base = _pick(cfg, "xuekubao_api_base", "XUEKUBAO_API_BASE", "https://api.xuekubao.com")
    key = _pick(cfg, "xuekubao_access_key", "XUEKUBAO_ACCESS_KEY")
    timeout = _pick(cfg, "xuekubao_timeout", "XUEKUBAO_TIMEOUT", "30")
    try:
        t = float(timeout or "30")
    except ValueError:
        t = 30.0
    adapter = XuekubaoAdapter(base_url=base, access_key=key)
    adapter.timeout = t
    return adapter


def tiku_cn_adapter(db: Session) -> TikuCnAdapter:
    cfg = _cfg(db)
    base = _pick(cfg, "tiku_cn_api_base", "TIKU_CN_API_BASE")
    app_key = _pick(cfg, "tiku_cn_app_key", "TIKU_CN_APP_KEY")
    search_path = _pick(cfg, "tiku_cn_search_path", "TIKU_CN_SEARCH_PATH", "/api/question/search")
    adapter = TikuCnAdapter(base_url=base or None, app_key=app_key or None, search_path=search_path)
    timeout = _pick(cfg, "tiku_cn_timeout", "TIKU_CN_TIMEOUT", "15")
    try:
        adapter.timeout = float(timeout or "15")
    except ValueError:
        adapter.timeout = 15.0
    return adapter


def sources_public(db: Session) -> dict:
    """给家长端展示的状态（密钥掩码）。"""
    cfg = _cfg(db)
    xkb_key = _pick(cfg, "xuekubao_access_key", "XUEKUBAO_ACCESS_KEY")
    tiku_key = _pick(cfg, "tiku_cn_app_key", "TIKU_CN_APP_KEY")
    tiku_base = _pick(cfg, "tiku_cn_api_base", "TIKU_CN_API_BASE")
    return {
        "xuekubao_api_base": _pick(
            cfg, "xuekubao_api_base", "XUEKUBAO_API_BASE", "https://api.xuekubao.com",
        ),
        "xuekubao_access_key": MASK if xkb_key else "",
        "xuekubao_configured": bool(xkb_key),
        "tiku_cn_api_base": tiku_base,
        "tiku_cn_app_key": MASK if tiku_key else "",
        "tiku_cn_configured": bool(tiku_base and tiku_key),
    }


def save_sources(db: Session, incoming: dict) -> None:
    """写入题库来源配置；密钥留空或 *** 表示不修改。"""

    def _set(key: str, value: str, *, secret: bool = False) -> None:
        v = (value or "").strip()
        if secret and (not v or v == MASK):
            return
        old = db.query(ModelConfig).filter_by(key=key).first()
        if old:
            old.value = v
        else:
            db.add(ModelConfig(key=key, value=v))

    _set("xuekubao_api_base", incoming.get("xuekubao_api_base", ""))
    _set("xuekubao_access_key", incoming.get("xuekubao_access_key", ""), secret=True)
    _set("tiku_cn_api_base", incoming.get("tiku_cn_api_base", ""))
    _set("tiku_cn_app_key", incoming.get("tiku_cn_app_key", ""), secret=True)
    db.commit()
