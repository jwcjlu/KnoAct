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
            raw = await asyncio.to_thread(
                self.provider.generate, prompt, self._system(ctx), True
            )
            parsed = self._parse(raw)

            if parsed.get("final_answer") is not None:
                answer = str(parsed["final_answer"]).strip()
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
            prompt = (
                f"孩子提问：{ctx.question}\n"
                "之前的工具结果如下，请直接给出最终回答（不要再调工具）：\n"
                + "\n".join(json.dumps(h, ensure_ascii=False) for h in history)
            )
            raw = await asyncio.to_thread(self.provider.generate, prompt, self._system(ctx), True)
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
