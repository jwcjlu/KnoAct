# KnoAct（知学伴）

面向小学生的 AI 学习伙伴。家长上传 PDF 教材，系统自动拆课、提取生词 / 知识点 / 课文，孩子在线阅读教材、边读边问、做作业和听写，系统按遗忘曲线安排复习。

## 功能

**孩子端**

- **学习首页**：今日学习计划、今日进度、古诗勉励、各学科课程进度
- **个性化学习**：选择教材直接进入沉浸式阅读（整本 / 分课时），在正文里划线、记笔记、查生词，划词追问 AI
- **本课作业**：AI 按课文出题、按意思判分；答错给出正确答案并继续出新题，正确率达到及格线（默认 60%）才算学完本课；做作业期间暂停 AI 对话
- **听写练习**：手写拍照，AI 视觉模型批改，错词进错题本
- **学习中心 / 错题本**：每日任务、错题复习、知识点主动回忆

**家长端**

家长端为独立应用，顶部可切换当前孩子。

- **教材**：上传 PDF，自动拆课（语文按课、数学按单元）并提取内容
- **知识点 / 题目审核台**：审核 AI 生成的知识点与题目
- **目标 / 任务 / 报告**：学习目标、每日任务、掌握度报告
- **学习配置**：每日听写量、新旧课比例、作业题数、及格正确率、各学科出题难度、AI 对话开关
- **设置**：配置 AI 对话模型、TTS 语音等 provider 与密钥

## 架构

```
浏览器
  │
  ├─▶ student-app（Flutter 学生端）─┐
  ├─▶ frontend（旧版学生端 Web）────┤
  │                                 ├─/api、/uploads─▶  backend（FastAPI）
  └─▶ parent-web（家长端）──────────┘                   │
                                                        │  SQLAlchemy：SQLite（默认）/ MySQL
                                                        │  AI / TTS provider 抽象（未配置时 fake 兜底）
                                                        ▼
                                     render_service（可选，manim 动画 + TTS 旁白）
                                                        │  HTTP
                                                        ▼
                                     sandbox-runner（隔离执行 LLM 生成的 manim 代码）
```

- 后端：FastAPI + SQLAlchemy + APScheduler（每天 03:00 生成当日任务）+ PyMuPDF（PDF 拆页）
- 前端：无框架原生 JS，`render*()` 函数拼 HTML；pdf.js 本地化在 `frontend/vendor/`
- AI：OpenAI 兼容接口（DeepSeek / 通义千问 / OpenAI 等），TTS 支持 MiniMax / OpenAI；均在家长端「设置」页配置，存数据库
- 详细设计见 [AGENTS.md](AGENTS.md)，动画渲染服务见 [render_service/README.md](render_service/README.md)

## 目录结构

```
backend/          FastAPI 后端（app/ 业务代码，tests/ 测试）
frontend/         旧版学生端 Web（冻结，Flutter 学生端完成后移除）
parent-web/       家长端（原生 JS 静态页，独立部署）
student-app/      Flutter 学生端（Web + Android，逐步替代 frontend/）
render_service/   动画渲染服务与 sandbox runner
docs/             设计与实现计划
prototype/        早期交互原型
docker-compose.yml、.env.example   容器化部署
```

## Docker Compose 部署

### 前置条件

- Docker 20.10+，Docker Compose v2（`docker compose` 命令）
- 能访问 Docker Hub 与 PyPI（构建镜像时拉基础镜像和 Python 依赖）

### 启动

```bash
git clone https://github.com/jwcjlu/KnoAct.git
cd KnoAct
cp .env.example .env            # 必须修改 MYSQL_PASSWORD、MYSQL_ROOT_PASSWORD；按需修改端口

docker compose up -d --build    # 启动 MySQL + 后端 + 学生端（Flutter 与旧版）+ 家长端
```

后端会等 MySQL 健康检查通过后才启动；MySQL 首次初始化约需半分钟。

浏览器访问 Flutter 学生端 `http://<服务器IP>:8082`、旧版学生端 `http://<服务器IP>:8080`、家长端 `http://<服务器IP>:8081`（端口分别由 `.env` 中的 `KNOACT_STUDENT_PORT`、`KNOACT_HTTP_PORT`、`KNOACT_PARENT_PORT` 决定）。Flutter 学生端镜像构建时会下载约 1.5 GB 的 Flutter SDK（走 `storage.flutter-io.cn` 镜像），首次构建较慢。

### 生产环境：JWT 与管理员密码（必做）

部署到公网或内网多人共用时，请在复制 `.env.example` 为 `.env` 后至少设置：

- **`JWT_SECRET`**：签发 Bearer JWT 的密钥。须为**长随机串**（例如 `openssl rand -hex 32`），禁止使用示例中的空值或代码里的 `dev-change-me` 默认值。
- **`ADMIN_INITIAL_PASSWORD`**：种子数据为「尚无 `password_hash` 的用户」和默认 **`login_name=admin`** 运营账号设置的**初始密码**。种子默认等价于 `ChangeMe123`；生产务必改为强密码，并在首次上线后通过运营后台（`admin-web`）或 `/api/admin/users` **立即修改** `admin` 密码。

`docker-compose.yml` 已将上述变量传入 `backend` 容器。本地用 `uvicorn` 时也应在 shell 中 `export` 或在 `backend/` 下使用同名环境变量。若未改 `JWT_SECRET` 或仍使用默认 `ADMIN_INITIAL_PASSWORD`，进程启动时会在日志中打出 **warning**（测试 `pytest` 不会触发）。

首次启动会自动建表并写入演示数据（孩子「金同学」、家长「金爸爸」）。AI 默认是 `fake` 兜底模式，打开家长端 →「设置」配置真实的模型与密钥后，出题、判分、对话等 AI 能力才会生效。

### 启用动画渲染（可选）

数学讲解动画依赖 manim + ffmpeg + LaTeX，镜像较大（runner 约 1–2 GB），按需启用：

```bash
docker compose --profile render up -d --build
```

会额外启动两个容器：

- `render`：渲染服务，负责调用 AI 生成 manim 代码、TTS 旁白和 ffmpeg 合轨
- `sandbox-runner`：唯一执行 LLM 生成代码的容器，不能访问外网（internal 网络）、非 root、只读根文件系统、`cap_drop ALL`、限制进程数与内存

### 服务与数据

| 服务 | 说明 | 端口 |
| --- | --- | --- |
| `mysql` | MySQL 8.4，库名默认 `zhixueban`，字符集 utf8mb4 | 仅内部 `3306` |
| `frontend` | 旧版学生端 Web，nginx 托管并反代 `/api`、`/uploads` | 对外 `8080` |
| `parent-web` | 家长端，nginx 托管并反代 `/api`、`/uploads` | 对外 `8081` |
| `student-app` | Flutter 学生端（Web），nginx 托管并反代 `/api`、`/uploads` | 对外 `8082` |
| `backend` | FastAPI 后端 | 仅内部 `8010` |
| `render` | 动画渲染服务（profile `render`） | 仅内部 `8011` |
| `sandbox-runner` | manim 隔离执行（profile `render`） | 仅内部 `8901` |

| 数据卷 | 内容 |
| --- | --- |
| `knoact-mysql` | MySQL 数据目录 |
| `knoact-uploads` | 上传的 PDF 与拆页图片 |
| `render-media` | 渲染出的动画视频 |

### 常用运维命令

```bash
docker compose ps                          # 查看状态
docker compose logs -f backend             # 查看后端日志
git pull && docker compose up -d --build   # 更新版本（数据卷保留）
docker compose down                        # 停止（保留数据卷）
docker compose down -v                     # 停止并删除所有数据（慎用）

# 备份数据库
docker compose exec mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction "$MYSQL_DATABASE"' \
  > knoact-db-$(date +%F).sql
# 恢复数据库
docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' < knoact-db-2026-11-01.sql
# 备份上传文件
docker run --rm -v knoact_knoact-uploads:/uploads -v "$PWD":/backup \
  alpine tar czf /backup/knoact-uploads-$(date +%F).tgz /uploads
```

### 数据库

docker 部署使用 compose 内置的 `mysql` 服务，连接串由 `.env` 里的 `MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DATABASE` 拼出，后端与渲染服务共用。表结构由后端启动时自动创建。

- 密码里含 `@ : / ? # %` 等字符时，要先做 URL 编码（例如 `@` 写成 `%40`），否则连接串解析出错。
- MySQL 只在容器网络内可访问，没有映射到宿主机；需要从外部连接时，自行在 `mysql` 服务下加 `ports`。
- 改用外部 MySQL：删掉 `mysql` 服务和后端的 `depends_on: mysql`，并把 `docker-compose.yml` 里的 `x-db-url` 改成外部地址。
- 本地开发仍默认用 SQLite（见下文），不需要 MySQL。

## 本地开发

需要 Python 3.10+。

### 后端

```bash
cd backend                      # 必须在 backend/ 下运行：默认 SQLite 路径相对当前目录
pip install -r requirements.txt
python -m app.seed              # 建表 + 演示数据（可重复执行）
python -m uvicorn app.main:app --port 8010 --reload
```

健康检查：`http://127.0.0.1:8010/health`

### 学生端（旧版 Web）

```bash
python -m http.server 8766 --directory frontend
```

访问 `http://127.0.0.1:8766`。前端默认连接 `http://127.0.0.1:8010`；后端部署在别处时，在 `frontend/config.js` 中设置 `window.KNOACT_API_BASE`。修改 `app.js` 后把 `index.html` 里 `app.js?v=` 的版本号加 1，避免浏览器缓存旧脚本。

### 家长端

```bash
python -m http.server 8767 --directory parent-web
```

访问 `http://127.0.0.1:8767`。家长端默认连接 `http://127.0.0.1:8010`；后端部署在别处时，在 `parent-web/config.js` 中设置 `window.KNOACT_API_BASE`。

### Flutter 学生端

需要 Flutter 3.47.8+（Dart 3.13.7+）。

```bash
cd student-app
flutter pub get
flutter run -d chrome                                            # Web，连本地后端 127.0.0.1:8010
flutter run -d emulator-5554 --dart-define=API_BASE=http://10.0.2.2:8010   # 安卓模拟器
flutter test && flutter analyze
```

国内网络先设置环境变量 `PUB_HOSTED_URL=https://pub.flutter-io.cn`、`FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn`。不传 `API_BASE` 时连 `http://127.0.0.1:8010`；`--dart-define=API_BASE=`（空值）时 Web 走页面同源（docker 部署即如此，由 nginx 反代 `/api`、`/uploads`）。

已知限制：

- **中文字体运行时联网下载**：Flutter Web 渲染中文时，回退字体在运行时从 `fonts.gstatic.com` 下载；访问不了该域名的网络中，中文可能显示为空白或方块。后续改为自托管字体。
- **安卓仅适合开发调试**：主 Manifest 允许明文 HTTP（`usesCleartextTraffic`），release 构建仍使用 debug 签名，正式发布前需在子项目 5 处理。
- **安卓必须传后端地址**：安卓上不传 `API_BASE` 会连设备自身的 `127.0.0.1`，必须加 `--dart-define=API_BASE=...`（模拟器用 `http://10.0.2.2:8010`，真机用电脑的局域网地址）。

### 动画渲染服务

见 [render_service/README.md](render_service/README.md)，本地需要 manim、ffmpeg 与 LaTeX。

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | 本地 `sqlite:///./zhixueban.db`；docker 部署由 `MYSQL_*` 拼出 | 数据库连接 |
| `MYSQL_DATABASE` / `MYSQL_USER` | `zhixueban` / `knoact` | docker 部署的 MySQL 库名与账号 |
| `MYSQL_PASSWORD` / `MYSQL_ROOT_PASSWORD` | 无，必须设置 | docker 部署的 MySQL 密码 |
| `KNOACT_RENDER_SERVICE_URL` | 本地 `http://127.0.0.1:8011`；容器 `http://render:8011` | 渲染服务地址 |
| `KNOACT_RENDER_SANDBOX` | `subprocess`（容器内为 `docker`） | manim 执行方式：`subprocess` / `docker` / `off` |
| `KNOACT_RENDER_RUNNER_URL` | `http://localhost:8901`（容器内为 `http://sandbox-runner:8901`） | sandbox runner 地址 |
| `KNOACT_HTTP_PORT` | `8080` | docker 部署的学生端（旧版 Web）对外端口 |
| `KNOACT_PARENT_PORT` | `8081` | docker 部署的家长端对外端口 |
| `KNOACT_STUDENT_PORT` | `8082` | docker 部署的 Flutter 学生端对外端口 |
| `TZ` | `Asia/Shanghai` | 时区，影响每日任务生成时间 |
| `JWT_SECRET` | 代码默认 `dev-change-me`（**仅本地**） | **生产必填**：JWT 签名密钥，须为长随机串 |
| `ADMIN_INITIAL_PASSWORD` | 默认 `ChangeMe123` | 种子幂等补全密码与创建 `admin` 时的初始密码；**生产须改**并在上线后改密 |
| `JWT_ACCESS_TTL` | `3600` | 访问令牌秒数 |
| `JWT_REFRESH_DAYS` | `30` | 刷新令牌有效天数 |
| `KNOACT_LEGACY_NAME_LOGIN` | 未设 | 设为 `1` 时放开旧版「仅姓名」登录（仅建议开发环境） |

AI、TTS 的 provider 与密钥以及学习配置不走环境变量，在家长端页面配置后保存在数据库中。

## 测试

```bash
cd backend && python -m pytest
python -m pytest render_service/tests   # 在仓库根目录执行
```

## 常见问题

- **页面能打开但没有数据**：本地后端不在 `backend/` 目录下启动时，SQLite 相对路径会指向别处的空库。回到 `backend/` 启动，或给 `DATABASE_URL` 写绝对路径。
- **出题、判分、对话没有真实 AI 效果**：AI provider 仍是 `fake`，打开家长端 →「设置」配置模型与密钥。
- **PDF 正文加载失败**：pdf.js 以 ES module 加载 `.mjs` 文件，自建的静态服务器需对 `.mjs` 返回 `application/javascript`（`frontend/nginx.conf` 已处理）。
