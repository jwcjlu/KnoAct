from app.services.drill_rule import infer_kind


def test_infer_kind_defaults():
    assert infer_kind("英语", "") == "phrase"
    assert infer_kind("语文", "") == "outline"
    assert infer_kind("数学", "") == "explore"


def test_infer_kind_respects_explicit():
    # 家长显式传了 kind 就尊重，不做覆盖
    assert infer_kind("语文", "explore") == "explore"
    assert infer_kind("英语", "outline") == "outline"


def test_infer_kind_unknown_subject_falls_back_outline():
    assert infer_kind("科学", "") == "outline"


def test_create_group_infers_kind_from_subject(client, db):
    """建组时不传 kind → 按学科推断（英语→phrase）。"""
    from conftest import parent_child
    from app.models import TrainingGroup
    parent, child, parent_h, _ = parent_child(db)
    r = client.post("/api/drill/groups", json={
        "source": "custom", "subject": "英语", "title": "look 短语",
        "items": [{"kind": "phrase", "primary": "look after", "secondary": "照顾"}],
    }, headers=parent_h)
    assert r.status_code == 200, r.text
    g = db.get(TrainingGroup, r.json()["group_id"])
    assert g.kind == "phrase"


def test_create_group_handout_inherits_subject(client, db):
    """讲义建组：subject 强制继承 PDF 学科，忽略请求值。"""
    from conftest import parent_child, make_document
    from app.models import PdfDocument, TrainingGroup
    parent, child, parent_h, _ = parent_child(db)
    doc = make_document(db, subject="英语", filename="短语.pdf", storage_path="")
    doc.content_kind = "handout"
    db.commit()
    r = client.post("/api/drill/groups", json={
        "source": "handout", "subject": "语文",  # 故意填错，应被覆盖为英语
        "title": "look 短语", "document_id": doc.id,
        "items": [{"kind": "phrase", "primary": "look after", "secondary": "照顾"}],
    }, headers=parent_h)
    assert r.status_code == 200, r.text
    g = db.get(TrainingGroup, r.json()["group_id"])
    assert g.subject == "英语"
    assert g.kind == "phrase"  # 英语 → phrase


def test_create_group_handout_wrong_doc_400(client, db):
    """讲义建组传非 handout 文档 → 400。"""
    from conftest import parent_child, make_document
    parent, child, parent_h, _ = parent_child(db)
    doc = make_document(db, subject="英语", filename="教材.pdf", storage_path="")
    # 默认 content_kind=textbook，非 handout
    r = client.post("/api/drill/groups", json={
        "source": "handout", "subject": "英语", "title": "x",
        "document_id": doc.id,
        "items": [{"kind": "phrase", "primary": "look after", "secondary": "照顾"}],
    }, headers=parent_h)
    assert r.status_code == 400
