from pathlib import Path

from tools.synthesize_rule_audio import synthesize_missing


def test_fake_writes_only_missing(tmp_path: Path):
    root = tmp_path / "phonics"
    (root / "audio" / "rule").mkdir(parents=True)
    rules = root / "rules.yaml"
    rules.write_text(
        """
rules:
  - id: vowel.a.short
    category: vowel
    grapheme: a
    ipa: "/æ/"
    approx_zh: "近似啊"
    example_words:
      - {word: cat, grades: [3, 5], source: common}
      - {word: map, grades: [3], source: common}
      - {word: abstract, grades: [5], source: common}
    accent: oxford_shanghai
    audio:
      rule: {path: audio/rule/vowel.a.short.wav, source: tts}
      examples: []
    path_order: 1
""",
        encoding="utf-8",
    )
    written = synthesize_missing(root, fake=True)
    assert written == 1
    assert (root / "audio/rule/vowel.a.short.wav").is_file()
    written2 = synthesize_missing(root, fake=True)
    assert written2 == 0