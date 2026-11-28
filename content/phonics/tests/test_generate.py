from pathlib import Path

from tools.generate_handbook import render_handbook
from tools.generate_manifest import build_manifest


def test_handbook_has_path_and_catalog_sections():
    root = Path(__file__).resolve().parents[1]
    text = render_handbook(root / "rules.yaml", root / "path.yaml")
    assert "## 推荐学习路径" in text
    assert "## 分类目录" in text


def test_manifest_lists_each_rule_audio(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    from tools.schema import load_rules

    man = build_manifest(root / "rules.yaml", root / "audio")
    assert "rules" in man
    assert len(man["rules"]) == len(load_rules(root / "rules.yaml"))
    row = man["rules"][0]
    assert "id" in row and "expected_path" in row and "exists" in row and "source" in row
    assert "examples" in row and len(row["examples"]) >= 3