# 递进式规律引导 + 识记「认→背→测」实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构专项训练的步序——探究型内容的「观察」改为 AI 生成的递进引导链（guide），识记型步序改为「认→背→测」，解决「17 步太长」「观察不足无法总结规律」。

**Architecture:** 后端 `generate_explore_items` 改生成 `guide`（递进引导链，替代 compare/formula），`_steps_for` 识记改三步；前端 `DrillItem` 解析 guide 结构，`drill_page.dart` 渲染递进问答（guide 链）和识记挖空（背）。

**Tech Stack:** FastAPI + SQLAlchemy（后端）、Flutter + Riverpod（前端）、pytest + flutter_test。参考 spec：`docs/superpowers/specs/2026-11-14-progressive-guide-design.md`。

---

## 关键约定

1. **跑后端测试用 Bash 的 python**：`cd backend && python -m pytest tests/test_X.py -v`。
2. **跑前端测试**：`cd student-app && /e/dev/flutter/bin/flutter test`（Flutter 在 `E:\dev\flutter`）。
3. **explore 数据重新生成**：guide 是建组时 AI 生成的，改代码后**旧组的数据还是旧结构**（compare/formula），需重新建组才生成 guide。测试用 fake 回退（空结构）验证流程，真实 guide 质量需配模型验证。
4. **guide 结构**：`[{prompt, samples, options, answer_index, reveal}, ..., {prompt, answer, reveal}]`——前 N-1 轮选择题，最后一轮填空题（无 options，有 answer）。

---

## 文件结构

**后端（`backend/app/`）**
- `services/drill_rule.py`（改）：`generate_explore_items` 的 prompt + 解析，生成 `guide`（替代 compare/formula）。
- `services/drill_content.py`（改）：`_steps_for` 识记步序改 `["recognize","recall","quiz"]`。

**前端（`student-app/lib/`）**
- `features/drill/data/drill_repository.dart`（改）：`DrillItem.explore` 解析 guide 结构（新增 `GuideStep` 类）。
- `features/drill/ui/drill_page.dart`（改）：guide 链渲染（递进问答）+ 识记「背」挖空渲染。

**测试**
- `backend/tests/test_drill_explore.py`（改/加）：guide 生成的 fake 回退 + 结构校验。
- `student-app/test/features/drill/drill_content_test.dart`（改/加）：guide 解析。

---

## Task 1: `generate_explore_items` 改生成 guide（替代 compare/formula）

**Files:**
- Modify: `backend/app/services/drill_rule.py`（`generate_explore_items` 函数）
- Test: `backend/tests/test_drill_explore.py`

- [ ] **Step 1: 写失败测试**

在 `test_drill_explore.py` 里，现有测试断言 `generate_explore_items` 的 fake 回退返回空 dict。新增一个测试验证「非 fake 时返回结构含 guide 键」。但 fake 环境测不了真实 guide，所以测试改为**验证空回退 + 结构键**：

```python
# 追加到 test_drill_explore.py
def test_generate_explore_empty_structure_has_guide_key(db):
    # fake 环境返回空 dict，但我们要验证「正常结构的键」设计为含 guide
    # 用 monkeypatch 一个假 provider 返回固定 JSON，验证解析出 guide 键
    from app.services import drill_rule
    class FakeP:
        name = "openai"
        def generate(self, prompt, system="", json_mode=False):
            import json as _j
            return _j.dumps({"items": [{
                "primary": "比喻",
                "guide": [
                    {"prompt": "共同点？", "samples": ["月亮像小船"],
                     "options": ["都有像", "都写月亮"], "answer_index": 0,
                     "reveal": "对，都有像。"},
                    {"prompt": "总结：比喻=本体+比喻词+___", "answer": "喻体", "reveal": "太棒了"}
                ],
                "classify": {"items": ["a"], "boxes": ["比喻"], "answers": {"a": "比喻"}},
                "trap": {"question": "q", "answer": "a", "explain": "e"},
            }]})
    monkeypatch.setattr(drill_rule, "get_provider", lambda db: FakeP())
    r = drill_rule.generate_explore_items(db, [{"primary": "比喻", "secondary": "x"}])
    assert "比喻" in r
    assert "guide" in r["比喻"]
    assert len(r["比喻"]["guide"]) == 2
    # 最后一轮是填空题（无 options，有 answer）
    assert "options" not in r["比喻"]["guide"][1]
    assert r["比喻"]["guide"][1]["answer"] == "喻体"
    # 不再有 compare/formula 键
    assert "compare" not in r["比喻"]
    assert "formula" not in r["比喻"]
```

（注意：测试文件顶部需 `import` 时加 `monkeypatch` fixture，pytest 自动注入。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_drill_explore.py -v`
Expected: FAIL（当前 `generate_explore_items` 返回的是 `{compare, classify, formula, trap}` 结构，没有 `guide` 键）

- [ ] **Step 3: 改 `generate_explore_items`**

把 `drill_rule.py` 里 `generate_explore_items` 的 prompt 和解析改成生成 guide。完整替换该函数：

```python
def generate_explore_items(db: Session | None, items: list[dict]) -> dict:
    """为 explore（探究型）条目生成「递进引导链（guide）+ 练习（classify/trap）」，返回 {primary: {guide, classify, trap}}。

    递进引导：像教师一样一步步揭露规律，前 N-1 轮选择题（点选项），最后一轮填空题（自己归纳）。
    fake/无 db/无 items/异常 → 空 dict。
    """
    if db is None or not items:
        return {}
    from .ai import get_provider
    provider = get_provider(db)
    if provider.name == "fake":
        return {}

    payload = [{"primary": it.get("primary", ""), "secondary": it.get("secondary", "")}
               for it in items if (it.get("primary") or "").strip()][:4]
    if not payload:
        return {}

    prompt = (
        "为下面的知识点生成「递进式规律引导」学习内容，像教师一样一步步把规律揭露出来，让孩子自己总结规律（不要一次给结论）。\n"
        "每个知识点返回三段：\n"
        '1. guide：3~4 轮的递进引导链。前 N-1 轮是选择题，格式 '
        '{"prompt":"教师提问","samples":["正例材料1","正例材料2"],"options":["选项1","选项2","选项3"],"answer_index":正确选项下标,"reveal":"教师揭示语"}；'
        "最后一轮是填空题（孩子自己归纳规律），格式 {\"prompt\":\"总结：xxx = ___\",\"answer\":\"答案\",\"reveal\":\"鼓励语\"}（无 options）。\n"
        "递进顺序：第1轮给正例问共同点 → 第2轮深挖关键区别 → 第3轮给反例制造冲突 → 最后一轮让孩子自己归纳完整规律。\n"
        '2. classify：一道「拖拽归类」题，格式 {"items":["场景1","场景2"],"boxes":["概念1","概念2"],"answers":{"场景":"概念"}}，items 4~6 个、boxes 2~3 个（易混概念）。\n'
        '3. trap：一道「反直觉陷阱题」，格式 {"question":"反直觉问题","answer":"答案","explain":"解释"}。\n'
        '只返回 JSON：{"items":[{"primary":"知识点","guide":[...],"classify":{...},"trap":{...}}]}。\n'
        f"知识点列表：{json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是小学老师，善于苏格拉底式启发教学，一步步引导不直接给答案。", json_mode=True)
        data = json.loads(raw)
        out = {}
        for it in data.get("items") or []:
            if not isinstance(it, dict):
                continue
            primary = (it.get("primary") or "").strip()
            if not primary:
                continue
            classify = it.get("classify") or {}
            trap = it.get("trap") or {}
            guide = []
            for g in (it.get("guide") or []):
                if not isinstance(g, dict):
                    continue
                p = (g.get("prompt") or "").strip()
                if not p:
                    continue
                if "answer_index" in g:  # 选择题
                    guide.append({
                        "prompt": p,
                        "samples": [s for s in (g.get("samples") or []) if isinstance(s, str)],
                        "options": [s for s in (g.get("options") or []) if isinstance(s, str)],
                        "answer_index": g.get("answer_index", 0),
                        "reveal": (g.get("reveal") or "").strip(),
                    })
                else:  # 填空题（最后一轮归纳）
                    guide.append({
                        "prompt": p,
                        "answer": (g.get("answer") or "").strip(),
                        "reveal": (g.get("reveal") or "").strip(),
                    })
            out[primary] = {
                "guide": guide,
                "classify": {
                    "items": [s for s in (classify.get("items") or []) if isinstance(s, str)],
                    "boxes": [s for s in (classify.get("boxes") or []) if isinstance(s, str)],
                    "answers": classify.get("answers") if isinstance(classify.get("answers"), dict) else {},
                },
                "trap": {"question": (trap.get("question") or "").strip(),
                         "answer": (trap.get("answer") or "").strip(),
                         "explain": (trap.get("explain") or "").strip()},
            }
        return out
    except Exception:
        return {}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_drill_explore.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/drill_rule.py backend/tests/test_drill_explore.py
git commit -m "feat(drill): explore 改生成递进引导链 guide（替代 compare/formula）"
```

---

## Task 2: 识记步序改「认→背→测」

**Files:**
- Modify: `backend/app/services/drill_content.py`（`_steps_for`）
- Test: `backend/tests/test_drill_photo.py`（或新增断言）

- [ ] **Step 1: 写失败测试**

在 `test_drill_explore.py` 或新建断言（`_steps_for` 是私有函数，通过 `build_task_content` 间接测）。直接在 `test_drill_explore.py` 追加：

```python
def test_steps_for_memorize_is_recognize_recall_quiz():
    from app.services.drill_content import _steps_for
    assert _steps_for("phrase") == ["recognize", "recall", "quiz"]
    assert _steps_for("outline") == ["recognize", "recall", "quiz"]
```

（注意：`_steps_for` 是模块私有函数，但可以直接 import 测试。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_drill_explore.py::test_steps_for_memorize_is_recognize_recall_quiz -v`
Expected: FAIL（当前 `_steps_for("phrase")` 返回 `["recognize","produce","quiz"]`）

- [ ] **Step 3: 改 `_steps_for`**

`backend/app/services/drill_content.py` 的 `_steps_for`：

```python
def _steps_for(kind: str) -> list[str]:
    if kind == "explore":
        return ["observe", "classify", "formula", "trap"]
    # 识记型：认 → 背 → 测
    return ["recognize", "recall", "quiz"]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_drill_explore.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/drill_content.py backend/tests/test_drill_explore.py
git commit -m "feat(drill): 识记步序改「认→背→测」（recognize→recall→quiz）"
```

---

## Task 3: 前端解析 guide 结构

**Files:**
- Modify: `student-app/lib/features/drill/data/drill_repository.dart`（`DrillItem.explore` 解析 + 新增 `GuideStep` 类）
- Test: `student-app/test/features/drill/drill_content_test.dart`

- [ ] **Step 1: 写失败测试**

在 `drill_content_test.dart` 追加：

```dart
  group('GuideStep 解析', () {
    test('guide 前选择后填空', () {
      final item = DrillItem.fromJson({
        'id': 1, 'primary': '比喻', 'type': 'explore',
        'explore': {
          'guide': [
            {'prompt': '共同点？', 'samples': ['月亮像小船'],
             'options': ['都有像', '都写月亮'], 'answer_index': 0, 'reveal': '对'},
            {'prompt': '总结：___', 'answer': '喻体', 'reveal': '太棒了'},
          ],
        },
      });
      final guide = item.explore['guide'] as List;
      expect(guide, hasLength(2));
      final first = GuideStep.fromJson(Map<String, dynamic>.from(guide[0] as Map));
      expect(first.isChoice, isTrue);
      expect(first.answerIndex, 0);
      final last = GuideStep.fromJson(Map<String, dynamic>.from(guide[1] as Map));
      expect(last.isChoice, isFalse);
      expect(last.answer, '喻体');
    });
  });
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd student-app && /e/dev/flutter/bin/flutter test test/features/drill/drill_content_test.dart`
Expected: FAIL（`GuideStep` 类不存在）

- [ ] **Step 3: 实现 GuideStep 类**

在 `student-app/lib/features/drill/data/drill_repository.dart` 里，`DrillItem` 类之后加：

```dart
/// guide 链的一轮：选择题（前 N-1 轮）或填空题（最后一轮归纳）。
class GuideStep {
  const GuideStep({
    this.prompt = '',
    this.samples = const [],
    this.options = const [],
    this.answerIndex = -1,
    this.answer = '',
    this.reveal = '',
  });

  final String prompt;
  final List<String> samples;
  final List<String> options;
  final int answerIndex; // -1 = 填空轮
  final String answer;   // 填空轮答案
  final String reveal;

  bool get isChoice => options.isNotEmpty && answerIndex >= 0;

  factory GuideStep.fromJson(Map<String, dynamic> j) => GuideStep(
        prompt: '${j['prompt'] ?? ''}',
        samples: j['samples'] is List ? (j['samples'] as List).map((e) => '$e').toList() : const [],
        options: j['options'] is List ? (j['options'] as List).map((e) => '$e').toList() : const [],
        answerIndex: (j['answer_index'] as num?)?.toInt() ?? -1,
        answer: '${j['answer'] ?? ''}',
        reveal: '${j['reveal'] ?? ''}',
      );
}
```

同时给 `DrillItem` 加一个便捷 getter `guideSteps`：

在 `DrillItem` 类里加：

```dart
  /// explore 的 guide 链（递进引导步骤）。
  List<GuideStep> get guideSteps {
    final g = explore['guide'];
    if (g is! List) return const [];
    return [for (final e in g.whereType<Map>()) GuideStep.fromJson(Map<String, dynamic>.from(e))];
  }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd student-app && /e/dev/flutter/bin/flutter test test/features/drill/drill_content_test.dart`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/drill/data/drill_repository.dart student-app/test/features/drill/drill_content_test.dart
git commit -m "feat(drill): 前端解析 guide 链（GuideStep 类）"
```

---

## Task 4: 前端渲染 guide 递进问答 + 识记「背」挖空

**Files:**
- Modify: `student-app/lib/features/drill/ui/drill_page.dart`（`_StepBody` 的 observe/recognize 渲染 guide；recall 渲染挖空）

- [ ] **Step 1: 写 widget 测试（验证 guide 问答渲染）**

`drill_page.dart` 里的 `_StepBody` 是私有组件，widget 测试需要构造 `DrillState` + `DrillSession`。为降低耦合，本 Task 只做「渲染逻辑正确」的验证，用 `flutter analyze` + 手动验证为主（widget 测试涉及 Riverpod 容器较复杂，本计划不强制）。

（说明：`_StepBody` 依赖 `DrillController` 的 Riverpod 状态，完整 widget 测试需 mock provider，超出本 Task 范围。改为「改完跑 flutter analyze + 全量 flutter test 确认无回归」，真实渲染由用户手动验证。）

- [ ] **Step 2: 改 `_StepBody` 渲染 guide 链**

在 `drill_page.dart` 的 `_StepBody` switch 里，`observe` 和 `recognize` 步改为渲染 guide 链（如果 item 有 guideSteps），否则回退 `_RuleCard`：

```dart
    switch (step) {
      case 'recognize':
      case 'observe':
        if (item != null && item.guideSteps.isNotEmpty) {
          return _GuideView(item: item, ctl: ctl);
        }
        return _RuleCard(session: session, reveal: s.revealRule, ctl: ctl);
      case 'structure':
        return _RuleCard(session: session, reveal: s.revealRule, ctl: ctl);
      ...
```

`recall`（背）步改为挖空渲染。当前 `recall` 在 `case 'recall': case 'drill': ...` 里是「补全：${item.primary}」。改为挖空：

在 `recall` 分支，把 `Text('补全：${item.primary}')` 改成挖空显示。先加一个挖空工具函数：

```dart
/// 把 primary 按标点切片段，每片段挖掉中间偏后的 1 个字。
String _blankPrimary(String primary) {
  final parts = primary.split(RegExp(r'[，。；、,.;\s]+')).where((s) => s.isNotEmpty).toList();
  if (parts.isEmpty) return primary;
  final out = <String>[];
  for (final p in parts) {
    if (p.length <= 1) { out.add(p); continue; }
    final idx = (p.length / 2).ceil();
    out.add(p.substring(0, idx) + '___' + p.substring(idx + 1));
  }
  return out.join('，');
}
```

- [ ] **Step 3: 新建 `_GuideView` 组件（递进问答）**

在 `drill_page.dart` 里加 `_GuideView` StatefulWidget，渲染 guide 链的多轮问答：

```dart
class _GuideView extends StatefulWidget {
  const _GuideView({required this.item, required this.ctl});
  final DrillItem item;
  final DrillController ctl;

  @override
  State<_GuideView> createState() => _GuideViewState();
}

class _GuideViewState extends State<_GuideView> {
  int _round = 0;        // 当前第几轮
  bool _revealed = false; // 本轮是否已揭示
  final _fill = TextEditingController();

  GuideStep get _current => widget.item.guideSteps[_round.clamp(0, widget.item.guideSteps.length - 1)];

  @override
  void dispose() { _fill.dispose(); super.dispose(); }

  void _answerChoice(int idx) {
    setState(() { _revealed = true; });
  }

  void _submitFill() {
    setState(() { _revealed = true; });
  }

  void _next() {
    if (_round + 1 < widget.item.guideSteps.length) {
      setState(() { _round++; _revealed = false; _fill.clear(); });
    } else {
      widget.ctl.nextItem();
    }
  }

  @override
  Widget build(BuildContext context) {
    final g = _current;
    return _card(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('🔍 第 ${_round + 1}/${widget.item.guideSteps.length} 步 · 一起发现',
              style: const TextStyle(fontSize: 12, color: AppColors.gray, fontWeight: FontWeight.w600)),
          const SizedBox(height: 10),
          Text(g.prompt, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, height: 1.5)),
          if (g.samples.isNotEmpty) ...[
            const SizedBox(height: 10),
            for (final s in g.samples)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(color: AppColors.bg, borderRadius: BorderRadius.circular(8)),
                  child: Text(s, style: const TextStyle(fontSize: 14)),
                ),
              ),
          ],
          const SizedBox(height: 14),
          if (g.isChoice) ...[
            for (var i = 0; i < g.options.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: _revealed ? null : () => _answerChoice(i),
                    style: OutlinedButton.styleFrom(
                      backgroundColor: _revealed && i == g.answerIndex ? AppColors.greenSoft : null,
                      foregroundColor: _revealed && i == g.answerIndex ? AppColors.green : AppColors.ink,
                    ),
                    child: Align(alignment: Alignment.centerLeft, child: Text(g.options[i])),
                  ),
                ),
              ),
          ] else ...[
            TextField(controller: _fill, decoration: const InputDecoration(hintText: '写下你的答案…', border: OutlineInputBorder())),
            const SizedBox(height: 10),
            SizedBox(width: double.infinity, child: FilledButton(onPressed: _revealed ? null : _submitFill, child: const Text('提交'))),
          ],
          if (_revealed) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: AppColors.greenSoft, borderRadius: BorderRadius.circular(10)),
              child: Text('✨ ${g.reveal}', style: const TextStyle(fontSize: 13, height: 1.6, color: AppColors.green)),
            ),
            const SizedBox(height: 12),
            SizedBox(width: double.infinity, child: FilledButton(onPressed: _next, child: const Text('下一步 →'))),
          ],
        ],
      ),
    );
  }
}
```

（`_card`、`AppColors` 已在文件里定义。）

- [ ] **Step 4: 跑 analyze + 全量测试**

Run: `cd student-app && /e/dev/flutter/bin/flutter analyze lib/features/drill/`
Expected: 无 error

Run: `cd student-app && /e/dev/flutter/bin/flutter test`
Expected: 全过（无回归）

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/drill/ui/drill_page.dart
git commit -m "feat(drill): guide 递进问答渲染 + 识记「背」挖空"
```

---

## Task 5: 全量测试 + 自检

- [ ] **Step 1: 全量后端测试**

Run: `cd backend && python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 2: 全量前端测试**

Run: `cd student-app && /e/dev/flutter/bin/flutter test`
Expected: 全部 PASS

- [ ] **Step 3: 提交（如有补测试）**

```bash
git add -A backend/tests/ student-app/test/
git commit -m "test(drill): 递进引导 + 认背测测试补齐"
```

---

## 自审记录

- **Spec 覆盖**：guide 生成→Task1；识记步序→Task2；guide 解析→Task3；guide 渲染+背挖空→Task4；测试→Task5。拆任务/动画/背挖空 AI 优化留后续（spec 明确不做）。
- **类型一致**：`GuideStep`（Task3 定义）在 Task4 使用，字段 prompt/samples/options/answerIndex/answer/reveal/isChoice 一致；`generate_explore_items` 返回 `{guide, classify, trap}`（Task1）与 Task3 解析一致。
- **占位符**：无 TBD/TODO；Task4 的 widget 测试说明改为「analyze + 全量测试 + 手动验证」，已明确不强制 mock Riverpod。
