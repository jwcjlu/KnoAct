"""内置工具：lookup_word / search_text / render_mermaid。"""
from ..core.context import UnifiedContext
from ..core.tool_protocol import BaseTool, ToolParameter


class LookupWordTool(BaseTool):
    name = "lookup_word"
    description = "查一个词的释义，用小学生能懂的话解释"
    parameters = [
        ToolParameter(name="word", type="string", description="要查的词"),
        ToolParameter(name="lesson_id", type="integer", description="教材课 id", required=False),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        word = (args.get("word") or "").strip()
        if not word:
            return {"error": "word 不能为空"}
        # 同步调用 provider 释义；provider 不可用时回落占位
        try:
            from ..services.ai import get_provider
            from ..database import SessionLocal
            db = SessionLocal()
            try:
                provider = get_provider(db)
                meaning = provider.generate(
                    prompt=f"请解释教材中的这个词：「{word}」。用小学生能懂的话说明它的意思，50 字以内。",
                    system="你是小学生的学习助手，解释生词要简洁、准确。",
                ).strip()
            finally:
                db.close()
        except Exception:
            meaning = f"「{word}」的释义（示例）"
        return {"word": word, "meaning": meaning}


class SearchTextTool(BaseTool):
    name = "search_text"
    description = "在教材上下文里检索含某关键词的句子，返回句号及其编号，用于标注出处"
    parameters = [
        ToolParameter(name="query", type="string", description="检索关键词"),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        query = (args.get("query") or "").strip()
        text = ctx.text or ""
        if not query or not text:
            return {"matches": []}
        matches = []
        # ctx.text 形如「1.句子一 2.句子二」；简单按行/句切分编号匹配
        for idx, line in enumerate(text.splitlines() or [text], start=1):
            if query in line:
                matches.append({"sentence_no": idx, "text": line.strip()})
        return {"matches": matches}


class RenderMermaidTool(BaseTool):
    name = "render_mermaid"
    description = "校验并输出 mermaid 代码块（graph TD / mindmap），用于把知识画成图"
    parameters = [
        ToolParameter(name="code", type="string", description="mermaid 源码"),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        code = (args.get("code") or "").strip()
        if not code:
            return {"ok": False, "error": "code 不能为空"}
        # 简单校验：含 mermaid 图类型关键字
        valid = any(k in code for k in ("graph", "mindmap", "flowchart"))
        return {"ok": valid, "code": code} if valid else {"ok": False, "error": "不是有效的 mermaid 图"}


lookup_word = LookupWordTool()
search_text = SearchTextTool()
render_mermaid = RenderMermaidTool()
