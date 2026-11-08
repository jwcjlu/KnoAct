"""题目来源标准化：各来源产出统一的 QuestionDraft 中间结构。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class QuestionDraft:
    qtype: str = ""
    question: str = ""
    options: list[dict] = field(default_factory=list)   # [{label, value}]
    answer_json: dict = field(default_factory=dict)     # 机器判分依据
    answer: str = ""                                     # 标准答案展示文本
    analysis: str = ""
    difficulty: str = "medium"
    tags: dict = field(default_factory=dict)
    passage_title: str = ""
    passage_content: str = ""


class SourceAdapter(ABC):
    """一个来源 = 一个 normalize 实现。输出 QuestionDraft，落库/审核/判分统一处理。"""

    @abstractmethod
    def normalize(self, raw) -> list[QuestionDraft]:
        ...


class ManualAdapter(SourceAdapter):
    """家长录入表单：raw 已经是富结构，直接产出单个 draft。"""

    def normalize(self, raw) -> list[QuestionDraft]:
        d = QuestionDraft(
            qtype=(raw.get("qtype") or "").strip(),
            question=(raw.get("question") or "").strip(),
            options=raw.get("options") or [],
            answer_json=raw.get("answer_json") or {},
            answer=(raw.get("answer") or "").strip(),
            analysis=(raw.get("analysis") or "").strip(),
            difficulty=(raw.get("difficulty") or "medium"),
            tags=raw.get("tags") or {},
            passage_title=(raw.get("passage_title") or "").strip(),
            passage_content=(raw.get("passage_content") or raw.get("passage") or "").strip(),
        )
        return [d] if d.question else []


class ThirdPartyAdapter(SourceAdapter):
    """第三方题库基类。子类实现 fetch() 拉取原始数据 + normalize() 转 QuestionDraft。

    第一版只有 tiku.cn 占位 stub：normalize 返回空，等待后续接入（需爬虫/商业授权）。
    """
    name = "third_party"

    def fetch(self, *args, **kwargs):
        raise NotImplementedError

    def normalize(self, raw) -> list[QuestionDraft]:
        return []


class OcrAdapter(SourceAdapter):
    """卷子拍照：OCR + LLM 结构化。raw 是 OCR 文字，结构化在 services/ocr_import 完成。

    normalize 接收已结构化的 dict（list of 题），转成 QuestionDraft。
    """
    def normalize(self, raw) -> list[QuestionDraft]:
        items = raw.get("questions") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            return []
        drafts = []
        for it in items:
            if not isinstance(it, dict):
                continue
            q = (it.get("question") or it.get("prompt") or "").strip()
            if not q:
                continue
            drafts.append(QuestionDraft(
                qtype=(it.get("qtype") or "short_answer").strip(),
                question=q,
                options=it.get("options") or it.get("choices") or [],
                answer_json=it.get("answer_json") or {},
                answer=(it.get("answer") or "").strip(),
                analysis=(it.get("analysis") or "").strip(),
                difficulty=(it.get("difficulty") or "medium"),
                tags=it.get("tags") or {},
                passage_title=(it.get("passage_title") or "").strip(),
                passage_content=(it.get("passage_content") or it.get("passage") or "").strip(),
            ))
        return drafts
