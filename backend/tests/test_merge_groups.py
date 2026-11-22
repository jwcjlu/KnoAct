"""跨页合并：连续多页、工作模式不同、stem 不匹配、不得边遍历边丢组。"""
from app.services.practice_import import _levenshtein, merge_cross_page_groups


def _g(page, work_mode="oral", stem="直接写出得数", cont=False, items=None):
    return {
        "key": f"{page}-0",
        "page_start": page,
        "page_end": page,
        "work_mode": work_mode,
        "stem": stem,
        "continues_next_page": cont,
        "incomplete": False,
        "items": items or [{"seq": 1, "text": f"p{page}-1"}],
    }


def test_levenshtein_basic():
    assert _levenshtein("abc", "abc") == 0
    assert _levenshtein("", "abc") == 3
    assert _levenshtein("kitten", "sitting") == 3


def test_merges_continuation_into_previous_group():
    gs = [_g(1, cont=True), _g(2)]
    out = merge_cross_page_groups(gs)
    assert len(out) == 1
    assert out[0]["page_start"] == 1 and out[0]["page_end"] == 2
    assert len(out[0]["items"]) == 2


def test_merges_across_three_pages():
    gs = [_g(1, cont=True), _g(2, cont=True), _g(3)]
    out = merge_cross_page_groups(gs)
    assert len(out) == 1
    assert out[0]["page_end"] == 3
    assert len(out[0]["items"]) == 3


def test_does_not_merge_when_work_mode_differs():
    gs = [_g(1, work_mode="oral", cont=True), _g(2, work_mode="app")]
    out = merge_cross_page_groups(gs)
    assert len(out) == 2


def test_does_not_merge_when_stem_unrelated():
    gs = [_g(1, stem="直接写出得数", cont=True), _g(2, stem="解决问题并验算")]
    out = merge_cross_page_groups(gs)
    assert len(out) == 2
    assert out[0]["incomplete"] is True


def test_marks_incomplete_and_stops_chain():
    """合并失败必须把 continues_next_page 置 False，否则下一轮还会误吞。"""
    gs = [_g(1, stem="甲组题", cont=True), _g(2, stem="完全不同的乙组")]
    out = merge_cross_page_groups(gs)
    assert len(out) == 2
    assert out[0]["continues_next_page"] is False
    assert out[0]["incomplete"] is True
    assert out[1]["page_start"] == 2


def test_non_contiguous_pages_not_merged():
    """page_start 必须紧接上一组 page_end，跳页不合并。"""
    gs = [_g(1, cont=True), _g(5)]
    out = merge_cross_page_groups(gs)
    assert len(out) == 2


def test_empty_and_single():
    assert merge_cross_page_groups([]) == []
    assert len(merge_cross_page_groups([_g(1)])) == 1


def test_does_not_mutate_input():
    gs = [_g(1, cont=True), _g(2)]
    before = len(gs[0]["items"])
    merge_cross_page_groups(gs)
    assert len(gs[0]["items"]) == before


def test_empty_stem_merges_any():
    """stem 有一侧为空时不作为否决条件（页面没有题干，靠 work_mode 判）。"""
    gs = [_g(1, stem="", cont=True), _g(2, stem="直接写出得数")]
    out = merge_cross_page_groups(gs)
    assert len(out) == 1
