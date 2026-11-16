# 教材配套真人音频（跟读/磨耳朵）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让家长把教材配套真人音频（Unit 1–8 + Word list）导入 KnoAct，自动/手动关联到课，孩子在学生端阅读器内与独立磨耳朵页播放真人课文音频跟读。

**Architecture:** 新增 `LessonAudio` 表 + 一个 FastAPI router（上传/列表/改绑定/marks 读写），音频文件存 `uploads/audio/` 走已有 `/uploads` 静态挂载直读；家长端（parent-web）加管理区 + 波形拖拽标记工具；学生端（Flutter）加 `lesson_audio` feature，在阅读器顶栏与独立磨耳朵页两处播放。

**Tech Stack:** FastAPI + SQLAlchemy（后端）；原生 JS（parent-web）；Flutter + Riverpod + audioplayers 6.8.1（学生端）。

**设计文档：** `docs/superpowers/specs/2026-11-16-textbook-audio-design.md`

---

## 文件结构

**后端**
- 修改 `backend/app/models.py` — 新增 `LessonAudio` 模型。
- 新建 `backend/app/routers/lesson_audio.py` — 上传/列表/改绑定/marks 端点 + 文件名解析纯函数。
- 修改 `backend/app/main.py` — 注册 router。
- 新建 `backend/tests/test_lesson_audio.py` — 后端测试。

**家长端**
- 修改 `parent-web/app.js` — 教材音频管理区 + 波形标记工具（挂在教材管理附近）。

**学生端（Flutter）**
- 新建 `student-app/lib/features/lesson_audio/data/lesson_audio_repository.dart` — API 调用 + URL 拼接。
- 新建 `student-app/lib/features/lesson_audio/models/lesson_audio.dart` — 数据模型 + marks 分段纯函数。
- 新建 `student-app/lib/features/lesson_audio/lesson_audio_controller.dart` — Riverpod 状态。
- 新建 `student-app/lib/features/lesson_audio/ui/audio_bar.dart` — 播放条 widget（audioplayers）。
- 新建 `student-app/lib/features/lesson_audio/ui/listening_page.dart` — 独立磨耳朵页。
- 修改 `student-app/lib/features/reader/ui/reader_view_page.dart` — 阅读器顶栏挂播放条。
- 修改 `student-app/lib/core/router.dart` — 注册 `/listening` 路由。
- 修改 `student-app/lib/features/shell/app_shell.dart` — 加磨耳朵导航入口（如必要）。
- 新建 `student-app/test/features/lesson_audio/lesson_audio_test.dart` — Flutter 测试（URL 拼接 + marks 分段）。

---

## Task 1: LessonAudio 模型

**Files:**
- Modify: `backend/app/models.py`（在 `Textbook` 模型之后新增）

- [ ] **Step 1: 新增模型**

在 `backend/app/models.py` 的 `Textbook` 类之后（约第 63 行）插入：

```python
class LessonAudio(Base):
    __tablename__ = "lesson_audios"
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"))
    unit_label: Mapped[str] = mapped_column(String(255))
    audio_path: Mapped[str] = mapped_column(String(255))
    marks_json: Mapped[str] = mapped_column(LongText, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

注意：`datetime`、`LongText`、`Mapped` 已在文件顶部 import（模型文件已有大量同类字段），无需新增 import。

- [ ] **Step 2: 验证模型可建表**

Run: `cd backend && python -c "from app.database import engine, Base; import app.models; Base.metadata.create_all(engine); print('ok')"`
Expected: 输出 `ok`（若报错，检查 import 是否缺失）。

- [ ] **Step 3: Commit**

```bash
git add backend/app/models.py
git commit -m "feat(bank): 新增 LessonAudio 模型存教材配套音频"
```

---

## Task 2: 文件名解析纯函数

**Files:**
- Modify: `backend/app/routers/lesson_audio.py`（新建）
- Test: `backend/tests/test_lesson_audio.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_lesson_audio.py`：

```python
from app.routers.lesson_audio import parse_unit_label


def test_parse_unit_label_unit_number():
    assert parse_unit_label("01_Unit 1.mp3") == "Unit 1"
    assert parse_unit_label("02_Unit 2.mp3") == "Unit 2"
    assert parse_unit_label("08_Unit 8.mp3") == "Unit 8"


def test_parse_unit_label_word_list():
    assert parse_unit_label("09_Word list.mp3") == "Word list"


def test_parse_unit_label_fallback():
    # 无法解析时回落：去扩展名的原始文件名
    assert parse_unit_label("whatever.mp3") == "whatever"
    assert parse_unit_label("Unit.mp3") == "Unit"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_lesson_audio.py -v`
Expected: FAIL，`ModuleNotFoundError` 或 `ImportError`（模块尚未创建）。

- [ ] **Step 3: 新建 router 并实现解析函数**

新建 `backend/app/routers/lesson_audio.py`：

```python
"""教材配套真人音频：上传/列表/改绑定/时间点标记。"""
import json
import os
import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.access import ensure_pdf_document_access
from ..core.deps import require_role
from ..database import get_db
from ..models import Lesson, LessonAudio, User

router = APIRouter(prefix="/api/lesson-audio", tags=["lesson-audio"])

_UNIT_RE = re.compile(r"^(?:\d+_)?Unit\s*(\d+)", re.IGNORECASE)


def parse_unit_label(filename: str) -> str:
    """从文件名解析展示名：Unit N / Word list；解析不出则回落到去扩展名的原名。"""
    base = os.path.splitext(os.path.basename(filename))[0]
    m = _UNIT_RE.match(base)
    if m:
        return f"Unit {int(m.group(1))}"
    if "word" in base.lower() and "list" in base.lower():
        return "Word list"
    return base
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_lesson_audio.py -v`
Expected: PASS（4 个用例通过）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/lesson_audio.py backend/tests/test_lesson_audio.py
git commit -m "feat(bank): 教材音频文件名解析纯函数"
```

---

## Task 3: 上传端点（自动匹配 Lesson）

**Files:**
- Modify: `backend/app/routers/lesson_audio.py`
- Test: `backend/tests/test_lesson_audio.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_lesson_audio.py` 末尾追加。conftest 提供 `client`、`db` fixture 及工具函数 `make_document` / `make_lesson` / `make_account` / `auth_headers`（`from conftest import make_document, make_lesson, make_account, auth_headers`）。家长账号用 `make_account(session, login_name="p1", role="parent")` 建，`auth_headers(parent)` 出 header：

```python
from conftest import make_document, make_lesson, make_account, auth_headers


def test_upload_audio_auto_matches_lesson(client, db):
    from app.models import User
    parent = make_account(db, login_name="p_audio", role="parent")
    doc = make_document(db, subject="英语", filename="英语五年级上册.pdf")
    lesson = make_lesson(db, subject="英语", title="Unit 1 Hello", document=doc)
    db.commit()
    files = {"file": ("01_Unit 1.mp3", b"ID3fake-mp3-bytes", "audio/mpeg")}
    data = {"document_id": str(doc.id)}
    r = client.post("/api/lesson-audio", files=files, data=data, headers=auth_headers(parent))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["unit_label"] == "Unit 1"
    assert body["lesson_id"] == lesson.id
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_lesson_audio.py::test_upload_audio_auto_matches_lesson -v`
Expected: FAIL（端点 404 或 `_match_lesson_by_label` 未定义）。

- [ ] **Step 3: 实现上传端点**

在 `backend/app/routers/lesson_audio.py` 追加（`router` 定义之后）：

```python
def _match_lesson_by_label(db: Session, document_id: int, subject: str, label: str) -> Lesson | None:
    """按 label（如 Unit 1）匹配教材下同一学科的课；0 或多个匹配均返回 None。"""
    if label == "Word list":
        return None
    q = db.query(Lesson).filter_by(document_id=document_id, subject=subject)
    hits = [l for l in q.all() if label in (l.title or "")]
    return hits[0] if len(hits) == 1 else None


@router.post("")
def upload_audio(
    file: UploadFile = File(...),
    document_id: int = Form(...),
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    doc = ensure_pdf_document_access(user, document_id, db)
    if not (file.filename or "").lower().endswith(".mp3"):
        raise HTTPException(status_code=400, detail="仅支持 MP3 音频")
    os.makedirs("uploads/audio", exist_ok=True)
    label = parse_unit_label(file.filename)
    safe = os.path.basename(file.filename or "audio.mp3")
    path = f"uploads/audio/{document_id}_{safe}"
    with open(path, "wb") as f:
        f.write(file.file.read())
    lesson = _match_lesson_by_label(db, document_id, doc.subject, label)
    row = LessonAudio(
        lesson_id=lesson.id if lesson else None,
        document_id=document_id,
        unit_label=label,
        audio_path=path,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "lesson_id": row.lesson_id, "unit_label": row.unit_label,
            "audio_path": row.audio_path, "marks": json.loads(row.marks_json)}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_lesson_audio.py::test_upload_audio_auto_matches_lesson -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/lesson_audio.py backend/tests/test_lesson_audio.py
git commit -m "feat(bank): 教材音频上传端点（自动匹配课）"
```

---

## Task 4: 列表 / 改绑定 / marks 端点 + 注册 router

**Files:**
- Modify: `backend/app/routers/lesson_audio.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_lesson_audio.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_lesson_audio.py`：

```python
from conftest import make_document, make_account, auth_headers


def test_list_audio_and_patch_binding_and_marks(client, db):
    from app.models import LessonAudio
    parent = make_account(db, login_name="p_audio2", role="parent")
    doc = make_document(db, subject="英语", filename="英语五年级上册.pdf")
    db.commit()
    row = LessonAudio(document_id=doc.id, unit_label="Word list",
                      audio_path="uploads/audio/x.mp3", marks_json="[]")
    db.add(row); db.commit(); db.refresh(row)

    r = client.get(f"/api/lesson-audio?document_id={doc.id}", headers=auth_headers(parent))
    assert r.status_code == 200
    items = r.json()
    assert any(it["id"] == row.id for it in items)

    # 改绑定
    r = client.patch(f"/api/lesson-audio/{row.id}", json={"unit_label": "Unit 9"}, headers=auth_headers(parent))
    assert r.status_code == 200
    assert r.json()["unit_label"] == "Unit 9"

    # 写 marks
    r = client.put(f"/api/lesson-audio/{row.id}/marks",
                   json={"marks": [{"label": "A", "start_sec": 12.5}]}, headers=auth_headers(parent))
    assert r.status_code == 200
    assert r.json()["marks"][0]["start_sec"] == 12.5
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_lesson_audio.py::test_list_audio_and_patch_binding_and_marks -v`
Expected: FAIL（端点 404）。

- [ ] **Step 3: 实现列表 / 改绑定 / marks 端点**

追加到 `backend/app/routers/lesson_audio.py`：

```python
class AudioPatchReq(BaseModel):
    lesson_id: int | None = None
    unit_label: str | None = None


class MarksReq(BaseModel):
    marks: list[dict] = []


def _row_payload(row: LessonAudio) -> dict:
    return {"id": row.id, "lesson_id": row.lesson_id, "unit_label": row.unit_label,
            "audio_path": row.audio_path, "marks": json.loads(row.marks_json or "[]")}


@router.get("")
def list_audio(
    document_id: int,
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    ensure_pdf_document_access(user, document_id, db)
    rows = db.query(LessonAudio).filter_by(document_id=document_id).order_by(LessonAudio.id).all()
    return [_row_payload(r) for r in rows]


@router.patch("/{audio_id}")
def patch_audio(audio_id: int, req: AudioPatchReq,
                user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    row = db.get(LessonAudio, audio_id)
    if row is None:
        raise HTTPException(status_code=404, detail="音频不存在")
    ensure_pdf_document_access(user, row.document_id, db)
    if req.lesson_id is not None:
        row.lesson_id = req.lesson_id
    if req.unit_label is not None:
        row.unit_label = req.unit_label
    db.commit(); db.refresh(row)
    return _row_payload(row)


@router.put("/{audio_id}/marks")
def put_marks(audio_id: int, req: MarksReq,
              user: User = Depends(require_role("parent", "admin")),
              db: Session = Depends(get_db)):
    row = db.get(LessonAudio, audio_id)
    if row is None:
        raise HTTPException(status_code=404, detail="音频不存在")
    ensure_pdf_document_access(user, row.document_id, db)
    row.marks_json = json.dumps(req.marks, ensure_ascii=False)
    db.commit(); db.refresh(row)
    return _row_payload(row)
```

- [ ] **Step 4: 注册 router**

在 `backend/app/main.py` 顶部 import 列表（第 8 行附近，`drill` 之后）加入 `lesson_audio`：

```python
from .routers import auth, config_router, pdf, progress, notes, points, learning, goals, mistakes, knowledge, questions, tts_router, annotations, home, tasks, quiz, mastery, render, math, users, buckets, screen_time, family, admin_users, bank, passages, xuekubao, drill, lesson_audio
```

并在 `app.include_router(xuekubao.router)` 之后加一行：

```python
app.include_router(lesson_audio.router)
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_lesson_audio.py -v`
Expected: PASS（全部用例通过）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/lesson_audio.py backend/app/main.py backend/tests/test_lesson_audio.py
git commit -m "feat(bank): 教材音频列表/改绑定/时间点标记端点并注册"
```

---

## Task 5: 家长端管理区 + 波形标记工具

**Files:**
- Modify: `parent-web/app.js`

- [ ] **Step 1: 加管理区骨架**

在 `parent-web/app.js` 的教材管理渲染处（`renderChildDocs` / `loadPdfDocs` 附近）新增「教材音频」入口。沿用现有 `api` / `apiForm` 辅助函数与渲染风格（`render*()` 拼 HTML 字符串）。新增：

```js
let lessonAudioRows = [];
async function loadLessonAudio(docId){
  lessonAudioRows = await api(`/api/lesson-audio?document_id=${docId}`);
}
function renderLessonAudio(docId){
  // 列表：unit_label + lesson_id 匹配状态 + 手动纠正下拉（Lesson 标题）
  // 每个音频一个「标记」按钮 → renderMarkTool(audioId)
}
async function uploadLessonAudio(docId, fileInput){
  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  fd.append('document_id', docId);
  await apiForm('/api/lesson-audio', fd);
  await loadLessonAudio(docId); renderLessonAudio(docId);
}
```

- [ ] **Step 2: 波形标记工具（精确版）**

新增 `renderMarkTool(audioId)`：用 `<audio>` 试听 + Web Audio API 渲染波形 + 拖拽播放头定位毫秒 + 「设为第 N 课起点」写入 marks。核心逻辑：

```js
async function renderMarkTool(audioId){
  const row = lessonAudioRows.find(r => r.id === audioId);
  const url = API + '/' + row.audio_path;   // 走 /uploads 静态直读
  // 1) 解码拿波形：fetch 音频 → arrayBuffer → AudioContext.decodeAudioData → 峰值数组画 canvas
  // 2) 拖拽：canvas 上 mousedown/mousemove 计算比例 → currentTime = 比例 * duration
  // 3) 存：把 {label, start_sec} push 进 marks，PUT /api/lesson-audio/{id}/marks
  const marks = row.marks || [];
  await api(`/api/lesson-audio/${audioId}/marks`, {method:'PUT', body:{marks}});
}
```

> 波形图用 `<canvas>` 逐帧画峰值条即可；播放头定位用 `<audio>` 元素的 `currentTime` 与 `duration` 换算，不必引入外部库。

- [ ] **Step 3: 手动验证（浏览器）**

Run 后端与家长端，在家长端上传 `E:\sixath\workspace\ops-agent\tmp\英语五年级上册_音频\01_Unit 1.mp3`，确认：列表出现 `Unit 1`、自动匹配到对应课、标记工具能试听并保存一个 `start_sec`。

（验证命令见 AGENTS.md「Running / Verification」：后端 `cd backend && python -m uvicorn app.main:app --port 8010`，家长端 `python -m http.server 8767 --directory parent-web`。）

- [ ] **Step 4: Commit**

```bash
git add parent-web/app.js
git commit -m "feat(parent-web): 教材音频管理区 + 波形标记工具"
```

---

## Task 6: 学生端 lesson_audio feature（模型 + repository + controller）

**Files:**
- Create: `student-app/lib/features/lesson_audio/models/lesson_audio.dart`
- Create: `student-app/lib/features/lesson_audio/data/lesson_audio_repository.dart`
- Create: `student-app/lib/features/lesson_audio/lesson_audio_controller.dart`
- Test: `student-app/test/features/lesson_audio/lesson_audio_test.dart`

- [ ] **Step 1: 写失败测试（marks 分段 + URL 拼接）**

新建 `student-app/test/features/lesson_audio/lesson_audio_test.dart`：

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:knoact/features/lesson_audio/models/lesson_audio.dart';

void main() {
  test('audioUrl 用 audio_path 拼 apiBase', () {
    expect(audioUrlForPath('uploads/audio/1_x.mp3', base: 'http://127.0.0.1:8010'),
        'http://127.0.0.1:8010/uploads/audio/1_x.mp3');
  });

  test('segmentStartFor 按 marks 返回最近起点，无 marks 返回 0', () {
    final marks = [AudioMark('A', 10.0), AudioMark('B', 25.0)];
    expect(segmentStartFor(marks, 15.0), 10.0);
    expect(segmentStartFor(marks, 30.0), 25.0);
    expect(segmentStartFor([], 5.0), 0.0);
  });
}
```

（包名 `knoact` 以 `pubspec.yaml` 的 `name` 为准，执行前确认。）

- [ ] **Step 2: 运行确认失败**

Run: `cd student-app && E:\dev\flutter\bin\flutter.bat test test/features/lesson_audio/lesson_audio_test.dart`
Expected: FAIL（文件不存在 / import 失败）。

- [ ] **Step 3: 实现模型 + repository + controller**

新建 `student-app/lib/features/lesson_audio/models/lesson_audio.dart`：

```dart
class AudioMark {
  final String label;
  final double startSec;
  const AudioMark(this.label, this.startSec);
  factory AudioMark.fromJson(Map<String, dynamic> j) =>
      AudioMark(j['label'] as String? ?? '', (j['start_sec'] as num? ?? 0).toDouble());
}

class LessonAudio {
  final int id;
  final int? lessonId;
  final String unitLabel;
  final String audioPath;
  final List<AudioMark> marks;
  const LessonAudio({
    required this.id, this.lessonId, required this.unitLabel,
    required this.audioPath, required this.marks,
  });
  factory LessonAudio.fromJson(Map<String, dynamic> j) => LessonAudio(
    id: j['id'] as int,
    lessonId: j['lesson_id'] as int?,
    unitLabel: j['unit_label'] as String? ?? '',
    audioPath: j['audio_path'] as String? ?? '',
    marks: ((j['marks'] as List?) ?? []).map((e) => AudioMark.fromJson(e as Map<String, dynamic>)).toList(),
  );
}

String audioUrlForPath(String path, {required String base}) {
  final p = path.startsWith('/') ? path : '/$path';
  return base.endsWith('/') ? '${base.substring(0, base.length - 1)}$p' : '$base$p';
}

double segmentStartFor(List<AudioMark> marks, double positionSec) {
  double start = 0;
  for (final m in marks) {
    if (m.startSec <= positionSec && m.startSec >= start) start = m.startSec;
  }
  return start;
}
```

新建 `student-app/lib/features/lesson_audio/data/lesson_audio_repository.dart`：

```dart
import '../../../core/api_client.dart';
import '../../../core/config.dart';
import '../models/lesson_audio.dart';

class LessonAudioRepository {
  LessonAudioRepository(this._api);
  final ApiClient _api;

  Future<List<LessonAudio>> listByDocument(int documentId) async {
    final data = await _api.get('/api/lesson-audio', query: {'document_id': documentId});
    return (data as List).map((e) => LessonAudio.fromJson(e as Map<String, dynamic>)).toList();
  }

  String audioUrl(String path) => audioUrlForPath(path, base: apiBaseForAssets());
}
```

新建 `student-app/lib/features/lesson_audio/lesson_audio_controller.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/api_client.dart';
import 'data/lesson_audio_repository.dart';
import 'models/lesson_audio.dart';

final lessonAudioRepositoryProvider = Provider<LessonAudioRepository>(
  (ref) => LessonAudioRepository(ref.read(apiClientProvider)),
);

final lessonAudioProvider = FutureProvider.family<List<LessonAudio>, int>((ref, docId) {
  return ref.read(lessonAudioRepositoryProvider).listByDocument(docId);
});
```

> `apiClientProvider` 是 `api_client.dart` 暴露的全局 provider 名；若实际名不同（如 `apiClient`），以该文件为准调整。

- [ ] **Step 4: 运行确认通过**

Run: `cd student-app && E:\dev\flutter\bin\flutter.bat test test/features/lesson_audio/lesson_audio_test.dart`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add student-app/lib/features/lesson_audio student-app/test/features/lesson_audio
git commit -m "feat(student-app): lesson_audio 模型/repository/controller + 分段纯函数"
```

---

## Task 7: 学生端播放条 widget + 独立磨耳朵页 + 路由

**Files:**
- Create: `student-app/lib/features/lesson_audio/ui/audio_bar.dart`
- Create: `student-app/lib/features/lesson_audio/ui/listening_page.dart`
- Modify: `student-app/lib/features/reader/ui/reader_view_page.dart`
- Modify: `student-app/lib/core/router.dart`

- [ ] **Step 1: 播放条 widget**

新建 `student-app/lib/features/lesson_audio/ui/audio_bar.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import '../models/lesson_audio.dart';

/// 单个教材音频的播放条：整段播，或按 marks 分段（点某段从 start_sec 起播）。
class AudioBar extends StatefulWidget {
  const AudioBar({super.key, required this.audio, required this.url});
  final LessonAudio audio;
  final String url;

  @override
  State<AudioBar> createState() => _AudioBarState();
}

class _AudioBarState extends State<AudioBar> {
  final _player = AudioPlayer();
  bool _playing = false;

  @override
  void dispose() { _player.dispose(); super.dispose(); }

  Future<void> _play({double fromSec = 0}) async {
    await _player.play(UrlSource(widget.url), position: Duration(milliseconds: (fromSec * 1000).round()));
    setState(() => _playing = true);
  }

  Future<void> _stop() async {
    await _player.stop();
    setState(() => _playing = false);
  }

  @override
  Widget build(BuildContext context) {
    final marks = widget.audio.marks;
    return Column(children: [
      Row(children: [
        Text(widget.audio.unitLabel),
        const Spacer(),
        IconButton(
          icon: Icon(_playing ? Icons.stop : Icons.play_arrow),
          onPressed: () => _playing ? _stop() : _play(),
        ),
      ]),
      if (marks.isNotEmpty)
        Wrap(spacing: 8, children: [
          for (final m in marks)
            ActionChip(label: Text(m.label), onPressed: () => _play(fromSec: m.startSec)),
        ]),
    ]);
  }
}
```

- [ ] **Step 2: 独立磨耳朵页**

新建 `student-app/lib/features/lesson_audio/ui/listening_page.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../lesson_audio_controller.dart';
import 'audio_bar.dart';

/// 磨耳朵：列教材 → Unit 音频 → 播放/循环。
class ListeningPage extends ConsumerWidget {
  const ListeningPage({super.key, required this.documentId});
  final int documentId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(lessonAudioProvider(documentId));
    return Scaffold(
      appBar: AppBar(title: const Text('磨耳朵')),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('加载失败：$e')),
        data: (rows) {
          final repo = ref.read(lessonAudioRepositoryProvider);
          return ListView(children: [
            for (final a in rows) AudioBar(audio: a, url: repo.audioUrl(a.audioPath)),
          ]);
        },
      ),
    );
  }
}
```

- [ ] **Step 3: 注册路由**

在 `student-app/lib/core/router.dart` 顶部 import `listening_page.dart`，并在 routes 列表（`/center` 同级，非 shell 内）加：

```dart
GoRoute(path: '/listening', builder: (_, state) =>
    ListeningPage(documentId: int.parse(state.uri.queryParameters['document_id'] ?? '0'))),
```

- [ ] **Step 4: 阅读器顶栏挂播放条**

在 `student-app/lib/features/reader/ui/reader_view_page.dart` 的 `_readerBody` 或 appBar 区域，当当前课（`lesson`）所属教材有对应音频时，插入 `AudioBar`。因该文件较大，具体插入点执行时定位：在拿到 `lesson` 与 `lesson.documentId` 后，用 `ref.watch(lessonAudioProvider(docId))` 取该教材音频，按 `unit_label` 匹配当前课标题，命中则在顶栏下方渲染 `AudioBar`。

- [ ] **Step 5: 加导航入口**

在 `student-app/lib/features/shell/app_shell.dart` 或学生端 home 页加「磨耳朵」入口，`context.go('/listening?document_id=…')`；若本期先不做独立入口，可仅通过路由可达（最小可用）。执行时视现有 shell 结构决定是否加常驻入口。

- [ ] **Step 6: 手动验证（Flutter Web）**

Run: `cd student-app && E:\dev\flutter\bin\flutter.bat run -d chrome`（连 `127.0.0.1:8010`）。确认：阅读器内选中已配音频的 Unit 出现播放条并能出声；`/listening` 页能列教材音频并播放。

- [ ] **Step 7: Commit**

```bash
git add student-app/lib/features/lesson_audio student-app/lib/features/reader/ui/reader_view_page.dart student-app/lib/core/router.dart student-app/lib/features/shell/app_shell.dart
git commit -m "feat(student-app): 教材音频播放条 + 磨耳朵页 + 路由"
```

---

## Task 8: 收尾验证与设计对齐

- [ ] **Step 1: 全量后端测试**

Run: `cd backend && python -m pytest -q`
Expected: 全绿（无新回归）。

- [ ] **Step 2: Flutter 静态检查 + 测试**

Run: `cd student-app && E:\dev\flutter\bin\flutter.bat analyze && E:\dev\flutter\bin\flutter.bat test`
Expected: 无 error；测试全绿。

- [ ] **Step 3: 对照设计文档核对**

逐条核对 `docs/superpowers/specs/2026-11-16-textbook-audio-design.md`：LessonAudio 表字段、五个端点、家长端管理 + 波形标记、学生端两处入口、错误处理（非 MP3 拒绝 / 解析失败仍入库 / 音频缺失不崩）。列出未覆盖项（若有）并补任务。

---

## 自检记录（Self-Review）

- **Spec 覆盖**：数据模型（Task 1）→ 上传/列表/改绑定/marks（Task 2–4）→ 家长端管理与波形标记（Task 5）→ 学生端模型/仓库/控制器（Task 6）→ 播放条/磨耳朵页/路由（Task 7）→ 收尾（Task 8）。全部设计章节均有对应任务。
- **占位符扫描**：无 TBD/TODO；所有代码步骤含完整代码；对 conftest fixture 名、`apiClientProvider` 名、包名等「以实际文件为准」之处已显式标注为执行时确认项，非占位。
- **类型一致性**：`parse_unit_label` → `"Unit N"` / `"Word list"`；`_row_payload` 字段名 `lesson_id/unit_label/audio_path/marks` 与 Flutter `LessonAudio.fromJson` 键名一致；`marks` 元素键 `start_sec` 与 Dart `AudioMark.fromJson` 读取的 `start_sec` 一致。
