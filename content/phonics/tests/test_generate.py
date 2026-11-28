from pathlib import Path

from tools.generate_handbook import render_handbook


def test_handbook_has_path_and_catalog_sections():
    root = Path(__file__).resolve().parents[1]
    text = render_handbook(root / "rules.yaml", root / "path.yaml")
    assert "## 推荐学习路径" in text
    assert "## 分类目录" in text