# render_service/tests/test_sandbox.py
import os
import subprocess
import sys

from render_service.sandbox import run_sandboxed, _scrubbed_env


def test_scrubbed_env_drops_sensitive_vars():
    os.environ["DATABASE_URL"] = "sqlite:///secret.db"
    os.environ["KNOACT_FAKE_API_KEY"] = "sk-secret"
    try:
        env = _scrubbed_env()
        assert "DATABASE_URL" not in env
        assert "KNOACT_FAKE_API_KEY" not in env
        assert "PATH" in env  # 安全键保留
    finally:
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("KNOACT_FAKE_API_KEY", None)


def test_run_sandboxed_confines_cwd(tmp_path):
    """cwd 被限定到给定目录，脚本看不到调用方的敏感文件。"""
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import os\n"
        "print(os.path.abspath(os.getcwd()))\n"
        "print('DATABASE_URL' in os.environ)\n",
        encoding="utf-8",
    )
    proc = run_sandboxed(
        [sys.executable, str(probe)],
        cwd=str(tmp_path),
        timeout=30,
    )
    assert proc.returncode == 0
    out = (proc.stdout or "").strip()
    # Windows 路径大小写不敏感，统一 lower 后比较
    assert str(tmp_path).lower().replace("\\", "/") in out.lower().replace("\\", "/")
    assert "False" in out  # DATABASE_URL 不在被清洗后的 env 里


def test_run_sandboxed_refuses_when_off(monkeypatch, tmp_path):
    monkeypatch.setenv("KNOACT_RENDER_SANDBOX", "off")
    try:
        try:
            run_sandboxed([sys.executable, "-c", "pass"], cwd=str(tmp_path))
            assert False, "should have raised"
        except RuntimeError as e:
            assert "拒绝执行" in str(e) or "未启用" in str(e)
    finally:
        monkeypatch.delenv("KNOACT_RENDER_SANDBOX", raising=False)
