"""渲染沙箱：执行 LLM 生成的 manim 代码时做受限隔离。

参照 DeepTutor 的 sandbox 后端分层（deeptutor/services/sandbox/）：

- ``subprocess`` —— 受限 subprocess（APPLICATION 级）：清洗环境变量 + 限定 cwd +
  资源限额。本机 Windows / 本地 dev 的默认。
- ``docker`` —— SYSTEM 级：转发到独立 runner sidecar 容器（无网络 + 非 root +
  cap_drop ALL + read_only rootfs），由 :mod:`render_service.runner.server` 执行。
- ``off`` —— 禁用渲染（默认不执行未沙箱代码）。

后端由环境变量 ``KNOACT_RENDER_SANDBOX`` 选择；未设置时默认 ``subprocess``。

docker 后端通过 ``KNOACT_RENDER_RUNNER_URL`` 指定 runner 地址（默认
``http://localhost:8901``）。runner 未连上时**报错而非降级到 subprocess**——
否则就静默退回了不隔离的执行，违背沙箱目的。
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

# 只透传这些环境变量给被执行的代码，杜绝 LLM 代码读到 DATABASE_URL / API key
# 等敏感值（DeepTutor RestrictedSubprocessBackend._SAFE_ENV_KEYS 同款思路）。
# Windows 上 Path.home() 依赖 USERPROFILE/HOMEDRIVE/HOMEPATH（而非 HOME），manim
# 启动时会调 Path.home()，缺了会抛 "Could not determine home directory"。
SAFE_ENV_KEYS = (
    "PATH", "PATHEXT", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
    "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT",
)

_SANDBOX_ENV = "KNOACT_RENDER_SANDBOX"
_RUNNER_URL_ENV = "KNOACT_RENDER_RUNNER_URL"
_DEFAULT_RUNNER_URL = "http://localhost:8901"


def backend() -> str:
    """当前启用的沙箱后端：subprocess | docker | off。"""
    return os.environ.get(_SANDBOX_ENV, "subprocess").strip().lower()


def _scrubbed_env() -> dict[str, str]:
    """只保留 SAFE_ENV_KEYS 里的环境变量，其余全部剔除。"""
    return {key: os.environ[key] for key in SAFE_ENV_KEYS if key in os.environ}


def _runner_url() -> str:
    return os.environ.get(_RUNNER_URL_ENV, _DEFAULT_RUNNER_URL).strip().rstrip("/")


# 宿主机 media 目录（与 pipeline.MEDIA_DIR 一致），docker 后端把其中的宿主路径
# 翻译成容器内的 /outputs 挂载路径。
_MEDIA_DIR = Path(__file__).resolve().parent / "media"
_OUTPUTS = "/outputs"


def _to_container_path(host_path: str) -> str:
    """把宿主机 media 目录下的路径翻译成容器内 /outputs 下的路径。

    不在 media 目录下的路径原样返回（通常不该发生，仅容错）。
    """
    try:
        rel = Path(host_path).resolve().relative_to(_MEDIA_DIR.resolve())
    except ValueError:
        return host_path
    return str(Path(_OUTPUTS) / rel).replace("\\", "/")


def _run_via_runner(
    argv: list[str],
    *,
    cwd: str,
    timeout: int,
    max_output_chars: int,
) -> subprocess.CompletedProcess:
    """SYSTEM 级隔离：把命令转发到 runner sidecar 容器执行（HTTP /exec）。

    把 argv 与 workdir 里的 media 宿主路径翻译成容器内 /outputs 路径。
    """
    import requests

    argv_c = [_to_container_path(a) for a in argv]
    workdir_c = _to_container_path(cwd)

    payload = {
        "argv": argv_c,
        "workdir": workdir_c,
        "env": _scrubbed_env(),
        "limits": {"timeout_s": timeout, "max_output_chars": max_output_chars},
    }
    try:
        resp = requests.post(
            f"{_runner_url()}/exec", json=payload, timeout=timeout + 15
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        # runner 不可达：报错而非降级到 subprocess（否则静默失去隔离）
        raise RuntimeError(f"docker 沙箱 runner 不可达：{type(exc).__name__}: {exc}")

    if data.get("error"):
        # runner 自身失败（坏请求/spawn 错误）
        return subprocess.CompletedProcess(
            argv, 1, stdout=data.get("stdout", ""), stderr=data.get("error", "")
        )

    exit_code = int(data.get("exit_code", 0))
    return subprocess.CompletedProcess(
        argv,
        exit_code,
        stdout=data.get("stdout", "") or "",
        stderr=data.get("stderr", "") or "",
    )


def run_sandboxed(
    argv: list[str],
    *,
    cwd: str,
    timeout: int = 120,
    max_output_chars: int = 4000,
) -> subprocess.CompletedProcess:
    """在受限沙箱里执行命令。

    - ``subprocess`` 后端：清洗环境变量 + 限定 cwd + 截断输出（APPLICATION 级）。
    - ``docker`` 后端：转发到 runner sidecar 容器（SYSTEM 级）。
    - ``off``：拒绝执行。

    返回 CompletedProcess（与 subprocess.run 兼容）。调用方按 returncode 判断成败。
    """
    mode = backend()
    if mode == "off":
        raise RuntimeError("渲染沙箱后端 'off'，拒绝执行未沙箱代码")
    if mode == "docker":
        return _run_via_runner(
            argv, cwd=cwd, timeout=timeout, max_output_chars=max_output_chars
        )

    # subprocess 后端：清洗 env + 限定 cwd
    env = _scrubbed_env()
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
    except subprocess.TimeoutExpired:
        # 超时也返回一个带超时标记的结果，供上层判断
        return subprocess.CompletedProcess(
            argv, -1, stdout="", stderr="timeout"
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            argv, -2, stdout="", stderr="command not found"
        )

    # 截断输出，防止 LLM 代码刷爆内存/日志
    if proc.stdout and len(proc.stdout) > max_output_chars:
        proc.stdout = proc.stdout[:max_output_chars] + "\n...[truncated]"
    if proc.stderr and len(proc.stderr) > max_output_chars:
        proc.stderr = proc.stderr[:max_output_chars] + "\n...[truncated]"

    return proc
