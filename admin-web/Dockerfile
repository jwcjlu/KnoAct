# KnoAct 运营后台（静态页）+ nginx 反代后端
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html app.js /usr/share/nginx/html/
RUN printf "window.KNOACT_API_BASE = '';\n" > /usr/share/nginx/html/config.js

EXPOSE 80
