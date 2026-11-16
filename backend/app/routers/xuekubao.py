"""学库宝元数据代理：供家长端选知识点（knowledgeApi oldId → knowledgeId）。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.deps import require_role
from ..core.xuekubao_adapter import XuekubaoAdapter
from ..database import get_db
from ..models import User
from ..services.source_config import xuekubao_adapter

router = APIRouter(prefix="/api/xuekubao", tags=["xuekubao"])


class ChapterTreeReq(BaseModel):
    pharse_id: str = Field(..., min_length=1, description="学段 code，来自 subjectEdition 树")
    subject_id: str = ""
    grade_id: str = ""
    edition_id: str = ""


def _adapter(db: Session = Depends(get_db)) -> XuekubaoAdapter:
    adapter = xuekubao_adapter(db)
    if not adapter.configured():
        raise HTTPException(
            status_code=503,
            detail="学库宝 API 未配置：请在「设置 → 题库来源」填写 Access Key，或设置环境变量 XUEKUBAO_ACCESS_KEY",
        )
    return adapter


@router.post("/subject-edition")
def subject_edition(
    user: User = Depends(require_role("parent", "admin")),
    adapter: XuekubaoAdapter = Depends(_adapter),
):
    """学段 / 学科 / 年级 / 教材版本四级树。"""
    raw = adapter.subject_edition_tree()
    if not raw.get("data") and str(raw.get("errorCode")) not in ("0", "200"):
        raise HTTPException(status_code=502, detail=raw.get("message") or "拉取失败")
    return raw


@router.post("/chapters")
def chapter_tree(
    req: ChapterTreeReq,
    user: User = Depends(require_role("parent", "admin")),
    adapter: XuekubaoAdapter = Depends(_adapter),
):
    """教材章节树（调试/兼容保留）。

    注意：语文等学科叶子 oldId 多为 0、单元为纯数字，**不能**当作 getQuestions
    的 knowledgeId。拉题请用 ``/knowledge``。
    """
    if not (req.grade_id or req.subject_id):
        raise HTTPException(
            status_code=400,
            detail="请先选择年级或学科再加载章节，仅选学段会拉取全量目录导致超时",
        )
    raw = adapter.chapter_tree(
        pharse_id=req.pharse_id,
        subject_id=req.subject_id,
        grade_id=req.grade_id,
        edition_id=req.edition_id,
    )
    if raw.get("data") is None and str(raw.get("errorCode")) not in ("0", "200"):
        raise HTTPException(status_code=502, detail=raw.get("message") or "拉取失败")
    return raw


@router.post("/knowledge")
def knowledge_tree(
    req: ChapterTreeReq,
    user: User = Depends(require_role("parent", "admin")),
    adapter: XuekubaoAdapter = Depends(_adapter),
):
    """知识点树；节点 oldId（hex）即 getQuestions 的 knowledgeId。

    语文等学科必须走此接口；chapterApi 的教材单元编号会导致拉到错学科题目。
    """
    if not req.subject_id:
        raise HTTPException(status_code=400, detail="请先选择学科再加载知识点")
    raw = adapter.knowledge_tree(
        pharse_id=req.pharse_id,
        subject_id=req.subject_id,
        grade_id=req.grade_id,
        edition_id=req.edition_id,
    )
    if raw.get("data") is None and str(raw.get("errorCode")) not in ("0", "200"):
        raise HTTPException(status_code=502, detail=raw.get("message") or "拉取失败")
    return raw
