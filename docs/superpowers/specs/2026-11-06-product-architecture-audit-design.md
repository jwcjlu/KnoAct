# KnoAct 现状功能与架构审计（2026-11）

> 日期：2026-11-06  
> 状态：已与用户确认审计框架（全面 D：产品 + 安全 + 架构）  
> 关联：`2026-11-05-account-system-design.md`（账号体系，部分落地）  
> 推进方式：**方案 1 — 止血 → 对齐 → 瘦身**（P0 / P1 / P2）

本文档是**问题清单 + 目标态 + 优先级 backlog**，不是新功能 PRD。实施时拆成独立 plan（如 `auth-p1-rollout`、`retire-frontend-web`）。

---

## 第 1 节：优先级定义

| 级别 | 含义 | 完成判定示例 |
|------|------|----------------|
| **P0** | 安全/越权/生产不可接受 | 任意 child 不能读他人 `user_id` 数据 |
| **P1** | 用户可感知错乱、双轨规则 | 仅一条「孩子建号」主路径；学生 Web 无旧登录 |
| **P2** | 技术债、维护成本 | 删除 `frontend/` 或只留跳转页；`User.name` 只读别名 |
| **P3** | 可选增强 | AI 全收编；屏幕时间 iOS |

**问题 ID**：`SEC-*` 安全，`ID-*` 身份/家庭，`CLI-*` 客户端/交付，`AI-*` AI 架构，`DATA-*` 数据/占位，`OPS-*` 运维，`PRD-*` 产品规则。

---

## 第 2 节：产品功能矩阵

图例：**完整** / **部分** / **占位** / **废弃** / **无**

| 能力 | student-app | parent-web | admin-web | frontend (旧) | 后端 | 主要问题 ID |
|------|-------------|------------|-----------|-----------------|------|-------------|
| 账号注册/登录 JWT | 完整 | 完整 | 完整 | **废弃**（姓名登录） | 完整 | CLI-01, CLI-02, ID-01 |
| 绑定家长 / 受限模式 | 完整 | 完整（邀请+审批） | 代建可绑 | 无 | 完整 | ID-01, PRD-01 |
| 孩子管理（编辑/归档/教材） | 无 | 完整 | 全局 | 无 | 完整 | PRD-01 |
| 家长代建孩子 POST /children | 无 | 完整 | 完整 | 无 | 需 parent token | ID-01 |
| 首页任务/积分/进度 | 完整 | 无 | 无 | 完整 | 部分鉴权 | SEC-01, DATA-01 |
| 学习中心（听/读/听写） | 完整 | 无 | 无 | 完整 | 部分鉴权 | SEC-01 |
| 错题本/掌握度/数学/知识点 | 完整 | 只读报告 | 无 | 部分 | **无鉴权** | SEC-01 |
| 阅读器 + 划词 | 完整 | 无 | 无 | 完整 | annotations 弱 | SEC-01, DATA-02 |
| 边读边问 /ask 流式 | 完整 | 无 | 无 | 完整 | agent-native | AI-01 |
| PDF 上传/拆课/审核 | 无 | 完整 | 无 | 家长模式 | 无鉴权* | SEC-02, PRD-02 |
| 目标/任务审核/规则 | 无 | 完整 | 无 | 家长模式 | 无鉴权* | SEC-02 |
| 模型/语音配置 | 无 | 完整 | 无 | **重复一套** | config 写已保护 | CLI-02, PRD-03 |
| 屏幕时间 | Android 部分 | 完整 | 无 | 无 | 无鉴权* | SEC-02, PRD-04 |
| 学年桶切换 | 间接（错题等） | 完整 | 无 | 无 | 完整 | PRD-05 |
| 运营用户 CRUD | 无 | 无 | 完整 | 无 | admin 门禁 | — |

\* 多数 router 仍接受任意 `user_id`，未校验与 Bearer 身份关系（见第 3 节）。

### 2.1 产品规则不合理（PRD）

| ID | 现状 | 目标态 | 优先级 |
|----|------|--------|--------|
| **PRD-01** | 孩子账号：**自助注册**、家长 **POST /children**、Admin 代建、legacy 姓名登录 并存 | **主路径**：孩子 App 注册 → 绑定家长；**辅路径**：Admin/家长邀请码；**移除**家长 prompt 代建与 legacy 自动建号 | P1 |
| **PRD-02** | 家长端能力集中在单页 JS，与「孩子端」能力边界靠 convention | 文档化「家长只做管理、孩子只做学习」；家长端不提供学习答题 UI | P2 |
| **PRD-03** | 模型密钥配置在 parent-web + 旧 frontend 两套 UI | 仅 parent-web（或未来统一设置中心）；frontend 下线后删除重复 | P1 |
| **PRD-04** | 屏幕时间仅 Android 有效，Web 无 | 产品声明「仅 Android 孩子端」或 Web 隐藏入口 | P2 |
| **PRD-05** | 学年桶 + 年级 + 家长切换，认知成本高 | 保留模型；UI 默认只展示 active 桶，历史入口收进「往年记录」 | P3 |

---

## 第 3 节：安全与 API 鉴权

### 3.1 已保护（截至审计日）

| 路由/区域 | 机制 |
|-----------|------|
| `/api/auth/me`, profile, credentials | `get_current_user` |
| `/api/family/*` | Bearer + 角色检查 |
| `/api/admin/*` | `require_role("admin")` |
| `POST /api/config` | `require_role("parent","admin")` |
| `POST /api/children` | `require_role("parent")` + parent_id 匹配 |
| `/api/home/snapshot` | `require_learning_user` + `resolve_target_user_id` |
| `/api/tasks` 列表、`submit` | `require_learning_user`（**未** resolve user_id） |
| `/api/learning` 部分（listening_material, dictation/words） | `require_learning_user` |

### 3.2 未保护或不足（P0 backlog）

以下 router **仍主要依赖 query/body `user_id`**，无 Bearer 或无可归属校验：

| Router | 典型风险 | 问题 ID |
|--------|----------|---------|
| `points`, `mistakes`, `mastery`, `goals` | 读/写他人积分、错题、掌握度 | SEC-01 |
| `quiz`, `learning`（其余端点）, `math` | 代答题、代提交 | SEC-01 |
| `progress`, `annotations`, `notes`（除 ask 编排） | 越权读写笔记/划词 | SEC-01 |
| `pdf`, `questions`, `knowledge` | 家长资源被任意 user 操作 | SEC-02 |
| `tasks` approve/confirm 等 | 家长审核被绕过 | SEC-01 |
| `screen_time`, `buckets` | 篡改他人屏幕数据/桶 | SEC-01 |
| `tts`, `render` | 滥用算力（中低危） | SEC-03 |

**SEC-01 目标态（P0）**：  
- 引入统一依赖 `resolve_target_user_id`（或等价）到所有带 `user_id` 的端点。  
- child：仅 self；parent：self + `parent_id` 下孩子；admin：全部。  
- 每个 router 至少 1 个越权 pytest。

**SEC-02（P0）**：pdf / 题目审核 / 上传 → 至少 `require_role("parent","admin")` + 操作对象归属。

**SEC-03（P1）**：tts/render 需登录 + 限流。

### 3.3 账号遗留

| ID | 现状 | 目标态 | 优先级 |
|----|------|--------|--------|
| **ID-01** | 见 PRD-01 | 单主路径 + 文档 | P1 |
| **ID-02** | `User.name` 与 login_name/display_name 双写 | API 对外仅 login_name + display_name；name 只读同步 | P2 |
| **ID-03** | `KNOACT_LEGACY_NAME_LOGIN`、name-only 兼容 | 默认关；下一大版本删除 | P1 |
| **ID-04** | 默认 admin/ChangeMe123 | 部署强制改密；启动警告 | P0 |

---

## 第 4 节：多端与交付

| ID | 问题 | 目标态 | 优先级 |
|----|------|--------|--------|
| **CLI-01** | `flutter run` 旧进程 vs `build/web`，用户看到无密码旧 UI | 文档 + `serve-web.ps1` + launch「student-app-web-build」；登录页展示 **构建标识**（如 git sha / 日期） | P1 |
| **CLI-02** | `frontend/` 8766 仍全功能 + 旧 auth + 对话 | **阶段 1**：index 跳转到 Flutter URL；**阶段 2**：删代码或仅保留静态说明 | P1 |
| **CLI-03** | student-app Web 与 Android API_BASE 不一致 | 文档 + docker 同源；Android `--dart-define` 检查清单 | P2 |
| **CLI-04** | parent-web / admin-web 无 token 时静默失败 | 统一 api() 处理 401 → 登录页（parent 已部分做） | P2 |

**端口约定（写入 README/AGENTS）**：

| 端口 | 用途 |
|------|------|
| 8010 | API |
| 8082 / 8898 | Flutter Web（应用 build，非旧 debug） |
| 8766 | **待废弃** frontend |
| 8767 | parent-web |
| 8768 | admin-web |

---

## 第 5 节：AI 与数据

| ID | 问题 | 目标态 | 优先级 |
|----|------|--------|--------|
| **AI-01** | 仅 `/api/ask` agent-native；quiz/learning/拆课等 prompt-in-code | 维持双轨但 **文档诚实**；P2 按 tool-adoption spec 收编 | P2 |
| **AI-02** | Flutter ask 与 frontend ask 行为需对齐 citations/流式 | 以 student-app 为准；frontend 下线后无此问题 | P1 |
| **DATA-01** | `home.snapshot` `week_stats: null` TODO | 要么接真实统计，要么 student-app 不展示周报占位 | P2 |
| **DATA-02** | `annotations` AI 失败假释义 | 改用 `lookup_word` 或返回空 + error | P1 |
| **DATA-03** | 讯飞 TTS WebSocket 未实现，靠 browser TTS | 产品标注；MiniMax/OpenAI 路径文档化 | P3 |

---

## 第 6 节：优先级 Backlog（实施顺序）

### P0 — 止血（1 个里程碑）

| 序 | ID | 工作项 | 工作量 |
|----|-----|--------|--------|
| 1 | SEC-01 | 全 router `user_id` 归属校验 + 越权测试套件 | L |
| 2 | SEC-02 | pdf/goals/questions 家长/admin 门禁 | M |
| 3 | ID-04 | 生产 admin 密码与 JWT_SECRET 强制 | S |
| 4 | SEC-01 | tasks 列表/submit 补 `resolve_target_user_id` | S |

**验收**：pytest 新增 `test_access_control_*` 覆盖主要 router；手动：两 child token 互访 403。

### P1 — 对齐（1–2 里程碑）

| 序 | ID | 工作项 | 工作量 |
|----|-----|--------|--------|
| 5 | PRD-01 / ID-01 / ID-03 | 孩子建号主路径；下线 legacy；家长端「新建孩子」改为邀请引导 | M |
| 6 | CLI-01 | 构建标识 + serve 文档 | S |
| 7 | CLI-02 | frontend 跳转页或下线 | M |
| 8 | DATA-02 | annotations 与 lookup_word 一致 | S |
| 9 | PRD-03 | 去掉 frontend 模型配置块 | S |
| 10 | CLI-04 | 三端 401 统一 | S |

### P2 — 瘦身

| 序 | ID | 工作项 | 工作量 |
|----|-----|--------|--------|
| 11 | ID-02 | name 字段退役计划 | M |
| 12 | DATA-01 | week_stats 实现或删 UI | M |
| 13 | AI-01 | 按 roadmap 收编调用点 | L |
| 14 | OPS-01 | SQLite 绝对路径默认/启动脚本 | S |
| 15 | CLI-02 | 删除 frontend 大段代码 | L |

### P3 — 可选

PRD-04、PRD-05、DATA-03、AI 全 agent 化。

---

## 第 7 节：度量与完成定义

| 指标 | 目标 |
|------|------|
| 鉴权覆盖 | 100% 带 `user_id` 的写操作 + 90% 读操作有归属校验 |
| 孩子建号路径 | 文档 + UI 仅暴露 1 主路径 + Admin |
| 客户端 | 8766 不再提供学习；8898/8082 登录页含密码 + 构建号 |
| 测试 | CI：`pytest` 鉴权套件；`flutter test`  auth 回归 |
| 账号 spec | `2026-11-05-account-system` P1/P2 项在 backlog 中可追溯 |

---

## 与账号体系 spec 的差距

| account-system 条款 | 审计状态 |
|---------------------|----------|
| P0 auth/family/admin | **已做** |
| P1 全 API user_id | **未做** → SEC-01 |
| P2 三端全 token | **部分**（Flutter/parent 有；frontend 无） |
| 孩子自助注册 + 绑定 | **已做** |
| 受限模式 | **已做** |
| 运营 Admin | **已做** |

---

## 非目标（本审计周期不做）

- 一孩子多家长 / 家庭组
- 微信/Apple 登录
- 重写 parent-web 框架
- 全 AI agent-native（仅排期 P2/P3）

---

## 下一步

1. 用户审阅本文档。  
2. 按 **writing-plans** 为 **P0 SEC-01** 单独写 implementation plan（最大块）。  
3. P1 项可合并为 `product-alignment-2026-11` plan。
