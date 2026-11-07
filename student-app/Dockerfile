# KnoAct Flutter 学生端（Web）
# 构建上下文为 student-app/：docker build -t knoact-student-app ./student-app
FROM --platform=linux/amd64 debian:bookworm-slim AS build
ARG APT_MIRROR=mirrors.aliyun.com
ARG FLUTTER_VERSION=3.47.9
ARG FLUTTER_SHA256=25ed8c3c29d51a7353f2a944310b478af8214920639524b19c50a19e6c044c5a
ARG FLUTTER_USER=flutter
ARG FLUTTER_UID=10001

ENV PUB_HOSTED_URL=https://pub.flutter-io.cn \
    FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn \
    PATH=/opt/flutter/bin:$PATH \
    CI=true

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

RUN curl -fL --retry 3 -o /tmp/flutter.tar.xz \
        "${FLUTTER_STORAGE_BASE_URL}/flutter_infra_release/releases/stable/linux/flutter_linux_${FLUTTER_VERSION}-stable.tar.xz" \
    && echo "${FLUTTER_SHA256}  /tmp/flutter.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/flutter.tar.xz -C /opt \
    && rm /tmp/flutter.tar.xz \
    && git config --system --add safe.directory /opt/flutter \
    && flutter config --no-analytics
    # 不单独 precache --web，由 build web 按需拉引擎，降低解压后磁盘峰值

RUN useradd -m -u "${FLUTTER_UID}" "${FLUTTER_USER}" \
    && chown -R "${FLUTTER_USER}:${FLUTTER_USER}" /opt/flutter

WORKDIR /app
RUN chown "${FLUTTER_USER}:${FLUTTER_USER}" /app

USER ${FLUTTER_USER}
ENV HOME=/home/${FLUTTER_USER} \
    PUB_CACHE=/home/${FLUTTER_USER}/.pub-cache

COPY --chown=10001:10001 pubspec.yaml pubspec.lock ./
RUN flutter --version \
    && (flutter pub get --enforce-lockfile \
        || (echo "pub mirror miss, retry pub.dev..." \
            && PUB_HOSTED_URL=https://pub.dev FLUTTER_STORAGE_BASE_URL=https://storage.googleapis.com flutter pub get --enforce-lockfile))

COPY --chown=10001:10001 . .
# API_BASE=""：Web 编译期标记已定义、值为空，走 nginx 同源 /api
RUN flutter build web --release --no-web-resources-cdn --no-wasm-dry-run \
    --dart-define=API_BASE=""

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build/web /usr/share/nginx/html
EXPOSE 80
