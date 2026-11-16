"""训练方案发布：把勾选知识点物化成 TrainingItem，幂等更新同一组。"""
import json
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import KnowledgePointPool, TrainingGroup, TrainingItem, TrainingItemMastery, TrainingPlan
from .drill_rule import infer_kind, generate_group_content
from .drill_review import review_group_items


def publish_plan(db: Session, plan: TrainingPlan) -> tuple[TrainingGroup, int]:
    """按 plan.point_ids 物化知识点，新建或更新 group，返回 (group, item_count)。

    - 幂等：plan.group_id 已存在则更新该组（不新建重复组）。
    - 保留掌握度：更新时按 point_pool_id 匹配，未变知识点保留原 TrainingItem（及 mastery），
      只增删变化的条目。
    """
    point_ids = json.loads(plan.point_ids or "[]")
    if not point_ids:
        raise ValueError("方案未勾选任何知识点")
    points = (db.query(KnowledgePointPool)
              .filter(KnowledgePointPool.id.in_(point_ids),
                      KnowledgePointPool.owner_id == plan.owner_id)
              .order_by(KnowledgePointPool.id).all())
    if not points:
        raise ValueError("未找到有效知识点")

    group = db.get(TrainingGroup, plan.group_id) if plan.group_id else None
    if group is None:
        group = TrainingGroup(owner_id=plan.owner_id, subject=plan.subject,
                              title=plan.title, source="custom",
                              kind=infer_kind(plan.subject, ""))
        db.add(group); db.flush()
    else:
        # 删除不再勾选的条目（保留命中 point_pool_id 的条目及其 mastery）
        wanted = {p.id for p in points}
        for it in db.query(TrainingItem).filter_by(group_id=group.id).all():
            if it.point_pool_id not in wanted:
                db.query(TrainingItemMastery).filter_by(item_id=it.id).delete()
                db.delete(it)
        db.flush()

    existing_by_pool = {it.point_pool_id: it for it in
                        db.query(TrainingItem).filter_by(group_id=group.id).all()}

    items_payload = []
    for p in points:
        if p.id in existing_by_pool:
            continue
        extra = _load_json(p.extra)
        item = TrainingItem(
            group_id=group.id, kind="drill_item",
            primary=p.content,
            secondary=extra.get("释义") or extra.get("作者") or "",
            example=extra.get("例句") or "",
            point_pool_id=p.id,
        )
        db.add(item); db.flush()
        items_payload.append({"primary": p.content,
                              "secondary": extra.get("释义") or extra.get("作者") or ""})

    all_items = db.query(TrainingItem).filter_by(group_id=group.id).order_by(TrainingItem.id).all()
    if items_payload:
        content = generate_group_content(db, plan.subject, group.kind, items_payload)
        group.intro = json.dumps(content["intro"], ensure_ascii=False)
        group.group_rule = json.dumps(content["group_rule"], ensure_ascii=False)
        group.ai_review = json.dumps(
            review_group_items(db, plan.subject, group.kind, items_payload), ensure_ascii=False)

    plan.group_id = group.id
    plan.status = "published"
    plan.updated_at = datetime.utcnow()
    db.commit()
    return group, len(all_items)


def _load_json(s: str) -> dict:
    try:
        v = json.loads(s or "{}")
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}
