# KnoAct 家长端（静态页）+ nginx 反代后端
# 构建上下文为 parent-web/：docker build -t knoact-parent-web ./parent-web
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html app.js /usr/share/nginx/html/
# 同源部署：API 地址置空，请求经 nginx 的 /api、/uploads 反代到后端
RUN printf "window.KNOACT_API_BASE = '';\n" > /usr/share/nginx/html/config.js

EXPOSE 80
