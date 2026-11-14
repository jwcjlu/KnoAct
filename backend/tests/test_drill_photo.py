from app.services.drill_rule import extract_drill_items, extract_items_from_pages


def test_extract_fake_returns_empty(db):
    # 测试库未配模型 → fake provider → 空结果
    r = extract_drill_items(db, "She look after her brother. 老师批注：应为 looks after")
    assert r == {"kind": "", "title": "", "items": []}


def test_extract_items_from_pages_fake_returns_empty(db):
    pages = [{"page_number": 1, "text": "look after 照顾"}]
    r = extract_items_from_pages(db, "phrase", pages)
    assert r == []


def test_extract_items_from_pages_none_db():
    pages = [{"page_number": 1, "text": "x"}]
    r = extract_items_from_pages(None, "phrase", pages)
    assert r == []


def test_extract_items_from_pages_empty_pages(db):
    r = extract_items_from_pages(db, "phrase", [])
    assert r == []



def test_extract_none_db_returns_empty():
    r = extract_drill_items(None, "任意错题文字")
    assert r["items"] == []


def test_extract_empty_text_returns_empty(db):
    r = extract_drill_items(db, "")
    assert r == {"kind": "", "title": "", "items": []}


def test_extract_result_structure_keys(db):
    r = extract_drill_items(db, "x" * 5)
    assert set(r.keys()) == {"kind", "title", "items"}


def test_photo_groups_endpoint(client, db, monkeypatch):
    """拍照出题端点：OCR→提取→建组（pending）。monkeypatch ocr 与提取。"""
    from app.routers import drill as drill_router
    from app.models import TrainingGroup, TrainingItem
    from conftest import parent_child

    # patch ocr_image 和 extract_drill_items，避免依赖真实视觉模型
    monkeypatch.setattr(drill_router, "ocr_image", lambda *a, **k: "look after 错题")
    monkeypatch.setattr(
        drill_router, "extract_drill_items",
        lambda db, text: {"kind": "phrase", "title": "look 短语辨析",
                          "items": [{"kind": "phrase", "primary": "look after",
                                     "secondary": "照顾", "example": "look after sb",
                                     "keywords": ["照顾"]}]},
    )
    parent, child, parent_h, _ = parent_child(db)
    files = {"file": ("wrong.jpg", b"\xff\xd8\xff fake jpeg", "image/jpeg")}
    r = client.post("/api/drill/photo-groups", data={"subject": "英语"}, files=files, headers=parent_h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "group_id" in data
    # 组是 pending，条目已建
    g = db.get(TrainingGroup, data["group_id"])
    assert g.audit_status == "pending"
    assert g.source == "custom"
    items = db.query(TrainingItem).filter_by(group_id=g.id).all()
    assert len(items) == 1
    assert items[0].primary == "look after"


def test_photo_groups_ocr_failure_400(client, db, monkeypatch):
    """OCR 失败（返回空文字）→ 400 提示换清晰照片。"""
    from app.routers import drill as drill_router
    from conftest import parent_child
    monkeypatch.setattr(drill_router, "ocr_image", lambda *a, **k: "")
    monkeypatch.setattr(
        drill_router, "extract_drill_items",
        lambda db, text: {"kind": "", "title": "", "items": []},
    )
    parent, child, parent_h, _ = parent_child(db)
    files = {"file": ("wrong.jpg", b"\xff\xd8\xff fake jpeg", "image/jpeg")}
    r = client.post("/api/drill/photo-groups", data={"subject": "英语"}, files=files, headers=parent_h)
    assert r.status_code == 400


def test_pdf_groups_endpoint(client, db, monkeypatch):
    """上传讲义 PDF → OCR → 提取条目 → 建组(handout, pending)。"""
    from app.services import pdf_split as ps
    from app.services import drill_rule as dr
    from app.models import TrainingGroup, TrainingItem
    from conftest import parent_child

    monkeypatch.setattr(ps, "render_pages",
                        lambda *a, **k: [{"page_number": 1, "image_path": "uploads/x_p1.png"}])
    monkeypatch.setattr(ps, "_ocr_page", lambda *a, **k: "look after 照顾")
    monkeypatch.setattr(
        dr, "extract_items_from_pages",
        lambda db, kind, pages: [{"primary": "look after", "secondary": "照顾", "source_page": 1}],
    )
    parent, child, parent_h, _ = parent_child(db)
    files = {"file": ("handout.pdf", b"%PDF-1.4 fake", "application/pdf")}
    r = client.post("/api/drill/pdf-groups",
                    data={"subject": "英语", "handout_kind": "phrase"},
                    files=files, headers=parent_h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "group_id" in data
    g = db.get(TrainingGroup, data["group_id"])
    assert g.source == "handout"
    assert g.audit_status == "pending"
    assert g.document_id is not None
    items = db.query(TrainingItem).filter_by(group_id=g.id).all()
    assert len(items) == 1
    assert items[0].primary == "look after"
    assert items[0].source_page == 1


def test_pdf_groups_no_items_400(client, db, monkeypatch):
    """提取不出条目 → 400。"""
    from app.services import pdf_split as ps
    from app.services import drill_rule as dr
    from conftest import parent_child
    monkeypatch.setattr(ps, "render_pages",
                        lambda *a, **k: [{"page_number": 1, "image_path": "x.png"}])
    monkeypatch.setattr(ps, "_ocr_page", lambda *a, **k: "文字")
    monkeypatch.setattr(dr, "extract_items_from_pages", lambda *a, **k: [])
    parent, child, parent_h, _ = parent_child(db)
    files = {"file": ("h.pdf", b"%PDF-1.4 fake", "application/pdf")}
    r = client.post("/api/drill/pdf-groups",
                    data={"subject": "英语", "handout_kind": "phrase"},
                    files=files, headers=parent_h)
    assert r.status_code == 400
