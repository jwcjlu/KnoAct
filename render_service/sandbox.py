"""渲染沙箱：执行 LLM 生成的 manim 代码时做受限隔离。

参照 DeepTutor 的 sandbox 后端分层（deeptutor/services/sandbox/）：

- ``subprocess`` —— 受限 subprocess（APPLICATION 级）：清洗环境变量 + 限定 cwd +
  资源限额。本机 Windows / 本地 dev 的默认。
- ``docker`` —— SYSTEM 级：跑在无网络独立容器（后置，需 Docker Desktop）。
- ``off`` —— 禁用渲染（默认不执行未沙箱代码）。

后端由环境变量 ``KNOACT_RENDER_SANDBOX`` 选择；未设置时默认 ``subprocess``
（本地 dev 的 APPLICATION 隔离，不提供 OS 级防护——LLM 代码若主动
``os.system`` 读盘/联网仍可逃逸，与 DeepTutor 对 APPLICATION 级的定位一致）。

SYSTEM 级隔离（docker）作为后置部署选项，落地后把默认值切到 ``docker``。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
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


def backend() -> str:
    """当前启用的沙箱后端：subprocess | docker | off。"""
    return os.environ.get(_SANDBOX_ENV, "subprocess").strip().lower()


def _scrubbed_env() -> dict[str, str]:
    """只保留 SAFE_ENV_KEYS 里的环境变量，其余全部剔除。"""
    return {key: os.environ[key] for key in SAFE_ENV_KEYS if key in os.environ}


def run_sandboxed(
    argv: list[str],
    *,
    cwd: str,
    timeout: int = 120,
    max_output_chars: int = 4000,
) -> subprocess.CompletedProcess:
    """在受限沙箱里执行命令。

    - ``subprocess`` 后端：清洗环境变量 + 限定 cwd + 截断输出（APPLICATION 级）。
    - ``docker`` / ``off``：见 :func:`backend`，docker 落地前视为 off。

    返回 CompletedProcess（与 subprocess.run 兼容）。调用方按 returncode 判断成败。
    """
    mode = backend()
    if mode in ("off", "docker"):
        # off：拒绝执行；docker 尚未落地，暂按 off 处理（避免裸跑脏代码）
        raise RuntimeError(f"渲染沙箱后端 {mode!r} 未启用，拒绝执行未沙箱代码")

    # subprocess 后端：清洗 env + 限定 cwd
    env = _scrubbed_env()
    if mode == "docker":
        # 占位：将来走 RunnerSidecarBackend 式 HTTP 转发，不在本机裸跑
        raise RuntimeError("docker 沙箱后端尚未实现")

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
