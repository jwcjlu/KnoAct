# ============================================
# KnoAct 渲染 Sandbox Runner Sidecar 镜像
# ============================================
# 一个刻意保持最小、最低权限的镜像，唯一职责是在独立容器里执行 LLM 生成的
# manim 代码。主渲染服务通过 HTTP（POST /exec）与它通信（见
# render_service/runner/server.py 与 render_service/sandbox.py 的 docker 后端）。
#
# 参照 DeepTutor Dockerfile.runner 的分层设计：runner 只装 manim + ffmpeg +
# TeX Live（重依赖）+ 纯标准库 HTTP server，不依赖主服务代码、不装重型框架，
# 攻击面与镜像体积最小化。
#
# 构建/运行（通常由 docker-compose 编排，不手跑）：
#   docker build -f render_service/runner/Dockerfile -t knoact-render-runner:local .
#   docker run --rm -p 8901:8901 knoact-render-runner:local
# ============================================

FROM python:3.11-slim

ARG APT_MIRROR=deb.debian.org

# ----- manim 渲染依赖 -----------------------------------------------------
# manim 渲染视频需要 ffmpeg；数学公式排版需要 LaTeX。texlive 装精简子集
# （texlive-latex-base + texlive-latex-recommended + texlive-fonts-recommended
# 覆盖 manim 的 MathTex/Tex 需求，远小于 texlive-full）。
RUN set -eux; \
    if [ "$APT_MIRROR" != "deb.debian.org" ]; then \
      if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
      elif [ -f /etc/apt/sources.list ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list; \
      fi; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        texlive-latex-base \
        texlive-latex-recommended \
        texlive-fonts-recommended \
        fonts-wqy-zenhei \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# manim 社区版（含 cloup/av 等渲染依赖）
RUN pip install --no-cache-dir manim

# ----- 非 root 用户 -------------------------------------------------------
# 降权：runner 以普通用户跑，cap_drop ALL（见 docker-compose），沙箱逃逸也
# 只能落到这个无敏感数据、无网络的容器里。
RUN useradd --create-home --uid 10001 runner
USER runner
WORKDIR /home/runner

# 复制 runner 的 std-lib HTTP server（无第三方依赖）
COPY --chown=runner:runner render_service/runner/server.py /app/server.py

EXPOSE 8901

# 产物写回目录：由 docker-compose 把主服务的 media outputs 挂载到 /outputs
VOLUME ["/outputs"]

CMD ["python", "/app/server.py"]
