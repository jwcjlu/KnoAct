# 学生端思维训练游戏设计（数独 / 舒尔特方格 / 数字扫雷）

日期：2026-11-19
状态：待评审

## 背景与目标

学生端目前所有练习都必须经由「每日任务」进入，孩子没有**自由、无压力**的动脑入口。
家长提出增加「锻炼思维类的小游戏」：数独、舒尔特方格、数字扫雷。

目标：在 Flutter 学生端加一个独立的「思维训练」入口，孩子随时可玩三个小游戏，
成绩存后端可看历史最佳。不进入每日任务、不涉及积分、不做家长端页面。

> 命名说明：用户口语中的「苏格尔特方格」即 **舒尔特方格（Schulte Table）**，
> 本设计与实现统一用「舒尔特方格」。

## 决策记录（已与用户确认）

| 议题 | 结论 |
| --- | --- |
| 定位 | 独立入口，孩子自由玩；**不进**每日任务 |
| 积分 | 玩不赚积分、也不消耗积分 |
| 成绩存储 | 存后端（跨设备可见） |
| 难度 | 孩子自己在游戏内选（不按年级、不由家长配） |
| 入口 | 首页（`/home`）加一张「思维训练」卡片 |
| 架构 | 方案 A：**客户端出题**，后端只存成绩（不校验题面） |

不做的（YAGNI）：排行榜、每日次数限制、家长端页面、音效、中途存档续局、
作弊校验（小学生场景下流畅度优先于防作弊）。

## 现状（已核实）

- 学生端：`student-app/`，Riverpod + go_router；底部 4 Tab
  （`/home` `/center` `/wrongbook` `/profile`，见 `lib/core/router.dart`）。
- 练习页面模式：`/math` `/knowledge` `/dictation` `/drill` `/bank-exercise` 等，
  由 `home_page.dart` 的 `_onTask(t)` 按 `taskAction` 分发；全屏页用
  `taskRoute(path, returnTo: '/home')`。
- 积分：`Point` 表 + `backend/app/routers/points.py`；本功能不读写积分。
- 做题明细：`AnswerRecord`（`routers/answer_records.py`）；
  **本功能不写 AnswerRecord**，避免游戏成绩污染家长端「当天做题明细」。
- 学年桶：`services/bucket_guard.py` 的 `resolve_bucket_id(db, user_id, None)`，
  与听写/积分等既有逻辑保持一致。

## 设计

### 一、整体结构与数据流

```
首页 HomePage
  └─ 「思维训练 · 动动脑」卡片（三个小方块，点击直接进对应游戏）
       ├─ /brain-games/sudoku      数独
       ├─ /brain-games/schulte     舒尔特方格
       └─ /brain-games/minesweeper 数字扫雷
```

流程：
1. 孩子点卡片进游戏 → 默认「简单」难度，顶部可切换。
2. 切换难度或点「重新开始」→ 本地生成新题面，计时归零开始。
3. 通关或失败 → 本地算出 `duration_ms` / `moves` / `solved`。
4. `solved=true` 时 `POST /api/brain-games/result` 存一条成绩；
   结束弹层展示本次用时与「新纪录！」（若优于历史最佳）。
5. 返回首页。

> 首页直接进游戏（不设中间列表页），减少一层点击。历史最佳在
> 游戏内顶部与结束弹层展示。

### 二、三个游戏的机制

#### 数独 Sudoku

| 难度 | 盘面 | 宫格 | 提示数 |
| --- | --- | --- | --- |
| easy | 4×4 | 2×2 | 8 |
| medium | 6×6 | 2×3 | 14 |
| hard | 9×9 | 3×3 | 34 |

- 生成：回溯随机填一个完整解（每步候选值随机打乱），再随机挖洞到提示数上限；
  挖洞后不校验唯一解（小学生场景，唯一解非必需，避免引入求解器复杂度）。
- 交互：点格子选中 → 底部数字条（1–N）落子；与解不符立即标红；
  同行/同列/同宫浅蓝高亮；已给定格子不可改。
- 通关：所有格子填满且与解一致。
- `moves` = 落子次数。无「提示」按钮（保持思考过程）。

#### 舒尔特方格 Schulte Table

| 难度 | 方格 | 内容 |
| --- | --- | --- |
| easy | 3×3 | 数字 1–9 |
| medium | 4×4 | 数字 1–16 |
| hard | 5×5 | 数字 1–25 |

- 数字随机打乱铺满，按 1→N 顺序依次点击。
- 点对：格子变绿并淡出；点错：红色抖动，计入 `errors`。
- 通关：点完全部数字。成绩 = 用时；`moves` = 总点击数（含点错），
  `errors` 不入库（只在本次弹层展示，避免表字段膨胀）。

#### 数字扫雷 Minesweeper

| 难度 | 盘面 | 雷数 |
| --- | --- | --- |
| easy | 6×6 | 5 |
| medium | 9×9 | 12 |
| hard | 12×12 | 24 |

- 首次点击后才布雷，保证首点不是雷。
- 交互：点击开格；长按插旗；数字表示相邻雷数；空白格（0）自动扩散。
- 失败：踩雷即结束（`solved=false`，仍写一条成绩用于统计「玩过」）。
- 通关：所有非雷格开完。
- `moves` = 点开格子数。

三者共用页面骨架：顶部「返回 · 游戏名 · 难度分段控件 · 计时器(mm:ss)」，
中间棋盘，底部操作区或结束弹层。

### 三、数据模型与接口

新表 `BrainGameResult`（`backend/app/models.py`）：

```python
class BrainGameResult(Base):
    __tablename__ = "brain_game_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bucket_id: Mapped[int | None] = mapped_column(ForeignKey("buckets.id"), nullable=True)
    game: Mapped[str] = mapped_column(String(24))        # sudoku | schulte | minesweeper
    difficulty: Mapped[str] = mapped_column(String(12))  # easy | medium | hard
    duration_ms: Mapped[int] = mapped_column(Integer)
    moves: Mapped[int] = mapped_column(Integer, default=0)
    solved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

接口（新 router `backend/app/routers/brain_games.py`，`prefix="/api/brain-games"`）：

- `POST /api/brain-games/result`
  body：`{user_id, game, difficulty, duration_ms, moves, solved}`
  - `ensure_user_access` 校验；服务端补 `bucket_id = resolve_bucket_id(...)`
  - 校验 `game`/`difficulty` 白名单，非法返回 400 `{"error": "invalid_game"}`
  - 返回 `{"ok": true, "is_best": bool}`（`is_best` 供前端显示「新纪录！」）
- `GET /api/brain-games/stats?user_id=`
  返回：

  ```json
  {
    "sudoku": {
      "easy": {"best_ms": 82000, "played": 3, "solved": 2}
    },
    "schulte": {},
    "minesweeper": {}
  }
  ```

  - `played` = 该难度总记录数；`solved` = `solved=true` 数量；
    `best_ms` = `solved=true` 中的最小 `duration_ms`（无通关则为 `null`）
  - 只返回当前 `bucket_id` 下的数据（与积分口径一致）

**不写 AnswerRecord、不动 `Point`。**

### 四、界面与体验细节

**首页卡片**
- 位置：现有任务区下方，标题「思维训练 · 动动脑」，
  副标题「数独 · 舒尔特方格 · 数字扫雷」。
- 三个小方块横排，各带图标与名称，点击直接进对应游戏。
- 样式沿用现有 `SectionCard` / `AppColors`，不引入新主题。

**游戏内**
- 顶部：返回、游戏名、难度分段控件（简单/中等/困难）、计时器 `mm:ss`。
- 数独：选中格主题蓝描边，同行/列/宫浅蓝底；数字条仅显示该盘面可用数字；
  错格标红；填满立即判定。
- 舒尔特：格子等宽正方形，点对变绿淡出，点错红色抖动。
- 扫雷：未点格灰色凸起，点开浅色凹陷；数字 1–8 经典配色；雷红点。
- 结束弹层：
  - 通关：「用时 02:14 · 新纪录！」+「再来一局 / 返回」
  - 失败（扫雷）：「踩到雷了」+「再来一局 / 返回」
  - 数独/舒尔特只有通关，无失败态。

**容错**
- 成绩提交失败（网络/服务端）：静默忽略，不影响本次游玩与本地用时展示。
- 题面生成异常（极小概率）：显示「重新生成」按钮重试，不白屏。

### 五、测试

后端 pytest（`backend/tests/test_brain_games.py`）：
- 写两条成绩后 `stats` 的 `played` / `solved` / `best_ms` 聚合正确
- `solved=false` 不参与 `best_ms`；全部未通关时 `best_ms` 为 `null`
- 非法 `game` 值返回 400
- 无权用户（别的家长的孩子）写入被拒

Flutter 单测（`student-app/test/features/brain_games/`）：
- 数独生成器：盘面尺寸/宫格正确、给定数不超过上限、解合法（行/列/宫无重复）
- 舒尔特生成器：数字集合完整且被打乱
- 扫雷生成器：首点非雷；雷数符合难度；相邻计数正确
- 通关判定：三游戏在构造的完成态下返回 `solved=true`

### 六、改动文件清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/models.py` | 新增 `BrainGameResult` |
| `backend/app/routers/brain_games.py` | 新增 router（result / stats） |
| `backend/app/main.py` | include_router |
| `backend/tests/test_brain_games.py` | 新增 |
| `student-app/lib/features/brain_games/` | 新增：三个游戏页 + 生成器 + repository |
| `student-app/lib/core/router.dart` | 新增 3 条路由并加入白名单 |
| `student-app/lib/features/home/ui/home_page.dart` | 卡片入口 |
| `student-app/test/features/brain_games/` | 新增生成器与判定测试 |

## 后续可扩展（不在本次范围）

- 家长端看到思维训练用时趋势
- 玩通给积分 / 每日上限
- 排行榜与同学对比
- 数独唯一解校验、提示按钮
