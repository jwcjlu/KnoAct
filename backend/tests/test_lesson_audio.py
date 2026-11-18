from app.routers.lesson_audio import parse_unit_label, _safe_filename


def test_parse_unit_label_unit_number():
    assert parse_unit_label("01_Unit 1.mp3") == "Unit 1"
    assert parse_unit_label("02_Unit 2.mp3") == "Unit 2"
    assert parse_unit_label("08_Unit 8.mp3") == "Unit 8"


def test_parse_unit_label_word_list():
    assert parse_unit_label("09_Word list.mp3") == "Word list"


def test_parse_unit_label_fallback():
    # 无法解析时回落：去扩展名的原始文件名
    assert parse_unit_label("whatever.mp3") == "whatever"
    assert parse_unit_label("Unit.mp3") == "Unit"


def test_safe_filename_normalizes_url_unsafe_chars():
    assert _safe_filename("01_Unit 1.mp3") == "01_Unit_1.mp3"
    # 非 ASCII / 空格 / 路径符全部剔除，仅剩 URL 安全字符 [A-Za-z0-9._-]
    assert _safe_filename("第1课.mp3") == "_1_.mp3"
    assert _safe_filename("../evil  path.mp3") == "evil_path.mp3"


from conftest import make_document, make_lesson, make_account, auth_headers


def test_upload_audio_auto_matches_lesson(client, db):
    parent = make_account(db, login_name="p_audio", role="parent")
    doc = make_document(db, subject="英语", filename="英语五年级上册.pdf")
    lesson = make_lesson(db, subject="英语", title="Unit 1 Hello", document=doc)
    db.commit()
    files = {"file": ("01_Unit 1.mp3", b"ID3fake-mp3-bytes", "audio/mpeg")}
    data = {"document_id": str(doc.id)}
    r = client.post("/api/lesson-audio", files=files, data=data, headers=auth_headers(parent))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["unit_label"] == "Unit 1"
    assert body["lesson_id"] == lesson.id


def test_list_audio_and_patch_binding_and_marks(client, db):
    from app.models import LessonAudio
    parent = make_account(db, login_name="p_audio2", role="parent")
    doc = make_document(db, subject="英语", filename="英语五年级上册.pdf")
    db.commit()
    row = LessonAudio(document_id=doc.id, unit_label="Word list",
                      audio_path="uploads/audio/x.mp3", marks_json="[]")
    db.add(row); db.commit(); db.refresh(row)

    r = client.get(f"/api/lesson-audio?document_id={doc.id}", headers=auth_headers(parent))
    assert r.status_code == 200
    items = r.json()
    assert any(it["id"] == row.id for it in items)

    r = client.patch(f"/api/lesson-audio/{row.id}", json={"unit_label": "Unit 9"}, headers=auth_headers(parent))
    assert r.status_code == 200
    assert r.json()["unit_label"] == "Unit 9"

    r = client.put(f"/api/lesson-audio/{row.id}/marks",
                   json={"marks": [{"label": "A", "start_sec": 12.5}]}, headers=auth_headers(parent))
    assert r.status_code == 200
    assert r.json()["marks"][0]["start_sec"] == 12.5


def test_match_lesson_rejects_unit_10_for_unit_1(db):
    from app.routers.lesson_audio import _match_lesson_by_label
    doc = make_document(db, subject="英语", filename="英语五年级上册.pdf")
    make_lesson(db, subject="英语", title="Unit 10 Review", document=doc)
    db.commit()
    # "Unit 1" 不应误匹配 "Unit 10"
    assert _match_lesson_by_label(db, doc.id, "英语", "Unit 1") is None


def test_upload_rejects_non_mp3(client, db):
    parent = make_account(db, login_name="p_audio3", role="parent")
    doc = make_document(db, subject="英语", filename="英语五年级上册.pdf")
    db.commit()
    files = {"file": ("01_Unit 1.txt", b"not-mp3", "text/plain")}
    data = {"document_id": str(doc.id)}
    r = client.post("/api/lesson-audio", files=files, data=data, headers=auth_headers(parent))
    assert r.status_code == 400


def test_list_audio_child_access(client, db):
    from app.models import UserDocument
    parent = make_account(db, login_name="p_audio4", role="parent")
    child = make_account(db, login_name="c_audio", role="child", parent=parent)
    doc = make_document(db, subject="英语", filename="英语五年级上册.pdf")
    db.add(UserDocument(user_id=child.id, document_id=doc.id))
    db.commit()

    # 已绑定教材的孩子可读该教材的音频列表
    r = client.get(f"/api/lesson-audio?document_id={doc.id}", headers=auth_headers(child))
    assert r.status_code == 200

    # 未绑定该教材的孩子不可读
    other_child = make_account(db, login_name="c_audio2", role="child", parent=parent)
    db.commit()
    r = client.get(f"/api/lesson-audio?document_id={doc.id}", headers=auth_headers(other_child))
    assert r.status_code == 403
