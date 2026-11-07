# KnoAct Flutter 学生端（Web）
# 构建上下文为 student-app/：docker build -t knoact-student-app ./student-app
# ghcr.io/cirruslabs/flutter 最新仅到 3.44（Dart 3.12），不满足 pubspec 的 sdk ^3.13.7，
# 故安装与本地开发一致的官方 Flutter 发行包；升级 Flutter 时同步改版本与 sha256
# （见 https://storage.flutter-io.cn/flutter_infra_release/releases/releases_linux.json）
FROM --platform=linux/amd64 debian:bookworm-slim AS build
ARG APT_MIRROR=mirrors.aliyun.com
ARG FLUTTER_VERSION=3.47.9
ARG FLUTTER_SHA256=25ed8c3c29d51a7353f2a944310b478af8214920639524b19c50a19e6c044c5a
# 国内网络：pub 与 Flutter 资源走镜像
ENV PUB_HOSTED_URL=https://pub.flutter-io.cn \
    FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn \
    PATH=/opt/flutter/bin:$PATH

RUN set -eux; \
    if [ "$APT_MIRROR" != "deb.debian.org" ]; then \
      if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
      elif [ -f /etc/apt/sources.list ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list; \
      fi; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git unzip xz-utils \
    && rm -rf /var/lib/apt/lists/*

# 发行包自带 .git，属主与 root 不同，需标记为 safe.directory，否则 flutter 工具取版本失败
RUN curl -fL --retry 3 -o /tmp/flutter.tar.xz \
        "${FLUTTER_STORAGE_BASE_URL}/flutter_infra_release/releases/stable/linux/flutter_linux_${FLUTTER_VERSION}-stable.tar.xz" \
    && echo "${FLUTTER_SHA256}  /tmp/flutter.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/flutter.tar.xz -C /opt \
    && rm /tmp/flutter.tar.xz \
    && git config --global --add safe.directory /opt/flutter \
    && flutter config --no-analytics \
    && flutter precache --web

WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get --enforce-lockfile
COPY . .
# API_BASE 置空：Web 走同源，经 nginx 反代 /api、/uploads 到后端；
# --no-web-resources-cdn 把 CanvasKit 打进产物，运行时不再访问 www.gstatic.com
RUN flutter build web --release --no-web-resources-cdn --dart-define=API_BASE=

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build/web /usr/share/nginx/html
EXPOSE 80
