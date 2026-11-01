"""Turn 引擎：JSON 二选一协议驱动的多步工具循环。"""
import asyncio
import json

from ..core.context import UnifiedContext
from ..core.stream import StreamBus, StreamEvent
from ..core.tool_protocol import BaseTool
from ..tools.registry import ToolRegistry, ToolNotFoundError


class TurnEngine:
    MAX_STEPS = 8

    def __init__(self, provider, registry: ToolRegistry, system_prompt: str = "") -> None:
        self.provider = provider
        self.registry = registry
        self.system_prompt = system_prompt

    async def run(self, ctx: UnifiedContext, stream: StreamBus) -> dict:
        """驱动多步循环，返回 {answer, status, tool_calls}。"""
        history: list[dict] = []
        tool_calls: list[dict] = []

        for step in range(1, self.MAX_STEPS + 1):
            prompt = self._build_prompt(ctx, history)
            raw, reasoning = await asyncio.to_thread(
                self.provider.generate_with_reasoning, prompt, self._system(ctx), True
            )
            if reasoning:
                stream.emit(StreamEvent(type="thinking", data={"text": reasoning}))
            parsed = self._parse(raw)

            if parsed.get("final_answer") is not None:
                answer = str(parsed["final_answer"]).strip()
                if (
                    ctx.mode == "visualize"
                    and "```mermaid" not in answer
                    and not any(h.get("tool") == "render_mermaid" for h in history)
                    and step < self.MAX_STEPS
                ):
                    history.append(
                        {
                            "tool": "_hint",
                            "result": {
                                "error": (
                                    "可视化模式：请先调用 render_mermaid 工具生成图，"
                                    "再在 final_answer 里附上 ```mermaid ... ``` 代码块；"
                                    "不要只写文字版思维导图。"
                                )
                            },
                        }
                    )
                    continue
                stream.emit(StreamEvent(type="final", data={"answer": answer}))
                return {"answer": answer, "status": "done", "tool_calls": tool_calls}

            tool_name = parsed.get("tool")
            args = parsed.get("args") or {}
            if not tool_name:
                # 解析失败：强制收尾
                return await self._forced_finish(ctx, history, stream)

            try:
                tool: BaseTool = self.registry.get(tool_name)
                # NOTE: 工具是同步的，必须用 to_thread 避免阻塞事件循环
                result = await asyncio.to_thread(tool.run, args, ctx)
            except ToolNotFoundError:
                result = {"error": f"工具 {tool_name} 不存在"}
            except Exception as e:
                result = {"error": str(e)}

            tool_calls.append({"step": step, "tool": tool_name, "args": args, "result": result})
            stream.emit(StreamEvent(type="tool_call", data={"step": step, "tool": tool_name, "args": args}))
            stream.emit(StreamEvent(type="tool_result", data={"step": step, "result": result}))
            history.append({"tool": tool_name, "args": args, "result": result})

        # 步数上限：强制收尾
        return await self._forced_finish(ctx, history, stream)

    def _system(self, ctx: UnifiedContext) -> str:
        schemas = json.dumps(self.registry.list_schemas(), ensure_ascii=False)
        base = self.system_prompt or "你是小学生的学习助手，讲解要通俗、有耐心。"
        return (
            f"{base}\n"
            "请始终用中文思考（推理过程也用中文），面向小学生讲解。\n"
            "你可以用工具辅助回答。你每次只能返回一种 JSON：\n"
            '  - 回答完成：{"final_answer": "你的回答"}\n'
            '  - 调用工具：{"tool": "工具名", "args": {...}}\n'
            f"可用工具：{schemas}\n"
            "需要查词/检索/画图时先调工具，再根据工具结果回答。"
        )

    def _build_prompt(self, ctx: UnifiedContext, history: list[dict]) -> str:
        parts = [f"教材上下文：{ctx.text or '（无）'}", f"孩子提问：{ctx.question}"]
        if history:
            parts.append("已执行的工具调用及结果：")
            for h in history:
                parts.append(json.dumps(h, ensure_ascii=False))
        return "\n".join(parts)

    def _parse(self, raw: str) -> dict:
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {}

    async def _forced_finish(self, ctx: UnifiedContext, history: list[dict], stream: StreamBus) -> dict:
        # 把历史交给 LLM 求 final；失败则返回友好文案
        try:
            context_part = f"教材上下文：{ctx.text or '（无）'}\n"
            history_part = (
                "之前的工具结果如下：\n" + "\n".join(json.dumps(h, ensure_ascii=False) for h in history)
                if history else ""
            )
            prompt = (
                f"{context_part}"
                f"孩子提问：{ctx.question}\n"
                f"{history_part}\n"
                "请只基于上面的教材上下文和工具结果直接给出最终回答（不要再调工具），"
                "不要编造教材里没有的内容。"
            )
            raw, reasoning = await asyncio.to_thread(self.provider.generate_with_reasoning, prompt, self._system(ctx), True)
            if reasoning:
                stream.emit(StreamEvent(type="thinking", data={"text": reasoning}))
            data = self._parse(raw)
            answer = data.get("final_answer")
            if answer:
                stream.emit(StreamEvent(type="final", data={"answer": answer}))
                return {"answer": str(answer), "status": "done", "tool_calls": []}
        except Exception:
            pass
        answer = "抱歉，我没有理解你的问题，请再试一次。"
        stream.emit(StreamEvent(type="final", data={"answer": answer}))
        return {"answer": answer, "status": "error", "tool_calls": []}
