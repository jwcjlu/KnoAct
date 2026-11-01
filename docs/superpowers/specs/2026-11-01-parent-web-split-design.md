# 家长端拆分与独立部署（子项目 1）设计

日期：2026-11-01

## 背景与目标

当前前端是单页应用 `frontend/`（`app.js` 约 3800 行、`index.html` 内联约 860 行样式），靠侧栏「家长端 / 孩子端」按钮在同一页面切换 `isParent`。家长端查询孩子数据用的 `uid` 来自启动时按名字登录的默认孩子（`POST /api/auth/login {name:'金同学'}`）。

学生端未来要支持 Web、安卓、iOS，已确定用 **Flutter** 重写；家长端保持原生 JS。整体拆为 5 个子项目，各自走「设计 → 计划 → 实现」：

| 序号 | 子项目 | 内容 |
| --- | --- | --- |
| 1 | **家长端拆分与独立部署（本文）** | 家长端独立为 `parent-web/`；后端新增孩子列表接口；docker-compose 分开部署 |
| 2 | Flutter 学生端骨架 + 首页、学习中心 | 工程结构、API 层、配置、选孩子登录、学习首页、每日任务 |
| 3 | 练习类页面 | 听写（拍照批改）、数学练习、知识点复习、错题本 |
| 4 | 个性化学习 | PDF 划词阅读、标注、AI 流式对话、多轮作业 |
| 5 | App 打包发布 | 安卓 APK/AAB、iOS（需 macOS + Xcode） |

本文只覆盖子项目 1。

## 范围

**包含**

1. 新建 `parent-web/`：只含家长端功能的原生 JS 静态应用，可独立部署。
2. 后端新增 `GET /api/users`（新路由文件 `routers/users.py`），家长端据此选择孩子。
3. docker-compose 新增 `parent-web` 服务，与现有前端分开端口部署；README 同步更新。

**不包含**

- `frontend/` 不做任何修改：冻结为「旧版学生 Web」，保留到 Flutter 学生端完成后删除（届时其中的家长端功能也随之移除）。
- 账号密码、权限控制：家长端仍无需登录，与现状一致。
- Flutter 学生端（子项目 2 起）。

## 设计

### 1. 目录结构

```
parent-web/
  index.html      页面骨架 + 家长端所需样式
  app.js          家长端逻辑
  config.js       运行时配置（API 地址），与 frontend/config.js 约定一致
  nginx.conf      静态托管 + /api、/uploads 同源反代
  Dockerfile      nginx 镜像
frontend/         不改动（旧版学生 Web，冻结）
```

### 2. 家长端代码（`parent-web/app.js`）

从 `frontend/app.js` 提取：

- **家长端全部页面**：教材、知识点、题目审核台、目标、报告、任务、规则、学习配置、设置（`renderParent`、`setParentTab`、`render*Tab` 及其加载、提交函数，即 `// ===== 家长端 =====` 段）。
- **它依赖的公共代码**：`API` 常量（读 `window.KNOACT_API_BASE`）、`api()`、`apiForm()`、`sleep`（教材提取轮询 `pollExtract` 使用）、`icon()` 及图标表、`toast()`、`escapeAttr()`、`loadConfig()` 与 `configMap`、`aiProviders` / `ttsProviders` 等配置状态、`loadMasteryReport()` 与 `masteryReport`（报告 Tab 使用），以及「通用状态」段里家长端用到的缓存变量；`index.html` 保留 `#toast` 元素。
- **朗读**：只带 `browserSpeak()` 一个函数——「设置 → 试听语音」的 `testVoice()` 在未配置真实 TTS 时用它兜底；其余朗读代码不带。
- **不带**：学生端页面、pdf.js、Mermaid、沉浸阅读器、对话、听写等代码，`index.html` 不再引入 pdf.js 和 Mermaid。
- 沿用 `app.js?v=` 版本号防缓存约定。
- 任务 Tab「查看照片」链接由 `/${photo_path}` 改为 `${API}/${photo_path}`，本地开发（无 nginx 反代）时也能打开。

行为调整：

- 去掉「家长端 / 孩子端」切换按钮与 `isParent`、`toggleRole`：页面始终渲染家长端，`render()` 直接渲染 `renderParent()`。
- 侧栏导航改为家长端的 9 个 Tab（复用现有 `nav-item` 样式，点击调用 `setParentTab`），家长端横幅里原有的 Tab 条移除，横幅只保留标题与「当前孩子」下拉框；侧栏底部用户卡片显示「家长」，去掉年级与切换按钮；学生端的「AI 学习建议」卡片移除。
- 启动时不再调用 `/api/auth/login`。
- **修复「学习配置」Tab**：现有 `renderLearningConfigTab()` 是 `async`，被同步的 `renderParent()` 直接拼接，会渲染出 `[object Promise]`。`setParentTab('学习配置')` 已在渲染前 `loadConfig()`，因此把它改为同步函数（去掉函数内的 `await loadConfig()`）。

### 3. 选择孩子

- 后端 `GET /api/users?role=child` 返回 `[{"id": 4, "name": "金同学", "role": "child"}, ...]`，按 `id` 升序；`role` 参数可选，不传时返回全部用户。
- 家长端顶部（家长端横幅内）放「当前孩子」下拉框：
  - 选项来自 `/api/users?role=child`。
  - 默认选中浏览器 `localStorage`（键 `knoact_parent_child_id`）里保存的孩子；保存的 id 不在列表中，或没有保存时，选第一个孩子。
  - 切换后写入 `localStorage`，更新全局 `uid`，重新加载当前 Tab 的数据。
  - 切换期间禁用下拉框，当前 Tab 数据加载完成后再启用，避免快速连续切换时旧请求覆盖新数据。
- 用到 `uid` 的只有目标、报告、任务 3 个 Tab（`loadGoals`、`addGoal`、`loadReport`、`loadMasteryReport`、`loadParentTasks`、`generateTodayTasks`、`approveAllTasks`、`showAddTask`），都读全局 `uid`，即选中孩子的 id。
- **初始化顺序**：先请求孩子列表并确定 `uid`，再加载并渲染默认 Tab（教材）；`uid` 的初值改为 `null`，避免在确定孩子前用错误的 id 查询。
- **没有孩子时**：下拉框显示「暂无孩子」；目标、报告、任务 3 个 Tab 显示「暂无孩子」空状态，上述加载与操作函数在 `uid` 为空时直接返回，不发请求（避免 `user_id=null` 被后端判为 422）。教材、知识点、题目审核台、规则、学习配置、设置不依赖孩子，照常可用。

### 4. 后端接口

新建 `backend/app/routers/users.py`（`APIRouter(prefix="/api/users")`），并在 `backend/app/main.py` 中 `include_router`：

```
GET /api/users?role=child
→ 200 [{"id": int, "name": str, "role": str}]
```

只读查询，不改动现有接口（`auth.py` 的路由前缀固定为 `/api/auth`，不在其中添加）。

### 5. 部署

- `parent-web/Dockerfile`：`nginx:1.27-alpine`，复制静态文件，把 `config.js` 覆盖为 `window.KNOACT_API_BASE = ''`。
- `parent-web/nginx.conf`：与 `frontend/nginx.conf` 相同的 `/api`、`/uploads`、`/health` 反代规则与上传大小限制；去掉 `.mjs` 规则（家长端不用 pdf.js）。
- `docker-compose.yml` 新增服务：

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

- 现有 `frontend` 服务不变（仍是 `KNOACT_HTTP_PORT`，默认 8080），作为旧版学生 Web。
- `.env.example` 增加 `KNOACT_PARENT_PORT=8081`；README 更新服务表、访问地址与本地开发方式（家长端本地：`python -m http.server 8767 --directory parent-web`）。

## 测试与验收

- **后端**：`backend/tests/` 新增孩子列表接口测试，覆盖按 `role=child` 过滤、不传 `role` 返回全部、按 id 升序、无数据时返回空列表；全量测试通过。
- **家长端（浏览器）**：
  - 9 个 Tab 逐个打开，页面渲染正常、数据加载成功、控制台无报错；
  - 「学习配置」Tab 正常显示配置表单（不再出现 `[object Promise]`）；
  - 切换孩子后，目标、报告、任务的数据随之变化，刷新页面后仍是上次选中的孩子；
  - 页面中不出现「孩子端」切换按钮，不加载 pdf.js、Mermaid。
- **旧版学生 Web**：`frontend/` 文件无改动，原有学生页面照常可用。
- **部署**：docker-compose YAML 解析通过；本机无 Docker 时，用同源代理模拟 nginx 验证家长端在 `KNOACT_API_BASE = ''` 下可用。
