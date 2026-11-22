# backend/tests/test_work_modes.py
"""题型注册表完整性：每个数学 mode 的字段都必须合法。"""
import pytest

from app.core.question_types import CATEGORY_OF_QTYPE
from app.core.work_modes import (
    ANSWER_KINDS,
    INPUT_UIS,
    MATH_WORK_MODES,
    REGISTRY,
    answer_kind_of,
    input_ui_of,
    legacy_qtype_of,
    spec_of,
)


def test_registry_ids_unique_and_ordered():
    ids = [m.id for m in MATH_WORK_MODES]
    assert len(ids) == len(set(ids))
    assert ids[0] == "oral" and ids[-1] == "other"


def test_every_spec_has_valid_fields():
    for m in MATH_WORK_MODES:
        assert m.answer_kind in ANSWER_KINDS, m
        assert m.input_ui in INPUT_UIS, m
        # legacy_qtype 必须能被既有 taxonomy 认识，否则 qtype_category 会退成 subjective
        assert m.legacy_qtype in CATEGORY_OF_QTYPE, m
        assert m.label


def test_lookup_never_raises_and_falls_back_to_other():
    assert answer_kind_of("oral") == "number"
    assert input_ui_of("vertical") == "camera"
    assert legacy_qtype_of("equation") == "fill_blank"


@pytest.mark.parametrize("bad", ["", None, "  ", "no_such_mode"])
def test_unknown_mode_falls_back(bad):
    assert spec_of(bad).id == "other"


def test_photo_kinds_map_to_camera():
    """photo answer_kind 必须配 camera，否则前端没有拍照入口。"""
    for m in MATH_WORK_MODES:
        if m.answer_kind == "photo":
            assert m.input_ui == "camera", m


def test_all_fourteen_modes_present():
    assert len(REGISTRY) == 14