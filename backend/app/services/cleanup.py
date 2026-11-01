"""删除课程/生词/知识点前清理引用它们的行（MySQL 强制外键，SQLite 不强制，两边都在应用层处理）。

口径：掌握度、标注、测验随父行删除；错题保留（错题本是孩子的历史），只解除关联；
学习进度、对话 turn 的课程指针置空。
"""
from sqlalchemy.orm import Session

from ..models import (
    Annotation, KnowledgeMastery, KnowledgePoint, LearningProgress, Lesson, Mistake,
    Note, Question, Quiz, Text, Turn, WordBank, WordMastery,
)


def detach_words(db: Session, word_bank_ids: list[int]) -> None:
    if not word_bank_ids:
        return
    db.query(WordMastery).filter(WordMastery.word_bank_id.in_(word_bank_ids)).delete(synchronize_session=False)
    db.query(Mistake).filter(Mistake.word_bank_id.in_(word_bank_ids)).update(
        {Mistake.word_bank_id: None}, synchronize_session=False)


def detach_points(db: Session, point_ids: list[int]) -> None:
    if not point_ids:
        return
    db.query(KnowledgeMastery).filter(KnowledgeMastery.knowledge_point_id.in_(point_ids)).delete(synchronize_session=False)
    db.query(Mistake).filter(Mistake.knowledge_point_id.in_(point_ids)).update(
        {Mistake.knowledge_point_id: None}, synchronize_session=False)
    db.query(Note).filter(Note.knowledge_point_id.in_(point_ids)).update(
        {Note.knowledge_point_id: None}, synchronize_session=False)


def purge_lesson_content(db: Session, lesson_ids: list[int]) -> None:
    """删除课程下提取出的生词/知识点/课文/题目（重新提取前调用），课程本身保留。"""
    if not lesson_ids:
        return
    word_ids = [r[0] for r in db.query(WordBank.id).filter(WordBank.lesson_id.in_(lesson_ids)).all()]
    point_ids = [r[0] for r in db.query(KnowledgePoint.id).filter(KnowledgePoint.lesson_id.in_(lesson_ids)).all()]
    detach_words(db, word_ids)
    detach_points(db, point_ids)
    db.query(WordBank).filter(WordBank.lesson_id.in_(lesson_ids)).delete(synchronize_session=False)
    db.query(KnowledgePoint).filter(KnowledgePoint.lesson_id.in_(lesson_ids)).delete(synchronize_session=False)
    db.query(Text).filter(Text.lesson_id.in_(lesson_ids)).delete(synchronize_session=False)
    db.query(Question).filter(Question.lesson_id.in_(lesson_ids)).delete(synchronize_session=False)


def purge_lessons(db: Session, lesson_ids: list[int]) -> None:
    """连同课程行一起删除（重新拆分 / 移除教材）。"""
    if not lesson_ids:
        return
    purge_lesson_content(db, lesson_ids)
    db.query(Note).filter(Note.lesson_id.in_(lesson_ids)).delete(synchronize_session=False)
    db.query(Annotation).filter(Annotation.lesson_id.in_(lesson_ids)).delete(synchronize_session=False)
    db.query(Quiz).filter(Quiz.lesson_id.in_(lesson_ids)).delete(synchronize_session=False)
    db.query(LearningProgress).filter(LearningProgress.current_lesson_id.in_(lesson_ids)).update(
        {LearningProgress.current_lesson_id: None}, synchronize_session=False)
    db.query(Turn).filter(Turn.lesson_id.in_(lesson_ids)).update(
        {Turn.lesson_id: None}, synchronize_session=False)
    # fetch：把已加载的课程对象移出 session，免得新课程复用同一 id 时撞 identity map
    db.query(Lesson).filter(Lesson.id.in_(lesson_ids)).delete(synchronize_session="fetch")
