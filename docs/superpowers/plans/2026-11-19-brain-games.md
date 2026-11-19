# 思维训练游戏（数独 / 舒尔特方格 / 数字扫雷）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在学生端 Flutter App 里加一个独立「思维训练」入口，孩子可自由玩数独、舒尔特方格、数字扫雷，成绩存后端并可看历史最佳。

**Architecture:** 客户端本地生成题面（纯 Dart，无网络依赖、可单测），后端只新增一张成绩表 `BrainGameResult` 与两个接口（写入成绩 + 聚合统计）。游戏页共用一套顶部栏（返回/标题/难度/计时器/历史最佳），三个游戏各自一个页面 + 一个纯逻辑文件。

**Tech Stack:** FastAPI + SQLAlchemy（后端）、Flutter + Riverpod + go_router（前端）、pytest / flutter_test。

**规格文档：** `docs/superpowers/specs/2026-11-19-brain-games-design.md`

---

## 背景：写代码前必须知道的几件事

1. **学年桶表名是 `school_year_buckets`**，不是 `buckets`。外键写错会让 SQLAlchemy 在
   metadata 解析阶段抛 `NoReferencedTableError`，后端直接起不来、全部 pytest 失败。
2. **`router.dart` 的 redirect 用「精确路径集合」匹配**（`_shellPaths` + 一串 `||` 判断）。
   新增路由必须**逐条**加进去，否则会被弹回 `/home`。
3. **测试库是自动建删的**：`backend/tests/conftest.py` 的 `setup_db` 是 autouse，
   每个用例前后 `drop_all` / `create_all`。新表只需在 `models.py` 里定义，不用写迁移。
4. **`make_account` 不建学年桶**，所以测试里要么自己建 `SchoolYearBucket`，
   要么覆盖到「无桶 → bucket_id 为 NULL」这条分支（本计划 Task 2/3 都有对应用例）。
5. **后端跑命令用 Bash 的 python**（已装依赖）；PowerShell 的 python 是 conda base，没装 sqlalchemy。
   本计划所有后端命令都从 `backend/` 目录跑。
6. **改动前端后**：`flutter analyze` 必须零 issue，`flutter test` 必须全绿。

---

## 文件结构

### 后端（新增/修改）

| 文件 | 职责 |
| --- | --- |
| `backend/app/models.py` | 新增 `BrainGameResult` 表（唯一改动） |
| `backend/app/routers/brain_games.py` | 新增：`POST /result` + `GET /stats` |
| `backend/app/main.py` | import + `include_router(brain_games.router)` |
| `backend/tests/test_brain_games.py` | 新增：写入、聚合、鉴权、非法值 |

### 前端（新增/修改）

| 文件 | 职责 |
| --- | --- |
| `student-app/lib/features/brain_games/logic/sudoku.dart` | 数独规格/生成/校验（纯逻辑） |
| `student-app/lib/features/brain_games/logic/schulte.dart` | 舒尔特方格生成（纯逻辑） |
| `student-app/lib/features/brain_games/logic/minesweeper.dart` | 扫雷棋盘生成/扩散（纯逻辑） |
| `student-app/lib/features/brain_games/data/brain_game_models.dart` | `GameKind` / `Difficulty` / `DifficultyStat` |
| `student-app/lib/features/brain_games/data/brain_game_repository.dart` | 调两个接口 |
| `student-app/lib/features/brain_games/ui/brain_game_shell.dart` | 共用顶部栏、难度分段控件、计时器、结束弹层 |
| `student-app/lib/features/brain_games/ui/sudoku_page.dart` | 数独页 |
| `student-app/lib/features/brain_games/ui/schulte_page.dart` | 舒尔特页 |
| `student-app/lib/features/brain_games/ui/minesweeper_page.dart` | 扫雷页 |
| `student-app/lib/core/router.dart` | 3 条路由 + 3 条白名单 |
| `student-app/lib/features/home/ui/home_page.dart` | 「思维训练」卡片 |
| `student-app/test/features/brain_games/brain_game_test_helpers.dart` | 注入会话的 `pumpBrainGame` + 类型正确的假仓库（三个页面测试共用） |
| `student-app/test/features/brain_games/sudoku_logic_test.dart` | 生成器测试 |
| `student-app/test/features/brain_games/schulte_logic_test.dart` | 生成器测试 |
| `student-app/test/features/brain_games/minesweeper_logic_test.dart` | 棋盘测试 |
| `student-app/test/features/brain_games/brain_game_repository_test.dart` | 仓库测试 |
| `student-app/test/features/home/home_page_test.dart` | 加卡片入口断言 |

---

## Task 1: 后端数据模型 `BrainGameResult`

**Files:**
- Modify: `backend/app/models.py`（文件末尾追加）
- Test: `backend/tests/test_brain_games.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_brain_games.py`：

```python
from datetime import datetime

from app import models  # noqa: F401  确保表已注册


def test_brain_game_result_persists(db):
    from app.models import BrainGameResult, SchoolYearBucket, User

    u = User(name="游戏孩子", role="child")
    db.add(u)
    db.flush()
    bucket = SchoolYearBucket(user_id=u.id, grade=3, school_year="2026-2027", status="active")
    db.add(bucket)
    db.flush()

    db.add(BrainGameResult(
        user_id=u.id, bucket_id=bucket.id, game="sudoku", difficulty="easy",
        duration_ms=82000, moves=30, solved=True,
    ))
    db.commit()

    row = db.query(BrainGameResult).one()
    assert row.game == "sudoku"
    assert row.difficulty == "easy"
    assert row.duration_ms == 82000
    assert row.solved is True
    assert isinstance(row.created_at, datetime)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/test_brain_games.py -v
```

Expected: FAIL，`ImportError: cannot import name 'BrainGameResult' from 'app.models'`

- [ ] **Step 3: 加模型**

在 `backend/app/models.py` **文件末尾**追加：

```python
class BrainGameResult(Base):
    """思维训练小游戏成绩：客户端本地出题，后端只记录结果用于统计最佳。

    不写 AnswerRecord（游戏不是做题，避免污染家长端「当天做题明细」），
    也不涉及积分。
    """
    __tablename__ = "brain_game_results"
    __table_args__ = (
        Index("ix_brain_game_results_user_bucket_game",
              "user_id", "bucket_id", "game", "difficulty"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bucket_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_year_buckets.id"), nullable=True)
    game: Mapped[str] = mapped_column(String(24))        # sudoku | schulte | minesweeper
    difficulty: Mapped[str] = mapped_column(String(12))  # easy | medium | hard
    duration_ms: Mapped[int] = mapped_column(Integer)
    moves: Mapped[int] = mapped_column(Integer, default=0)
    solved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

> `Index` / `String` / `Integer` / `Boolean` / `DateTime` / `ForeignKey` 在 `models.py`
> 顶部已全部 import，无需新增 import。

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/test_brain_games.py -v
```

Expected: PASS（1 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/models.py backend/tests/test_brain_games.py
git commit -m "feat(brain-games): 新增 BrainGameResult 成绩表"
```

---

## Task 2: 后端 `POST /api/brain-games/result`

**Files:**
- Create: `backend/app/routers/brain_games.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_brain_games.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_brain_games.py` **追加**：

```python
def _client_with_router():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.brain_games import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _bound_child():
    """建一个已绑定家长的孩子，返回 (child, child_headers)。"""
    from app.database import SessionLocal
    from conftest import parent_child

    s = SessionLocal()
    parent, child, parent_h, child_h = parent_child(s, "bg")
    s.close()
    return child, child_h


def test_post_result_first_solve_is_best():
    child, h = _bound_child()
    client = _client_with_router()
    r = client.post("/api/brain-games/result", headers=h, json={
        "user_id": child.id, "game": "sudoku", "difficulty": "easy",
        "duration_ms": 82000, "moves": 30, "solved": True,
    })
    assert r.status_code == 200
    assert r.json() == {"ok": True, "is_best": True}


def test_post_result_slower_is_not_best():
    child, h = _bound_child()
    client = _client_with_router()
    base = {"user_id": child.id, "game": "schulte", "difficulty": "easy",
            "duration_ms": 50000, "moves": 9, "solved": True}
    client.post("/api/brain-games/result", headers=h, json=base)
    r = client.post("/api/brain-games/result", headers=h,
                    json={**base, "duration_ms": 60000})
    assert r.json()["is_best"] is False


def test_post_result_faster_is_best():
    child, h = _bound_child()
    client = _client_with_router()
    base = {"user_id": child.id, "game": "schulte", "difficulty": "medium",
            "duration_ms": 60000, "moves": 16, "solved": True}
    client.post("/api/brain-games/result", headers=h, json=base)
    r = client.post("/api/brain-games/result", headers=h,
                    json={**base, "duration_ms": 45000})
    assert r.json()["is_best"] is True


def test_post_result_tie_is_not_best():
    child, h = _bound_child()
    client = _client_with_router()
    base = {"user_id": child.id, "game": "schulte", "difficulty": "hard",
            "duration_ms": 30000, "moves": 25, "solved": True}
    client.post("/api/brain-games/result", headers=h, json=base)
    r = client.post("/api/brain-games/result", headers=h, json=base)
    assert r.json()["is_best"] is False


def test_post_result_failed_game_is_never_best():
    child, h = _bound_child()
    client = _client_with_router()
    r = client.post("/api/brain-games/result", headers=h, json={
        "user_id": child.id, "game": "minesweeper", "difficulty": "easy",
        "duration_ms": 5000, "moves": 3, "solved": False,
    })
    assert r.status_code == 200
    assert r.json()["is_best"] is False


def test_post_result_rejects_invalid_game():
    child, h = _bound_child()
    client = _client_with_router()
    r = client.post("/api/brain-games/result", headers=h, json={
        "user_id": child.id, "game": "tetris", "difficulty": "easy",
        "duration_ms": 1000, "moves": 1, "solved": True,
    })
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_game"


def test_post_result_rejects_invalid_difficulty():
    child, h = _bound_child()
    client = _client_with_router()
    r = client.post("/api/brain-games/result", headers=h, json={
        "user_id": child.id, "game": "sudoku", "difficulty": "insane",
        "duration_ms": 1000, "moves": 1, "solved": True,
    })
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_difficulty"


def test_post_result_forbidden_for_other_family():
    child, _ = _bound_child()
    from app.database import SessionLocal
    from conftest import parent_child

    s = SessionLocal()
    _p, _c, other_parent_h, _other_child_h = parent_child(s, "bg2")
    s.close()

    client = _client_with_router()
    r = client.post("/api/brain-games/result", headers=other_parent_h, json={
        "user_id": child.id, "game": "sudoku", "difficulty": "easy",
        "duration_ms": 1000, "moves": 1, "solved": True,
    })
    assert r.status_code == 403
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/test_brain_games.py -v
```

Expected: 新增用例 FAIL，`ModuleNotFoundError: No module named 'app.routers.brain_games'`

- [ ] **Step 3: 写 router**

新建 `backend/app/routers/brain_games.py`：

```python
"""思维训练小游戏成绩接口：客户端本地出题，后端只存成绩与聚合最佳。

不写 AnswerRecord（游戏不是做题，不污染家长端「当天做题明细」），不涉及积分。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access, require_learning_user, resolve_target_user_id
from ..database import get_db
from ..models import BrainGameResult, User
from ..services.bucket_guard import resolve_bucket_id
from ..services.bucket_service import ensure_bucket

router = APIRouter(prefix="/api/brain-games", tags=["brain-games"])

GAMES = ("sudoku", "schulte", "minesweeper")
DIFFICULTIES = ("easy", "medium", "hard")


class ResultReq(BaseModel):
    user_id: int
    game: str
    difficulty: str
    duration_ms: int
    moves: int = 0
    solved: bool = False


@router.post("/result")
def post_result(req: ResultReq,
                user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    if req.game not in GAMES:
        raise HTTPException(status_code=400, detail={"error": "invalid_game"})
    if req.difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=400, detail={"error": "invalid_difficulty"})

    # 无 active 桶时先兜底建桶，否则成绩写进 NULL 桶、后续 /stats 再也读不到
    ensure_bucket(db, req.user_id)
    bid = resolve_bucket_id(db, req.user_id, None)

    # 必须先查后插：插入后再查会让新记录成为自己的对照，「严格小于」恒为 false
    best = (
        db.query(func.min(BrainGameResult.duration_ms))
        .filter(BrainGameResult.user_id == req.user_id,
                BrainGameResult.bucket_id == bid,
                BrainGameResult.game == req.game,
                BrainGameResult.difficulty == req.difficulty,
                BrainGameResult.solved.is_(True))
        .scalar()
    )
    # solved=False 的局恒不算新纪录
    is_best = bool(req.solved and (best is None or req.duration_ms < best))

    db.add(BrainGameResult(user_id=req.user_id, bucket_id=bid, game=req.game,
                           difficulty=req.difficulty, duration_ms=req.duration_ms,
                           moves=req.moves, solved=req.solved))
    db.commit()
    return {"ok": True, "is_best": is_best}
```

在 `backend/app/main.py` 的 router import 行加上 `brain_games`：

```python
from .routers import auth, config_router, pdf, progress, notes, points, learning, goals, mistakes, knowledge, questions, tts_router, annotations, home, tasks, quiz, mastery, render, math, users, buckets, screen_time, family, admin_users, bank, passages, xuekubao, drill, lesson_audio, knowledge_pool, answer_records, brain_games
```

并在 `app.include_router(answer_records.router)` 后面加一行：

```python
app.include_router(brain_games.router)
```

> 注：测试里用 `FastAPI()` 单独挂 router，不依赖 `main.py` 的装配；
> 但 `main.py` 必须加，否则真实服务没有这两个端点。

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/test_brain_games.py -v
```

Expected: PASS（9 passed：Task 1 模型测试 1 + 本任务 8 条）

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/brain_games.py backend/app/main.py backend/tests/test_brain_games.py
git commit -m "feat(brain-games): 成绩写入接口（is_best 先查后插）"
```

---

## Task 3: 后端 `GET /api/brain-games/stats`

**Files:**
- Modify: `backend/app/routers/brain_games.py`（追加端点）
- Test: `backend/tests/test_brain_games.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_brain_games.py` **追加**：

```python
def _post(client, h, child_id, **kw):
    body = {"user_id": child_id, "game": "sudoku", "difficulty": "easy",
            "duration_ms": 1000, "moves": 1, "solved": True}
    body.update(kw)
    return client.post("/api/brain-games/result", headers=h, json=body)


def test_stats_aggregates_played_solved_best():
    child, h = _bound_child()
    client = _client_with_router()
    _post(client, h, child.id, duration_ms=90000)
    _post(client, h, child.id, duration_ms=70000)
    _post(client, h, child.id, duration_ms=5000, solved=False, moves=2)

    r = client.get(f"/api/brain-games/stats?user_id={child.id}", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["sudoku"]["easy"] == {"best_ms": 70000, "played": 3, "solved": 2}
    # 结构固定包含三个游戏 key
    assert set(body) == {"sudoku", "schulte", "minesweeper"}
    assert body["schulte"] == {}


def test_stats_best_is_null_when_never_solved():
    child, h = _bound_child()
    client = _client_with_router()
    _post(client, h, child.id, game="minesweeper", duration_ms=3000, solved=False, moves=2)

    r = client.get(f"/api/brain-games/stats?user_id={child.id}", headers=h)
    body = r.json()
    assert body["minesweeper"]["easy"] == {"best_ms": None, "played": 1, "solved": 0}


def test_stats_isolated_per_difficulty():
    child, h = _bound_child()
    client = _client_with_router()
    _post(client, h, child.id, difficulty="easy", duration_ms=20000)
    _post(client, h, child.id, difficulty="hard", duration_ms=120000)

    r = client.get(f"/api/brain-games/stats?user_id={child.id}", headers=h)
    body = r.json()["sudoku"]
    assert body["easy"]["best_ms"] == 20000
    assert body["hard"]["best_ms"] == 120000


def test_stats_forbidden_for_other_family():
    child, _ = _bound_child()
    from app.database import SessionLocal
    from conftest import parent_child

    s = SessionLocal()
    _p, _c, other_parent_h, _och = parent_child(s, "bg3")
    s.close()

    client = _client_with_router()
    r = client.get(f"/api/brain-games/stats?user_id={child.id}", headers=other_parent_h)
    assert r.status_code == 403


def test_stats_requires_auth():
    child, _ = _bound_child()
    client = _client_with_router()
    r = client.get(f"/api/brain-games/stats?user_id={child.id}")
    assert r.status_code == 401
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && python -m pytest tests/test_brain_games.py -v -k stats
```

Expected: FAIL，404（端点不存在）

- [ ] **Step 3: 加 stats 端点**

在 `backend/app/routers/brain_games.py` **末尾追加**：

```python
@router.get("/stats")
def stats(user_id: int = Depends(resolve_target_user_id),
          bucket_id: int | None = Query(None),
          _auth: User = Depends(require_learning_user),
          db: Session = Depends(get_db)):
    """按 game × difficulty 聚合：played（含失败）、solved、best_ms（仅通关最小用时）。

    `resolve_target_user_id` 内部已做越权校验（跨家庭 403），无需重复。
    bucket_id 解析为 None 时只聚合 bucket_id IS NULL 的记录（不跨学年串数据）。
    """
    bid = resolve_bucket_id(db, user_id, bucket_id)
    out: dict[str, dict[str, dict]] = {g: {} for g in GAMES}
    rows = (
        db.query(BrainGameResult)
        .filter(BrainGameResult.user_id == user_id,
                BrainGameResult.bucket_id == bid)
        .all()
    )
    for g in GAMES:
        for d in DIFFICULTIES:
            subset = [r for r in rows if r.game == g and r.difficulty == d]
            if not subset:
                continue
            solved = [r for r in subset if r.solved]
            out[g][d] = {
                "best_ms": min((r.duration_ms for r in solved), default=None),
                "played": len(subset),
                "solved": len(solved),
            }
    return out
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && python -m pytest tests/test_brain_games.py -v
```

Expected: PASS（14 passed：9 + 本任务 5 条 stats）

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/brain_games.py backend/tests/test_brain_games.py
git commit -m "feat(brain-games): 成绩统计接口（按 game×difficulty 聚合）"
```

---

## Task 4: 前端数据层（模型 + 仓库）

**Files:**
- Create: `student-app/lib/features/brain_games/data/brain_game_models.dart`
- Create: `student-app/lib/features/brain_games/data/brain_game_repository.dart`
- Test: `student-app/test/features/brain_games/brain_game_repository_test.dart`

- [ ] **Step 1: 写失败测试**

新建 `student-app/test/features/brain_games/brain_game_repository_test.dart`：

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/api_client.dart';
import 'package:student_app/features/brain_games/data/brain_game_models.dart';
import 'package:student_app/features/brain_games/data/brain_game_repository.dart';

class FakeApi implements ApiClient {
  FakeApi({this.statsJson = const {}});

  final Map<String, dynamic> statsJson;
  final posts = <({String path, Object? body})>[];

  @override
  Future<dynamic> post(String path, {Object? body}) async {
    posts.add((path: path, body: body));
    return {'ok': true, 'is_best': true};
  }

  @override
  Future<dynamic> get(String path, {Map<String, dynamic>? query}) async {
    if (path == '/api/brain-games/stats') return statsJson;
    throw ApiException('unexpected path $path');
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test('Difficulty 的 id 与中文标签', () {
    expect(BrainGameDifficulty.easy.id, 'easy');
    expect(BrainGameDifficulty.medium.label, '中等');
    expect(BrainGameDifficulty.values.length, 3);
  });

  test('GameKind 的 id 与接口路径片段一致', () {
    expect(BrainGameKind.sudoku.id, 'sudoku');
    expect(BrainGameKind.schulte.id, 'schulte');
    expect(BrainGameKind.minesweeper.id, 'minesweeper');
    expect(GameKindRoute.pathOf(BrainGameKind.sudoku), '/brain-games/sudoku');
  });

  test('提交成绩会打 /api/brain-games/result 并回传 isBest', () async {
    final api = FakeApi();
    final repo = BrainGameRepository(api);
    final r = await repo.postResult(
      userId: 11,
      kind: BrainGameKind.sudoku,
      difficulty: BrainGameDifficulty.easy,
      durationMs: 82000,
      moves: 30,
      solved: true,
    );
    expect(r.isBest, isTrue);
    expect(api.posts.single.path, '/api/brain-games/result');
    final body = api.posts.single.body as Map<String, dynamic>;
    expect(body['user_id'], 11);
    expect(body['game'], 'sudoku');
    expect(body['difficulty'], 'easy');
    expect(body['duration_ms'], 82000);
    expect(body['moves'], 30);
    expect(body['solved'], true);
  });

  test('解析 stats 为 DifficultyStat 映射', () async {
    final api = FakeApi(statsJson: {
      'sudoku': {
        'easy': {'best_ms': 82000, 'played': 3, 'solved': 2},
      },
      'schulte': <String, dynamic>{},
      'minesweeper': {
        'hard': {'best_ms': null, 'played': 1, 'solved': 0},
      },
    });
    final repo = BrainGameRepository(api);
    final stats = await repo.stats(userId: 11);

    expect(stats[BrainGameKind.sudoku]![BrainGameDifficulty.easy]!.bestMs, 82000);
    expect(stats[BrainGameKind.sudoku]![BrainGameDifficulty.easy]!.played, 3);
    expect(stats[BrainGameKind.schulte], isEmpty);
    expect(stats[BrainGameKind.minesweeper]![BrainGameDifficulty.hard]!.bestMs, isNull);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd student-app && flutter test test/features/brain_games/brain_game_repository_test.dart
```

Expected: FAIL，`Error: Couldn't resolve the package 'student_app/features/brain_games/...'`

- [ ] **Step 3: 写模型**

新建 `student-app/lib/features/brain_games/data/brain_game_models.dart`：

```dart
/// 三个思维训练游戏。
enum BrainGameKind {
  sudoku('sudoku', '数独'),
  schulte('schulte', '舒尔特方格'),
  minesweeper('minesweeper', '数字扫雷');

  const BrainGameKind(this.id, this.label);
  final String id;
  final String label;
}

/// 难度，孩子在游戏内自选。
enum BrainGameDifficulty {
  easy('easy', '简单'),
  medium('medium', '中等'),
  hard('hard', '困难');

  const BrainGameDifficulty(this.id, this.label);
  final String id;
  final String label;
}

/// 路由路径与枚举的对应关系。
class GameKindRoute {
  static String pathOf(BrainGameKind kind) => '/brain-games/${kind.id}';

  static BrainGameKind? fromPath(String path) {
    for (final k in BrainGameKind.values) {
      if (pathOf(k) == path) return k;
    }
    return null;
  }
}

/// 某游戏某难度的历史成绩。
class DifficultyStat {
  const DifficultyStat({required this.bestMs, required this.played, required this.solved});

  /// 通关最小用时；从未通关为 null。
  final int? bestMs;
  final int played;
  final int solved;

  factory DifficultyStat.fromJson(Map<String, dynamic> j) => DifficultyStat(
        bestMs: (j['best_ms'] as num?)?.toInt(),
        played: (j['played'] as num?)?.toInt() ?? 0,
        solved: (j['solved'] as num?)?.toInt() ?? 0,
      );
}

/// stats 的三层结构：game → difficulty → stat
typedef BrainGameStats = Map<BrainGameKind, Map<BrainGameDifficulty, DifficultyStat>>;
```

- [ ] **Step 4: 写仓库**

新建 `student-app/lib/features/brain_games/data/brain_game_repository.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';
import 'brain_game_models.dart';

class BrainGameRepository {
  BrainGameRepository(this._api);

  final ApiClient _api;

  /// 提交一局成绩。`solved=false`（扫雷踩雷）也提交，用于 played 统计。
  Future<({bool ok, bool isBest})> postResult({
    required int userId,
    required BrainGameKind kind,
    required BrainGameDifficulty difficulty,
    required int durationMs,
    required int moves,
    required bool solved,
  }) async {
    final d = asMap(await _api.post('/api/brain-games/result', body: {
      'user_id': userId,
      'game': kind.id,
      'difficulty': difficulty.id,
      'duration_ms': durationMs,
      'moves': moves,
      'solved': solved,
    }));
    return (ok: d['ok'] == true, isBest: d['is_best'] == true);
  }

  /// 拉成绩统计；失败时返回空映射（游戏本身不受影响）。
  Future<BrainGameStats> stats({required int userId, int? bucketId}) async {
    try {
      final raw = asMap(await _api.get('/api/brain-games/stats', query: {
        'user_id': userId,
        'bucket_id': ?bucketId,
      }));
      final out = <BrainGameKind, Map<BrainGameDifficulty, DifficultyStat>>{};
      for (final kind in BrainGameKind.values) {
        final perKind = raw[kind.id];
        if (perKind is! Map) continue;
        final m = <BrainGameDifficulty, DifficultyStat>{};
        for (final diff in BrainGameDifficulty.values) {
          final v = perKind[diff.id];
          if (v is Map) {
            m[diff] = DifficultyStat.fromJson(Map<String, dynamic>.from(v));
          }
        }
        out[kind] = m;
      }
      return out;
    } catch (_) {
      return const {};
    }
  }
}

final brainGameRepositoryProvider =
    Provider<BrainGameRepository>((ref) => BrainGameRepository(ref.watch(apiClientProvider)));
```

- [ ] **Step 5: 跑测试确认通过**

```bash
cd student-app && flutter test test/features/brain_games/brain_game_repository_test.dart
```

Expected: PASS（4 tests）

- [ ] **Step 6: 提交**

```bash
git add student-app/lib/features/brain_games student-app/test/features/brain_games
git commit -m "feat(brain-games): 前端成绩模型与仓库"
```

---

## Task 5: 数独逻辑（纯 Dart）

**Files:**
- Create: `student-app/lib/features/brain_games/logic/sudoku.dart`
- Test: `student-app/test/features/brain_games/sudoku_logic_test.dart`

- [ ] **Step 1: 写失败测试**

新建 `student-app/test/features/brain_games/sudoku_logic_test.dart`：

```dart
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/brain_games/logic/sudoku.dart';

void main() {
  test('三档难度规格正确', () {
    expect(sudokuSpecFor('easy').size, 4);
    expect(sudokuSpecFor('easy').boxRows, 2);
    expect(sudokuSpecFor('easy').boxCols, 2);
    expect(sudokuSpecFor('easy').givens, 8);

    expect(sudokuSpecFor('medium').size, 6);
    expect(sudokuSpecFor('medium').boxRows, 2);
    expect(sudokuSpecFor('medium').boxCols, 3);

    expect(sudokuSpecFor('hard').size, 9);
    expect(sudokuSpecFor('hard').boxRows, 3);
    expect(sudokuSpecFor('hard').boxCols, 3);
    expect(sudokuSpecFor('hard').givens, 34);
  });

  test('生成的解是合法数独（行列宫无重复）', () {
    for (final diff in ['easy', 'medium', 'hard']) {
      final p = generateSudoku(diff, random: Random(7));
      final spec = p.spec;
      final n = spec.size;
      for (var r = 0; r < n; r++) {
        expect(p.solution[r].toSet().length, n, reason: '$diff 第 $r 行有重复');
      }
      for (var c = 0; c < n; c++) {
        final col = [for (var r = 0; r < n; r++) p.solution[r][c]];
        expect(col.toSet().length, n, reason: '$diff 第 $c 列有重复');
      }
      for (var br = 0; br < n; br += spec.boxRows) {
        for (var bc = 0; bc < n; bc += spec.boxCols) {
          final box = <int>[];
          for (var i = 0; i < spec.boxRows; i++) {
            for (var j = 0; j < spec.boxCols; j++) {
              box.add(p.solution[br + i][bc + j]);
            }
          }
          expect(box.toSet().length, n, reason: '$diff 宫 ($br,$bc) 有重复');
        }
      }
    }
  });

  test('给定数数量等于难度上限，且给定格与解一致', () {
    for (final diff in ['easy', 'medium', 'hard']) {
      final p = generateSudoku(diff, random: Random(11));
      var count = 0;
      for (var r = 0; r < p.spec.size; r++) {
        for (var c = 0; c < p.spec.size; c++) {
          if (p.givens[r][c] != 0) {
            count++;
            expect(p.givens[r][c], p.solution[r][c]);
          }
        }
      }
      expect(count, p.spec.givens, reason: '$diff 给定数应为 ${p.spec.givens}');
    }
  });

  test('isSolved：全填且等于解才为真', () {
    final p = generateSudoku('easy', random: Random(3));
    expect(p.isSolved(p.solution), isTrue);

    final wrong = [for (final row in p.solution) List<int>.from(row)];
    wrong[0][0] = wrong[0][0] == 1 ? 2 : 1;
    expect(p.isSolved(wrong), isFalse);

    final partial = [for (final row in p.solution) List<int>.from(row)];
    partial[0][0] = 0;
    expect(p.isSolved(partial), isFalse);
  });

  test('isSolved：填满但与解不同（每行仍无重复）也算未通关', () {
    final p = generateSudoku('easy', random: Random(5));
    final alt = [for (final row in p.solution) List<int>.from(row)];
    // 交换第一行前两列，仍合法但不等同于解
    final t = alt[0][0];
    alt[0][0] = alt[0][1];
    alt[0][1] = t;
    expect(p.isSolved(alt), isFalse);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd student-app && flutter test test/features/brain_games/sudoku_logic_test.dart
```

Expected: FAIL，找不到 `logic/sudoku.dart`

- [ ] **Step 3: 实现数独逻辑**

新建 `student-app/lib/features/brain_games/logic/sudoku.dart`：

```dart
import 'dart:math';

/// 一档数独的盘面规格。
class SudokuSpec {
  const SudokuSpec({
    required this.size,
    required this.boxRows,
    required this.boxCols,
    required this.givens,
  });

  final int size;      // 4 / 6 / 9
  final int boxRows;   // 宫内行数
  final int boxCols;   // 宫内列数
  final int givens;    // 保留的提示数
}

const _specs = <String, SudokuSpec>{
  'easy': SudokuSpec(size: 4, boxRows: 2, boxCols: 2, givens: 8),
  'medium': SudokuSpec(size: 6, boxRows: 2, boxCols: 3, givens: 14),
  'hard': SudokuSpec(size: 9, boxRows: 3, boxCols: 3, givens: 34),
};

/// 按难度 id 取规格；未知难度回落 easy。
SudokuSpec sudokuSpecFor(String difficultyId) => _specs[difficultyId] ?? _specs['easy']!;

class SudokuPuzzle {
  SudokuPuzzle({required this.spec, required this.givens, required this.solution});

  final SudokuSpec spec;

  /// 0 表示空格。
  final List<List<int>> givens;
  final List<List<int>> solution;

  bool isGiven(int row, int col) => givens[row][col] != 0;

  /// 全部填满（无 0）且与解完全一致才通关。
  bool isSolved(List<List<int>> grid) {
    for (var r = 0; r < spec.size; r++) {
      for (var c = 0; c < spec.size; c++) {
        if (grid[r][c] == 0 || grid[r][c] != solution[r][c]) return false;
      }
    }
    return true;
  }
}

List<List<int>> _empty(int size) => List.generate(size, (_) => List.filled(size, 0));

bool _canPlace(List<List<int>> g, SudokuSpec spec, int r, int c, int v) {
  for (var i = 0; i < spec.size; i++) {
    if (g[r][i] == v || g[i][c] == v) return false;
  }
  final br = (r ~/ spec.boxRows) * spec.boxRows;
  final bc = (c ~/ spec.boxCols) * spec.boxCols;
  for (var i = 0; i < spec.boxRows; i++) {
    for (var j = 0; j < spec.boxCols; j++) {
      if (g[br + i][bc + j] == v) return false;
    }
  }
  return true;
}

/// 回溯填满整个盘面（每步候选值随机打乱，保证每次不同）。
bool _fill(List<List<int>> g, SudokuSpec spec, int pos, Random rnd) {
  final n = spec.size;
  if (pos == n * n) return true;
  final r = pos ~/ n;
  final c = pos % n;
  final candidates = List.generate(n, (i) => i + 1)..shuffle(rnd);
  for (final v in candidates) {
    if (!_canPlace(g, spec, r, c, v)) continue;
    g[r][c] = v;
    if (_fill(g, spec, pos + 1, rnd)) return true;
    g[r][c] = 0;
  }
  return false;
}

/// 生成一道题：先造完整解，再随机挖洞到 [SudokuSpec.givens] 个提示数。
/// 不校验唯一解（小学生场景，唯一解非必需）。
SudokuPuzzle generateSudoku(String difficultyId, {Random? random}) {
  final spec = sudokuSpecFor(difficultyId);
  final rnd = random ?? Random();
  final solution = _empty(spec.size);
  _fill(solution, spec, 0, rnd);

  final givens = [for (final row in solution) List<int>.from(row)];
  final cells = List.generate(spec.size * spec.size, (i) => i)..shuffle(rnd);
  var remaining = spec.size * spec.size;
  for (final idx in cells) {
    if (remaining <= spec.givens) break;
    givens[idx ~/ spec.size][idx % spec.size] = 0;
    remaining--;
  }
  return SudokuPuzzle(spec: spec, givens: givens, solution: solution);
}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd student-app && flutter test test/features/brain_games/sudoku_logic_test.dart
```

Expected: PASS（5 tests）

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/brain_games/logic/sudoku.dart student-app/test/features/brain_games/sudoku_logic_test.dart
git commit -m "feat(brain-games): 数独生成与判定逻辑"
```

---

## Task 6: 舒尔特方格逻辑

**Files:**
- Create: `student-app/lib/features/brain_games/logic/schulte.dart`
- Test: `student-app/test/features/brain_games/schulte_logic_test.dart`

- [ ] **Step 1: 写失败测试**

新建 `student-app/test/features/brain_games/schulte_logic_test.dart`：

```dart
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/brain_games/logic/schulte.dart';

void main() {
  test('三档难度方格尺寸正确', () {
    expect(schulteSizeFor('easy'), 3);
    expect(schulteSizeFor('medium'), 4);
    expect(schulteSizeFor('hard'), 5);
    expect(schulteSizeFor('unknown'), 3);
  });

  test('数字集合完整且被打乱', () {
    for (final diff in ['easy', 'medium', 'hard']) {
      final b = generateSchulte(diff, random: Random(42));
      final n = b.size * b.size;
      expect(b.numbers.length, n);
      expect(b.numbers.toSet(), {for (var i = 1; i <= n; i++) i});
      expect(b.max, n);
    }
  });

  test('同一随机种子可复现，不同种子会不同', () {
    final a = generateSchulte('hard', random: Random(1));
    final b = generateSchulte('hard', random: Random(1));
    final c = generateSchulte('hard', random: Random(2));
    expect(a.numbers, b.numbers);
    expect(a.numbers, isNot(c.numbers));
  });

  test('isComplete：全部点完为真', () {
    final b = generateSchulte('easy', random: Random(9));
    expect(b.isComplete({for (var i = 1; i <= b.max; i++) i}), isTrue);
    expect(b.isComplete({for (var i = 1; i < b.max; i++) i}), isFalse);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd student-app && flutter test test/features/brain_games/schulte_logic_test.dart
```

Expected: FAIL，找不到 `logic/schulte.dart`

- [ ] **Step 3: 实现**

新建 `student-app/lib/features/brain_games/logic/schulte.dart`：

```dart
import 'dart:math';

/// 舒尔特方格难度 → 边长。
int schulteSizeFor(String difficultyId) => switch (difficultyId) {
      'medium' => 4,
      'hard' => 5,
      _ => 3,
    };

class SchulteBoard {
  SchulteBoard({required this.size, required this.numbers});

  final int size;

  /// 按行优先铺开的乱序数字（1..size²）。
  final List<int> numbers;

  int get max => size * size;

  /// 已点掉的数字集合 == 全部数字 → 通关。
  bool isComplete(Set<int> cleared) => cleared.length >= max && cleared.containsAll(
        List.generate(max, (i) => i + 1),
      );
}

SchulteBoard generateSchulte(String difficultyId, {Random? random}) {
  final size = schulteSizeFor(difficultyId);
  final n = size * size;
  final numbers = List.generate(n, (i) => i + 1)..shuffle(random ?? Random());
  return SchulteBoard(size: size, numbers: numbers);
}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd student-app && flutter test test/features/brain_games/schulte_logic_test.dart
```

Expected: PASS（4 tests）

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/brain_games/logic/schulte.dart student-app/test/features/brain_games/schulte_logic_test.dart
git commit -m "feat(brain-games): 舒尔特方格生成与判定逻辑"
```

---

## Task 7: 数字扫雷逻辑

**Files:**
- Create: `student-app/lib/features/brain_games/logic/minesweeper.dart`
- Test: `student-app/test/features/brain_games/minesweeper_logic_test.dart`

- [ ] **Step 1: 写失败测试**

新建 `student-app/test/features/brain_games/minesweeper_logic_test.dart`：

```dart
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/brain_games/logic/minesweeper.dart';

void main() {
  test('三档难度规格正确', () {
    expect(minesweeperSpecFor('easy'), (rows: 6, cols: 6, mines: 5));
    expect(minesweeperSpecFor('medium'), (rows: 9, cols: 9, mines: 12));
    expect(minesweeperSpecFor('hard'), (rows: 12, cols: 12, mines: 24));
  });

  test('首点安全：指定格永不是雷', () {
    for (final diff in ['easy', 'medium', 'hard']) {
      for (var seed = 0; seed < 20; seed++) {
        final b = generateMinesweeper(diff, safeIndex: 0, random: Random(seed));
        expect(b.isMine(0), isFalse, reason: '$diff seed=$seed 首点是雷');
      }
    }
  });

  test('雷数正确且相邻计数正确', () {
    final b = generateMinesweeper('easy', safeIndex: 0, random: Random(7));
    expect(b.mines.length, 5);
    final rows = b.rows, cols = b.cols;
    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        if (b.isMineAt(r, c)) continue;
        var n = 0;
        for (var dr = -1; dr <= 1; dr++) {
          for (var dc = -1; dc <= 1; dc++) {
            if (dr == 0 && dc == 0) continue;
            if (b.isMineAt(r + dr, c + dc)) n++;
          }
        }
        expect(b.adjacentAt(r, c), n, reason: '($r,$c) 相邻雷数不对');
      }
    }
  });

  test('越界访问返回 false / -1 而不抛异常', () {
    final b = generateMinesweeper('easy', safeIndex: 0, random: Random(3));
    expect(b.isMineAt(-1, 0), isFalse);
    expect(b.isMineAt(99, 99), isFalse);
    expect(b.adjacentAt(-1, 0), -1);
  });

  test('reveal 空白格扩散，遇数字停止', () {
    final b = generateMinesweeper('easy', safeIndex: 0, random: Random(11));
    final opened = b.reveal(0);
    expect(opened, isNotEmpty);
    expect(opened.contains(0), isTrue);
    // 扩散出来的格子都不能是雷
    for (final i in opened) {
      expect(b.isMine(i), isFalse);
    }
  });

  test('isCleared：所有非雷格开完才算通关', () {
    final b = generateMinesweeper('easy', safeIndex: 0, random: Random(5));
    final allSafe = {for (var i = 0; i < b.rows * b.cols; i++) if (!b.isMine(i)) i};
    expect(b.isCleared(allSafe), isTrue);
    expect(b.isCleared(allSafe.difference({0})), isFalse);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd student-app && flutter test test/features/brain_games/minesweeper_logic_test.dart
```

Expected: FAIL，找不到 `logic/minesweeper.dart`

- [ ] **Step 3: 实现**

新建 `student-app/lib/features/brain_games/logic/minesweeper.dart`：

```dart
import 'dart:math';

/// 一档扫雷的规格。
typedef MinesweeperSpec = ({int rows, int cols, int mines});

MinesweeperSpec minesweeperSpecFor(String difficultyId) => switch (difficultyId) {
      'medium' => (rows: 9, cols: 9, mines: 12),
      'hard' => (rows: 12, cols: 12, mines: 24),
      _ => (rows: 6, cols: 6, mines: 5),
    };

class MinesweeperBoard {
  MinesweeperBoard({
    required this.rows,
    required this.cols,
    required this.mineCount,
    required this.mines,
    required this.adjacent,
  });

  final int rows;
  final int cols;
  final int mineCount;

  /// 雷的位置，index = row * cols + col。
  final Set<int> mines;

  /// -1 表示雷；否则为相邻雷数。
  final List<List<int>> adjacent;

  int get total => rows * cols;

  bool isMine(int index) => mines.contains(index);

  bool isMineAt(int r, int c) {
    if (r < 0 || r >= rows || c < 0 || c >= cols) return false;
    return mines.contains(r * cols + c);
  }

  /// 越界返回 -1（与「雷」同值，调用方需先判断坐标）。
  int adjacentAt(int r, int c) {
    if (r < 0 || r >= rows || c < 0 || c >= cols) return -1;
    return adjacent[r][c];
  }

  /// 点开一格并扩散：0 格自动展开邻居；返回本次新开的所有 index。
  Set<int> reveal(int index) {
    if (isMine(index)) return {};
    final opened = <int>{};
    final stack = <int>[index];
    while (stack.isNotEmpty) {
      final cur = stack.removeLast();
      if (opened.contains(cur)) continue;
      if (isMine(cur)) continue;
      opened.add(cur);
      final r = cur ~/ cols;
      final c = cur % cols;
      if (adjacent[r][c] != 0) continue;
      for (var dr = -1; dr <= 1; dr++) {
        for (var dc = -1; dc <= 1; dc++) {
          if (dr == 0 && dc == 0) continue;
          final nr = r + dr;
          final nc = c + dc;
          if (nr < 0 || nr >= rows || nc < 0 || nc >= cols) continue;
          final ni = nr * cols + nc;
          if (!opened.contains(ni) && !isMine(ni)) stack.add(ni);
        }
      }
    }
    return opened;
  }

  /// 所有非雷格都开完 → 通关。
  bool isCleared(Set<int> opened) {
    for (var i = 0; i < total; i++) {
      if (isMine(i)) continue;
      if (!opened.contains(i)) return false;
    }
    return true;
  }
}

/// 布雷时排除 [safeIndex]，保证首次点击不是雷。
MinesweeperBoard generateMinesweeper(
  String difficultyId, {
  required int safeIndex,
  Random? random,
}) {
  final spec = minesweeperSpecFor(difficultyId);
  final rnd = random ?? Random();
  final total = spec.rows * spec.cols;
  final candidates = List.generate(total, (i) => i)..remove(safeIndex);
  candidates.shuffle(rnd);
  final mines = candidates.take(spec.mines).toSet();

  final adjacent = List.generate(spec.rows, (_) => List.filled(spec.cols, 0));
  for (var r = 0; r < spec.rows; r++) {
    for (var c = 0; c < spec.cols; c++) {
      final i = r * spec.cols + c;
      if (mines.contains(i)) {
        adjacent[r][c] = -1;
        continue;
      }
      var n = 0;
      for (var dr = -1; dr <= 1; dr++) {
        for (var dc = -1; dc <= 1; dc++) {
          if (dr == 0 && dc == 0) continue;
          final nr = r + dr;
          final nc = c + dc;
          if (nr < 0 || nr >= spec.rows || nc < 0 || nc >= spec.cols) continue;
          if (mines.contains(nr * spec.cols + nc)) n++;
        }
      }
      adjacent[r][c] = n;
    }
  }

  return MinesweeperBoard(
    rows: spec.rows,
    cols: spec.cols,
    mineCount: spec.mines,
    mines: mines,
    adjacent: adjacent,
  );
}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd student-app && flutter test test/features/brain_games/minesweeper_logic_test.dart
```

Expected: PASS（6 tests）

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/brain_games/logic/minesweeper.dart student-app/test/features/brain_games/minesweeper_logic_test.dart
git commit -m "feat(brain-games): 扫雷棋盘生成、扩散与判通逻辑"
```

---

## Task 8: 共用顶部栏与计时器

**Files:**
- Create: `student-app/lib/features/brain_games/ui/brain_game_shell.dart`

- [ ] **Step 1: 实现（纯展示组件，由后续页面的 widget 测试间接覆盖）**

新建 `student-app/lib/features/brain_games/ui/brain_game_shell.dart`：

```dart
import 'package:flutter/material.dart';

import '../../../core/theme.dart';
import '../data/brain_game_models.dart';

/// 毫秒 → "mm:ss"（超过 99 分钟按分钟显示）。
String formatGameMs(int ms) {
  final totalSeconds = ms ~/ 1000;
  final m = (totalSeconds ~/ 60).toString().padLeft(2, '0');
  final s = (totalSeconds % 60).toString().padLeft(2, '0');
  return '$m:$s';
}

/// 三个游戏共用的顶栏：返回、标题、难度分段、计时器、历史最佳。
class GameTopBar extends StatelessWidget {
  const GameTopBar({
    super.key,
    required this.title,
    required this.difficulty,
    required this.onDifficultyChanged,
    required this.elapsedMs,
    required this.bestMs,
    this.onRestart,
  });

  final String title;
  final BrainGameDifficulty difficulty;
  final ValueChanged<BrainGameDifficulty> onDifficultyChanged;
  final int elapsedMs;
  final int? bestMs;
  final VoidCallback? onRestart;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [
        IconButton(
          onPressed: () => Navigator.of(context).maybePop(),
          icon: const Icon(Icons.arrow_back),
          tooltip: '返回',
        ),
        Expanded(
          child: Text(title,
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: AppColors.blue.withValues(alpha: .10),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text(
            formatGameMs(elapsedMs),
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              fontFeatures: [FontFeature.tabularFigures()],
            ),
          ),
        ),
        if (onRestart != null)
          IconButton(
            onPressed: onRestart,
            icon: const Icon(Icons.refresh),
            tooltip: '重新开始',
          ),
      ]),
      const SizedBox(height: 4),
      Row(children: [
        Expanded(
          child: SegmentedButton<BrainGameDifficulty>(
            segments: [
              for (final d in BrainGameDifficulty.values)
                ButtonSegment(value: d, label: Text(d.label)),
            ],
            selected: {difficulty},
            showSelectedIcon: false,
            onSelectionChanged: (s) => onDifficultyChanged(s.first),
          ),
        ),
        const SizedBox(width: 12),
        Text(
          bestMs == null ? '最佳 —' : '最佳 ${formatGameMs(bestMs!)}',
          style: const TextStyle(fontSize: 12, color: AppColors.gray),
        ),
      ]),
    ]);
  }
}

/// 结束弹层（通关/失败共用）。
Future<void> showGameResultDialog(
  BuildContext context, {
  required String title,
  required String detail,
  required bool showNewRecord,
  required VoidCallback onRestart,
}) {
  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        Text(detail, textAlign: TextAlign.center),
        if (showNewRecord) ...[
          const SizedBox(height: 8),
          const Text('新纪录！',
              style: TextStyle(color: AppColors.orange, fontWeight: FontWeight.w700)),
        ],
      ]),
      actions: [
        TextButton(
          onPressed: () {
            Navigator.of(ctx).pop();
            Navigator.of(context).maybePop();
          },
          child: const Text('返回'),
        ),
        FilledButton(
          onPressed: () {
            Navigator.of(ctx).pop();
            onRestart();
          },
          child: const Text('再来一局'),
        ),
      ],
    ),
  );
}
```

> **颜色常量只允许用 `AppColors` 里实际存在的 11 个**：
> `blue / blueSoft / green / greenSoft / orange / orangeSoft / gold / bg / ink / gray / line`。
> 没有 `red` / `card` / `white` —— 需要红色/白色时在本文件顶部定义
> `const _gameRed = Color(0xFFC05B4A);` 这样的私有常量（如上方示例），
> **不要往 `theme.dart` 里加新颜色**。

- [ ] **Step 2: 静态检查**

```bash
cd student-app && flutter analyze lib/features/brain_games
```

Expected: `No issues found!`

> 本文件只放**被引用**的东西（`formatGameMs` / `GameTopBar` / `showGameResultDialog`）。
> 不要在这里定义未被使用的颜色常量，否则 `flutter analyze` 会报
> `The declaration '...' isn't referenced`（warning 也会让命令非零退出）。
> `FontFeature` 已由 `material.dart` 导出，**不要**再 `import 'dart:ui'`。

- [ ] **Step 3: 提交**

```bash
git add student-app/lib/features/brain_games/ui/brain_game_shell.dart
git commit -m "feat(brain-games): 共用顶栏/计时器/结束弹层"
```

---

## Task 9: 数独页面

**Files:**
- Create: `student-app/lib/features/brain_games/ui/sudoku_page.dart`
- Test: `student-app/test/features/brain_games/sudoku_page_test.dart`

- [ ] **Step 1: 写失败测试**

新建 `student-app/test/features/brain_games/brain_game_test_helpers.dart`（**必须**先建这个文件，
它提供注入登录会话的 `pumpBrainGame` 与类型正确的假仓库，三个页面测试共用）：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:student_app/features/auth/data/auth_repository.dart';
import 'package:student_app/features/auth/data/session_store.dart';
import 'package:student_app/features/auth/session.dart';
import 'package:student_app/features/brain_games/data/brain_game_models.dart';
import 'package:student_app/features/brain_games/data/brain_game_repository.dart';
import 'package:student_app/features/brain_games/ui/sudoku_page.dart';

import '../auth/session_test.dart' show FakeAuthRepository;

/// 假仓库：返回值类型必须与真实 `BrainGameRepository` 完全一致，
/// 否则 `implements` 直接编译失败（`noSuchMethod` 救不了返回类型不兼容）。
class FakeBrainGameRepo implements BrainGameRepository {
  FakeBrainGameRepo({this.statsResult = const {}, this.best = false});

  final BrainGameStats statsResult;
  final bool best;
  int statsCalls = 0;
  final results = <({
    BrainGameKind kind,
    BrainGameDifficulty difficulty,
    int durationMs,
    int moves,
    bool solved,
  })>[];

  @override
  Future<BrainGameStats> stats({required int userId, int? bucketId}) async {
    statsCalls++;
    return statsResult;
  }

  @override
  Future<({bool ok, bool isBest})> postResult({
    required int userId,
    required BrainGameKind kind,
    required BrainGameDifficulty difficulty,
    required int durationMs,
    required int moves,
    required bool solved,
  }) async {
    results.add((
      kind: kind,
      difficulty: difficulty,
      durationMs: durationMs,
      moves: moves,
      solved: solved,
    ));
    return (ok: true, isBest: best);
  }
}

/// 灌好登录会话后渲染任意游戏页。
///
/// 必须注入会话：页面 `initState` 里读 `currentChildIdProvider` 拿用户 id，
/// 裸 `ProviderScope` 会让 `sessionProvider` 走真实存储（测试里抛异常 + 留 pending Timer）。
Future<FakeBrainGameRepo> pumpBrainGame(
  WidgetTester tester,
  Widget page, {
  FakeBrainGameRepo? repo,
  Size size = const Size(420, 900),
}) async {
  final r = repo ?? FakeBrainGameRepo();
  SharedPreferences.setMockInitialValues({
    'knoact_child_id': 4,
    'knoact_child_name': '金同学',
    SessionStore.accessTokenKey: 'tok',
    SessionStore.refreshTokenKey: 'ref',
  });
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);

  final container = ProviderContainer(
    overrides: [
      brainGameRepositoryProvider.overrideWithValue(r),
      authRepositoryProvider
          .overrideWithValue(FakeAuthRepository(const Child(4, '金同学'))),
    ],
    retry: (_, _) => null,
  );
  addTearDown(container.dispose);
  await container.read(sessionProvider.future);
  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: MaterialApp(home: page),
  ));
  await tester.pumpAndSettle();
  return r;
}

Widget sudokuPageForTest() => const SudokuPage();
```

> **本 Task 只建 helper 的通用部分 + 数独工厂函数。**
> `schultePageForTest()` / `minesweeperPageForTest()` 及对应 import
> 分别在 Task 10 / Task 11 的 Step 1 补上 —— 否则此处会引用尚不存在的页面文件，
> `flutter test` 直接编译失败。

新建 `student-app/test/features/brain_games/sudoku_page_test.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'brain_game_test_helpers.dart';

void main() {
  testWidgets('数独页显示棋盘与数字条', (tester) async {
    final repo = await pumpBrainGame(tester, sudokuPageForTest());

    expect(find.text('数独'), findsOneWidget);
    expect(find.text('简单'), findsOneWidget);
    expect(find.byKey(const ValueKey('sudoku-grid')), findsOneWidget);
    expect(find.byKey(const ValueKey('sudoku-pad-1')), findsOneWidget);
    expect(repo.statsCalls, 1);
  });

  testWidgets('切难度会重新生成棋盘（出现 6 的数字键）', (tester) async {
    await pumpBrainGame(tester, sudokuPageForTest());

    await tester.tap(find.text('中等'));
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('sudoku-pad-6')), findsOneWidget);
    expect(find.byKey(const ValueKey('sudoku-pad-7')), findsNothing);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd student-app && flutter test test/features/brain_games/sudoku_page_test.dart
```

Expected: FAIL，找不到 `ui/sudoku_page.dart`

- [ ] **Step 3: 实现数独页**

新建 `student-app/lib/features/brain_games/ui/sudoku_page.dart`：

```dart
import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../auth/session.dart';
import '../data/brain_game_models.dart';
import '../data/brain_game_repository.dart';
import '../logic/sudoku.dart';
import 'brain_game_shell.dart';

/// 落错格的标红底色（`AppColors` 无 red，用局部常量）
const _gameWrong = Color(0x1FC05B4A);

class SudokuPage extends ConsumerStatefulWidget {
  const SudokuPage({super.key});

  @override
  ConsumerState<SudokuPage> createState() => _SudokuPageState();
}

class _SudokuPageState extends ConsumerState<SudokuPage> {
  static const _kind = BrainGameKind.sudoku;

  BrainGameDifficulty _difficulty = BrainGameDifficulty.easy;
  BrainGameStats _stats = const {};

  /// 当前题面（null = 生成失败或未就绪）。字段名勿与 build 用方法重名。
  SudokuPuzzle? _puzzle;
  List<List<int>> _cells = const [];
  String? _generateError;
  int? _selectedRow;
  int? _selectedCol;
  int? _wrongRow;
  int? _wrongCol;

  final _sw = Stopwatch();
  Timer? _ticker;
  bool _finished = false;
  int _moves = 0;
  int _elapsedMs = 0;

  @override
  void initState() {
    super.initState();
    _newGame();
    _loadStats();
    _ticker = Timer.periodic(const Duration(milliseconds: 200), (_) {
      if (!mounted || _finished) return;
      setState(() => _elapsedMs = _sw.elapsedMilliseconds);
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  int? get _userId => ref.read(currentChildIdProvider);

  Future<void> _loadStats() async {
    final uid = _userId;
    if (uid == null) return;
    final s = await ref.read(brainGameRepositoryProvider).stats(userId: uid);
    if (!mounted) return;
    setState(() => _stats = s);
  }

  /// 生成题面；异常时进入错误态，由 UI 提供「重新生成」。
  void _newGame() {
    try {
      final p = generateSudoku(_difficulty.id, random: Random());
      _puzzle = p;
      _cells = [for (final row in p.givens) List<int>.from(row)];
      _generateError = null;
      _selectedRow = null;
      _selectedCol = null;
      _wrongRow = null;
      _wrongCol = null;
      _moves = 0;
      _finished = false;
      _elapsedMs = 0;
      _sw
        ..reset()
        ..start();
    } catch (e) {
      // 生成异常不白屏：显示「重新生成」按钮（规格容错节要求）
      _puzzle = null;
      _cells = const [];
      _generateError = '$e';
      _finished = true;
      _sw.stop();
    }
  }

  void _restart() => setState(_newGame);

  void _changeDifficulty(BrainGameDifficulty d) {
    if (d == _difficulty) return;
    setState(() {
      _difficulty = d;
      _newGame();
    });
  }

  void _select(int r, int c) {
    final p = _puzzle;
    if (p == null || _finished || p.isGiven(r, c)) return;
    setState(() {
      _selectedRow = r;
      _selectedCol = c;
    });
  }

  Future<void> _place(int value) async {
    final p = _puzzle;
    final r = _selectedRow;
    final c = _selectedCol;
    if (p == null || r == null || c == null || _finished) return;

    if (value == p.solution[r][c]) {
      setState(() {
        _cells[r][c] = value;
        _moves++;
        _wrongRow = null;
        _wrongCol = null;
      });
      if (p.isSolved(_cells)) await _finish();
    } else {
      // 落错：标红后自动清空该格，避免「填满但未通关且无提示」的静默态
      setState(() {
        _cells[r][c] = 0;
        _moves++;
        _wrongRow = r;
        _wrongCol = c;
      });
    }
  }

  Future<void> _finish() async {
    _sw.stop();
    setState(() {
      _finished = true;
      _elapsedMs = _sw.elapsedMilliseconds;
    });
    final uid = _userId;
    var isBest = false;
    var submitted = false;
    if (uid != null) {
      try {
        final r = await ref.read(brainGameRepositoryProvider).postResult(
              userId: uid,
              kind: _kind,
              difficulty: _difficulty,
              durationMs: _elapsedMs,
              moves: _moves,
              solved: true,
            );
        submitted = true;
        isBest = r.isBest;
      } catch (_) {
        // 提交失败静默忽略，不影响本次游玩
      }
    }
    if (!mounted) return;
    await _loadStats();
    if (!mounted) return;
    await showGameResultDialog(
      context,
      title: '完成！',
      detail: '用时 ${formatGameMs(_elapsedMs)} · 落子 $_moves 次',
      // 未成功提交时没有 is_best，不显示新纪录
      showNewRecord: submitted && isBest,
      onRestart: _restart,
    );
  }

  Color _cellColor(int r, int c) {
    if (r == _wrongRow && c == _wrongCol) return _gameWrong;
    if (r == _selectedRow && c == _selectedCol) {
      return AppColors.blue.withValues(alpha: .14);
    }
    final p = _puzzle;
    if (_selectedRow != null && _selectedCol != null && p != null) {
      final spec = p.spec;
      final sameBox =
          r ~/ spec.boxRows == _selectedRow! ~/ spec.boxRows &&
              c ~/ spec.boxCols == _selectedCol! ~/ spec.boxCols;
      // 同行 / 同列 / 同宫都浅蓝底（规格要求）
      if (r == _selectedRow || c == _selectedCol || sameBox) {
        return AppColors.blue.withValues(alpha: .05);
      }
    }
    return Colors.transparent;
  }

  Widget _buildBoard(SudokuSpec spec) {
    final p = _puzzle!;
    final n = spec.size;
    return AspectRatio(
      aspectRatio: 1,
      child: Container(
        key: const ValueKey('sudoku-grid'),
        decoration: BoxDecoration(border: Border.all(color: AppColors.line)),
        child: Column(children: [
          for (var r = 0; r < n; r++)
            Expanded(
              child: Row(children: [
                for (var c = 0; c < n; c++)
                  Expanded(
                    child: GestureDetector(
                      onTap: () => _select(r, c),
                      child: Container(
                        decoration: BoxDecoration(
                          color: _cellColor(r, c),
                          // 选中格加主题蓝描边（规格要求）
                          border: r == _selectedRow && c == _selectedCol
                              ? Border.all(color: AppColors.blue, width: 2)
                              : Border(
                                  right: BorderSide(
                                    color: (c + 1) % spec.boxCols == 0 && c != n - 1
                                        ? AppColors.ink
                                        : AppColors.line,
                                    width: (c + 1) % spec.boxCols == 0 && c != n - 1 ? 2 : .5,
                                  ),
                                  bottom: BorderSide(
                                    color: (r + 1) % spec.boxRows == 0 && r != n - 1
                                        ? AppColors.ink
                                        : AppColors.line,
                                    width: (r + 1) % spec.boxRows == 0 && r != n - 1 ? 2 : .5,
                                  ),
                                ),
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          _cells[r][c] == 0 ? '' : '${_cells[r][c]}',
                          style: TextStyle(
                            fontSize: n >= 9 ? 18 : 22,
                            fontWeight:
                                p.isGiven(r, c) ? FontWeight.w700 : FontWeight.w500,
                            color: p.isGiven(r, c) ? AppColors.ink : AppColors.blue,
                          ),
                        ),
                      ),
                    ),
                  ),
              ]),
            ),
        ]),
      ),
    );
  }

```dart
  Widget _pad(SudokuSpec spec) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      alignment: WrapAlignment.center,
      children: [
        for (var v = 1; v <= spec.size; v++)
          SizedBox(
            width: 44,
            height: 44,
            child: FilledButton(
              key: ValueKey('sudoku-pad-$v'),
              style: FilledButton.styleFrom(padding: EdgeInsets.zero),
              onPressed: () => _place(v),
              child: Text('$v'),
            ),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = _puzzle;
    final best = _stats[_kind]?[_difficulty]?.bestMs;
    return Scaffold(
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(108),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            child: GameTopBar(
              title: _kind.label,
              difficulty: _difficulty,
              onDifficultyChanged: _changeDifficulty,
              elapsedMs: _elapsedMs,
              bestMs: best,
              onRestart: _restart,
            ),
          ),
        ),
      ),
      body: p == null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Text('题面生成失败，请点下方重新生成'),
                  if (_generateError != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(_generateError!,
                          style: const TextStyle(fontSize: 11, color: AppColors.gray)),
                    ),
                  const SizedBox(height: 12),
                  FilledButton(onPressed: _restart, child: const Text('重新生成')),
                ]),
              ),
            )
          : ListView(padding: const EdgeInsets.all(16), children: [
              _buildBoard(p.spec),
              const SizedBox(height: 20),
              _pad(p.spec),
              const SizedBox(height: 16),
              const Text('点格子后在下方选数字；填错会标红并清空',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, color: AppColors.gray)),
            ]),
    );
  }
}
```

> **颜色常量只允许用 `AppColors` 里实际存在的 11 个**
> （`blue / blueSoft / green / greenSoft / orange / orangeSoft / gold / bg / ink / gray / line`）。
> 需要红色时用文件顶部定义的 `_gameWrong` 之类私有常量，**不要改 `theme.dart`**。
> 当前孩子 id 用 `currentChildIdProvider`（`features/auth/session.dart:111` 已提供），
> 不要直接 `ref.read(sessionProvider).value?.id`。

- [ ] **Step 4: 跑测试确认通过**

```bash
cd student-app && flutter test test/features/brain_games/sudoku_page_test.dart
```

Expected: PASS（2 tests）

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/brain_games/ui/sudoku_page.dart student-app/test/features/brain_games/sudoku_page_test.dart
git commit -m "feat(brain-games): 数独游戏页"
```

---

## Task 10: 舒尔特方格页面

**Files:**
- Create: `student-app/lib/features/brain_games/ui/schulte_page.dart`
- Test: `student-app/test/features/brain_games/schulte_page_test.dart`

- [ ] **Step 1: 写失败测试**

新建 `student-app/test/features/brain_games/schulte_page_test.dart`（并在
`brain_game_test_helpers.dart` 顶部加 `import 'package:student_app/features/brain_games/ui/schulte_page.dart';`，
文件末尾加 `Widget schultePageForTest() => const SchultePage();`）：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'brain_game_test_helpers.dart';

void main() {
  testWidgets('舒尔特页显示方格与下一个目标', (tester) async {
    final repo = await pumpBrainGame(tester, schultePageForTest());

    expect(find.text('舒尔特方格'), findsOneWidget);
    expect(find.byKey(const ValueKey('schulte-board')), findsOneWidget);
    expect(find.textContaining('下一个：1'), findsOneWidget);
    expect(repo.statsCalls, 1);
  });

  testWidgets('点错会累加错误数，点对推进目标', (tester) async {
    await pumpBrainGame(tester, schultePageForTest());

    // 点一个不是 1 的格子 → 错误 +1
    final notOne = find.byWidgetPredicate(
      (w) => w is Text && w.data != null && w.data != '1' && int.tryParse(w.data!) != null,
    );
    await tester.tap(notOne.first);
    await tester.pump();
    expect(find.textContaining('错误 1'), findsOneWidget);

    // 点 1 → 目标推进到 2
    await tester.tap(find.text('1').first);
    await tester.pump();
    expect(find.textContaining('下一个：2'), findsOneWidget);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd student-app && flutter test test/features/brain_games/schulte_page_test.dart
```

Expected: FAIL，找不到 `ui/schulte_page.dart`

- [ ] **Step 3: 实现**

新建 `student-app/lib/features/brain_games/ui/schulte_page.dart`：

```dart
import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../auth/session.dart';
import '../data/brain_game_models.dart';
import '../data/brain_game_repository.dart';
import '../logic/schulte.dart';
import 'brain_game_shell.dart';

/// 点错抖动用的边框红（`AppColors` 无 red）
const _gameRed = Color(0xFFC05B4A);

class SchultePage extends ConsumerStatefulWidget {
  const SchultePage({super.key});

  @override
  ConsumerState<SchultePage> createState() => _SchultePageState();
}

class _SchultePageState extends ConsumerState<SchultePage> {
  static const _kind = BrainGameKind.schulte;

  BrainGameDifficulty _difficulty = BrainGameDifficulty.easy;
  BrainGameStats _stats = const {};
  SchulteBoard? _board;
  String? _generateError;
  final _cleared = <int>{};
  int _next = 1;
  int _errors = 0;
  int _moves = 0;
  int _shake = 0;

  /// 最近一次点错的数字，用于给它加红色边框。
  int? _wrongValue;

  final _sw = Stopwatch();
  Timer? _ticker;
  bool _finished = false;
  int _elapsedMs = 0;

  @override
  void initState() {
    super.initState();
    _newGame();
    _loadStats();
    _ticker = Timer.periodic(const Duration(milliseconds: 200), (_) {
      if (!mounted || _finished) return;
      setState(() => _elapsedMs = _sw.elapsedMilliseconds);
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  int? get _userId => ref.read(currentChildIdProvider);

  Future<void> _loadStats() async {
    final uid = _userId;
    if (uid == null) return;
    final s = await ref.read(brainGameRepositoryProvider).stats(userId: uid);
    if (!mounted) return;
    setState(() => _stats = s);
  }

  /// 生成题面；异常时进入错误态（不白屏）。
  void _newGame() {
    try {
      final b = generateSchulte(_difficulty.id, random: Random());
      _board = b;
      _generateError = null;
      _cleared.clear();
      _next = 1;
      _errors = 0;
      _moves = 0;
      _shake = 0;
      _wrongValue = null;
      _finished = false;
      _elapsedMs = 0;
      _sw
        ..reset()
        ..start();
    } catch (e) {
      _board = null;
      _generateError = '$e';
      _finished = true;
      _sw.stop();
    }
  }

  void _restart() => setState(_newGame);

  void _changeDifficulty(BrainGameDifficulty d) {
    if (d == _difficulty) return;
    setState(() {
      _difficulty = d;
      _newGame();
    });
  }

  Future<void> _tap(int value) async {
    final b = _board;
    if (b == null || _finished || _cleared.contains(value)) return;
    if (value == _next) {
      setState(() {
        _moves++;
        _cleared.add(value);
        _next++;
        _wrongValue = null;
      });
      if (b.isComplete(_cleared)) await _finish();
    } else {
      setState(() {
        _moves++;
        _errors++;
        _wrongValue = value;
        _shake++;
      });
    }
  }

  Future<void> _finish() async {
    _sw.stop();
    setState(() {
      _finished = true;
      _elapsedMs = _sw.elapsedMilliseconds;
    });
    final uid = _userId;
    var isBest = false;
    var submitted = false;
    if (uid != null) {
      try {
        final r = await ref.read(brainGameRepositoryProvider).postResult(
              userId: uid,
              kind: _kind,
              difficulty: _difficulty,
              durationMs: _elapsedMs,
              moves: _moves,
              solved: true,
            );
        submitted = true;
        isBest = r.isBest;
      } catch (_) {}
    }
    if (!mounted) return;
    await _loadStats();
    if (!mounted) return;
    await showGameResultDialog(
      context,
      title: '完成！',
      detail: '用时 ${formatGameMs(_elapsedMs)} · 错误 $_errors 次',
      showNewRecord: submitted && isBest,
      onRestart: _restart,
    );
  }

  Widget _cell(int value, int size) {
    final cleared = _cleared.contains(value);
    // 点错时给该格加红色边框（规格要求「点错红色抖动」的可见反馈）
    final wrong = _wrongValue == value;
    return AnimatedOpacity(
      opacity: cleared ? 0 : 1,
      duration: const Duration(milliseconds: 220),
      child: IgnorePointer(
        ignoring: cleared,
        child: AspectRatio(
          aspectRatio: 1,
          child: Padding(
            padding: const EdgeInsets.all(3),
            child: Material(
              color: cleared
                  ? AppColors.green.withValues(alpha: .25)
                  : AppColors.blue.withValues(alpha: .08),
              // 注意：Material 不能同时传 borderRadius 与 shape（框架断言会抛异常）
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
                side: wrong
                    ? const BorderSide(color: _gameRed, width: 2)
                    : BorderSide.none,
              ),
              child: InkWell(
                borderRadius: BorderRadius.circular(10),
                onTap: () => _tap(value),
                child: Center(
                  child: Text(
                    '$value',
                    style: TextStyle(
                      fontSize: size >= 5 ? 22 : 26,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
  Widget _boardWidget(SchulteBoard b) {
    final size = b.size;
    return Column(children: [
      for (var r = 0; r < size; r++)
        Row(children: [
          for (var c = 0; c < size; c++)
            Expanded(child: _cell(b.numbers[r * size + c], size)),
        ]),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final b = _board;
    final best = _stats[_kind]?[_difficulty]?.bestMs;
    return Scaffold(
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(108),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            child: GameTopBar(
              title: _kind.label,
              difficulty: _difficulty,
              onDifficultyChanged: _changeDifficulty,
              elapsedMs: _elapsedMs,
              bestMs: best,
              onRestart: _restart,
            ),
          ),
        ),
      ),
      body: b == null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Text('题面生成失败，请点下方重新生成'),
                  if (_generateError != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(_generateError!,
                          style: const TextStyle(fontSize: 11, color: AppColors.gray)),
                    ),
                  const SizedBox(height: 12),
                  FilledButton(onPressed: _restart, child: const Text('重新生成')),
                ]),
              ),
            )
          : ListView(padding: const EdgeInsets.all(16), children: [
              Row(children: [
                Text('下一个：$_next',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                const Spacer(),
                Text('错误 $_errors', style: const TextStyle(color: AppColors.gray)),
              ]),
              const SizedBox(height: 12),
              // 点错时左右轻微抖动：key 变化触发一次从 -6px 到 0 的位移
              TweenAnimationBuilder<double>(
                key: ValueKey('schulte-shake-$_shake'),
                tween: Tween(begin: _shake == 0 ? 0 : -6, end: 0),
                duration: const Duration(milliseconds: 160),
                curve: Curves.easeOut,
                builder: (context, dx, child) => Transform.translate(
                  offset: Offset(dx, 0),
                  child: child,
                ),
                child: Container(
                  key: const ValueKey('schulte-board'),
                  child: _boardWidget(b),
                ),
              ),
              const SizedBox(height: 16),
              const Text('按 1 → N 的顺序依次点击数字',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, color: AppColors.gray)),
            ]),
    );
  }
}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd student-app && flutter test test/features/brain_games/schulte_page_test.dart
```

Expected: PASS（2 tests）

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/brain_games/ui/schulte_page.dart student-app/test/features/brain_games/schulte_page_test.dart
git commit -m "feat(brain-games): 舒尔特方格页"
```

---

## Task 11: 数字扫雷页面

**Files:**
- Create: `student-app/lib/features/brain_games/ui/minesweeper_page.dart`
- Test: `student-app/test/features/brain_games/minesweeper_page_test.dart`

- [ ] **Step 1: 写失败测试**

新建 `student-app/test/features/brain_games/minesweeper_page_test.dart`（并在
`brain_game_test_helpers.dart` 顶部加 `import 'package:student_app/features/brain_games/ui/minesweeper_page.dart';`，
文件末尾加 `Widget minesweeperPageForTest() => const MinesweeperPage();`）：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'brain_game_test_helpers.dart';

void main() {
  testWidgets('扫雷页首点前不布雷，显示开始提示', (tester) async {
    final repo = await pumpBrainGame(tester, minesweeperPageForTest());

    expect(find.text('数字扫雷'), findsOneWidget);
    expect(find.byKey(const ValueKey('minesweeper-board')), findsOneWidget);
    expect(find.textContaining('点一格开始'), findsOneWidget);
    expect(repo.statsCalls, 1);
  });

  testWidgets('首点后显示剩余雷数（说明首点安全未踩雷）', (tester) async {
    await pumpBrainGame(tester, minesweeperPageForTest());

    await tester.tap(find.byKey(const ValueKey('mine-cell-0')).first);
    await tester.pumpAndSettle();

    expect(find.textContaining('剩余'), findsOneWidget);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd student-app && flutter test test/features/brain_games/minesweeper_page_test.dart
```

Expected: FAIL，找不到 `ui/minesweeper_page.dart`

- [ ] **Step 3: 实现**

新建 `student-app/lib/features/brain_games/ui/minesweeper_page.dart`：

```dart
import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../auth/session.dart';
import '../data/brain_game_models.dart';
import '../data/brain_game_repository.dart';
import '../logic/minesweeper.dart';
import 'brain_game_shell.dart';

/// 扫雷红色标记 / 棋盘底色（`AppColors` 无 red / card）
const _gameRed = Color(0xFFC05B4A);
const _gameCellClosed = Color(0xFFDCE1DA);

class MinesweeperPage extends ConsumerStatefulWidget {
  const MinesweeperPage({super.key});

  @override
  ConsumerState<MinesweeperPage> createState() => _MinesweeperPageState();
}

class _MinesweeperPageState extends ConsumerState<MinesweeperPage> {
  static const _kind = BrainGameKind.minesweeper;

  BrainGameDifficulty _difficulty = BrainGameDifficulty.easy;
  BrainGameStats _stats = const {};

  /// 首点前为 null（不布雷）。
  MinesweeperBoard? _board;
  MinesweeperSpec _spec = minesweeperSpecFor('easy');
  final _opened = <int>{};
  final _flags = <int>{};
  int _moves = 0;
  bool _boom = false;

  final _sw = Stopwatch();
  Timer? _ticker;
  bool _finished = false;
  int _elapsedMs = 0;

  @override
  void initState() {
    super.initState();
    _newGame();
    _loadStats();
    _ticker = Timer.periodic(const Duration(milliseconds: 200), (_) {
      if (!mounted || _finished) return;
      setState(() => _elapsedMs = _sw.elapsedMilliseconds);
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  int? get _userId => ref.read(currentChildIdProvider);

  Future<void> _loadStats() async {
    final uid = _userId;
    if (uid == null) return;
    final s = await ref.read(brainGameRepositoryProvider).stats(userId: uid);
    if (!mounted) return;
    setState(() => _stats = s);
  }

  /// 重置一局（首点前不布雷，因此这里是同步的、不会抛）。

  void _newGame() {
    _spec = minesweeperSpecFor(_difficulty.id);
    _board = null;
    _opened.clear();
    _flags.clear();
    _moves = 0;
    _boom = false;
    _finished = false;
    _elapsedMs = 0;
    _sw
      ..reset()
      ..stop();
  }

  void _restart() => setState(_newGame);

  void _changeDifficulty(BrainGameDifficulty d) {
    if (d == _difficulty) return;
    setState(() {
      _difficulty = d;
      _newGame();
    });
  }

  Future<void> _tap(int index) async {
    if (_finished) return;
    if (_flags.contains(index)) return;

    var board = _board;
    if (board == null) {
      // 首点：先布雷，保证该格不是雷
      board = generateMinesweeper(_difficulty.id, safeIndex: index, random: Random());
      _board = board;
      _sw.start();
    }

    if (board.isMine(index)) {
      _moves++;
      setState(() => _boom = true);
      await _finish(solved: false);
      return;
    }

    final newly = board.reveal(index);
    _moves++;
    setState(() => _opened.addAll(newly));

    if (board.isCleared(_opened)) {
      await _finish(solved: true);
    }
  }

  void _toggleFlag(int index) {
    if (_finished || _opened.contains(index)) return;
    setState(() {
      if (!_flags.remove(index)) _flags.add(index);
    });
  }

  Future<void> _finish({required bool solved}) async {
    _sw.stop();
    setState(() {
      _finished = true;
      _elapsedMs = _sw.elapsedMilliseconds;
    });
    final uid = _userId;
    var isBest = false;
    var submitted = false;
    if (uid != null) {
      try {
        final r = await ref.read(brainGameRepositoryProvider).postResult(
              userId: uid,
              kind: _kind,
              difficulty: _difficulty,
              durationMs: _elapsedMs,
              moves: _moves,
              solved: solved,
            );
        submitted = true;
        isBest = r.isBest;
      } catch (_) {}
    }
    if (!mounted) return;
    await _loadStats();
    if (!mounted) return;
    await showGameResultDialog(
      context,
      title: solved ? '通关！' : '踩到雷了',
      detail: '用时 ${formatGameMs(_elapsedMs)} · 点开 $_moves 次',
      // 失败局永不显示新纪录
      showNewRecord: solved && submitted && isBest,
      onRestart: _restart,
    );
  }

  static const _numberColors = <int, Color>{
    1: Color(0xFF3158E8),
    2: Color(0xFF2E8B57),
    3: Color(0xFFC05B4A),
    4: Color(0xFF6B4FA8),
    5: Color(0xFFAA5A23),
    6: Color(0xFF1F7A8C),
    7: Color(0xFF444444),
    8: Color(0xFF8E9691),
  };

  Widget _cell(int index) {
    final board = _board;
    final r = index ~/ _spec.cols;
    final c = index % _spec.cols;

    // 统一外包 AspectRatio：已开格若只有 Container 会按内容收缩，导致整盘行高不一致
    return AspectRatio(
      aspectRatio: 1,
      child: _cellBody(index, board, r, c),
    );
  }

  Widget _cellBody(int index, MinesweeperBoard? board, int r, int c) {
    if (board == null) {
      // 首点前统一灰色凸起
      return _greyCell(index);
    }

    if (_boom && board.isMine(index)) {
      return Container(
        decoration: BoxDecoration(
          color: _gameRed.withValues(alpha: .18),
          border: Border.all(color: AppColors.line),
        ),
        alignment: Alignment.center,
        child: Icon(Icons.dangerous, size: 16, color: _gameRed),
      );
    }

    if (!_opened.contains(index)) {
      return _greyCell(index, flag: _flags.contains(index));
    }

    final adj = board.adjacentAt(r, c);
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: AppColors.line),
      ),
      alignment: Alignment.center,
      child: adj > 0
          ? Text('$adj',
              style: TextStyle(
                fontWeight: FontWeight.w700,
                fontSize: 14,
                color: _numberColors[adj] ?? AppColors.ink,
              ))
          : const SizedBox.shrink(),
    );
  }

  Widget _greyCell(int index, {bool flag = false}) {
    return GestureDetector(
      key: ValueKey('mine-cell-$index'),
      onTap: () => _tap(index),
      onLongPress: () => _toggleFlag(index),
      child: Container(
        decoration: BoxDecoration(
          color: _gameCellClosed,
          border: Border.all(color: AppColors.line),
          borderRadius: BorderRadius.circular(3),
        ),
        alignment: Alignment.center,
        child: flag
            ? Icon(Icons.flag, size: 14, color: _gameRed)
            : const SizedBox.shrink(),
      ),
    );
  }

  Widget _boardWidget() {
    return Column(children: [
      for (var r = 0; r < _spec.rows; r++)
        Row(children: [
          for (var c = 0; c < _spec.cols; c++)
            Expanded(child: _cell(r * _spec.cols + c)),
        ]),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final best = _stats[_kind]?[_difficulty]?.bestMs;
    final remaining = _spec.mines - _flags.length;
    return Scaffold(
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(108),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            child: GameTopBar(
              title: _kind.label,
              difficulty: _difficulty,
              onDifficultyChanged: _changeDifficulty,
              elapsedMs: _elapsedMs,
              bestMs: best,
              onRestart: _restart,
            ),
          ),
        ),
      ),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Row(children: [
          Text(
            _board == null ? '点一格开始' : '剩余 $remaining 雷',
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          ),
          const Spacer(),
          const Text('长按插旗', style: TextStyle(color: AppColors.gray, fontSize: 12)),
        ]),
        const SizedBox(height: 12),
        Container(key: const ValueKey('minesweeper-board'), child: _boardWidget()),
        const SizedBox(height: 16),
        const Text('数字表示周围 8 格的地雷数',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 12, color: AppColors.gray)),
      ]),
    );
  }
}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd student-app && flutter test test/features/brain_games/minesweeper_page_test.dart
```

Expected: PASS（2 tests）

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/brain_games/ui/minesweeper_page.dart student-app/test/features/brain_games/minesweeper_page_test.dart
git commit -m "feat(brain-games): 数字扫雷页"
```

---

## Task 12: 路由 + 首页入口

**Files:**
- Modify: `student-app/lib/core/router.dart`
- Modify: `student-app/lib/features/home/ui/home_page.dart`
- Test: `student-app/test/features/home/home_page_test.dart`

- [ ] **Step 1: 加路由**

在 `student-app/lib/core/router.dart` 顶部 import 区加**这三条**（游戏页不用
`taskRoute`，因此不需要 `brain_game_shell.dart`）：

```dart
import '../features/brain_games/ui/minesweeper_page.dart';
import '../features/brain_games/ui/schulte_page.dart';
import '../features/brain_games/ui/sudoku_page.dart';
```

在 `redirect` 的 `if (_shellPaths.contains(path) || ...)` 分支里，**把三条路径都加上**
（该处是精确集合匹配，漏一条就被弹回 `/home`）：

```dart
          path == '/bank-exercise' ||
          path == '/listening' ||
          path == '/brain-games/sudoku' ||
          path == '/brain-games/schulte' ||
          path == '/brain-games/minesweeper') {
```

在 `routes:` 列表里（`GoRoute(path: '/listening', ...)` 之后）加三条：

```dart
      GoRoute(path: '/brain-games/sudoku', builder: (_, _) => const SudokuPage()),
      GoRoute(path: '/brain-games/schulte', builder: (_, _) => const SchultePage()),
      GoRoute(path: '/brain-games/minesweeper', builder: (_, _) => const MinesweeperPage()),
```

> 只加这 3 条 import 即可；`brain_game_shell.dart` 不需要被 router 引用。

- [ ] **Step 2: 写首页卡片（先看现有卡片写法保持一致）**

在 `student-app/lib/features/home/ui/home_page.dart`，
**「磨耳朵」那张 `Card(...)` 的闭合 `),` 之后**（即 `// 磨耳朵入口` 注释所在 Card 结束处，
`home_page.dart:168` 那个 `const SizedBox(height: 16),` **之前**）插入下面这段：
（该区域有两个相邻的 `SizedBox(height:16)`，务必以「磨耳朵 Card 结束」为锚点，
不要插到 `if (wide)` 分支之后。）

```dart
          // 思维训练：独立入口，孩子自由玩，不进每日任务
          Card(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('思维训练 · 动动脑',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                const Text('数独 · 舒尔特方格 · 数字扫雷',
                    style: TextStyle(fontSize: 12, color: AppColors.gray)),
                const SizedBox(height: 12),
                Row(children: [
                  _BrainGameEntry(
                    icon: Icons.grid_on,
                    label: '数独',
                    route: GameKindRoute.pathOf(BrainGameKind.sudoku),
                  ),
                  const SizedBox(width: 10),
                  _BrainGameEntry(
                    icon: Icons.apps,
                    label: '舒尔特',
                    route: GameKindRoute.pathOf(BrainGameKind.schulte),
                  ),
                  const SizedBox(width: 10),
                  _BrainGameEntry(
                    icon: Icons.flag,
                    label: '扫雷',
                    route: GameKindRoute.pathOf(BrainGameKind.minesweeper),
                  ),
                ]),
              ]),
            ),
          ),
          const SizedBox(height: 16),
```

在同文件**文件末尾**加一个私有 widget：

```dart
class _BrainGameEntry extends StatelessWidget {
  const _BrainGameEntry({required this.icon, required this.label, required this.route});

  final IconData icon;
  final String label;
  final String route;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => context.push(route),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            color: AppColors.blue.withValues(alpha: .08),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(children: [
            Icon(icon, size: 22, color: AppColors.blue),
            const SizedBox(height: 6),
            Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
          ]),
        ),
      ),
    );
  }
}
```

并在 `home_page.dart` 顶部 import 区加：

```dart
import '../../brain_games/data/brain_game_models.dart';
```

- [ ] **Step 3: 加首页测试断言**

在 `student-app/test/features/home/home_page_test.dart` 的 `main()` 内追加：

```dart
  testWidgets('首页显示思维训练入口', (tester) async {
    await pumpHome(tester, FakeHomeRepository());

    expect(find.text('思维训练 · 动动脑'), findsOneWidget);
    expect(find.text('数独'), findsOneWidget);
    expect(find.text('舒尔特'), findsOneWidget);
    expect(find.text('扫雷'), findsOneWidget);
  });
```

> 本文件已有 `Future<void> pumpHome(WidgetTester tester, FakeHomeRepository repo, {Size size})`
> （约在 `home_page_test.dart:68`），**必须传 repo 参数**，不要写成 `pumpHome(tester)`。

- [ ] **Step 4: 跑测试**

```bash
cd student-app && flutter test test/features/home/home_page_test.dart test/features/brain_games
```

Expected: 全部 PASS

- [ ] **Step 5: 静态检查（只查本功能，不看基线）**

```bash
cd student-app && flutter analyze lib/features/brain_games lib/core/router.dart
```

Expected: `No issues found!`

> **注意**：仓库基线本就有 14 个既存 analyzer 问题（`deprecated_member_use`、
> `unused_import` 等，见 `home_page.dart`、`center_page.dart`、`bank_exercise_page.dart`），
> 全量 `flutter analyze` 的退出码本来就是 1。**不要**顺手去修这些无关文件（scope creep）。
> 判定标准是「brain_games 相关文件零 issue，且既有问题数量不增加」。

- [ ] **Step 6: 提交**

```bash
git add student-app/lib/core/router.dart student-app/lib/features/home/ui/home_page.dart student-app/test/features/home/home_page_test.dart
git commit -m "feat(brain-games): 路由与首页思维训练入口"
```

---

## Task 13: 端到端验证

**Files:** 无新增，只验证。

- [ ] **Step 1: 后端全量测试**

```bash
cd backend && python -m pytest -q
```

Expected: 全绿（含新增 14 个 brain-games 用例；全量约 617 passed）。若出现其它模块失败，
先确认是否与本功能无关（`git stash` 后复跑对比）。

- [ ] **Step 2: 前端全量测试**

```bash
cd student-app && flutter test
```

Expected: 全绿。

- [ ] **Step 3: 前端静态检查**

```bash
cd student-app && flutter analyze lib/features/brain_games
```

Expected: `No issues found!`

全量 `flutter analyze` 基线为 14 个既存问题（与本功能无关），
只需确认**没有新增**在 brain_games / router / home_page 相关文件上的问题：

```bash
cd student-app && flutter analyze 2>&1 | grep -E "brain_games|router\.dart|home_page\.dart"
```

Expected: 除 `home_page.dart` 既有的 `use_build_context_synchronously`（1 条，
改动前就存在）外，无 brain_games / router 相关输出。

- [ ] **Step 4: 手工冒烟（真实后端）**

1. 启动后端：`cd backend && python -m uvicorn app.main:app --port 8010`
2. 启动学生端：`cd student-app && flutter run -d chrome`（或已装的 APK 连同一后端）
3. 首页 → 「思维训练 · 动动脑」→ 点「数独」
4. 验证：顶栏有难度切换、计时器在走、「最佳 —」；点格子选数字能落子；
   落错标红并清空
5. 切「中等」→ 盘面变 6×6、数字条出现 6
6. 返回首页 → 点「舒尔特」→ 按 1、2、3… 点击，格子淡出；点错「错误」+1
7. 返回首页 → 点「扫雷」→ 首点安全（不炸）；长按能插旗；「剩余 N 雷」随插旗变化
8. 用孩子账号调接口确认成绩入库（**先查真实孩子 id，别硬编码**）：

```bash
cd backend && python -c "
import json, urllib.request, urllib.parse
from app.database import SessionLocal
from app.models import User
from app.services.security import create_access_token

db = SessionLocal()
child = db.query(User).filter(User.role == 'child', User.login_name == 'jinyuxuan').first()
uid = child.id
db.close()
tok = create_access_token({'sub': str(uid), 'role': 'child'})
q = urllib.parse.urlencode({'user_id': uid})
r = urllib.request.Request(f'http://127.0.0.1:8010/api/brain-games/stats?{q}',
                           headers={'Authorization': 'Bearer ' + tok})
print(json.dumps(json.load(urllib.request.urlopen(r)), ensure_ascii=False, indent=2))
"
```

Expected: 能看到刚玩过的 `game`/`difficulty` 下的 `played`/`solved`/`best_ms`。

- [ ] **Step 5: 最终提交（如有冒烟过程中的小修）**

```bash
git add -A
git commit -m "test(brain-games): 端到端验证与收尾"
```

---

## 验收标准

- [ ] 首页有「思维训练 · 动动脑」卡片，三个入口各自直达对应游戏
- [ ] 三个游戏都能选难度、计时、显示历史最佳
- [ ] 数独落错标红并清空；填满且正确弹「完成」并入库
- [ ] 舒尔特按序点击、点错计错、点完弹结果并入库
- [ ] 扫雷首点不是雷、长按插旗、踩雷弹失败（不入 best，但入 played）
- [ ] `POST /result` 的 `is_best` 口径正确（首通 true、更慢 false、更快 true、平手 false、失败恒 false）
- [ ] `GET /stats` 禁止跨家庭读取（403）
- [ ] `pytest` 与 `flutter test` 全绿，`flutter analyze lib/features/brain_games` 零 issue（不要求全量零 issue，基线有 14 条既存）
- [ ] 不写 `AnswerRecord`、不动积分、无家长端改动
