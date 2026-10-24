from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from ..models import ModelConfig  # noqa: F401  register model on Base.metadata

class AIProvider(ABC):
    name = "base"
    def __init__(self, model: str = "", api_key: str = ""):
        self.model = model
        self.api_key = api_key

    @abstractmethod
    def generate(self, prompt: str, system: str = "", json_mode: bool = False) -> str:
        ...

class DeepSeekProvider(AIProvider):
    name = "deepseek"
    def generate(self, prompt, system="", json_mode=False):
        from openai import OpenAI
        if not self.api_key:
            raise RuntimeError("DeepSeek API Key 未配置")
        client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content

class GLMProvider(AIProvider):
    name = "glm"
    def generate(self, prompt, system="", json_mode=False):
        from openai import OpenAI
        if not self.api_key:
            raise RuntimeError("GLM API Key 未配置")
        client = OpenAI(api_key=self.api_key, base_url="https://open.bigmodel.cn/api/paas/v4")
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content

class FakeProvider(AIProvider):
    """本地兜底/测试用：不调外部 API，返回固定可预测文本。"""
    name = "fake"
    def generate(self, prompt, system="", json_mode=False):
        return f"[fake] {prompt[:20]}"

PROVIDERS = {"deepseek": DeepSeekProvider, "glm": GLMProvider, "fake": FakeProvider}

def _cfg(db: Session) -> dict:
    rows = {r.key: r.value for r in db.query(ModelConfig).all()}
    return rows

def get_provider(db: Session) -> AIProvider:
    cfg = _cfg(db)
    provider_name = cfg.get("ai_provider", "fake")
    model = cfg.get("ai_model", "deepseek-chat" if provider_name == "deepseek" else "glm-4-flash")
    api_key = cfg.get("ai_key", "")
    cls = PROVIDERS.get(provider_name, FakeProvider)
    return cls(model=model, api_key=api_key)
