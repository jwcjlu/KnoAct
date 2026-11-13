from app.models import TrainingGroup, TrainingItem, TrainingItemMastery, PdfDocument


def test_training_group_full_fields(db):
    from app.models import User
    u = User(name="晨晨", role="child")
    db.add(u); db.flush()
    g = TrainingGroup(owner_id=u.id, subject="数学", title="周长面积探究",
                      source="custom", kind="explore",
                      mastery_interval_days=15, interval_max_days=60,
                      group_rule="{}", intro="{}")
    db.add(g); db.flush()
    assert g.kind == "explore"
    assert g.mastery_interval_days == 15


def test_training_item_explore_and_mistake(db):
    from app.models import User
    u = User(name="晨晨", role="child"); db.add(u); db.flush()
    g = TrainingGroup(owner_id=u.id, subject="英语", title="look 短语", source="custom", kind="phrase")
    db.add(g); db.flush()
    it = TrainingItem(group_id=g.id, kind="phrase", primary="look after",
                      secondary="照顾", common_mistake='{"wrong":"look for","correct":"look after"}',
                      explore="{}")
    db.add(it); db.flush()
    assert it.common_mistake.startswith('{"wrong"')
    assert it.kind == "phrase"


def test_mastery_has_bucket_id(db):
    from app.models import User
    u = User(name="晨晨", role="child"); db.add(u); db.flush()
    g = TrainingGroup(owner_id=u.id, subject="语文", title="古诗", source="custom", kind="outline")
    db.add(g); db.flush()
    it = TrainingItem(group_id=g.id, kind="drill_item", primary="床前明月光")
    db.add(it); db.flush()
    m = TrainingItemMastery(user_id=u.id, item_id=it.id, interval=1, lapse=0, last_hinted=False, bucket_id=None)
    db.add(m); db.flush()
    assert m.interval == 1 and m.bucket_id is None


def test_pdf_handout_fields_and_default(db):
    h = PdfDocument(filename="a.pdf", subject="英语", storage_path="", content_kind="handout", handout_kind="phrase")
    db.add(h); db.flush()
    t = PdfDocument(filename="b.pdf", subject="语文", storage_path="")
    db.add(t); db.flush()
    assert h.content_kind == "handout" and h.handout_kind == "phrase"
    assert t.content_kind == "textbook" and t.handout_kind is None
