// 运行时配置。本地开发保持为空：app.js 默认连 http://127.0.0.1:8010。
// docker 部署时由 admin-web/Dockerfile 覆盖为 window.KNOACT_API_BASE = ''（同源，经 nginx 反代到后端）。
