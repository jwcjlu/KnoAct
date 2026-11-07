# Flutter 听写对齐 Web（纸上听写 + 拍照打卡 + 双端审核）设计

日期：2026-11-07  
状态：已确认（brainstorming），待实现  
范围：`task_type=dictation` 的听写任务；Flutter 学生端、家长端、运营后台；后端偏好与提交校验。

## 关系说明

- 纸上听写 + 视觉批改的后端能力见 [2026-11-01-handwriting-dictation-design.md](./2026-11-01-handwriting-dictation-design.md)（`grade-handwriting`、错词重写、申诉等）。
- 本文聚焦：**Flutter 与旧 Web 流程对齐**、**家长可配置听写方式**、**纸上模式任务打卡照必传**、**家长审核 + 运营只读监管**。
- **不在范围**：`listening`（听力理解）任务形态；运营代审/改积分；听写回合全量落库（OCR JSON）。
- **同版约束**：后端 `photo_required` 与 Web `finishDictation` 顺序冲突——**实现阶段须同版调整** `frontend/app.js` 为先 `upload-photo` 再 `submit`（冻结 Web 仍被部分环境使用，避免默认 `paper_photo` 下打卡 400）。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 任务类型 | 仅 `dictation`（语文/英语词表） |
| 默认体验 | 纸上听写 + 拍照批改（对齐 `frontend/app.js` 状态机） |
| 备选体验 | 屏上手写板（保留）；**家长**在家长端配置，孩子端只读 |
| 配置键 | `child_config.dictation_input_mode` = `paper_photo` \| `on_screen`（默认 `paper_photo`） |
| 打卡照 | 纸上模式：**必传** `Task.photo_path` 后才能 `submit`；屏上模式可不传 |
| 家长端 | 沿用任务 Tab 审核（`confirm` + 查看照片）；新增听写方式配置 |
| 运营端 | `admin-web` **只读**列表：按孩子查看听写打卡与照片 |
| 运营权限 | 不展示通过/驳回；不改积分 |

## 成功标准

1. Flutter **纸上模式**完整链路：听词 → 整页拍照 → 批量 `grade-handwriting` → 结果/申诉 → 错词重写 → `complete` → **upload-photo** → `submit`。
2. Flutter **屏上模式**保持逐词手写；`complete` 后可直接 `submit`，无打卡照要求。
3. 家长可为**当前选中孩子**设置听写方式；App 展示当前模式、不可切换。
4. 家长任务列表可审核听写打卡（含照片链接）。
5. 运营可按日期/孩子/状态筛选 `dictation` 任务并查看照片（只读）。

### 迁移与默认策略

- API 默认 `dictation_input_mode` = `paper_photo`（未配置行时）。
- 上线后 App 行为会从「屏上逐词」切到纸上流程；**不**为孩子静默改 `ChildConfig`。
- 家长端在「听写作答方式」旁加一句说明；可选灰字「未配置时与孩子端默认一致（纸上听写）」。
- 若需灰度：可在实现计划中评估种子/首启 `on_screen` 仅用于演示账号（非本 spec 必须项）。

---

## 一、Flutter 学生端

### 1.1 入口与模式

- 路由仍为 `/dictation`；`init` 从首页任务带入 `taskId`、`title`、`subject`、`content`（词 JSON）。
- 进入时 `GET /api/learning/preferences?user_id=` 读取 `dictation_input_mode`。
- UI 顶部只读标签：「纸上听写（家长设置）」/「屏上手写（家长设置）」。

### 1.2 屏上模式（`on_screen`）

- 复用现有 `HandwritingPad` + 逐词 `grade-handwriting` + `complete`。
- 完成后调用 `POST /api/tasks/{id}/submit`（无 `photo_path` 要求）。
- 不展示强制打卡照步骤。

### 1.3 纸上模式（`paper_photo`）

状态机与 Web 一致：

```
listen → upload → grading → result → [rewrite → listen …] → finishGate → done
```

**状态字段（扩展现有 controller 或拆分 `PaperDictationController`）**

- `phase`: `listen` \| `upload` \| `grading` \| `result` \| `rewrite` \| `finishGate` \| `done`
- `idx`, `rewriteIdx`, `rewriting`, `hints`（词 key → `pinyin` \| `meaning`）
- `gradeImageBase64`（批改用图；`finishGate` 可复用为打卡照）
- `wrong`, `firstRoundWrong`, `correct`, `results`（`DictGradeItem` 列表）
- `taskId`（已有）

**阶段行为**

| Phase | 行为 |
|-------|------|
| listen | TTS；提示（英语→释义；语文→拼音再释义）；下一词；末词→`upload`（首轮）或重写子流程 |
| upload | 文案 + `image_picker`（相机优先） |
| grading | 单次 `gradeHandwriting`；**首轮** `words[].index` = 词表下标 `0..n-1`；**重写轮**仅错词，且 `index` = 当前 `wrong` 列表下标 `0..wrong.length-1`（与 Web `gradeDict()` 一致，非原词表序号） |
| result | 统计、申诉、进入 `rewrite` 或 `finishGate` |
| rewrite | `rewriting=true`；错词逐词听写后整页拍照批改 |
| finishGate | 对应 Web `finishDictation()` 内打卡段（Web 无独立 phase 名）：`complete`（`wrong_words` 来自 `firstRoundWrong`）→ 必选打卡：`upload-photo`（默认可复用批改图）→ `submit` |
| done | 汇总；刷新首页任务 |

**API 顺序（纸上 + 有 taskId）**

1. `POST /api/dictation/complete`
2. `POST /api/tasks/{id}/upload-photo`（multipart）
3. `POST /api/tasks/{id}/submit`

**模块建议**

- `dictation_paper_flow.dart`：纸上 UI 各 phase
- `dictation_preferences_repository.dart`：偏好 GET
- `home_repository` 或 `dictation_repository`：`uploadTaskPhoto`

### 1.4 错误与边界

- OCR 无结果 → 回 `upload`，提示重拍。
- 无相机权限 → 引导系统设置（不自动改模式）。
- `submit` 若返回 `photo_required` → 留在 `finishGate` 重传。
- Web 构建：文件选择代替相机，可接受。

### 1.5 Flutter 测试

- Controller：phase 迁移、重写收缩 `wrong`、`firstRoundWrong` 保留。
- 纸上 `finishGate`：未 `upload-photo` 不调用 `submit`。
- 屏上路径回归测试。

---

## 二、后端

### 2.1 Child 偏好

**存储**：`child_config`（`user_id` + `dictation_input_mode`）

**`services/child_config.py`**

- 新增 `set_child_config_str(db, child_id, key, value) -> None`（upsert）

**`GET /api/learning/preferences`**

- Query：`user_id`
- Auth：`require_learning_user` + `ensure_user_access`
- Response：`{ "dictation_input_mode": "paper_photo" | "on_screen" }`
- **读取规则**：`dictation_input_mode` **仅查 `ChildConfig` 表**；无行时默认 `paper_photo`。**不**回落全局 `ModelConfig`（与 `get_child_config_str` 通用行为区分开，可用专用 `get_dictation_input_mode(db, child_id)`）。

**`PUT /api/learning/preferences`**

- Body：`{ "user_id": int, "dictation_input_mode": str }`
- Auth：`require_role("parent")` + 孩子归属校验
- 校验枚举；非法 → 400

### 2.2 任务提交校验

**`POST /api/tasks/{task_id}/submit`**

当同时满足：

- `t.task_type == "dictation"`
- `get_child_config_str(..., "dictation_input_mode", "paper_photo") == "paper_photo"`
- `not t.photo_path`

→ `HTTPException(status_code=400, detail={"error": "photo_required", "message": "请先上传听写打卡照片"})`（与 FastAPI / 学生端 `ApiClient` 解析 `detail` 一致）

**必做加固**：`POST /api/tasks/{id}/confirm` 在相同条件下同样返回 400（防止无照 `submitted` 被家长确认发积分）。

`upload-photo` 保持仅写 `photo_path`，不自动改 `submit_status`。

### 2.3 运营只读 API

**`GET /api/admin/dictation-checkins`**

- Auth：`require_role("admin")`
- Query：`date`（默认当天，`YYYY-MM-DD`）、`q`（孩子登录名/.display_name）、`submit_status`、`subject`、`limit`（默认 50）、`offset`
- 过滤：`task_type == "dictation"`
- 返回项示例：

```json
{
  "items": [
    {
      "task_id": 1,
      "user_id": 2,
      "child_login_name": "kid",
      "child_display_name": "小明",
      "parent_display_name": "妈妈",
      "date": "2026-11-07",
      "subject": "语文",
      "title": "桂花雨 生词听写",
      "detail": "...",
      "submit_status": "submitted",
      "photo_path": "uploads/task_photos/task_1.jpg",
      "points": 20
    }
  ],
  "total": 1
}
```

不新增写接口；管理员角色在其它路由上的既有写权限不在本功能 UI 暴露。

### 2.4 后端测试（pytest）

- preferences GET/PUT 权限与 upsert
- submit：`paper_photo` 无图 400；`on_screen` 无图 200
- admin checkins：仅 admin、筛选与分页

---

## 三、家长端 `parent-web`

### 学习配置

- 在当前孩子上下文（`uid`）增加下拉「听写作答方式」。
- 打开 Tab / 切换孩子时：`GET /api/learning/preferences?user_id={uid}` 回显当前值。
- 保存：`PUT /api/learning/preferences`（**不**写入全局 `POST /api/config`）。

### 任务 Tab

- 保持 `confirm`、照片链接。
- 可选：`dictation` + `submitted` + 无 `photo_path` 显示「未上传打卡照」。

---

## 四、运营端 `admin-web`

- 侧栏新增「听写打卡」。
- 调用 `GET /api/admin/dictation-checkins`；表格展示筛选结果；照片链到 `API_BASE + photo_path`。
- 无确认/删除/驳回按钮。

---

## 五、发布与风险

| 风险 | 缓解 |
|------|------|
| 旧 App / Web 先 submit 后传图 | Flutter + `frontend/app.js` 与后端校验同版发布 |
| 运营看不到 OCR 明细 | 方案 1 有意为之；可看打卡照与错题本 |
| 家长配置仍用全局 `ModelConfig` 的其它项 | 本次不重构，仅 `dictation_input_mode` 走 `child_config` |

**推荐发布顺序**：后端（含 `submit`/`confirm` 校验）→ 家长配置 UI → Flutter 纸上流程 → `frontend/app.js` 打卡顺序 → admin 页。

---

## 六、实现检查清单（摘要）

- [ ] `set_child_config_str` + preferences GET/PUT
- [ ] `submit` + `confirm` 校验
- [ ] `get_dictation_input_mode`（不回落 ModelConfig）
- [ ] `frontend/app.js` 听写打卡顺序（先传图再 submit）
- [ ] `GET /api/admin/dictation-checkins` + pytest
- [ ] parent-web 听写方式下拉 + save
- [ ] admin-web 听写打卡页
- [ ] Flutter 纸上状态机 + `upload-photo` + 偏好只读
- [ ] Flutter 屏上路径 + submit 回归
