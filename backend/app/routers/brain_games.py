"""思维训练小游戏成绩接口：客户端本地出题，后端只存成绩与聚合最佳。

不写 AnswerRecord（游戏不是做题，不污染家长端「当天做题明细」），不涉及积分。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access, require_learning_user, resolve_target_user_id
from ..database import get_db
from ..models import BrainGameResult, User
from ..services.bucket_guard import resolve_bucket_id
from ..services.bucket_service import ensure_bucket

router = APIRouter(prefix="/api/brain-games", tags=["brain-games"])

GAMES = ("sudoku", "schulte", "minesweeper")
DIFFICULTIES = ("easy", "medium", "hard")


class ResultReq(BaseModel):
    user_id: int
    game: str
    difficulty: str
    duration_ms: int
    moves: int = 0
    solved: bool = False


@router.post("/result")
def post_result(req: ResultReq,
                user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    if req.game not in GAMES:
        raise HTTPException(status_code=400, detail={"error": "invalid_game"})
    if req.difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=400, detail={"error": "invalid_difficulty"})

    # 无 active 桶时先兜底建桶，否则成绩写进 NULL 桶、后续 /stats 再也读不到
    ensure_bucket(db, req.user_id)
    bid = resolve_bucket_id(db, req.user_id, None)

    # 必须先查后插：插入后再查会让新记录成为自己的对照，「严格小于」恒为 false
    best = (
        db.query(func.min(BrainGameResult.duration_ms))
        .filter(BrainGameResult.user_id == req.user_id,
                BrainGameResult.bucket_id == bid,
                BrainGameResult.game == req.game,
                BrainGameResult.difficulty == req.difficulty,
                BrainGameResult.solved.is_(True))
        .scalar()
    )
    # solved=False 的局恒不算新纪录
    is_best = bool(req.solved and (best is None or req.duration_ms < best))

    db.add(BrainGameResult(user_id=req.user_id, bucket_id=bid, game=req.game,
                           difficulty=req.difficulty, duration_ms=req.duration_ms,
                           moves=req.moves, solved=req.solved))
    db.commit()
    return {"ok": True, "is_best": is_best}


@router.get("/stats")
def stats(user_id: int = Depends(resolve_target_user_id),
          bucket_id: int | None = Query(None),
          _auth: User = Depends(require_learning_user),
          db: Session = Depends(get_db)):
    """按 game × difficulty 聚合：played（含失败）、solved、best_ms（仅通关最小用时）。

    `resolve_target_user_id` 内部已做越权校验（跨家庭 403），无需重复。
    bucket_id 解析为 None 时只聚合 bucket_id IS NULL 的记录（不跨学年串数据）。
    """
    bid = resolve_bucket_id(db, user_id, bucket_id)
    out: dict[str, dict[str, dict]] = {g: {} for g in GAMES}
    rows = (
        db.query(BrainGameResult)
        .filter(BrainGameResult.user_id == user_id,
                BrainGameResult.bucket_id == bid)
        .all()
    )
    for g in GAMES:
        for d in DIFFICULTIES:
            subset = [r for r in rows if r.game == g and r.difficulty == d]
            if not subset:
                continue
            solved = [r for r in subset if r.solved]
            out[g][d] = {
                "best_ms": min((r.duration_ms for r in solved), default=None),
                "played": len(subset),
                "solved": len(solved),
            }
    return out
