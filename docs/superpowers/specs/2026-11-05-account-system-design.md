# 完整账号体系设计

> 日期：2026-11-05  
> 状态：已与用户确认（登录名唯一、资料可改、密码/验证码双通道登录、孩子自助注册、运营 Admin）

## 背景与目标

KnoAct 当前认证为「姓名即身份」：`POST /api/auth/login` 仅传 `name`，无密码、无验证码、
无会话 token；业务 API 普遍不校验身份，客户端自行传 `user_id`。学生端找不到名字会自动建号，
且常无 `parent_id`，与家长端按 `parent_id` 过滤的孩子列表脱节。

目标：

1. **唯一登录名**（自定义用户名）+ **密码注册**；登录支持 **密码或验证码**（适合记不住密码的孩子）。
2. App 内可维护 **资料**：真实姓名、出生年月、性别、兴趣爱好等（与登录名分离）。
3. **孩子可在学生 App 自助注册**，再 **绑定家长**；未绑定前 **受限模式**（不可使用学习功能）。
4. **平台运营 Admin**：代建/管理家长与学生、重置密码、调整绑定关系（解决「后台不能添加学生」等运营场景）。
5. 全 API 逐步接入 **Bearer 鉴权**，以 token 内用户身份为准，杜绝越权访问。

## 核心决策

| 决策 | 结论 |
|------|------|
| 登录标识 | 自定义 **login_name**，全局唯一（如 3–32 位 `[a-zA-Z0-9_]`） |
| 展示与登录分离 | **login_name** 固定；**display_name** 等为资料字段，App 可改 |
| 注册 | **login_name + password + role**（child / parent）；**禁止**公开注册 admin |
| 登录 | **D**：用户名+密码，或用户名+验证码（验证码发到已绑且已验证的手机/邮箱） |
| 孩子来源 | **B**：学生 App 自助注册；家长端 **邀请码 / 确认绑定**；Admin 可代建 |
| 未绑定家长 | **受限模式**：仅绑定流程 + 资料页，不可进学习首页/任务等 |
| 验证码通道（一期） | **手机号 + 短信** 为主；邮箱绑定与发码 **二期**；注册不强制手机，但无绑定则无法用验证码登录 |
| Admin | 独立 **admin-web** + `User.role=admin`；路由 **`/api/admin/*`** |
| 会话 | JWT（access 短 + refresh 长）或等价 opaque token；三端 `Authorization: Bearer` |
| 旧「按名登录/自动建号」 | 迁移后 **关闭**（dev 可环境变量开关便于本地种子） |

---

## 第 1 节：数据模型

### 1.1 `User` 扩展

在现有 `User`（`role`, `grade`, `edition`, `parent_id`, `status`）上增加：

| 字段 | 类型 | 说明 |
|------|------|------|
| `login_name` | String(32), **UNIQUE**, NOT NULL | 登录名 |
| `password_hash` | String | bcrypt 等；admin/家长/孩子均有 |
| `display_name` | String(64) | 真实姓名/展示名 |
| `birth_month` | String(7) | `YYYY-MM`，可空 |
| `gender` | String(16) | `unknown` / `male` / `female`（可扩展） |
| `interests` | Text / JSON | 兴趣爱好列表 |
| `phone` | String(20) | 可空；验证码登录依赖 |
| `email` | String(128) | 可空；二期 |
| `phone_verified` | Boolean | 默认 false |
| `email_verified` | Boolean | 默认 false |

**角色**：`role` ∈ `child` | `parent` | `admin`。

**废弃语义**：原 `name` 列迁移为 `login_name` 或 `display_name` 后弃用或作只读别名（迁移脚本见第 5 节）。

### 1.2 验证码 `otp_codes`

| 字段 | 说明 |
|------|------|
| `user_id` 或 `login_name` | 关联用户 |
| `channel` | `phone` / `email` |
| `purpose` | `login` / `reset_password` / `bind_phone` |
| `code_hash` | 不存明文 |
| `expires_at` | 通常 5–10 分钟 |
| `attempts` | 防暴力 |

限流：同一用户/同一 IP 发送频率（如 1 次/60s，10 次/日）。

### 1.3 家长–孩子绑定 `family_invites`（可选表）

| 字段 | 说明 |
|------|------|
| `parent_id` | 发起家长 |
| `code` | 短码或 token |
| `expires_at` | |
| `used_by_child_id` | 使用后写入 |

或使用 **绑定请求** 表：`child_id`, `parent_id`, `status` pending/approved/rejected。

### 1.4 会话 `refresh_tokens`（若用 JWT + refresh）

存 `user_id`, `token_hash`, `expires_at`, `revoked`；登出/改密时撤销。

---

## 第 2 节：认证 API

前缀 **`/api/auth`**。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/register` | `{ login_name, password, role }` → user + tokens |
| POST | `/login` | `{ login_name, password }` |
| POST | `/otp/send` | `{ login_name, purpose }` → 需已绑且 verified 的手机 |
| POST | `/otp/login` | `{ login_name, code }` |
| POST | `/password/reset` | `{ login_name, code, new_password }` |
| POST | `/logout` | 撤销 refresh |
| POST | `/refresh` | 续期 access |
| GET | `/me` | 当前用户 + profile + `parent_bound: bool` |
| PATCH | `/me/profile` | 更新 display_name, birth_month, gender, interests, grade/edition（孩子） |
| PATCH | `/me/credentials` | 改密码；绑手机 + 验证 |

**归档**：`status=archived` → 403，与现有一致。

**密码策略**：≥8 位，含字母与数字（孩子账号可 UI 提示家长协助；规则后端统一）。

### 2.1 家庭绑定 `/api/family`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/invite` | 家长生成邀请码 |
| POST | `/bind` | 孩子 `{ code }` → 写 `parent_id` |
| POST | `/request` | 孩子 `{ parent_login_name }` → pending |
| GET | `/requests` | 家长看待处理 |
| POST | `/requests/{id}/approve` | 同意 |
| POST | `/requests/{id}/reject` | 拒绝 |
| POST | `/unbind` | 家长或 admin 解绑（需确认策略） |

绑定成功 → 孩子解除受限模式。

### 2.2 鉴权依赖

- `get_current_user`：解析 Bearer，加载 User，检查 archived。
- `require_role("parent"|"admin"|"child")`。
- **P1 规则**：业务接口的 `user_id` 必须与 token 一致，或为家长访问 `parent_id` 下的孩子，或为 admin。

### 2.3 鉴权 rollout

| 阶段 | 范围 |
|------|------|
| P0 | auth、me、family、config 写、admin |
| P1 | 所有带 `user_id` 的读写：校验归属 |
| P2 | 三端全面带 token，移除裸 `user_id` 信任 |

---

## 第 3 节：平台运营 Admin

### 3.1 入口

- 新目录 **`admin-web/`**（静态 JS，nginx 同源反代 `/api`）。
- Admin 账号仅 **seed / 其他 admin 创建**，无 `/register?role=admin`。

### 3.2 `/api/admin` 能力（一期）

| 能力 | 说明 |
|------|------|
| 用户搜索 | role、login_name、phone、parent 绑定状态 |
| 创建学生 | login_name、初始密码、可选 parent_id、grade/edition → 共用 `create_child_user()` |
| 创建家长 | 同上 |
| 编辑档案 | 同 profile + status |
| 重置密码 | 生成临时密码或强制 reset 链接 |
| 绑定/解绑 | 修改 `parent_id` |
| 归档/恢复 | 复用 children archive/unarchive |

### 3.3 与家长端分工

| 场景 | 入口 |
|------|------|
| 家庭日常使用 | 家长邀请 + 孩子自助注册 |
| 客服/入校批量 | Admin 代建 + 分发初始密码 |
| 孩子管理 UI | 家长端「孩子管理」仅 **已绑定** 孩子；Admin 看全局 |

---

## 第 4 节：前端改动

### 4.1 student-app

- 登录 / 注册 / 验证码登录 Tab 或入口。
- `ApiClient` 注入 token；401 → 回登录。
- 受限模式路由：未 `parent_id` → 绑定家长页。
- 「我的」：资料编辑表单；退出登录清 token。
- 移除「仅名字登录」与「自动建号」文案。

### 4.2 parent-web

- 账号注册/登录（替换姓名登录）。
- token 持久化；`parentId` 来自 `/me` 而非仅 localStorage 信任。
- 邀请码、绑定请求列表。
- 孩子管理：与已绑定孩子一致；可选保留「代填注册信息」引导至 App。

### 4.3 admin-web

- 登录页、用户列表、创建用户表单、重置密码、绑定编辑、归档。

### 4.4 frontend（旧学生 Web）

- 冻结态：最小改动或显示「请使用新 App」；不优先投入。

---

## 第 5 节：迁移、错误处理、测试

### 5.1 数据迁移

1. 加列：`login_name`, `password_hash`, profile 字段等；幂等 `ALTER`（`seed.py` 模式）。
2. 现有用户：`name` → `login_name`（去重冲突加 `_2` 后缀）；`display_name` = 原 `name`。
3. 种子：`金爸爸` / 默认孩子 → 文档化初始 login_name + 密码；首次启动提示改密。
4. `role=admin`：seed 一个 `admin` 账号（仅 dev/部署文档说明）。

### 5.2 错误码（JSON `detail`）

| 场景 | HTTP |
|------|------|
| login_name 已存在 | 409 |
| 凭据错误 | 401 |
| archived | 403 `{ "error": "archived" }` |
| 未绑定家长访问学习 API | 403 `{ "error": "parent_required" }` |
| OTP 无效/过期 | 401 |
| 非 admin 访问 admin | 403 |

### 5.3 短信

- `services/sms.py`：抽象 `SmsProvider`（fake / 阿里云等），与 `model_config` 类似可配置。
- fake：日志打印 6 位码，测试固定 `123456`（仅 test env）。

### 5.4 测试

- `test_auth.py`：注册唯一性、密码登录、OTP 登录、归档拒绝。
- `test_family.py`：邀请绑定、请求审批、受限模式 API 403。
- `test_admin.py`：非 admin 403、代建学生、`ensure_bucket` 调用。
- 迁移测试：旧库补列后 login 仍可用。

### 5.5 安全

- 密码 bcrypt；OTP hash；HTTPS 生产必选。
- 登录/OTP 限流；refresh  rotation 可选。
- 不在日志打印密码/明文 OTP。

---

## 非目标（一期不做）

- 微信/Apple 一键登录。
- 一孩子多家长、一家长多「家庭组」复杂模型。
- 邮箱验证码（二期）。
- 细粒度 RBAC（admin 仅 `role=admin` 门禁）。

---

## 与现有 spec 关系

- **多学生 + 学年桶**（2026-11-04）：`parent_id`、`grade`、`ensure_bucket` 保持不变；本设计替换登录与鉴权层。
- **孩子管理中心**（2026-11-05）：归档/编辑/教材视图保留；新建孩子入口从「仅 prompt」扩展为邀请 + Admin + 自助注册。

---

## 验收标准

1. 两用户不能注册相同 `login_name`。
2. 孩子注册后未绑定家长时，学习类 API 返回 `parent_required`。
3. 孩子/App 可修改 display_name、birth_month、gender、interests，且不影响 login_name。
4. 同一账号可用密码或短信验证码登录（已绑手机且 verified）。
5. Admin 可创建学生并指定家长；家长端可见该孩子。
6. 带 token 访问他人 `user_id` 数据被拒绝（P1 完成后）。
