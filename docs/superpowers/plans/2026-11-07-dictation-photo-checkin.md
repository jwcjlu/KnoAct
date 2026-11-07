# 听写纸上打卡对齐（Flutter + 家长 + 运营）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Flutter `dictation` 听写与 Web 一致（纸上听写 + 拍照批改 + 任务打卡照），家长按孩子配置听写方式，运营只读查看打卡。

**Architecture:** 后端用 `ChildConfig.dictation_input_mode` + `submit`/`confirm` 校验；Flutter 按模式分支（纸上状态机 vs 现有屏写）；家长/运营仅增 UI 与只读 API。同版改 `frontend/app.js` 打卡顺序。

**Tech Stack:** FastAPI · SQLAlchemy · pytest · Flutter/Riverpod · image_picker · parent-web/admin-web 原生 JS。

**Spec:** [../specs/2026-11-07-dictation-photo-checkin-design.md](../specs/2026-11-07-dictation-photo-checkin-design.md)

---

## 文件职责（创建 / 修改）

| 路径 | 职责 |
|------|------|
| `backend/app/services/child_config.py` | `set_child_config_str`、`get_dictation_input_mode`（不回落 ModelConfig） |
| `backend/app/routers/learning.py` 或新 `child_preferences.py` | `GET/PUT /api/learning/preferences` |
| `backend/app/routers/tasks.py` | `submit` / `confirm` 的 `photo_required` |
| `backend/app/routers/admin_users.py` 或 `admin_checkins.py` | `GET /api/admin/dictation-checkins` |
| `backend/app/main.py` | 注册新 router（若拆分） |
| `backend/tests/test_dictation_preferences.py` | 偏好与校验（新建） |
| `backend/tests/test_tasks_router.py` | 追加 submit/confirm 场景 |
| `parent-web/app.js` | 学习配置下拉 + GET/PUT 偏好 |
| `frontend/app.js` | `finishDictation` 先传图再 submit |
| `admin-web/app.js` + `index.html` | 听写打卡只读页 |
| `student-app/pubspec.yaml` | 添加 `image_picker` |
| `student-app/lib/features/dictation/data/dictation_preferences_repository.dart` | GET 偏好 |
| `student-app/lib/features/dictation/data/dictation_repository.dart` | `uploadTaskPhoto` multipart |
| `student-app/lib/features/dictation/paper_dictation_controller.dart` | 纸上状态机 |
| `student-app/lib/features/dictation/ui/dictation_paper_flow.dart` | 纸上各 phase UI |
| `student-app/lib/features/dictation/ui/dictation_page.dart` | 模式分支 + 屏写保留 |
| `student-app/lib/features/dictation/dictation_controller.dart` | 屏写路径 + 加载偏好 |
| `student-app/test/features/dictation/*` | controller / 流程测试 |

---

### Task 1: `get_dictation_input_mode` + `set_child_config_str`

**Files:**
- Modify: `backend/app/services/child_config.py`
- Test: `backend/tests/test_child_config.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_child_config.py` 追加：

```python
from app.services.child_config import (
    get_dictation_input_mode,
    set_child_config_str,
)


def test_get_dictation_input_mode_defaults_without_row(setup_db, db, child):
    assert get_dictation_input_mode(db, child.id) == "paper_photo"


def test_get_dictation_input_mode_ignores_model_config(setup_db, db, child):
    from app.models import ModelConfig
    db.add(ModelConfig(key="dictation_input_mode", value="on_screen"))
    db.commit()
    assert get_dictation_input_mode(db, child.id) == "paper_photo"


def test_set_child_config_str_upsert(setup_db, db, child):
    set_child_config_str(db, child.id, "dictation_input_mode", "on_screen")
    assert get_dictation_input_mode(db, child.id) == "on_screen"
    set_child_config_str(db, child.id, "dictation_input_mode", "paper_photo")
    assert get_dictation_input_mode(db, child.id) == "paper_photo"
```

- [ ] **Step 2: 运行确认失败**

Run（在 `backend/` 下，使用已装依赖的 Python）:

`python -m pytest tests/test_child_config.py::test_get_dictation_input_mode_defaults_without_row -v`

Expected: FAIL（`ImportError` / 函数不存在）

- [ ] **Step 3: 实现**

```python
VALID_DICTATION_MODES = frozenset({"paper_photo", "on_screen"})


def set_child_config_str(db: Session, child_id: int, key: str, value: str) -> None:
    row = db.query(ChildConfig).filter_by(user_id=child_id, key=key).first()
    if row:
        row.value = value
    else:
        db.add(ChildConfig(user_id=child_id, key=key, value=value))
    db.commit()


def get_dictation_input_mode(db: Session, child_id: int) -> str:
    row = db.query(ChildConfig).filter_by(user_id=child_id, key="dictation_input_mode").first()
    if row and row.value in VALID_DICTATION_MODES:
        return row.value
    return "paper_photo"
```

- [ ] **Step 4: 全量跑 `test_child_config.py`**

`python -m pytest tests/test_child_config.py -v` → PASS

- [ ] **Step 5: Commit**

`git add backend/app/services/child_config.py backend/tests/test_child_config.py`

`git commit -m "feat(backend): child dictation input mode helpers"`

---

### Task 2: Learning preferences API

**Files:**
- Create: `backend/app/routers/child_preferences.py`（或扩 `learning.py`）
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_dictation_preferences.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_dictation_preferences.py`:

```python
def test_preferences_get_default(child_headers, child):
    r = client.get(f"/api/learning/preferences?user_id={child.id}", headers=child_headers)
    assert r.status_code == 200
    assert r.json()["dictation_input_mode"] == "paper_photo"


def test_preferences_put_parent_only(parent_headers, child):
    r = client.put(
        "/api/learning/preferences",
        json={"user_id": child.id, "dictation_input_mode": "on_screen"},
        headers=parent_headers,
    )
    assert r.status_code == 200
    r2 = client.get(f"/api/learning/preferences?user_id={child.id}", headers=parent_headers)
    assert r2.json()["dictation_input_mode"] == "on_screen"


def test_preferences_put_invalid_mode(parent_headers, child):
    r = client.put(
        "/api/learning/preferences",
        json={"user_id": child.id, "dictation_input_mode": "bogus"},
        headers=parent_headers,
    )
    assert r.status_code == 400
```

（复用 `conftest` 里 `child` / `parent_headers` / `child_headers` fixture 模式，与 `test_tasks_router.py` 一致。）

- [ ] **Step 2: 运行 pytest → FAIL**

- [ ] **Step 3: 实现 router**

- `GET /api/learning/preferences?user_id=`
- `PUT` body `PreferencesReq(user_id, dictation_input_mode)`
- PUT：校验 `VALID_DICTATION_MODES`；家长须 `child.parent_id == user.id`
- GET：`ensure_user_access`

- [ ] **Step 4: `include_router` in `main.py`**

- [ ] **Step 5: pytest PASS + commit**

`git commit -m "feat(api): learning preferences for dictation input mode"`

---

### Task 3: Task submit / confirm `photo_required`

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/tests/test_tasks_router.py`

- [ ] **Step 1: 写失败测试**

```python
def test_dictation_submit_requires_photo_in_paper_mode(setup_db, db, child):
    from app.models import ChildConfig, Task
    from datetime import date
    db.add(ChildConfig(user_id=child.id, key="dictation_input_mode", value="paper_photo"))
    t = Task(user_id=child.id, date=str(date.today()), task_type="dictation", subject="语文",
             title="听写", submit_status="not_started", photo_path="")
    db.add(t); db.commit(); db.refresh(t)
    r = client.post(f"/api/tasks/{t.id}/submit", headers=_h(child.id))
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "photo_required"


def test_dictation_submit_ok_on_screen_without_photo(setup_db, db, child):
    from app.models import ChildConfig, Task
    ...
    db.add(ChildConfig(..., value="on_screen"))
    ...
    assert client.post(...).json() == {"ok": True}
```

再加 `confirm` 无照 400 测试。

- [ ] **Step 2: FAIL → 实现共享函数**

在 `tasks.py` 内：

```python
def _dictation_photo_required(db, t: Task) -> bool:
    if t.task_type != "dictation":
        return False
    from ..services.child_config import get_dictation_input_mode
    if get_dictation_input_mode(db, t.user_id) != "paper_photo":
        return False
    return not (t.photo_path or "").strip()
```

`submit` / `confirm` 开头调用，满足则 `raise HTTPException(400, detail={...})`。

- [ ] **Step 3: pytest `test_tasks_router.py` PASS**

- [ ] **Step 4: Commit**

---

### Task 4: Admin dictation-checkins（只读）

**Files:**
- Create: `backend/app/routers/admin_checkins.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_dictation_preferences.py` 或 `test_admin_checkins.py`

- [ ] **Step 1: 测试 admin 200、parent 403、筛选 date/q**

- [ ] **Step 2: 实现查询** — `Task.task_type=="dictation"` join `User` child；可选 join parent；分页 `limit/offset`

- [ ] **Step 3: pytest + commit**

`git commit -m "feat(admin): read-only dictation check-in list"`

---

### Task 5: 家长端学习配置

**Files:**
- Modify: `parent-web/app.js`

- [ ] **Step 1:** `renderLearningConfigTab` 增加 `sel('dictation_input_mode', 'paper_photo', '听写作答方式', ['纸上听写 + 拍照','屏上手写'])` — 选项值映射 `paper_photo` / `on_screen`

- [ ] **Step 2:** `loadLearningPreferences()`：`GET /api/learning/preferences?user_id=${uid}` 写入 `configMap.dictation_input_mode`；在 `renderParentTab` 进入「学习配置」且 `uid` 变化时调用

- [ ] **Step 3:** `saveLearningConfig` 中对 `dictation_input_mode` 单独 `PUT /api/learning/preferences`（带 `user_id: uid`），其它项仍 `POST /api/config`

- [ ] **Step 4:** 任务行可选：`dictation && submitted && !photo_path` 显示「未上传打卡照」

- [ ] **Step 5:** 手动冒烟：家长选孩子 → 学习配置保存 → 孩子 GET 偏好一致

- [ ] **Step 6: Commit**（若本仓库惯例不提交静态前端可跳过，由执行者按项目习惯）

---

### Task 6: 冻结 Web `finishDictation` 顺序

**Files:**
- Modify: `frontend/app.js`（`finishDictation` 约 1054+）

- [ ] **Step 1:** 找到 `POST .../submit` 与 `upload-photo` 逻辑

- [ ] **Step 2:** 改为：**有 task 时**先引导/上传 `upload-photo`（成功写 `photo_path`）→ 再 `submit`；纸上模式默认不再先 submit

- [ ] **Step 3:** 手动：8766 走完听写 → Network 顺序 `complete` → `upload-photo` → `submit`

- [ ] **Step 4: Commit**

---

### Task 7: Flutter 依赖与数据层

**Files:**
- Modify: `student-app/pubspec.yaml`
- Create: `dictation_preferences_repository.dart`
- Modify: `dictation_repository.dart`、`home_repository.dart`（或 dictation 内 upload）

- [ ] **Step 1:** `flutter pub add image_picker`

- [ ] **Step 2:** `DictationPreferencesRepository.fetch(userId)` → `DictationInputMode` enum

- [ ] **Step 3:** `uploadTaskPhoto(taskId, bytes, filename)` 用 `dio` `FormData` 对齐 `tasks.py` `File(...)`

- [ ] **Step 4:** `dart analyze` PASS

- [ ] **Step 5: Commit**

---

### Task 8: Flutter 纸上状态机（TDD）

**Files:**
- Create: `paper_dictation_controller.dart`
- Test: `student-app/test/features/dictation/paper_dictation_controller_test.dart`

- [ ] **Step 1: 失败测试** — `dictNext` 末词 → `upload`；`applyGradeResults` 首轮填充 `firstRoundWrong`；重写轮 index 0..wrong.len-1

- [ ] **Step 2: 实现 controller**（mock repository）

核心方法对齐 Web：

- `speakCurrent`、`hint`、`advanceListen`
- `setGradeImage` → `gradeAll` / `applyGradeResults`
- `startRewrite`、`finishComplete`（只调 complete，不调 submit）
- `uploadCheckInPhoto` → `submitTask`

- [ ] **Step 3:** `flutter test test/features/dictation/paper_dictation_controller_test.dart`

- [ ] **Step 4: Commit**

---

### Task 9: Flutter UI — `dictation_paper_flow` + 页面分支

**Files:**
- Create: `ui/dictation_paper_flow.dart`
- Modify: `ui/dictation_page.dart`、`dictation_controller.dart`

- [ ] **Step 1:** `init` 时拉偏好；`DictationPage`：`on_screen` 保留现有 widget 树；`paper_photo` 渲染 `DictationPaperFlow`

- [ ] **Step 2:** 各 phase UI（listen/upload/grading/result/rewrite/finishGate/done）

- [ ] **Step 3:** `finishGate`：按钮「用批改照片打卡」「重新拍照」→ upload → submit

- [ ] **Step 4:** 屏写路径：`on_screen` 完成仍直接 `submitTask`（无 finishGate）

- [ ] **Step 5:** `flutter analyze && flutter test`

- [ ] **Step 6: Commit**

---

### Task 10: admin-web 听写打卡页

**Files:**
- Modify: `admin-web/app.js`, `admin-web/index.html`（侧栏槽位）

- [ ] **Step 1:** 侧栏项「听写打卡」

- [ ] **Step 2:** `loadDictationCheckins()` 调 `GET /api/admin/dictation-checkins`

- [ ] **Step 3:** 表格：孩子、日期、学科、标题、状态、缩略图链接；**无**操作按钮

- [ ] **Step 4:** 8768 手动登录 admin 验证

- [ ] **Step 5: Commit**

---

### Task 11: 端到端验证清单

- [ ] 后端：`cd backend && python -m pytest tests/test_child_config.py tests/test_dictation_preferences.py tests/test_tasks_router.py -v`

- [ ] Flutter：`cd student-app && flutter analyze && flutter test`

- [ ] 联调：家长设 `on_screen` → App 屏写 → submit 无图 OK

- [ ] 联调：家长设 `paper_photo` → 纸上全流程 → 无图 submit 400 → 传图后 submit → 家长 confirm

- [ ] 运营：admin 列表可见该任务与照片

---

## Plan 执行顺序

```text
Task 1 → 2 → 3 → 4   # 后端可独立发布
Task 5                  # 家长配置（依赖 2）
Task 6                  # Web（依赖 3）
Task 7 → 8 → 9          # Flutter（依赖 2、3）
Task 10                 # admin（依赖 4）
Task 11                 # 验收
```

## 参考

- Web 状态机：`frontend/app.js` 约 873–1090
- 现有 Flutter 屏写：`student-app/lib/features/dictation/dictation_controller.dart`
- 任务 API 测试：`backend/tests/test_tasks_router.py`
