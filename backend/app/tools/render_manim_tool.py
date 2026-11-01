"""render_manim：提交型工具，把数学概念交给独立渲染服务渲染成带旁白视频。"""
import uuid

from ..core.context import UnifiedContext
from ..core.tool_protocol import BaseTool, ToolParameter

from ..config import RENDER_SERVICE_URL


class RenderManimTool(BaseTool):
    name = "render_manim"
    description = "把数学概念渲染成带旁白讲解的动画视频，返回渲染任务 id（前端据此轮询进度）"
    parameters = [
        ToolParameter(name="prompt", type="string",
                      description="要演示的数学概念，如「演示 1/2+1/4=3/4」"),
        ToolParameter(name="narration", type="string",
                      description="旁白讲解稿（小学生能听懂的话）", required=False),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        prompt = (args.get("prompt") or "").strip()
        narration = (args.get("narration") or "").strip()
        if not prompt:
            return {"error": "prompt 不能为空"}
        task_id = uuid.uuid4().hex

        try:
            import requests
            resp = requests.post(
                f"{RENDER_SERVICE_URL}/render",
                json={"task_id": task_id, "prompt": prompt, "narration": narration},
                timeout=5,
            )
            resp.raise_for_status()
            status = "submitted"
        except Exception as e:
            # 渲染服务不可用：降级，返回代码占位 + 错误
            return {"task_id": task_id, "status": "unavailable",
                    "video_url": None, "error": f"渲染服务不可用：{e}"}

        # 落库 RenderTask（失败不阻断工具返回）
        try:
            from ..database import SessionLocal
            from ..models import RenderTask
            db = SessionLocal()
            try:
                db.add(RenderTask(task_id=task_id, user_id=ctx.user_id,
                                  prompt=prompt, narration=narration, status="submitted"))
                db.commit()
            finally:
                db.close()
        except Exception:
            pass

        return {"task_id": task_id, "status": status, "video_url": None}


render_manim = RenderManimTool()
