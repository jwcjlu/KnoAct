"""Provider 白名单：代码常量，不是用户数据。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    needs_base_url: bool
    default_model: str = ""


OPENAI = ProviderSpec("openai", "中转站 / OpenAI 兼容", True, "gpt-4o")
DEEPSEEK = ProviderSpec("deepseek", "DeepSeek", False, "deepseek-chat")
GLM = ProviderSpec("glm", "GLM（智谱）", False, "glm-4-flash")
MINIMAX = ProviderSpec("minimax", "MiniMax", False, "speech-01-turbo")
XUNFEI = ProviderSpec("xunfei", "科大讯飞", False, "")
FAKE = ProviderSpec("fake", "本地兜底", False, "")

REGISTRY: dict[str, tuple[ProviderSpec, ...]] = {
    "llm":       (OPENAI, DEEPSEEK, GLM, FAKE),
    "task":      (OPENAI, DEEPSEEK, GLM, FAKE),
    "embedding": (OPENAI, FAKE),
    "search":    (OPENAI, FAKE),
    "tts":       (OPENAI, MINIMAX, XUNFEI, FAKE),
    "stt":       (OPENAI, FAKE),
    "imagegen":  (OPENAI, FAKE),
}

ROLES: tuple[str, ...] = tuple(REGISTRY.keys())


def find(provider_id: str, role: str = "llm") -> ProviderSpec:
    for spec in REGISTRY.get(role, REGISTRY["llm"]):
        if spec.id == provider_id:
            return spec
    return FAKE
