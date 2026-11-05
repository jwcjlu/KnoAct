# 孩子管理中心设计

> 日期：2026-11-05
> 状态：与用户逐节确认中

## 背景与目标

家长端目前没有独立的「孩子管理」页面：新建孩子靠三个 `prompt()` 弹窗、不能编辑、
不能删除/归档，也看不到「孩子绑定了哪些教材」。孩子 ↔ 家长关系只靠 `parent_id`
隐式关联，无聚合管理视图。

目标：家长端新增一个完整的「孩子管理」中心，支持孩子的**新建 / 编辑 / 归档（软删）**，
以及**从孩子侧查看/修改其绑定的教材**。

## 核心决策（已与用户确认）

| 决策 | 结论 |
|------|------|
| 删除力度 | **归档（软删）**：`User.status` 加 `active/archived`，数据全保留 |
| 编辑年级 | **只改 `User.grade`** + `ensure_bucket` 确保有对应 active 桶，不封存历史桶 |
| 绑定教材视图 | 从孩子侧查其绑定的教材（复用 `UserDocument` 反向查） |

## 影响面（归档的连锁）

归档一个孩子，需同步：

1. `/api/auth/login`：归档孩子按名字登录时拒绝（返回错误或标记，避免归档形同虚设）。
2. `generate_daily_tasks`（定时任务）：遍历孩子时排除 `status="archived"`。
3. `/api/users?role=child`：默认排除 archived；家长端可带 `include_archived=1` 回看。
4. 学生端：归档孩子登录被拒 → 前端引导重新登录（学生端基本不动，靠后端登录拒绝兜底）。

---

## 第 1 节：数据模型

`User` 表加一列：

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | String(16), default="active" | active | archived |

幂等迁移 `_migrate_user_status`（`seed.py`）：`ALTER TABLE users ADD COLUMN status VARCHAR(16) DEFAULT 'active'`。

## 第 2 节：后端接口

1. **`PUT /api/children/{child_id}`** body `{name?, grade?, edition?}` → 更新孩子。
   grade 变更时：`user.grade = grade` + `ensure_bucket(db, child_id)`（不封存历史桶）。
2. **`POST /api/children/{child_id}/archive`** → `user.status = "archived"`（软删，幂等）。
3. **`POST /api/children/{child_id}/unarchive`** → `user.status = "active"`（恢复，幂等）。
4. **`GET /api/children/{child_id}/documents`** → 返回该孩子绑定的教材列表
   （复用 `UserDocument` 反向查，返回 `{documents: [{id, filename, subject, grade, edition}]}`）。
5. **`GET /api/users?role=child`** 增加 `include_archived` 参数：默认排除 archived，
   传 `include_archived=1` 时返回全部（含 archived）。
6. **`/api/auth/login`**：命中归档孩子时返回错误（如 `{"error": "archived"}`），不自动建号。

## 第 3 节：家长端（parent-web）

新增「孩子管理」Tab：

1. **孩子列表**：每行显示姓名、年级、教材版本、当前学年，加「编辑」「归档」「看教材」按钮。
2. **新建孩子**：表单式（替换 `prompt`），姓名 + 年级下拉（1~6）+ 版本输入。
3. **编辑孩子**：弹表单改姓名/年级/版本。
4. **归档孩子**：带确认提示；归档后从默认列表隐藏（可切换「显示已归档」）。
5. **孩子 → 教材**：点某个孩子，显示/勾选 ta 绑定的教材（复用教材绑定接口，
   反向视图）。

## 第 4 节：学生端（基本不动）

归档孩子登录被后端拒绝，学生端现有「登录失败」提示已能兜底，无需专门改动。

## 第 5 节：错误处理与边界

- 归档已归档的孩子 → 幂等返回 ok。
- 编辑不存在的孩子 → 返回 `{"error": "not found"}`。
- 归档孩子后，其名下数据（任务/错题/掌握度/桶/绑定）全部保留，不级联删除。

## 第 6 节：测试

- 后端：编辑孩子（含 grade→ensure_bucket）、归档幂等、登录拒绝归档孩子、
  定时任务排除归档、`/users` include_archived 过滤、`/children/{id}/documents` 返回绑定教材。
- 前端：孩子管理 Tab 的新建/编辑/归档交互（`node --check` + 人工）。

## 范围边界

- **不做**：孩子的真删（级联清空数据）——归档已满足需求。
- **不做**：多家长权限隔离（parent_id 已存在但无鉴权，与全库一致）。
- **不做**：孩子端 UI 改动（登录拒绝已兜底）。
