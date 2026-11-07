# 数学应用题拍照 + AI 批改与家长审核 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 数学每日任务拆分计算题（屏上判分）与应用题（一题一照、AI 批改过程+答案、家长 confirm/reject）；家长可配 `task_math_calc_count` / `task_math_word_count`；学习配置对当前孩子展示听写方式。

**Architecture:** `Task.content` 存 `{calc, word}`；`upload-photo` 增 `word_index` 写回并调 `grade_math_work_photo`；`submit`/`confirm`/`reject` 扩展 math；Flutter `math_page` 双 UI 路径；家长端配置与待审核面板。

**Tech Stack:** FastAPI · pytest · Flutter/Riverpod · image_picker · parent-web JS · 视觉 LLM（`services/ai.py`）

**Spec:** [../specs/2026-11-07-math-word-photo-design.md](../specs/2026-11-07-math-word-photo-design.md)

---

## 文件职责

| 路径 | 职责 |
|------|------|
| `backend/app/services/math_gen.py` | 拆分 calc/word 出题；`grade_math_work_photo` |
| `backend/app/services/task_gen.py` | `_gen_math_practice` 新 content、读题数配置 |
| `backend/app/services/child_config.py` | （如需）数学题数 getter 默认值常量 |
| `backend/app/routers/math.py` | task material（无 word 答案泄露）、grade calc only |
| `backend/app/routers/tasks.py` | upload `word_index`、submit/confirm/reject math |
| `backend/tests/test_math_gen.py` | 出题形状、判分、vision 假数据 |
| `backend/tests/test_task_gen.py` | math task content calc+word 长度 |
| `backend/tests/test_tasks_router.py` | upload/submit/confirm/reject math |
| `parent-web/app.js` | 数学题数配置；未选孩子提示；math 待审核 UI |
| `student-app/lib/features/math_exercise/data/math_models.dart` | `calc`/`word` 模型 |
| `student-app/lib/features/math_exercise/data/math_repository.dart` | material、upload、grade |
| `student-app/lib/features/math_exercise/math_controller.dart` | 双路径状态机 |
| `student-app/lib/features/math_exercise/ui/math_page.dart` | 计算输入 + 应用拍照 |
| `student-app/test/features/math_exercise/*` | 解析、提交条件 |

---

### Task 1: 数学题数配置与 `task_gen`

**Files:**
- Modify: `backend/app/services/task_gen.py`
- Modify: `backend/app/services/math_gen.py`
- Test: `backend/tests/test_task_gen.py`, `backend/tests/test_math_gen.py`

- [ ] **Step 1:** 写失败测试 `test_generate_tasks_math_respects_calc_and_word_counts`：ChildConfig `task_math_calc_count=2`, `task_math_word_count=1` → content JSON `len(calc)==2`, `len(word)==1`

- [ ] **Step 2:** `pytest …` FAIL

- [ ] **Step 3:** `generate_math_questions` 拆为 `generate_math_calc(db, text, n)` / `generate_math_word(db, text, n)`（或单函数返回 dict）；`_gen_math_practice` 读 `_default_count(..., "task_math_calc_count", 2)` / `task_math_word_count`，写入 `content`

- [ ] **Step 4:** pytest PASS

- [ ] **Step 5:** commit `feat(math): split calc and word daily task content`

---

### Task 2: `grade_math_work_photo`

**Files:**
- Create/Modify: `backend/app/services/math_gen.py`（或 `math_photo_grade.py` 若文件过大）
- Test: `backend/tests/test_math_gen.py`

- [ ] **Step 1:** 测试 fake provider：`grade_math_work_photo(db, bytes, question, expected)` → 含 `ai_status`, `final_answer`, `steps_plausible`, `confidence`

- [ ] **Step 2:** 实现 vision prompt + `json_mode`；归一答案比对；置信度阈值常量；fake 固定返回

- [ ] **Step 3:** 三分支断言：`ok` / `pending_review` / `failed`

- [ ] **Step 4:** commit

---

### Task 3: `upload-photo` + content 写回

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Test: `backend/tests/test_tasks_router.py`

- [ ] **Step 1:** 测试 `POST /api/tasks/{id}/upload-photo` multipart `word_index=0` → `content.word[0].photo_path` 与 `ai_status` 存在

- [ ] **Step 2:** 解析 `task_type==math` 的 content；校验 index；存文件；更新 JSON；调用 `grade_math_work_photo`；`db.commit`

- [ ] **Step 3:** dictation 路径不变（无 `word_index`）

- [ ] **Step 4:** commit

---

### Task 4: `GET` material + `grade` calc

**Files:**
- Modify: `backend/app/routers/math.py`
- Test: `backend/tests/test_math_router.py`（无则新建）

- [ ] **Step 1:** `GET /api/math/task/{id}/material` 从 Task.content 返回 `calc`（可含 answer 供服务端）、`word`（**仅 question/id**，无 `answer`）

- [ ] **Step 2:** `POST grade` body `{answers:[]}` 只判 calc 下标；写回 `calc[i].correct`

- [ ] **Step 3:** 旧 content 数组兼容 → 全算 calc

- [ ] **Step 4:** commit

---

### Task 5: submit / confirm / reject

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Test: `backend/tests/test_tasks_router.py`

- [ ] **Step 1:** `math_submit_requires_all_word_photos_and_calc_graded`

- [ ] **Step 2:** `_math_ready_to_submit(task, content)` helper

- [ ] **Step 3:** `confirm`：math 不要求 `Task.photo_path`；`reject` 新路由 `POST /{id}/reject` scope=task，清 submit、设 word rejected

- [ ] **Step 4:** commit

---

### Task 6: 家长端学习配置

**Files:**
- Modify: `parent-web/app.js`

- [ ] **Step 1:** `renderLearningConfigTab` 增加 `task_math_calc_count` / `task_math_word_count` num 行

- [ ] **Step 2:** 未选 `uid` 时保存按钮禁用 + 提示；听写 select 仅在 `uid` 时展示（或灰显）

- [ ] **Step 3:** 手动验证 8767：选孩子 → 保存 → force 生成 → 题数生效

- [ ] **Step 4:** commit

---

### Task 7: 家长任务审核 UI

**Files:**
- Modify: `parent-web/app.js`

- [ ] **Step 1:** 解析 math task `content` JSON；列表展示 calc 对错摘要、word 缩略图链 `/uploads/...`、AI 标签

- [ ] **Step 2:** `rejectTask(id)` 调新 API；与 `confirmTask` 并列

- [ ] **Step 3:** commit

---

### Task 8: Flutter 数据层

**Files:**
- Create: `math_models.dart`；Modify: `math_repository.dart`
- Test: `student-app/test/features/math_exercise/math_models_test.dart`

- [ ] **Step 1:** 解析 `{calc, word}`；word 无 answer 字段

- [ ] **Step 2:** `uploadWordPhoto(taskId, index, bytes)`；`gradeCalc(taskId, answers)`

- [ ] **Step 3:** `flutter test` PASS

- [ ] **Step 4:** commit

---

### Task 9: Flutter UI + 控制器

**Files:**
- Modify: `math_controller.dart`, `math_page.dart`
- Test: controller test

- [ ] **Step 1:** calc TextField；word `image_picker` + 状态文案（无终局对错）

- [ ] **Step 2:** 全完成 → `submitTask`；监听家长打回后重载

- [ ] **Step 3:** `flutter test` + 手动 chrome 联调

- [ ] **Step 4:** commit

---

### Task 10: 验收

- [ ] `cd backend && python -m pytest tests/test_math_gen.py tests/test_task_gen.py tests/test_tasks_router.py -v`

- [ ] `cd student-app && flutter test test/features/math_exercise/`

- [ ] 家长配 calc=2 word=2 → force → Flutter 拍照 2 张 → submit → 家长 confirm

- [ ] README/发版说明：force 重生今日任务

---

## 执行顺序

```text
Task 1 → 2 → 3 → 4 → 5    # 后端闭环
Task 6 → 7                 # 家长端
Task 8 → 9                 # Flutter
Task 10 验收
```

## 风险

- Vision 未配置：全面测 `failed` → 家长 confirm 路径
- `content` JSON 与 `Task.photo_path` 并存：文档标明听写与数学语义分离
