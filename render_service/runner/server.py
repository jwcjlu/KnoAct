"""Sandbox runner sidecar HTTP server（纯标准库，无第三方依赖）。

这个进程跑在独立的 runner 容器里（带 manim + ffmpeg + LaTeX 重依赖），是**唯一**
执行 LLM 生成的 manim 代码的地方。主渲染服务不自己跑 manim，而是通过
:mod:`render_service.sandbox` 的 docker 后端把命令 HTTP 转发到这里。

设计约束（参照 DeepTutor deeptutor/services/sandbox/runner/server.py）：

* 只用标准库 ``http.server``，runner 镜像保持最小、无重型框架。
* 纵深防御：容器本身已降权（非 root、cap_drop ALL、read_only rootfs），
  这里再叠加每命令的资源限制。
* 命令以 argv 形式执行（不用 shell），杜绝 shell 元字符注入。

协议（与 sandbox.py 的 docker 后端匹配）：

    GET  /health -> 200 "ok"
    POST /exec   -> {"argv": [...], "workdir": "...", "env": {...},
                     "limits": {"timeout_s": ..., "max_output_chars": ...}}
                    返回 {"stdout", "stderr", "exit_code", "timed_out", "error"}

``error`` 仅在 runner 自身失败（坏 JSON、spawn 错误）时非空，命令 exit_code
非零不算 runner 错误。
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import subprocess
import sys
from typing import Any

DEFAULT_PORT = 8901

# 请求体上限，防止恶意/异常调用方在读 JSON 前就撑爆内存
_MAX_REQUEST_BYTES = 4 * 1024 * 1024

_DEFAULT_TIMEOUT_S = 120
_DEFAULT_MAX_OUTPUT_CHARS = 10_000


def _truncate(text: str, max_chars: int) -> str:
    """截断到 max_chars，保留头尾（中间省略）。"""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    half = max_chars // 2
    dropped = len(text) - max_chars
    return text[:half] + f"\n\n... ({dropped:,} chars truncated) ...\n\n" + text[-half:]


def execute(payload: dict[str, Any]) -> dict[str, Any]:
    """执行一个 argv 命令，返回响应 dict。命令级失败走 exit_code/stderr，
    只有 runner 自身失败才填 error。"""
    raw_argv = payload.get("argv") or []
    if not isinstance(raw_argv, list) or not raw_argv:
        return _error_result("'argv' must be a non-empty list of strings")
    if any(not isinstance(item, str) for item in raw_argv):
        return _error_result("'argv' must be a list of strings")
    argv: list[str] = list(raw_argv)

    workdir = payload.get("workdir") or None
    if workdir is not None and not isinstance(workdir, str):
        return _error_result("'workdir' must be a string or null")

    raw_env = payload.get("env") or {}
    if not isinstance(raw_env, dict):
        return _error_result("'env' must be an object")
    env: dict[str, str] = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")}
    for key, value in raw_env.items():
        env[str(key)] = str(value)

    limits = payload.get("limits") or {}
    if not isinstance(limits, dict):
        return _error_result("'limits' must be an object")
    timeout_s = _int(limits.get("timeout_s"), _DEFAULT_TIMEOUT_S)
    max_output_chars = _int(limits.get("max_output_chars"), _DEFAULT_MAX_OUTPUT_CHARS)

    try:
        completed = subprocess.run(
            argv,
            cwd=workdir,
            env=env,
            timeout=timeout_s,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": _truncate(_decode(exc.stdout), max_output_chars),
            "stderr": _truncate(_decode(exc.stderr), max_output_chars),
            "exit_code": 124,
            "timed_out": True,
            "error": "",
        }
    except (OSError, ValueError) as exc:
        return _error_result(f"{type(exc).__name__}: {exc}")

    return {
        "stdout": _truncate(completed.stdout or "", max_output_chars),
        "stderr": _truncate(completed.stderr or "", max_output_chars),
        "exit_code": completed.returncode,
        "timed_out": False,
        "error": "",
    }


def _decode(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _int(value: Any, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default


def _error_result(message: str) -> dict[str, Any]:
    return {"stdout": "", "stderr": "", "exit_code": 0, "timed_out": False, "error": message}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        sys.stdout.write("runner: " + (format % args) + "\n")

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/health", ""):
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._send_json(404, _error_result("not found"))

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/exec":
            self._send_json(404, _error_result("not found"))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, _error_result("invalid Content-Length"))
            return
        if length > _MAX_REQUEST_BYTES:
            self._send_json(413, _error_result("request body too large"))
            return
        try:
            raw = self.rfile.read(length) if length > 0 else b""
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
        except (ValueError, UnicodeDecodeError) as exc:
            self._send_json(400, _error_result(f"invalid JSON: {exc}"))
            return

        try:
            result = execute(payload)
        except Exception as exc:  # noqa: BLE001
            result = _error_result(f"runner crashed: {type(exc).__name__}: {exc}")
        self._send_json(200, result)


def main() -> None:
    try:
        port = int(os.environ.get("RUNNER_PORT", "") or DEFAULT_PORT)
    except ValueError:
        port = DEFAULT_PORT
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    sys.stdout.write(f"runner: listening on 0.0.0.0:{port}\n")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
