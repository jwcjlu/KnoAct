import pytest
from tools.schema import validate_rule, ValidationError, CATEGORIES


def _ok_rule(**over):
    base = {
        "id": "vowel.a.short",
        "category": "vowel",
        "grapheme": "a",
        "ipa": "/æ/",
        "approx_zh": "近似「啊」（短）",
        "example_words": [
            {"word": "cat", "grades": [3, 5], "source": "common"},
            {"word": "map", "grades": [3], "source": "common"},
            {"word": "fantastic", "grades": [5], "source": "common"},
        ],
        "accent": "oxford_shanghai",
        "audio": {
            "rule": {"path": "audio/rule/vowel.a.short.wav", "source": "tts"},
            "examples": [],
        },
        "path_order": 1,
        "notes": "",
    }
    base.update(over)
    return base


def test_valid_rule_passes():
    validate_rule(_ok_rule())


def test_rejects_bad_category():
    with pytest.raises(ValidationError):
        validate_rule(_ok_rule(category="vowel_letter"))


def test_requires_grade3_and_grade5_coverage():
    with pytest.raises(ValidationError):
        validate_rule(_ok_rule(example_words=[
            {"word": "cat", "grades": [3], "source": "common"},
            {"word": "map", "grades": [3], "source": "common"},
            {"word": "bat", "grades": [3], "source": "common"},
        ]))


def test_awareness_may_omit_ipa():
    validate_rule(_ok_rule(
        id="syllable_pattern.closed_syllable.awareness",
        category="syllable_pattern",
        grapheme="closed_syllable",
        ipa="",
        approx_zh="闭音节：元音发短音（说明）",
        path_order=40,
    ))
def test_openlettersounds_source_allowed():
    validate_rule(_ok_rule(audio={
        "rule": {"path": "audio/rule/vowel.a.short.wav", "source": "openlettersounds"},
        "examples": [],
    }))


def test_vocamax_ipa_source_allowed():
    validate_rule(_ok_rule(audio={
        "rule": {"path": "audio/rule/vowel_team.ai.primary.wav", "source": "vocamax_ipa"},
        "examples": [],
    }))
