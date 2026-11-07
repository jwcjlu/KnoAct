# 英语听力选择题（3～5 × 4 选 1）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将英语 `listening` 从一道简答题改为 3～5 道全英文四选一，Flutter/Web 听力 Tab 用单选，阅读保持填空。

**Architecture:** 扩展 `GenerateListeningTool` 输出 `questions[]`；`listening_material` 映射 API；可选在 GET 发现旧 `content` 时 regenerate 写回；Flutter `CenterQuestion` 双形态；Web `centerAnswer` 按下标判分。

**Tech Stack:** FastAPI · pytest · Flutter/Riverpod · `frontend/app.js`

**Spec:** [../specs/2026-11-07-listening-mc-design.md](../specs/2026-11-07-listening-mc-design.md)

---

## 文件职责

| 路径 | 职责 |
|------|------|
| `backend/app/tools/generation.py` | 新 prompt、`_normalize_listening`、fake 回落 |
| `backend/app/routers/learning.py` | `listening_material` 解析/旧格式 regenerate |
| `backend/app/services/task_gen.py` | `_gen_listening` 写入新 JSON、`Question` 摘要 |
| `backend/tests/test_generation_tools.py` | 生成结构断言 |
| `backend/tests/test_learning.py` | material API + 旧格式升级路径 |
| `backend/tests/test_task_gen.py` | listening task content 形状 |
| `student-app/lib/features/center/data/center_models.dart` | `CenterQuestion` 选择题字段 |
| `student-app/lib/features/center/center_logic.dart` | 下标判分 helper |
| `student-app/lib/features/center/center_controller.dart` | listening `answer` 分支 |
| `student-app/lib/features/center/ui/center_page.dart` | 听力 Radio UI |
| `student-app/test/features/center/*` | 解析/判分/页面 |
| `frontend/app.js` | 听力 radio、`centerAnswer` |

---

### Task 1: `_normalize_listening` + 生成工具

**Files:**
- Modify: `backend/app/tools/generation.py`
- Test: `backend/tests/test_generation_tools.py`

- [ ] **Step 1: 写失败测试**

```python
from app.tools.generation import generate_listening, normalize_listening


def test_normalize_listening_requires_four_options():
    raw = {
        "dialogue": "A: Hi",
        "questions": [
            {
                "id": "q1",
                "question": "What did A say?",
                "options": ["Hi", "Bye", "Yes", "No"],
                "correct_index": 0,
            }
        ],
    }
    out = normalize_listening(raw)
    assert len(out["questions"]) >= 3
    assert all(len(q["options"]) == 4 for q in out["questions"])


def test_generate_listening_returns_mc_schema():
    result = generate_listening.run({}, _ctx())
    assert "dialogue" in result
    assert "questions" in result
    assert len(result["questions"]) >= 3
    q0 = result["questions"][0]
    assert len(q0["options"]) == 4
    assert 0 <= q0["correct_index"] <= 3
```

- [ ] **Step 2:** `pytest backend/tests/test_generation_tools.py -v` → FAIL

- [ ] **Step 3: 实现**

- `normalize_listening(data)`: 保证 3～5 题、每题 4 选项、index 合法；不足则 pad 或 truncate
- `GenerateListeningTool.run`: 新 prompt JSON `{"dialogue","questions":[...]}`；异常 → fake 模板（3 题）
- 导出 `normalize_listening` 供 router 复用

- [ ] **Step 4:** pytest PASS

- [ ] **Step 5:** `git commit -m "feat(listening): generate multiple-choice material"`

---

### Task 2: `listening_material` API

**Files:**
- Modify: `backend/app/routers/learning.py`
- Test: `backend/tests/test_learning.py`

- [ ] **Step 1: 更新/新增测试**

- `test_listening_material_returns_mc_fields`：每题含 `options`、`correct_index`
- 修改 `test_listening_material_reads_pregenerated_task`：content 为新 JSON
- 新增 `test_listening_material_regenerates_legacy_content`：旧 `{dialogue,question,answer}` → GET 后 content 变为新 schema（兜底）

- [ ] **Step 2:** pytest FAIL

- [ ] **Step 3: 实现 `_listening_payload_from_content`**

- 新格式 → `questions` 原样映射（API 可去掉每题 `answer` 字段防泄题，仅 `correct_index` 不下发——**推荐不下发 `correct_index` 给客户端**，判分改服务端或下发用于本地判分：与现网一致保持**下发 correct_index** 供本地判分，与阅读相同信任模型）

- 旧格式检测：`question` in data and `questions` not in data → `generate_listening.run` + 写回 `Task.content`

- [ ] **Step 4:** pytest `test_learning.py` 相关用例 PASS

- [ ] **Step 5:** commit

---

### Task 3: `task_gen._gen_listening`

**Files:**
- Modify: `backend/app/services/task_gen.py`
- Test: `backend/tests/test_task_gen.py`

- [ ] **Step 1:** 更新 `test_generate_tasks_creates_listening_for_english`：`content` 含 `questions` 数组 length ≥ 3

- [ ] **Step 2:** 调整 `_gen_listening`：`Question.question` = 首题题干；`answer` = 正确选项文本

- [ ] **Step 3:** pytest PASS + commit

---

### Task 4: Flutter 数据层

**Files:**
- Modify: `student-app/lib/features/center/data/center_models.dart`
- Test: `student-app/test/features/center/center_repository_test.dart` 或新建 `center_models_test.dart`

- [ ] **Step 1: 测试 JSON 解析**

```dart
test('parses listening mc question', () {
  final m = CenterMaterial.fromJson({
    'text': 'A: Hi',
    'questions': [{
      'question': 'What?',
      'options': ['a','b','c','d'],
      'correct_index': 1,
    }],
  });
  expect(m.questions.first.isMultipleChoice, isTrue);
  expect(m.questions.first.correctIndex, 1);
});
```

- [ ] **Step 2:** `CenterQuestion` 增加 `options`、`correctIndex`、`bool get isMultipleChoice`

- [ ] **Step 3:** 阅读题仍仅 `answer` 字符串

- [ ] **Step 4:** `flutter test` + commit

---

### Task 5: Flutter controller + logic

**Files:**
- Modify: `student-app/lib/features/center/center_logic.dart`
- Modify: `student-app/lib/features/center/center_controller.dart`
- Test: `student-app/test/features/center/center_controller_test.dart`

- [ ] **Step 1:** `isCorrectListening(int selected, int correct) => selected == correct`

- [ ] **Step 2:** `answer(index, {String? text, int? selectedIndex})`：listening 用 index；错题记 `options[selected]`

- [ ] **Step 3:** 更新既有 center 测试；listening fixture 改为 4 选项

- [ ] **Step 4:** `flutter test test/features/center/` + commit

---

### Task 6: Flutter UI（听力 Tab）

**Files:**
- Modify: `student-app/lib/features/center/ui/center_page.dart`
- Test: `student-app/test/features/center/center_page_test.dart`

- [ ] **Step 1:** 听力 `_QuestionCard`：若 `isMultipleChoice` → `RadioListTile` 列表，无 `TextField`

- [ ] **Step 2:** 听力区不展示 `material.text`（仅播放按钮）

- [ ] **Step 3:** 更新 page test：expect 无「输入你的答案」于 listening tab

- [ ] **Step 4:** commit

---

### Task 7: Web `frontend/app.js`

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1:** 听力题渲染：`options.map` → radio，`centerPick[k]` 存 index

- [ ] **Step 2:** `centerAnswer('listening', qi)`：`Number(centerPick[k]) === q.correct_index`；错题传选项文案

- [ ] **Step 3:** 阅读分支保持不变

- [ ] **Step 4:** commit

---

### Task 8: 验收

- [ ] `cd backend && python -m pytest tests/test_generation_tools.py tests/test_learning.py tests/test_task_gen.py -v`

- [ ] `cd student-app && flutter test test/features/center/`

- [ ] 家长端 force 生成今日任务 → 孩子 Web/Flutter 听力 3+ 题单选

- [ ] 阅读 Tab 仍为输入框

---

## 执行顺序

```text
Task 1 → 2 → 3   # 后端
Task 4 → 5 → 6   # Flutter
Task 7             # Web
Task 8             # 验收
```

## 发布后

在 `README` 或发版说明加一句：部署后请在家长端 **重新生成本日任务** 以更新英语听力卷。
