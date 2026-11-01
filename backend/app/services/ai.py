from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from ..models import ModelConfig  # noqa: F401  register model on Base.metadata

class AIProvider(ABC):
    name = "base"
    def __init__(self, model: str = "", api_key: str = ""):
        self.model = model
        self.api_key = api_key

    @abstractmethod
    def generate(self, prompt: str, system: str = "", json_mode: bool = False, timeout: float = None) -> str:
        ...

    def generate_with_reasoning(self, prompt: str, system: str = "", json_mode: bool = False):
        """默认实现：只回 content，reasoning 为空。推理型 provider 覆写此方法。"""
        return self.generate(prompt, system, json_mode), ""

class DeepSeekProvider(AIProvider):
    name = "deepseek"
    def generate(self, prompt, system="", json_mode=False, timeout=None):
        from openai import OpenAI
        if not self.api_key:
            raise RuntimeError("DeepSeek API Key 未配置")
        client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com", timeout=timeout or 600.0, max_retries=0)
        kwargs = {"model": self.model,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

class GLMProvider(AIProvider):
    name = "glm"
    def generate(self, prompt, system="", json_mode=False, timeout=None):
        from openai import OpenAI
        if not self.api_key:
            raise RuntimeError("GLM API Key 未配置")
        client = OpenAI(api_key=self.api_key, base_url="https://open.bigmodel.cn/api/paas/v4", timeout=timeout or 600.0, max_retries=0)
        kwargs = {"model": self.model,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

class OpenAICompatibleProvider(AIProvider):
    """自定义中转站 / 任意 OpenAI 兼容服务：base_url 可配置。

    用于接入如 CloudSky 等 API 中转站（算力调度平台），走 OpenAI Chat Completions 协议。
    """
    name = "openai"

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(model=model, api_key=api_key)
        self.base_url = base_url

    def generate(self, prompt, system="", json_mode=False, timeout=None):
        from openai import OpenAI
        if not self.api_key:
            raise RuntimeError("API Key 未配置")
        if not self.base_url:
            raise RuntimeError("中转站 Base URL 未配置")
        client = OpenAI(api_key=self.api_key, base_url=self.base_url,
                        timeout=timeout or 600.0, max_retries=0)
        kwargs = {"model": self.model,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

    def generate_with_reasoning(self, prompt, system="", json_mode=False):
        """返回 (content, reasoning) 元组。reasoning 取自推理模型的
        message.reasoning_content 字段（glm 等）；无则空字符串。"""
        from openai import OpenAI
        if not self.api_key:
            raise RuntimeError("API Key 未配置")
        if not self.base_url:
            raise RuntimeError("中转站 Base URL 未配置")
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        kwargs = {"model": self.model,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        reasoning = getattr(msg, "reasoning_content", "") or ""
        return msg.content, reasoning

    def list_models(self) -> list[str]:
        """调中转站 /models 接口，返回模型 id 列表。"""
        from openai import OpenAI
        if not self.api_key:
            raise RuntimeError("API Key 未配置")
        if not self.base_url:
            raise RuntimeError("中转站 Base URL 未配置")
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        models = client.models.list()
        return [m.id for m in models.data]


class FakeProvider(AIProvider):
    """本地兜底/测试用：不调外部 API，返回固定可预测文本。"""
    name = "fake"
    def generate(self, prompt, system="", json_mode=False, timeout=None):
        return f"[fake] {prompt[:20]}"

PROVIDERS = {"deepseek": DeepSeekProvider, "glm": GLMProvider, "openai": OpenAICompatibleProvider, "fake": FakeProvider}

def get_provider(db: Session) -> AIProvider:
    from .model_config import resolve
    r = resolve(db, "llm")
    cls = PROVIDERS.get(r.provider, FakeProvider)
    if cls is OpenAICompatibleProvider:
        return cls(model=r.model, api_key=r.api_key, base_url=r.base_url)
    return cls(model=r.model, api_key=r.api_key)


def ocr_image(db: Session, image_bytes: bytes, instruction: str = "识别图片中的全部文字，原样输出，不要解释。") -> str:
    """用视觉模型对扫描版教材页面做 OCR。

    视觉模型取自 llm 档位的 options.vision_model，未设则回落老键，再没有则用默认值。
    """
    from openai import OpenAI
    import base64
    from .model_config import resolve

    r = resolve(db, "llm")
    vision_model = r.options.get("vision_model", "")
    if not vision_model:
        from ..models import ModelConfig
        row = db.query(ModelConfig).filter_by(key="vision_model").first()
        vision_model = row.value if row else "qwen3-vl-plus"
    if not r.api_key or not r.base_url:
        raise RuntimeError("中转站 API Key / Base URL 未配置，无法 OCR")
    client = OpenAI(api_key=r.api_key, base_url=r.base_url)
    b64 = base64.b64encode(image_bytes).decode()
    resp = client.chat.completions.create(
        model=vision_model,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": instruction},
        ]}],
    )
    return resp.choices[0].message.content or ""
