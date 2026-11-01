# 家长端拆分与独立部署 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把家长端从 `frontend/` 拆成可独立部署的 `parent-web/` 静态应用，后端新增孩子列表接口供家长端选择孩子，docker-compose 分开部署。

**Architecture:** 后端新增只读路由 `GET /api/users`。`parent-web/app.js`、`parent-web/index.html` 由一次性生成脚本从 `frontend/` 按段落标记提取（公共函数 + 家长端段），并对家长端专属行为做定点替换（每处替换断言恰好命中一次）。`frontend/` 不做任何修改。部署新增 nginx 服务 `parent-web`（端口 8081）。

**Tech Stack:** FastAPI + SQLAlchemy + pytest（后端）；原生 JS 静态页（前端）；nginx、docker-compose（部署）。

**Spec:** `docs/superpowers/specs/2026-11-01-parent-web-split-design.md`

---

## 文件结构

| 文件 | 动作 | 职责 |
| --- | --- | --- |
| `backend/app/routers/users.py` | 新建 | `GET /api/users?role=` 用户列表 |
| `backend/app/main.py` | 修改 | 注册 users 路由 |
| `backend/tests/test_users.py` | 新建 | 用户列表接口测试 |
| `parent-web/app.js` | 生成 | 家长端逻辑（公共函数 + 家长端段 + 选孩子 + 初始化） |
| `parent-web/index.html` | 生成 | 页面骨架 + 样式（沿用 frontend 样式 + 选孩子样式） |
| `parent-web/config.js` | 新建 | 运行时 API 地址配置 |
| `parent-web/nginx.conf` | 新建 | 静态托管 + `/api`、`/uploads`、`/health` 反代 |
| `parent-web/Dockerfile` | 新建 | nginx 镜像 |
| `docker-compose.yml`、`.env.example`、`README.md` | 修改 | 新增 parent-web 服务与文档 |

生成脚本只在实现时运行一次，放在临时目录，不提交。

---

### Task 1: 后端孩子列表接口

**Files:**
- Create: `backend/app/routers/users.py`
- Modify: `backend/app/main.py`（第 4 行 import、`app.include_router` 列表）
- Test: `backend/tests/test_users.py`

- [ ] **Step 1: 写失败的测试**

`backend/tests/test_users.py`（`setup_db` fixture 来自 `backend/tests/conftest.py`，每个测试一个干净库）：

```python
from fastapi.testclient import TestClient


def _client():
    from app.main import app
    return TestClient(app)


def _add_users(*users):
    from app.models import User
    from app.database import SessionLocal
    s = SessionLocal()
    for name, role in users:
        s.add(User(name=name, role=role))
    s.commit()
    s.close()


def test_list_children_filters_by_role_and_sorts_by_id(setup_db):
    _add_users(("金同学", "child"), ("金爸爸", "parent"), ("林晨", "child"))
    resp = _client().get("/api/users?role=child")
    assert resp.status_code == 200
    data = resp.json()
    assert [u["name"] for u in data] == ["金同学", "林晨"]
    assert all(set(u) == {"id", "name", "role"} for u in data)
    assert data[0]["id"] < data[1]["id"]


def test_list_users_without_role_returns_all(setup_db):
    _add_users(("金同学", "child"), ("金爸爸", "parent"))
    data = _client().get("/api/users").json()
    assert [u["role"] for u in data] == ["child", "parent"]


def test_list_users_empty(setup_db):
    assert _client().get("/api/users?role=child").json() == []
```

- [ ] **Step 2: 运行测试，确认失败**

Run（在 `backend/` 下）: `python -m pytest tests/test_users.py -v`
Expected: 3 个测试 FAIL（`/api/users` 返回 404）。

- [ ] **Step 3: 实现路由**

`backend/app/routers/users.py`：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(role: str | None = None, db: Session = Depends(get_db)):
    """用户列表（家长端选择孩子用）：可按 role 过滤，按 id 升序。"""
    q = db.query(User)
    if role:
        q = q.filter_by(role=role)
    return [{"id": u.id, "name": u.name, "role": u.role} for u in q.order_by(User.id).all()]
```

`backend/app/main.py`：第 4 行 import 末尾加 `, users`：

```python
from .routers import auth, config_router, pdf, progress, notes, points, learning, goals, mistakes, knowledge, questions, tts_router, annotations, home, tasks, quiz, mastery, render, math, users
```

在 `app.include_router(math.router)` 之后加一行：

```python
app.include_router(users.router)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_users.py -v`
Expected: 3 passed。

Run: `python -m pytest -q`
Expected: 全部通过（含新增 3 个）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/users.py backend/app/main.py backend/tests/test_users.py
git commit -m "feat: 新增 GET /api/users 用户列表接口（家长端选择孩子）"
```

---

### Task 2: 生成 parent-web 的 app.js 与 index.html

**Files:**
- Create（生成）: `parent-web/app.js`、`parent-web/index.html`
- 读取（不修改）: `frontend/app.js`、`frontend/index.html`

- [ ] **Step 1: 写生成脚本**

保存为临时文件 `$env:TEMP\gen_parent_web.py`（不提交；命令以 PowerShell 为准）：

```python
"""一次性生成 parent-web/app.js 与 index.html：从 frontend/ 按段落标记提取，并做家长端专属替换。"""
import io
import re
from pathlib import Path

ROOT = Path(r"d:\workspace\github\KnoAct")
SRC_JS = (ROOT / "frontend/app.js").read_text(encoding="utf-8").replace("\r\n", "\n")
SRC_HTML = (ROOT / "frontend/index.html").read_text(encoding="utf-8").replace("\r\n", "\n")
OUT = ROOT / "parent-web"
OUT.mkdir(exist_ok=True)


def between(text, start, end, include_start=True):
    """返回 text 中 [start, end) 区间；start/end 都必须恰好出现一次。"""
    assert text.count(start) == 1, f"start not unique: {start!r}"
    assert text.count(end) == 1, f"end not unique: {end!r}"
    i = text.index(start) if include_start else text.index(start) + len(start)
    j = text.index(end)
    assert i < j, (start, end)
    return text[i:j]


def func_block(text, signature):
    """提取以 signature 开头、到下一个顶层（行首）`}` 为止的函数。"""
    assert text.count(signature) == 1, signature
    i = text.index(signature)
    j = text.index("\n}\n", i) + 3
    return text[i:j]


def rep(text, old, new):
    assert text.count(old) == 1, f"replace target not unique: {old[:60]!r}"
    return text.replace(old, new)


# ---------- app.js ----------
icons = between(SRC_JS, "// ===== 图标 =====", "// 对话栏空态插图")
providers = between(SRC_JS, "const aiProviders = [", "// 聊天模式（能力）列表")
helpers = between(SRC_JS, "function toast(msg){", "// ===== 渲染入口 =====")
escape_attr = func_block(SRC_JS, "function escapeAttr(s){")
browser_speak = func_block(SRC_JS, "function browserSpeak(text){")
parent = between(SRC_JS, "// ===== 家长端 =====", "// ===== 初始化 =====")

state = r"""// ===== 通用状态 =====
const PARENT_TABS = [
  ['教材','book'],['知识点','brain'],['题目审核台','list'],['目标','star'],['报告','chart'],
  ['任务','pen'],['规则','gift'],['学习配置','grid'],['设置','menu']
];
const CHILD_TABS = ['目标','报告','任务'];   // 依赖当前孩子（uid）的 Tab
const CHILD_KEY = 'knoact_parent_child_id';
let uid = null;            // 当前孩子 id，由孩子列表决定；确定前不发依赖孩子的请求
let children = [];         // [{id, name, role}]
let childSwitching = false;
let parentTab = '教材';

// 家长端数据缓存
let pdfDocs = [];
let pdfTab = null; // null | 'upload' | 'confirm'
let confirmDocId = null;
let knowledgeRows = [];
let goalRows = [];
let reportRows = [];
let masteryReport = null;
async function loadMasteryReport(){
  if(!uid){ masteryReport = null; return null; }
  masteryReport = await api(`/api/mastery/report?user_id=${uid}`);
  return masteryReport;
}
let configMap = {};
let aiConfig = {provider:'deepseek', model:'deepseek-chat', key:'', baseUrl:''};
let aiModelOptions = [];  // 中转站拉取到的动态模型列表
let ttsModelOptions = []; // 中转站拉取到的动态语音模型列表
let ttsConfig = {provider:'minimax', voice:'清澈男声', key:'', baseUrl:'', model:'speech-2.8-hd', speed:1.0, repeat:2};

// 家长端任务审核
let parentTaskDate = '';   // 家长端任务查看的日期（默认今天）
let parentTasks = [];      // 当天全部任务（含待审核）

"""

render_entry = r"""
// ===== 渲染入口 =====
function renderNav(){
  document.getElementById('nav').innerHTML = PARENT_TABS.map(([label,ic])=>
    `<button class="nav-item ${parentTab===label?'active':''}" onclick="setParentTab('${label}')">${icon(ic,19)}${label}</button>`
  ).join('');
}
function render(){
  document.getElementById('main').innerHTML = renderParent();
}

"""

child_fns = r"""// ===== 家长端 =====
// ---- 当前孩子 ----
async function loadChildren(){
  const list = await api('/api/users?role=child');
  children = Array.isArray(list) ? list : [];
  let saved = null;
  try{ saved = Number(localStorage.getItem(CHILD_KEY)); }catch(e){}
  const hit = children.find(c => c.id === saved);
  uid = hit ? hit.id : (children[0] ? children[0].id : null);
}
async function reloadChildData(){
  if(parentTab==='目标') await loadGoals();
  else if(parentTab==='报告') await Promise.all([loadReport(), loadMasteryReport()]);
  else if(parentTab==='任务') await loadParentTasks();
}
// 切换期间禁用下拉框，避免快速连续切换时旧请求覆盖新数据
async function switchChild(id){
  if(childSwitching) return;
  uid = Number(id) || null;
  try{ localStorage.setItem(CHILD_KEY, String(uid)); }catch(e){}
  childSwitching = true; render();
  try{ await reloadChildData(); } finally { childSwitching = false; render(); }
}
function childSelectHtml(){
  if(!children.length) return `<span class="child-empty">暂无孩子</span>`;
  return `<label class="child-select">当前孩子
    <select onchange="switchChild(this.value)" ${childSwitching?'disabled':''}>
      ${children.map(c=>`<option value="${c.id}" ${c.id===uid?'selected':''}>${escapeAttr(c.name)}</option>`).join('')}
    </select>
  </label>`;
}
"""

init = r"""// ===== 初始化 =====
async function init(){
  await loadChildren();
  try{ await loadConfig(); }catch(e){}
  renderNav();
  await loadParentData();
  render();
}

init();
"""

# --- 家长端段的定点替换 ---
p = parent
p = rep(p, "// ===== 家长端 =====\n", "")
p = rep(p, func_block(p, "function toggleRole(){"), "")
p = rep(p, "function setParentTab(t){\n  parentTab=t;\n", "function setParentTab(t){\n  parentTab=t;\n  renderNav();\n")
p = rep(p, "async function loadGoals(){\n  goalRows", "async function loadGoals(){\n  if(!uid){ goalRows = []; return; }\n  goalRows")
p = rep(p, "async function loadReport(){\n  reportRows", "async function loadReport(){\n  if(!uid){ reportRows = []; return; }\n  reportRows")
p = rep(p, "async function loadParentTasks(){\n", "async function loadParentTasks(){\n  if(!uid){ parentTasks = []; return; }\n")
p = rep(p, "async function generateTodayTasks(){\n", "async function generateTodayTasks(){\n  if(!uid) return;\n")
p = rep(p, "async function approveAllTasks(){ await api(", "async function approveAllTasks(){ if(!uid) return; await api(")
p = rep(p, "async function showAddTask(){\n", "async function showAddTask(){\n  if(!uid) return;\n")
p = rep(p, "async function addGoal(){\n", "async function addGoal(){\n  if(!uid) return;\n")
p = rep(p, '<a href="/${t.photo_path}"', '<a href="${API}/${t.photo_path}"')
p = rep(p,
        "async function renderLearningConfigTab(){\n  // 确保 configMap 已加载\n  if(Object.keys(configMap).length === 0){ await loadConfig(); }\n",
        "function renderLearningConfigTab(){\n")
# renderParent：去掉横幅里的 Tab 条，换成选孩子；依赖孩子的 Tab 在无孩子时显示空状态
tabs_decl = re.search(r"  const tabs = \['教材'.*?\n  \)\.join\(''\);\n", p, re.S)
assert tabs_decl, "tabs declaration not found"
p = rep(p, tabs_decl.group(0), "")
p = rep(p,
        "\n  return `<div class=\"parent-banner\">",
        "\n  if(CHILD_TABS.includes(parentTab) && !uid){\n"
        "    body = `<div class=\"parent-panel\"><div class=\"bd\" style=\"text-align:center;padding:48px 0;color:#8e9691\">暂无孩子：孩子首次登录学生端后会出现在这里</div></div>`;\n"
        "  }\n"
        "  return `<div class=\"parent-banner\">")
p = rep(p,
        "    <div style=\"display:flex;gap:8px;background:#f2f4f1;border-radius:12px;padding:4px\">${tabs}</div>\n",
        "    ${childSelectHtml()}\n")
assert "toggleRole" not in p and "isParent" not in p

head = "// ===== 知学伴 · 家长端 =====\n" + between(SRC_JS, "// 后端地址：", "// ===== 图标 =====") + "\n"
app_js = "".join([head, icons, state, providers, helpers, escape_attr, "\n", browser_speak, render_entry, child_fns, p, init])
(OUT / "app.js").write_text(app_js, encoding="utf-8", newline="\n")

# ---------- index.html ----------
style_part = between(SRC_HTML, "<!DOCTYPE html>", "</style>") if "<!DOCTYPE html>" in SRC_HTML else between(SRC_HTML, SRC_HTML.split("\n", 1)[0], "</style>")
style_part = rep(style_part, "<title>知学伴 · AI 学习伙伴</title>", "<title>知学伴 · 家长端</title>")
extra_css = """
  /* 家长端：当前孩子选择 */
  .child-select{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:#5c6761;white-space:nowrap}
  .child-select select{border:1px solid var(--line3);border-radius:10px;padding:6px 10px;font-size:13px;font-family:inherit;background:#fff;color:var(--ink)}
  .child-select select:disabled{opacity:.6}
  .child-empty{font-size:13px;color:#8e9691}
"""
logo = between(SRC_HTML, '    <div class="logo">', '    <nav class="nav" id="nav"></nav>')
logo = rep(logo, '<div class="logo-sub">你的 AI 学习伙伴</div>', '<div class="logo-sub">家长端</div>')
body = f"""</style>
</head>
<body>
<div class="layout">
  <!-- 侧边栏 -->
  <aside class="sidebar">
{logo}    <nav class="nav" id="nav"></nav>
    <div class="user-row" style="margin-top:auto">
      <div class="avatar" id="userAvatar">家</div>
      <div style="flex:1">
        <div class="user-name" id="userName">家长</div>
      </div>
    </div>
  </aside>

  <!-- 主内容 -->
  <main class="main" id="main"></main>
</div>

<div class="toast" id="toast"></div>

<!-- 改 app.js 后把 v= 后面的数字 +1，避免浏览器缓存旧脚本 -->
<script src="config.js?v=1"></script>
<script src="app.js?v=1"></script>
</body>
</html>
"""
(OUT / "index.html").write_text(style_part + extra_css + body, encoding="utf-8", newline="\n")
print("generated", len(app_js.splitlines()), "lines app.js")
```

- [ ] **Step 2: 运行生成脚本**

Run: `python $env:TEMP\gen_parent_web.py`
Expected: 输出 `generated N lines app.js`（N 约 1200），无 AssertionError。若某处断言失败，说明 `frontend/` 与计划编写时不一致：对照断言信息定位后调整对应匹配字符串，不得放宽为模糊匹配。

- [ ] **Step 3: 静态检查**

Run: `node --check parent-web/app.js`
Expected: 无输出（语法正确）。

Run: `rg -n -e toggleRole -e isParent -e pdfjsLib -e mermaid -e renderPersonalized -e chatAsk parent-web/app.js`
Expected: 无匹配（rg 退出码 1 即为通过）。

Run: `rg -n "<script" parent-web/index.html`
Expected: 只有 `config.js?v=1`、`app.js?v=1` 两条（不再引入 pdf.js、mermaid）。`index.html` 的样式整段沿用 `frontend/`，其中含学生端样式与 mermaid 注释，暂不精简、属预期。

Run: `git status --short frontend/`
Expected: 无输出（frontend 未被修改）。

- [ ] **Step 4: Commit**

```bash
git add parent-web/app.js parent-web/index.html
git commit -m "feat: parent-web 家长端独立应用（从 frontend 提取家长端，选择孩子）"
```

---

### Task 3: parent-web 运行时配置、nginx 与 Dockerfile

**Files:**
- Create: `parent-web/config.js`、`parent-web/nginx.conf`、`parent-web/Dockerfile`

- [ ] **Step 1: 写 `parent-web/config.js`**

```js
// 运行时配置。本地开发保持为空：app.js 默认连 http://127.0.0.1:8010。
// docker 部署时由 parent-web/Dockerfile 覆盖为 window.KNOACT_API_BASE = ''（同源，经 nginx 反代到后端）。
// 与后端分开部署时可在这里写后端地址，例如：
// window.KNOACT_API_BASE = 'https://api.example.com';
```

- [ ] **Step 2: 写 `parent-web/nginx.conf`**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # PDF 教材上传
    client_max_body_size 200m;

    location /api/ {
        proxy_pass http://backend:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Connection "";
        # 教材拆课、AI 出题等耗时较长
        proxy_buffering off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    location /uploads/ {
        proxy_pass http://backend:8010;
        proxy_set_header Host $host;
    }

    location = /health {
        proxy_pass http://backend:8010;
    }

    location = /index.html {
        add_header Cache-Control "no-cache";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: 写 `parent-web/Dockerfile`**

```dockerfile
# KnoAct 家长端（静态页）+ nginx 反代后端
# 构建上下文为 parent-web/：docker build -t knoact-parent-web ./parent-web
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html app.js /usr/share/nginx/html/
# 同源部署：API 地址置空，请求经 nginx 的 /api、/uploads 反代到后端
RUN printf "window.KNOACT_API_BASE = '';\n" > /usr/share/nginx/html/config.js

EXPOSE 80
```

- [ ] **Step 4: Commit**

```bash
git add parent-web/config.js parent-web/nginx.conf parent-web/Dockerfile
git commit -m "feat: parent-web nginx 反代与 Dockerfile"
```

---

### Task 4: docker-compose、.env.example 与 README

**Files:**
- Modify: `docker-compose.yml`、`.env.example`、`README.md`

- [ ] **Step 1: docker-compose 新增 parent-web 服务**

在 `docker-compose.yml` 的 `frontend:` 服务块之后（`render:` 之前）插入：

```yaml
  parent-web:
    build: ./parent-web
    image: knoact-parent-web:latest
    restart: unless-stopped
    ports:
      - "${KNOACT_PARENT_PORT:-8081}:80"
    depends_on:
      backend:
        condition: service_healthy
```

并把文件头部注释里的服务说明改为：

```yaml
# 基础服务（默认启动）：
#   backend     FastAPI 后端，SQLite 库与上传文件挂卷持久化
#   frontend    旧版学生端 Web（冻结，Flutter 学生端完成后移除）
#   parent-web  家长端
#   两个前端均由 nginx 托管静态页，并把 /api、/uploads 反代到 backend（同源，无跨域）
```

头部「访问」一行改为：

```yaml
# 访问：学生端 http://<服务器IP>:${KNOACT_HTTP_PORT:-8080}，家长端 http://<服务器IP>:${KNOACT_PARENT_PORT:-8081}
```

- [ ] **Step 2: `.env.example` 增加家长端端口**

在 `KNOACT_HTTP_PORT=8080` 之后加：

```bash

# 家长端对外端口：http://<服务器IP>:8081
KNOACT_PARENT_PORT=8081
```

并把 `KNOACT_HTTP_PORT` 上方注释改为 `# 学生端（旧版 Web）对外端口：http://<服务器IP>:8080`。

- [ ] **Step 3: README 更新**

- 「目录结构」加一行：`parent-web/       家长端（原生 JS 静态页，独立部署）`，并把 `frontend/` 一行改为 `frontend/         旧版学生端 Web（冻结，Flutter 学生端完成后移除）`。
- 「启动」一节访问地址改为：学生端 `http://<服务器IP>:8080`，家长端 `http://<服务器IP>:8081`（端口分别由 `KNOACT_HTTP_PORT`、`KNOACT_PARENT_PORT` 决定）。
- 「服务与数据」表格加一行：`| parent-web | 家长端，nginx 托管并反代 /api、/uploads | 对外 8081 |`，`frontend` 一行说明改为「旧版学生端 Web」。
- 「本地开发」新增「家长端」小节：

  ```bash
  python -m http.server 8767 --directory parent-web
  ```

  访问 `http://127.0.0.1:8767`，默认连接 `http://127.0.0.1:8010`；后端在别处时在 `parent-web/config.js` 设置 `window.KNOACT_API_BASE`。
- 「功能 → 家长端」第一句前加：家长端为独立应用，顶部可切换当前孩子。
- 「配置」表格加一行：`| KNOACT_PARENT_PORT | 8081 | docker 部署的家长端对外端口 |`，`KNOACT_HTTP_PORT` 一行说明改为「docker 部署的学生端（旧版 Web）对外端口」。
- 文中「切到家长端 →「设置」」「到家长端「设置」」等说法统一改为「打开家长端 →「设置」」。

- [ ] **Step 4: 校验 YAML**

Run（仓库根目录）:

```bash
python -c "import yaml;d=yaml.safe_load(open('docker-compose.yml',encoding='utf-8'));s=d['services']['parent-web'];print(list(d['services']), s['ports'], s['depends_on'])"
```

Expected: 服务列表含 `parent-web`，端口 `['${KNOACT_PARENT_PORT:-8081}:80']`，依赖 `backend` healthy。

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml .env.example README.md
git commit -m "feat: docker-compose 新增 parent-web 家长端服务，README 更新"
```

---

### Task 5: 浏览器验收

**前置：** 本地后端需加载 Task 1 的新接口——若 8010 端口的后端进程不是 `--reload` 启动，先在 `backend/` 下重启：`python -m uvicorn app.main:app --port 8010`。

- [ ] **Step 1: 启动家长端静态服务**

Run: `python -m http.server 8767 --directory parent-web`（后台运行）

- [ ] **Step 2: 逐项验收（浏览器打开 `http://127.0.0.1:8767`）**

1. 侧栏显示 9 个 Tab，无「家长端/孩子端」切换按钮、无「AI 学习建议」卡片；页面不请求 `vendor/pdfjs`、mermaid。
2. 横幅右侧显示「当前孩子」下拉框，选项来自 `/api/users?role=child`。
3. 9 个 Tab 逐个点击：页面渲染正常，控制台无报错；「学习配置」显示配置表单，不出现 `[object Promise]`。
4. 在「目标」「报告」「任务」Tab 切换孩子：数据随之变化；切换过程中下拉框为禁用状态。
5. 刷新页面：仍是上次选中的孩子（`localStorage` 键 `knoact_parent_child_id`）。
6. 在 DevTools 执行 `localStorage.setItem('knoact_parent_child_id','999999')` 后刷新：回落为第一个孩子。
7. 任务 Tab 若有带照片的任务，「查看照片」链接指向 `http://127.0.0.1:8010/uploads/...`。

- [ ] **Step 3: 同源模式验证**

用同源代理模拟 nginx（本机无 Docker 时）：保存为 `$env:TEMP\parent_proxy.py` 并后台运行 `python $env:TEMP\parent_proxy.py`，打开 `http://127.0.0.1:8091`，重复 Step 2 的第 2、3 项，确认 `API` 为空串时数据正常加载：

```python
import http.server
import urllib.error
import urllib.request

ROOT = r"d:\workspace\github\KnoAct\parent-web"
BACKEND = "http://127.0.0.1:8010"
PROXY = ("/api/", "/uploads/", "/health")


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def _proxy(self):
        n = int(self.headers.get("Content-Length") or 0)
        req = urllib.request.Request(BACKEND + self.path, data=self.rfile.read(n) if n else None, method=self.command,
                                     headers={k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection")})
        try:
            resp = urllib.request.urlopen(req, timeout=600)
        except urllib.error.HTTPError as e:
            resp = e
        data = resp.read()
        self.send_response(resp.status)
        for k, v in resp.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith(PROXY):
            return self._proxy()
        if self.path.split("?")[0] == "/config.js":
            body = b"window.KNOACT_API_BASE = '';\n"
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    do_POST = do_PUT = do_DELETE = _proxy


http.server.ThreadingHTTPServer(("127.0.0.1", 8091), H).serve_forever()
```

- [ ] **Step 4: 旧版学生端回归**

Run: `git diff --stat 6d16c97 -- frontend/`（`6d16c97` 为 spec 提交，作为固定基准）
Expected: 无输出（frontend 未改动）。打开旧版学生端 `http://127.0.0.1:8766`（`python -m http.server 8766 --directory frontend`），学习首页正常加载。

- [ ] **Step 5: 全量后端测试**

Run（`backend/` 下）: `python -m pytest -q`
Expected: 全部通过。

- [ ] **Step 6: 停止临时服务**

结束 Step 1、Step 3 启动的静态服务与代理进程。
