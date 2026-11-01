from app.services.mermaid_sanitize import normalize_mermaid_code, normalize_mermaid_in_answer


def test_mindmap_converted_to_graph_td():
    code = "mindmap\n  root((小数))\n    意义\n    读写\n"
    out = normalize_mermaid_code(code, fallback_title="小数")
    assert out.startswith("graph TD")
    assert '["' in out
    assert "意义" in out or "小数" in out


def test_broken_graph_rebuilt():
    code = "graph TD\n  小数的意义 --> 读写\n  mindmap\n  syntax error here"
    out = normalize_mermaid_code(code, fallback_title="小数")
    assert out.startswith("graph TD")
    assert "root" in out
    assert "-->" in out


def test_normalize_dedupes_mermaid_blocks():
    ans = "说明\n```mermaid\nmindmap\n  a\n```\n\n```mermaid\nmindmap\n  b\n```"
    out = normalize_mermaid_in_answer(ans, question="小数")
    assert out.count("```mermaid") == 1
