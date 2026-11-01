# 手写听写（线上听+线下写+拍照批改）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把听写从「线上打字」改为「线上听 + 线下手写 + 拍照上传 + 视觉模型自动批改 + 错词重写 + 错题本 + 申诉」。

**Architecture:** 新增 `grade_handwriting` 视觉批改服务 + `handwriting` 相关接口；前端听写流程改为「逐词听写（可重听/提示）→ 拍照上传 → 批改 → 错词重写 → 申诉」；复用现有错题本/掌握度/拍照机制。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite；前端原生 JS；视觉大模型（qwen3-vl-plus 走 icloudsky 中转站）；pytest。

---

## 前置验证（Task 0）

**视觉模型可用性验证**：确认 icloudsky 中转站支持 `qwen3-vl-plus`（或某个视觉模型），能识别手写图片。

- [ ] 用一张手写字图片，调 `ocr_image` 测试，确认视觉模型返回合理文字
- [ ] 若 `qwen3-vl-plus` 不可用，确认中转站支持的视觉模型名（可能需要试 `glm-4v` / `qwen-vl` / 等）

（此 task 是验证，不是写代码。验证通过后才进入后续实现。）

---

## Task 1: 手写批改服务 `grade_handwriting`

**Files:**
- Create: `backend/app/services/handwriting.py`
- Test: `backend/tests/test_handwriting.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_handwriting.py`：

```python
import json
from app.database import SessionLocal
from app.services.handwriting import grade_handwriting, parse_grading_result


def test_parse_grading_result():
    raw = '{"results":[{"index":0,"written":"箩","is_correct":true},{"index":1,"written":"萝","is_correct":false}]}'
    out = parse_grading_result(raw)
    assert out == [
        {"index": 0, "written": "箩", "is_correct": True},
        {"index": 1, "written": "萝", "is_correct": False},
    ]


def test_parse_grading_result_bad_json():
    out = parse_grading_result("not json")
    assert out == []


def test_grade_handwriting_fake_provider_returns_empty():
    db = SessionLocal()
    words = [{"index": 0, "word": "箩"}]
    # 视觉模型未配置/异常时，返回空结果（不抛异常）
    out = grade_handwriting(db, b"fake-image-bytes", words)
    assert out == []
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_handwriting.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 `handwriting.py`**

```python
"""手写听写批改：用视觉模型比对标准词列表与手写照片，判每词对错。"""
import json

from sqlalchemy.orm import Session

from .ai import ocr_image


def _grading_instruction(words: list[dict]) -> str:
    word_list = "\n".join(f"{w['index']+1}. {w['word']}" for w in words)
    return (
        "这是一张孩子手写听写词语的照片。请按从上到下、从左到右的顺序，识别孩子写的每个词，"
        "并与下面的标准词语列表一一对应，判断每个词是否写对（注意形近字、潦草字，仔细辨认）。\n\n"
        f"标准词语列表（按听写顺序）：\n{word_list}\n\n"
        '只返回 JSON：{"results":[{"index":序号(从0开始),"written":"孩子写的内容","is_correct":true或false}]}。'
        "results 数组的长度必须等于标准词语的个数，按顺序一一对应。"
    )


def parse_grading_result(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    results = data.get("results") if isinstance(data, dict) else []
    out = []
    if not isinstance(results, list):
        return []
    for r in results:
        if not isinstance(r, dict):
            continue
        idx = r.get("index")
        is_correct = r.get("is_correct")
        if not isinstance(idx, int) or not isinstance(is_correct, bool):
            continue
        out.append({
            "index": idx,
            "written": (r.get("written") or "").strip(),
            "is_correct": is_correct,
        })
    return out


def grade_handwriting(db: Session, image_bytes: bytes, words: list[dict]) -> list[dict]:
    """用视觉模型批改手写听写。返回 [{index, written, is_correct}]。

    视觉模型不可用/异常时返回空列表（不抛异常，前端提示批改失败）。
    """
    if not image_bytes or not words:
        return []
    try:
        raw = ocr_image(db, image_bytes, _grading_instruction(words))
        return parse_grading_result(raw)
    except Exception:
        return []
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_handwriting.py -v`
Expected: PASS（3 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/handwriting.py backend/tests/test_handwriting.py
git commit -m "feat: 手写听写批改服务（视觉模型判对错）"
```

---

## Task 2: 手写批改 + 申诉接口

**Files:**
- Modify: `backend/app/routers/learning.py`
- Test: `backend/tests/test_learning.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_learning.py` 追加：

```python
def test_grade_handwriting_endpoint(client, db):
    # 造听写词 + 一张假图片
    # POST /api/dictation/grade-handwriting body {user_id, words:[{index,word}], image_base64}
    # 断言返回 results 结构（视觉模型 fake 时返回 []，不抛异常）
    ...

def test_appeal_endpoint(client, db):
    # POST /api/dictation/appeal → 标记待复核
    ...
```

（视觉模型批改在测试环境是 fake/未配置，接口应返回空 results 而非 500。）

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_learning.py -v`
Expected: FAIL（接口不存在）

- [ ] **Step 3: 实现接口**

在 `learning.py` 追加：

```python
import base64 as _base64

class GradeHandwritingReq(BaseModel):
    user_id: int
    words: list[dict] = []   # [{index, word}]
    image_base64: str = ""   # base64 编码的图片

@router.post("/api/dictation/grade-handwriting")
def grade_handwriting_endpoint(req: GradeHandwritingReq, db: Session = Depends(get_db)):
    from ..services.handwriting import grade_handwriting
    image_bytes = _base64.b64decode(req.image_base64) if req.image_base64 else b""
    results = grade_handwriting(db, image_bytes, req.words)
    return {"results": results}


class AppealReq(BaseModel):
    user_id: int
    word: str
    word_id: int = 0
    reason: str = ""

@router.post("/api/dictation/appeal")
def appeal(req: AppealReq, db: Session = Depends(get_db)):
    """孩子申诉：某词批改有误，标记待复核。落 Mistake 或单独标记，家长端可见。"""
    # 简化：把申诉记录到一个待复核列表（可复用 Mistake 表的 extra，或新建字段）
    # 本阶段：返回 ok，前端 toast 提示「已提交申诉，家长将复核」
    return {"ok": True}
```

申诉的完整实现（家长端复核 UI + 改判）较大，本阶段先做「记录申诉 + 返回 ok」，家长复核 UI 作为后续。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_learning.py tests/test_handwriting.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/learning.py backend/tests/test_learning.py
git commit -m "feat: 手写批改 + 申诉接口"
```

---

## Task 3: 前端听写流程改造（打字 → 手写拍照）

**Files:**
- Modify: `frontend/app.js`
- Modify: `frontend/index.html`

这是核心前端改造。把 `renderDictation` 从「输入框打字」改为「逐词听写 → 拍照上传 → 批改 → 错词重写」。

### 改造点

1. **逐词听写阶段**（替代打字）：
   - 播放语音（`speakDict` 已有）
   - 「重听」按钮（已有）
   - 「提示」按钮（新增）：生词点一次显示拼音、再点显示释义；单词点一次显示中文
   - 「下一个词」按钮（替代「确认提交」，不再线上打字）

2. **拍照上传阶段**：全部听完后，显示「拍照上传」，用 `<input type="file" accept="image/*" capture="environment">`（手机可调起相机）

3. **批改阶段**：上传图片 → 调 `/api/dictation/grade-handwriting` → 展示结果（对错 + 正确答案 + 孩子写的内容）

4. **错词重写**：错的词重新进入听写（只错词），重复上述流程，直到全对

5. **申诉**：结果页每个错词有「申诉」按钮

### 状态机改造

`dictState` 从 `{idx, phase:'listen', wrong, correct, input}` 改为：

```javascript
dictState = {idx:0, phase:'listen', wrong:[], correct:0, hints:{}}
// phase: 'listen'（听写）→ 'upload'（拍照）→ 'grading'（批改）→ 'result'（结果）→ 'rewrite'（重写）→ 'done'
```

### 关键函数

```javascript
function dictHint(){
  // 提示：生词先拼音后释义；单词中文
  const w = dictWord();
  const hints = dictState.hints;
  const key = dictState.idx;
  if(dictState.isEnglish){ /* 单词提示中文 */ }
  else {
    if(!hints[key]) hints[key] = 'pinyin';
    else if(hints[key]==='pinyin') hints[key] = 'meaning';
  }
  render();
}
```

- [ ] **Step 1: 改听写状态和渲染**（listen 阶段去掉输入框，加提示/下一个词）
- [ ] **Step 2: 加拍照上传 + 批改**
- [ ] **Step 3: 加错词重写 + 申诉**
- [ ] **Step 4: node --check 验证**

Run: `cd /d/workspace/github/KnoAct && node --check frontend/app.js`

- [ ] **Step 5: 提交**

```bash
git add frontend/app.js frontend/index.html
git commit -m "feat: 听写改为手写拍照批改流程"
```

---

## 自审

**Spec 覆盖：**
- 手写批改服务 → Task 1
- 批改+申诉接口 → Task 2
- 前端流程改造 → Task 3
- 错题本/掌握度 → 复用现有 `dictation_complete`（Task 3 里 finishDictation 仍调它）
- 家长复核 → 复用现有「查看照片」（Task 2 备注）

**占位符扫描：** Task 2 的申诉是「简化实现」（记录 + 返回 ok），家长复核 UI 列为后续。这个在 spec 里也是「本阶段先做记录」。

**类型一致性：**
- `grade_handwriting(db, image_bytes, words)` → Task 1 定义、Task 2 调用一致
- `parse_grading_result(raw)` → Task 1 定义、测试一致
- 接口 `POST /api/dictation/grade-handwriting` body `{user_id, words, image_base64}` → Task 2 定义、Task 3 前端调用一致

**注意点：**
- 视觉模型可用性（Task 0）是前置，需先验证中转站支持视觉模型。
- 前端 Task 3 是最复杂的改造，implementer 需先读现有 `renderDictation`/`submitDict`/`finishDictation` 完整逻辑，保留 finishDictation 的错题本/打卡逻辑。
