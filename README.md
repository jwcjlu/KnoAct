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
  ├─▶ frontend（旧版学生端 Web）────┐
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
cp .env.example .env            # 按需修改端口、数据库等

docker compose up -d --build    # 启动后端 + 学生端 + 家长端
```

浏览器访问学生端 `http://<服务器IP>:8080`、家长端 `http://<服务器IP>:8081`（端口分别由 `.env` 中的 `KNOACT_HTTP_PORT`、`KNOACT_PARENT_PORT` 决定）。

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
| `frontend` | 旧版学生端 Web，nginx 托管并反代 `/api`、`/uploads` | 对外 `8080` |
| `parent-web` | 家长端，nginx 托管并反代 `/api`、`/uploads` | 对外 `8081` |
| `backend` | FastAPI 后端 | 仅内部 `8010` |
| `render` | 动画渲染服务（profile `render`） | 仅内部 `8011` |
| `sandbox-runner` | manim 隔离执行（profile `render`） | 仅内部 `8901` |

| 数据卷 | 内容 |
| --- | --- |
| `knoact-data` | SQLite 数据库 `/data/zhixueban.db` |
| `knoact-uploads` | 上传的 PDF 与拆页图片 |
| `render-media` | 渲染出的动画视频 |

### 常用运维命令

```bash
docker compose ps                          # 查看状态
docker compose logs -f backend             # 查看后端日志
git pull && docker compose up -d --build   # 更新版本（数据卷保留）
docker compose down                        # 停止（保留数据卷）
docker compose down -v                     # 停止并删除所有数据（慎用）

# 备份数据库与上传文件
docker run --rm -v knoact_knoact-data:/data -v knoact_knoact-uploads:/uploads -v "$PWD":/backup \
  alpine tar czf /backup/knoact-backup-$(date +%F).tgz /data /uploads
```

### 使用 MySQL

在 `.env` 中设置 `DATABASE_URL`，后端和渲染服务会共用这个连接：

```bash
DATABASE_URL=mysql+pymysql://user:password@mysql-host:3306/zhixueban?charset=utf8mb4
```

数据库需事先创建好，表结构由后端启动时自动创建。

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

### 动画渲染服务

见 [render_service/README.md](render_service/README.md)，本地需要 manim、ffmpeg 与 LaTeX。

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | 本地 `sqlite:///./zhixueban.db`；容器 `sqlite:////data/zhixueban.db` | 数据库连接 |
| `KNOACT_RENDER_SERVICE_URL` | 本地 `http://127.0.0.1:8011`；容器 `http://render:8011` | 渲染服务地址 |
| `KNOACT_RENDER_SANDBOX` | `subprocess`（容器内为 `docker`） | manim 执行方式：`subprocess` / `docker` / `off` |
| `KNOACT_RENDER_RUNNER_URL` | `http://localhost:8901`（容器内为 `http://sandbox-runner:8901`） | sandbox runner 地址 |
| `KNOACT_HTTP_PORT` | `8080` | docker 部署的学生端（旧版 Web）对外端口 |
| `KNOACT_PARENT_PORT` | `8081` | docker 部署的家长端对外端口 |
| `TZ` | `Asia/Shanghai` | 时区，影响每日任务生成时间 |

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
