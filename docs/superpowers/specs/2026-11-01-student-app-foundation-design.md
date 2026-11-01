# Flutter 学生端骨架 + 学习首页、学习中心（子项目 2）设计

日期：2026-11-01

## 背景

学生端将用 Flutter 重写，支持 Web、安卓、iOS（整体拆分见 `2026-11-01-parent-web-split-design.md`）。子项目 1 已把家长端拆成 `parent-web/`；旧版 `frontend/` 冻结，作为过渡的学生 Web，直到 Flutter 学生端功能对齐后删除。

本子项目搭建 Flutter 学生端工程，并实现登录、学习首页、学习中心。后续子项目：3（听写、数学练习、知识点复习、错题本）、4（个性化学习）、5（App 打包发布，含 iOS）。

## 范围

**包含**

1. 本机 Flutter 开发环境：Flutter SDK（stable）+ JDK 17 + Android 命令行工具（SDK、build-tools、platform-tools、一个模拟器镜像），`flutter doctor` 中 Flutter、Android toolchain、Chrome 三项通过。安装前检查 Windows 硬件加速（WHPX / Hyper-V）是否可用；不可用时安卓验收改为：能成功 `flutter build apk --debug`，并记录「需真机或可加速环境验证运行」。
2. 新建 Flutter 工程 `student-app/`，平台 Web + Android。
3. 登录（输入名字）、自适应导航外壳、学习首页、学习中心、「我的」页。
4. Web 部署：多阶段 Dockerfile + nginx，docker-compose 新增 `student-app` 服务（端口 8082）。
5. 安卓：本机构建 debug APK 并在模拟器上运行验证。

**不包含**

- 听写、数学练习、知识点复习、错题本、个性化学习页面（子项目 3、4）。
- 本周学习统计（后端 `week_stats` 为 `null`，保持占位）。
- iOS、应用商店发布、签名（子项目 5）。
- 账号密码、鉴权。
- 后端改动（本子项目只消费现有接口）。

## 技术选型

| 用途 | 选择 |
| --- | --- |
| 状态管理 | flutter_riverpod |
| 路由 | go_router（`StatefulShellRoute` 承载底部导航 / 侧栏） |
| 网络 | dio |
| 本地存储 | shared_preferences（记住登录的孩子） |
| 音频播放 | audioplayers（播放后端 TTS 返回的 mp3） |
| 设备朗读 | flutter_tts（后端 TTS 为 fake 时兜底，对应旧版的浏览器 speechSynthesis） |

Dart/Flutter 取当前 stable；依赖版本在实现时由 `flutter pub add` 解析并锁定在 `pubspec.lock`。

## 工程结构

```
student-app/
  lib/
    main.dart                 入口：ProviderScope + MaterialApp.router
    core/
      config.dart             API_BASE（--dart-define），默认 http://127.0.0.1:8010
      api_client.dart         dio 封装：baseUrl、超时、JSON 解析、错误转换为 ApiException
      theme.dart              配色与字体（沿用旧版学生端：主色 #3158e8 等）
      router.dart             go_router：登录守卫 + 外壳路由
    features/
      auth/                   登录页、当前孩子状态（id、name）持久化
      shell/                  自适应导航外壳（手机底部导航，宽屏 NavigationRail）
      home/                   学习首页：数据层（repository + models）+ 页面与组件
      center/                 学习中心：听力、阅读
      profile/                「我的」：显示名字、积分，退出登录
  test/                       单元测试与组件测试
  web/、android/              flutter create 生成
  Dockerfile、nginx.conf      Web 部署
```

每个 feature 内分 `data/`（接口调用与模型）和 `ui/`（页面与组件），页面只依赖 provider，不直接调用 dio。

## 功能设计

### 1. 登录与身份

- 未登录时进入登录页：输入名字 → `POST /api/auth/login {name}` → 返回 `{id, name, role}`；保存 `id`、`name` 到 shared_preferences。
- 后端找不到名字会自动创建孩子账号：登录页在输入框下方提示「首次使用会自动创建账号，请确认名字无误」。
- 返回的 `role` 不是 `child`（例如输入了家长名字）时不保存，提示「这个名字不是孩子账号，请输入孩子的名字」。
- 已登录时直接进首页；「我的」页「退出登录」清除本地保存并回到登录页。
- 名字为空时不能提交；接口失败时提示「登录失败，请检查网络或后端服务」。

### 2. 自适应导航外壳

- 三个入口：首页、学习中心、我的。
- 宽度 < 840dp：底部 `NavigationBar`；≥ 840dp：左侧 `NavigationRail`（带应用名），内容区限宽居中。
- 每个入口保留各自的页面状态（`StatefulShellRoute.indexedStack`）。

### 3. 学习首页

数据（`user_id` 为当前孩子 id，`date` 为本地当天 `YYYY-MM-DD`）：

| 接口 | 用途 |
| --- | --- |
| `GET /api/home/snapshot?user_id=&subject=` | `subject` 取首页当前选中学科（默认语文）；用其 `user_name`、`lesson_progress{current,total,mastered,current_lesson_id}`（忽略其中的 `points`） |
| `GET /api/tasks?user_id=&date=&role=child` | 当天全部学科任务 `[{id, subject, task_type, title, detail, points, submit_status, ...}]` |
| `GET /api/points/balance?user_id=` | 积分 `{balance}`——首页、「我的」显示的积分统一以此为准 |
| `POST /api/points/redeem {user_id, device, minutes}` | 兑换 `{success, reason?}` |
| `POST /api/tasks/{id}/submit` | 阅读、听力类任务完成后提交 |

页面区块（与旧版一致，按屏宽单列或多列排布）：

- **问候区**：日期、按时段问候（夜深了 / 早上好 / 下午好 / 晚上好）+ 名字、积分。
- **今日计划**：「第 N 课重点学习与旧课复习」+ 说明，按钮滚动到任务区；每日古诗（竹、兰、梅、菊按「自 1970-01-01 起的天数 % 4」轮换，文本与旧版 `POEMS` 相同）。
- **今日进度**：全部学科已完成 / 总数与百分比（`submit_status == 'approved'` 视为完成），语文、英语、数学各自进度条；课程进度「已学到第 N 课 · mastered / total 课」，无教材时提示「请在家长端导入教材后开始学习」。
- **今日任务**：学科切换（语文 / 英语 / 数学，角标为该学科待完成数，全完成显示 ✓）；当前学科任务分「待完成」「已完成」两组；任务卡片显示类型标签、标题、说明、积分、预计时长（各类型标签与时长沿用旧版 `taskTypeMeta`）。
- **任务按钮**（按 `submit_status` 与 `task_type`）：
  - `approved` → 「已完成」（不可点）。
  - `submitted` → 「等待家长确认」（不可点）。
  - 未开始的 `reading` / `listening` → 「开始练习」，跳转学习中心对应 Tab；该 Tab 内全部题目作答后提交 `POST /api/tasks/{id}/submit`，提示「已提交，等待家长确认」，返回首页时刷新任务。
  - 未开始的其他类型（`dictation`、`math`、`knowledge`、`review`、`custom`）→ 「开始练习」点击后提示「该练习即将在 App 上线，可先在网页版完成」。
- **积分兑换**：平板 30 分钟（300 积分）、手机 20 分钟（200 积分）；成功提示「已兑换…，等待家长确认」并刷新积分，失败提示「积分还不够，再完成几个任务吧」。
- **本周学习**：占位卡片「暂无记录」。
- 切换学科时重新拉取该学科快照（「第 N 课」、说明文案「根据今日{学科}进度…」、课程进度随之变化）与任务分组。
- 下拉刷新、以及每次切回首页 Tab 时，重新加载全部首页数据（学习中心拉听力材料可能新建当天听力任务，回首页需看到）。

### 4. 学习中心

| 接口 | 用途 |
| --- | --- |
| `GET /api/listening/material?user_id=` | 听力 `{text, questions:[{question, answer}]}` |
| `GET /api/reading/material?lesson_id=` | 阅读 `{text, questions:[...]}`；`lesson_id` 取**语文**快照（`/api/home/snapshot?subject=语文`）的 `lesson_progress.current_lesson_id`；缺失时不请求，显示阅读空状态 |
| `GET /api/tts/synthesize?text=` | 返回 `audio/mpeg` 字节；或 JSON `{use_browser_tts: true}`（fake） |
| `POST /api/review/submit {user_id, question, your_answer, correct_answer, source_type}` | 答错收入错题本 |

- 两个 Tab：听力理解、阅读理解。
- **听力**：「播放对话」按钮——把对话文本中的换行替换为空格后请求 TTS（dio 用 `ResponseType.bytes`，按响应 `content-type` 判断）：是 `audio/*` 则用 audioplayers 播放；是 JSON（`use_browser_tts`）、非 2xx（后端出错返回 502）或网络失败，则用 flutter_tts 朗读（文本含英文字母用 en-US，否则 zh-CN；语速对应旧版 0.9）。不显示对话文本。
- **阅读**：显示课文全文。
- **答题**：每题一个输入框 +「提交」；提交后显示答案并标记对错（去首尾空白后与 `answer` 全等，与旧版一致）；答错调用 `/api/review/submit`（`source_type` 为 `listening` / `reading`）并提示「答错了，已收录进错题本」，答对提示「回答正确！」。
- 材料为空时显示空状态：听力「暂无听力材料，AI 将根据学习进度生成对话」，阅读「暂无阅读材料，请在家长端导入教材」。
- **生命周期**：每次切到学习中心 Tab、切换听力/阅读 Tab、或从首页任务跳入时，都重新拉取对应材料并清空该 Tab 的作答状态。
- **任务自动提交**：从首页点阅读/听力任务的「开始练习」时，带任务 id 与目标 Tab 跳入学习中心（选中该 Tab）。仅当**该任务对应的 Tab** 的题目数 > 0 且全部题目已提交时，才调用 `POST /api/tasks/{id}/submit` 并提示「已提交，等待家长确认」；之后清除待提交的任务 id。材料为空（题目数为 0）时不提交，并提示「暂无材料，暂时无法完成该任务」。待提交的任务 id 在以下情况清除（之后再完成题目也不会提交该任务）：提交成功、切到另一个听力/阅读 Tab、离开学习中心 Tab。提交请求进行中用「提交中」标记防重复，不重复发请求、不重复提示。自动提交条件实现为纯函数（输入：任务目标 Tab、当前 Tab、题目数、已作答数、是否提交中）。

### 5. 「我的」

- 显示名字、积分；「退出登录」。

## 错误处理

- dio 连接超时 10 秒、接收超时 120 秒（听力、阅读材料与 TTS 可能当场调用大模型生成）。
- `ApiException` 统一承载网络错误、非 2xx、非预期响应体；页面加载失败显示错误卡片 +「重试」按钮，不白屏。
- 操作类请求（兑换、提交、答题）失败用 SnackBar 提示，不改变本地状态。

## 配置与部署

- **API 地址**：`--dart-define=API_BASE=...`；未定义时默认 `http://127.0.0.1:8010`（本地开发）。Web 镜像构建时传空串：`config.dart` 用 `bool.hasEnvironment('API_BASE')` 区分「未定义」与「空串」，为空串时在 Web 上取 `Uri.base.origin` 作为 baseUrl（同源，经 nginx 反代）。
- **CORS**：后端已 `allow_origins=["*"]`，本地 `flutter run -d chrome` 直连 8010 可用。
- **Web 镜像** `student-app/Dockerfile`：第一阶段用 `ghcr.io/cirruslabs/flutter:stable` 执行 `flutter build web --release --dart-define=API_BASE=`；第二阶段 `nginx:1.27-alpine` 托管 `build/web`，`nginx.conf` 与 `parent-web/nginx.conf` 相同的 `/api/`、`/uploads/`、`/health` 反代规则；另对 `index.html`、`flutter_bootstrap.js`、`flutter_service_worker.js`、`main.dart.js`、`version.json` 设 `Cache-Control: no-cache`，避免发版后用旧版本。`student-app/.dockerignore` 排除 `build/`、`.dart_tool/`、`android/`。
- **docker-compose**：新增 `student-app` 服务，端口 `${KNOACT_STUDENT_PORT:-8082}:80`，依赖 backend 健康；同步更新文件头部的服务说明与「访问」端口说明、`.env.example`、README。
- **安卓**：`flutter build apk --debug --dart-define=API_BASE=http://10.0.2.2:8010`（模拟器访问宿主机）；`AndroidManifest.xml` 加 `INTERNET` 权限，并允许明文 HTTP（`usesCleartextTraffic`），以便连接本地后端。

## 测试与验收

- **单元测试**：模型解析（快照、任务、材料）、任务分组与进度计算、任务按钮状态映射、古诗轮换、问候语、自动提交条件（目标 Tab 与当前 Tab 不一致、题目数为 0、部分作答、全部作答、提交中）。
- **组件测试**（mock repository）：登录页提交与校验、首页按状态渲染任务分组与按钮、学习中心答题对错与错题提交调用。
- **静态检查**：`flutter analyze` 无错误。
- **Web 验收**：`flutter run -d chrome`（或 `flutter build web` 后本地托管）连接本地后端，完成登录 → 首页数据与旧版一致 → 学科切换 → 积分兑换 → 学习中心听力播放与答题 → 退出登录；分别在窄屏（手机宽度）与宽屏下检查导航形态。
- **安卓验收**：模拟器安装 debug APK，完成登录与首页、学习中心浏览；模拟器不可用时按「范围 1」的兜底执行。
- **部署**：docker-compose YAML 解析通过；本机无 Docker 时以 `flutter build web --dart-define=API_BASE=` 产物 + 同源代理验证。
