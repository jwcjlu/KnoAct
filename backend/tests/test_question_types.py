from app.core.question_types import CATEGORY_OF_QTYPE, QTYPE_LABELS, QTYPES, CATEGORIES, LEGACY_QTYPE_MAP

def test_every_qtype_has_category_and_label():
    for qtype in QTYPES:
        assert qtype in CATEGORY_OF_QTYPE, f"{qtype} 缺 category"
        assert qtype in QTYPE_LABELS, f"{qtype} 缺 label"

def test_category_in_categories():
    for cat in CATEGORY_OF_QTYPE.values():
        assert cat in CATEGORIES

def test_known_mappings():
    assert CATEGORY_OF_QTYPE["single_choice"] == "choice"
    assert CATEGORY_OF_QTYPE["true_false"] == "choice"
    assert CATEGORY_OF_QTYPE["fill_blank"] == "blank"
    assert CATEGORY_OF_QTYPE["calculation"] == "blank"
    assert CATEGORY_OF_QTYPE["matching"] == "match"
    assert CATEGORY_OF_QTYPE["essay"] == "subjective"

def test_legacy_qtype_map_targets_real_qtypes():
    for legacy, qtype in LEGACY_QTYPE_MAP.items():
        assert qtype in CATEGORY_OF_QTYPE, f"{legacy} → {qtype} 不是合法 qtype"
