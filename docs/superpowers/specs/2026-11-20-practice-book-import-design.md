# 练习册 PDF 导入 + 每日一练设计

日期：2026-11-20（修订 1）
状态：待评审

## 背景与目标

家长手上有《阳光同学·计算小达人·数学 RJ 五（上）》这类**与教材同步的计算练习册**
（扫描版 PDF，108 页，按课时划分，每页一课时的「每日一练」，末尾约 100–107 页是答案页）。

现在 App 里的数学练习只有两条路：AI 现场生成（`math_gen`），或家长手工/拍照录题进题库。
前者不对应教材进度和题型，后者对一本 108 页的练习册不现实。

目标：家长在家长端上传一本练习册 PDF，**半自动**（答案页范围需家长指定）OCR 拆出
「课时 → 题目 → 答案」并入库；孩子端新增「每日一练」入口，按家长设定的当前课时，
每天练一页题；口算/填空直接输入判分，竖式/脱式/应用题白纸写 + 拍照判过程。

## 决策记录（已与用户确认）

| 议题 | 结论 |
| --- | --- |
| 目标形态 | **导入题库**（结构化题目），不是只推 PDF 页图 |
| 答案来源 | 从 PDF 末尾**答案页 OCR** 获得 |
| 导入范围 | 全部 108 页（含阶段检测、期中期末、答案页） |
| 推进度依据 | **家长手动设定「当前课时」** |
| 竖式/脱式/应用题 | **白纸写 + 拍照**，AI 判过程 |
| 题目组织 | **整本书一个卷**，用题目的课时字段分组（不用 tags 过滤，见下） |
| 导入过程 | **后台任务 + 进度条**，可关页面稍后再看 |
| 孩子端形态 | **独立「每日一练」入口**，不占每日任务位 |

不做的（YAGNI）：积分奖励、错题自动重练、多本练习册混合推送、离线缓存、
从阅读进度自动推断课时、第三方练习册平台适配、答案 OCR 置信度自动复核。

## 现状（已核实）

| 项 | 现状 |
| --- | --- |
| 页图渲染 | `services/pdf_split.py:621 render_pages()`，PyMuPDF 300 DPI → `uploads/{doc_id}_pages/{doc_id}_pN.png` |
| 页图表 | `PdfPage(document_id, page_number, image_path)`（`models.py:42`） |
| 文档类型 | `PdfDocument.content_kind` 默认 `textbook`，另有 `handout`（`models.py:38`） |
| OCR | `services/ai.py:120 ocr_image(db, image_bytes, instruction)`，走 llm 档 `options.vision_model`，会回落老 `ModelConfig` 键与默认 `qwen3-vl-plus` |
| OCR→题目 | `services/ocr_import.py:56 structure_questions_from_text()` → `list[QuestionDraft]`；fake provider 返回空列表 |
| Draft 结构 | `core/source_adapter.py:7 QuestionDraft`（qtype/question/options/answer_json/answer/analysis/tags/passage_*） |
| 落库 | `routers/bank.py:104 _persist_drafts()`，写入 `Question` 且 **`status="pending"`** |
| 取题链路 | 只认 `status="published"`（`bank.py:286/335/361`、`task_gen.py:390`） |
| Question 字段 | 有 `tags`（LongText 存 JSON 字符串）、`extra`、`qtype`、`answer_json` |
| 判分 | `math_gen.py:153 grade_math_answer()`（单值归一化比较）、`:248 grade_math_work_photo()`（视觉判题，返回 `final_answer`/`steps_plausible`/`ai_status`） |
| AnswerRecord | `module` 已被题库练习占用 `"practice"`（`bank.py:383`）；无 `photo_path`/`ai_status` 列 |
| 后台任务先例 | `routers/pdf.py:_run_extract`：每步新开 `SessionLocal()` + 内存进度 dict |
| 定时任务 | `main.py:142` apscheduler 03:00 生成每日任务 |
| 学生端 | Flutter + Riverpod + go_router，底部 4 Tab；`app_shell.dart:35-42` 用**硬编码下标**做副作用；`router.dart:33 _shellPaths` 是精确集合 |
| 孩子配置 | `services/child_config.py` 有 `set_child_config_str` / `get_child_config_int`（按 user_id 存，读时回落全局 ModelConfig 同名键） |

## 设计

### 一、整体结构

```
家长端「题库管理」→ 新增「练习册导入」子视图
    ├─ 上传 PDF + 填写答案页范围（扫描版无法自动探测）
    ├─ 后台任务：渲染页 → OCR 题面页 → 解析课时/题号 → OCR 答案页 → 对齐 → 入库 → 发布
    └─ 进度卡片 + 待补答案清单 + 失败页重试

题库（一个卷 = 一本书，Question 带 lesson_no / question_no 可索引列）
    └─ 家长端设定「当前课时」

学生端
    └─ 底部新增第 5 个 Tab「每日一练」（插在「错题本」之后，见 §三）
         └─ 每天一页题（按家长设定的当前课时）
              ├─ 口算/填空 → 输入答案，即时判分
              └─ 竖式/脱式/应用 → 白纸写 + 拍照，AI 判过程
```

数据流：
`PDF → PdfDocument(content_kind="practice") + PdfPage 页图
 → ocr_image() 题面文本 → 解析出 (课时号, 课时标题, 题号, 题干, 题型, 答案)
 → ocr_image() 答案页文本 → 同结构
 → 按 (lesson_no, question_no) 对齐
 → _persist_drafts() 入 Question(status=pending) → 置 published
 → 每日一练按 practice_current_lesson 取题`

### 二、数据模型与导入任务

#### 2.1 `Question` 增加三个可索引列

```python
lesson_no: Mapped[int | None] = mapped_column(Integer, nullable=True)      # 第N课时
lesson_title: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 「小数乘小数」
question_no: Mapped[str | None] = mapped_column(String(16), nullable=True)   # "1" / "2(1)"
__table_args__ = (Index("ix_questions_bank_lesson", "bank_id", "lesson_no"),)
```

**理由**：`tags` 是 LongText 存 JSON 字符串，按课时取题只能整卷拉出后在 Python 过滤；
单卷 2000+ 题时不可接受。题号必须落库，否则「重对齐」「待补答案清单回填」都无从做起。
`lesson_title` 必须有，否则学生端标题「第 3 课时 · 小数乘小数」和家长端下拉都拿不到文案。

>`Question` 目前**没有** `__table_args__`（`models.py:109-132`），追加不会冲突。
> 既有数据这三列为 NULL，不影响现有逻辑。

**索引必须靠迁移脚本建**：`schema_sync.py` 明写「不补索引」，存量库（dev SQLite /
生产 MySQL）的 `questions` 表已存在，`create_all` 不会补索引。因此新增
`backend/app/migrate_practice_import.py`（参照 `migrate_question_bank.py` 的写法），
在 `main.py` 启动时执行，且**每一步都独立 try/except 保证幂等**：

```sql
ALTER TABLE questions ADD COLUMN lesson_no INTEGER;          -- 已存在则跳过
ALTER TABLE questions ADD COLUMN lesson_title VARCHAR(64);   -- 已存在则跳过
ALTER TABLE questions ADD COLUMN question_no VARCHAR(16);    -- 已存在则跳过
-- source_document_id 由 schema_sync 自动补（模型里有该列），无需在此 ALTER
CREATE INDEX ix_questions_bank_lesson ON questions (bank_id, lesson_no);
-- 新库 create_all 已按 __table_args__ 建好同名索引 → CREATE 会报错，需 catch 后忽略
```

**注意**：`CREATE INDEX` 的失败要单独 catch（不能与 ALTER 共用同一个 try），
否则新库上「索引已存在」会让后续步骤被跳过。

#### 2.1b `QuestionDraft` 加字段 + `_persist_drafts` 透传（**数据流关键**）

原设计只加列不加通道，`_persist_drafts` 无法写入课时信息。必须：

`core/source_adapter.py` 的 `QuestionDraft` 加两个字段：
```python
lesson_no: int | None = None
lesson_title: str = ""
question_no: str = ""
```

`routers/bank.py:104 _persist_drafts()` 构造 `Question(...)` 时透传：
```python
lesson_no=d.lesson_no, lesson_title=d.lesson_title or None,
question_no=d.question_no or None,
source_document_id=d.source_document_id,   # 见 §2.10
user_id=bank.user_id,                       # ★ 必须写，见下方警告
```
（`qtype_category` 仍由 `CATEGORY_OF_QTYPE.get(d.qtype)` 计算，
**不要**接受外部传入的 category。）

#### 2.2 新表 `PracticeImportJob`

```python
class PracticeImportJob(Base):
    __tablename__ = "practice_import_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # 家长
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending | rendering | ocr | aligning | done | failed
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    done_pages: Mapped[int] = mapped_column(Integer, default=0)
    question_start_page: Mapped[int] = mapped_column(Integer, default=1)
    question_end_page: Mapped[int] = mapped_column(Integer, nullable=True)
    answer_start_page: Mapped[int] = mapped_column(Integer, nullable=True)
    answer_end_page: Mapped[int] = mapped_column(Integer, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    aligned_count: Mapped[int] = mapped_column(Integer, default=0)
    published_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_pages: Mapped[str] = mapped_column(LongText, default="[]")  # JSON [12, 47]
    error: Mapped[str] = mapped_column(String(512), default="")
    created_at / updated_at
```

#### 2.3 新表 `PracticeAttempt`（逐题作答，关键补充）

原设计只记 `completed` 计数，会导致「AI 判了没处记」。逐题一行：

```python
class PracticeAttempt(Base):
    __tablename__ = "practice_attempts"
    __table_args__ = (UniqueConstraint("user_id", "question_id", "date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"))
    date: Mapped[date] = mapped_column(Date)          # 本地日历日
    lesson_no: Mapped[int] = mapped_column(Integer)
    question_snapshot: Mapped[str] = mapped_column(LongText, default="")  # 题干快照
    student_answer: Mapped[str] = mapped_column(LongText, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    photo_path: Mapped[str] = mapped_column(String(512), default="")
    ai_status: Mapped[str] = mapped_column(String(16), default="")   # ""|ok|pending_review|failed
    ai_final_answer: Mapped[str] = mapped_column(String(64), default="")
    ai_steps_plausible: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_reason: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

**`question_snapshot` 是必须的**：家长事后查看时，题库里的题可能已被补答案/改写，
快照保证「当时练的题干」可追溯。

#### 2.3b 家长端查看（新需求：能看每道题 + 过程题照片）

家长要看孩子练了什么、哪里错了、过程题的手写照片。三块补齐：

**判题标准（过程题）**：答案对 **且** 过程合理。
复用 `grade_math_work_photo` 已有的 `final_answer` / `steps_plausible` / `reason`，
`is_correct = (final == expected) and steps_plausible`；
`ai_status == "failed"` 时 `is_correct=False` 且标「待家长确认」。

**新接口**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/practice/records?child_id=&date=` | 家长视角：某天逐题明细（按课时分组）。返回每题：题干快照、孩子答案、标准答案、对错、`ai_*`、`photo_url`、`lesson_no/title` |
| `GET` | `/api/practice/attempts/{id}/photo` | 带鉴权，返回孩子手写照片（家长仅限自己的孩子；比直连 `/uploads/` 安全） |
| `GET` | `/api/practice/summary?child_id=&days=7` | 近 N 天汇总：每天练了哪课、共几题、对几题、用时 |

**照片存储**：`uploads/practice_photos/q{question_id}_{timestamp}.jpg`
**照片访问必须走鉴权接口**，不要把 `uploads/practice_photos` 挂到静态目录外的地方
（`/uploads` 已全量静态挂载，照片可被任何人猜路径访问 —— 若要彻底隔离，
`practice_photos` 不应放在 `uploads/` 下，改放 `private_uploads/` 并只由接口读）。

**家长端 UI**：报告 Tab 新增「每日一练」子视图

```
11月21日 · 第3课时 小数乘小数
12 题 · 对 10 · 错 2 · 用时 08:32
────────────────────────────────
✓ 1. 8.9 + 4.5 =
   孩子答：13.4   标准：13.4
✗ 2. 3.32 × 2.74 =
   标准：9.0968
   AI 识别：9.096  过程合理 ✓
   [查看手写照片]
✓ 3. (72÷18+8)×28 =
   标准：1792  AI 识别：1792  过程合理 ✓
   [查看手写照片]
```

- 口算/填空：显示孩子答案与标准答案
- 过程题：显示标准答案 + AI 识别结果 + 缩略图（点击放大）
- `ai_status="failed"` 的题标黄「未能识别，请人工核对」

#### 2.4 当前课时（复用 `ChildConfig`）

- `key = "practice_current_lesson"`，`value = "3"`（课时号）
- `key = "practice_current_document"`，`value = "<doc_id>"`（哪本练习册；单本时可缺省）

> `child_config` 按 `user_id` 分孩子存；读时注意 `get_child_config_str` 会回落全局
> `ModelConfig` 同名键，因此 key 前缀带 `practice_` 避免撞车。

#### 2.5 题型映射（`kind` 不进库，落库用 `qtype`）

**不新增 `kind` 字段**，避免与既有 `qtype` 并行冲突。OCR 解析阶段先得到 `kind`，
落库时映射成 `qtype`；**`qtype_category` 由 `CATEGORY_OF_QTYPE` 自动派生，不手填**。
判分一律按 `qtype` 分派（不按 `qtype_category`）。

| 解析出的 kind | `qtype` | 派生 category | 判分方式 |
| --- | --- | --- | --- |
| `oral`（口算，单值） | `oral` | `subjective` | `grade_math_answer()` 单值比较 |
| `fill`（多空填空） | `fill_blank` | `blank` | `answer_json.blanks` 逐空比较 |
| `vertical`（竖式） | `calculation` | `blank` | `grade_math_work_photo()` |
| `step`（脱式/简算） | `calculation` | `blank` | 同上 |
| `app`（应用题） | `application` | `subjective` | 同上 |

> **两处关键修正**：
> 1. 上一版把 category 写成 `objective`（**该值不存在**，`CATEGORIES` 只有
>    `choice/blank/match/subjective`），且与 `CATEGORY_OF_QTYPE` 相反。现改为派生，不手填。
> 2. 原设计把「口算/填空」都当 `oral` 用单值比较，**多空填空必然判错**。
>    现拆成 `oral`（单值）与 `fill_blank`（多空，`answer_json.blanks`）。
>
> 注意 `calculation` 的 category 是 `blank`：题库练习页会对竖式渲染填空输入框。
> 因此**练习册的卷必须从题库练习列表中排除**（见 §2.11），竖式只在「每日一练」的拍照流程里出现。

#### 2.5b ⚠️ 致命：`_persist_drafts` 不写 `user_id`，题目会被启动迁移删光

`_persist_drafts()`（`bank.py:134-150`）构造 `Question` 时**没有传 `user_id`**，
落库为 `NULL`。而 `migrate_grade_buckets.migrate()` 最后一行是：

```python
db.query(Question).filter(Question.user_id.is_(None)).delete(synchronize_session=False)
```

`main.py:61-68` **每次启动**都跑这个迁移。结果：108 页导入成功、发布、孩子练完，
**下次重启服务，整本练习册的题会被静默删除**。

**必须在本次一并修掉**（二选一，推荐前者）：

- **（推荐）** `_persist_drafts` 补 `user_id=bank.user_id`（`ReadingPassage` 已经这么做了，
  见 `bank.py:122`）。这同时修好了既有拍照录题的同类隐患。
- 或把迁移的删除条件收紧为 `user_id IS NULL AND bank_id IS NULL`。

验收要求：**导入后重启服务，题数不变**（写进 §四 测试）。

#### 2.6 答案对齐策略

1. 题面页 OCR → 解析出「课时标题 + 题号 + 题干」。课时标题形如 `第3课时 小数乘小数`，
   题号形如 `1.` `2.` `(1)`。
2. 答案页 OCR → 同样结构。
3. 按 **`(lesson_no, question_no)`** 两层匹配。
4. 匹配不上 → `answer` 留空 + `status="pending"`，进入「待补答案」清单。
5. 答案页里的解题过程整段存入 `analysis`。

**不静默跳过**：未对齐的题必须在家长端可见可补。

#### 2.7 任务执行（后台 + 可注入 + 可恢复）

参照 `routers/pdf.py:_run_extract` 的既有做法，但补齐三点：

- **会话**：后台每处理一页新开 `SessionLocal()`，请求级 `db` 不进后台。
- **执行器可注入**：抽成模块级函数 `run_import_job(job_id: int)`，
  由 `BackgroundTasks.add_task(run_import_job, job.id)` 触发；
  测试里 monkeypatch 成同步假实现，避免 `TestClient` 真的跑完 108 页 OCR。
- **进程重启恢复**：`main.py` 启动时把 `status in ("rendering","ocr","aligning")`
  的 job 置为 `pending`（或标记 `failed` + `error="服务重启，请重试"`），避免永久卡住。

**答案页范围必须由家长填写**：
本题材是扫描版（无文字层），不先 OCR 无法探测「参考答案」页。
因此上传接口**必填** `answer_start_page` / `answer_end_page`；
题面范围默认 `1` 到 `answer_start_page - 1`，也可由家长覆盖。

**不得复用 `POST /api/pdf/upload`**：
`upload_pdf`（`pdf.py:52-64`）只对 `content_kind == "handout"` 跳过拆课，
其它值都会走 `detect_lessons_from_pdf` —— 对 108 页扫描书会**整本 OCR**
并建出一堆假 Lesson。因此导入接口必须**自己**建 `PdfDocument(content_kind="practice")`
+ 调 `render_pages`，不经过 upload 路由。

**OCR 不得走 `pdf_split._ocr_page`**：
它把结果 memo 进模块级 `_OCR_CACHE`（key 只含 path/page/instruction），
**失败时把空字符串也缓存住**，于是 `POST /retry` 永远拿到同一个失败结果。
必须直接 `_render_page_png(pdf_path, i, dpi=150)` + `services.ai.ocr_image()`。

#### 2.8 发布（只发布已对齐的题，**关键约束**）

`_persist_drafts()` 写入的是 `status="pending"`，而取题链路只认 `published`。
导入流程在落库后，**只把「已对齐答案」的 id 置为 published**：

```python
aligned_ids = [qid for qid, d in zip(ids, drafts) if _draft_aligned(d)]
db.query(Question).filter(Question.id.in_(aligned_ids)).update(
    {"status": "published"}, synchronize_session=False)
```

- `_draft_aligned(d)`：`answer` 非空；若 `qtype in ("fill_blank","cloze")`
  还要求 `answer_json["blanks"]` 非空且数量与题干 `____` 一致。
- **未对齐的题保持 `pending`**，不进孩子端。若全量置 published，
  `grade_math_answer(user, "")` 恒返回 False，孩子每天必然做错、家长还看不到待补入口。
- 「待补答案」清单口径：`bank_id = ? AND status = "pending" AND answer = ""`
- 家长端「撤销发布」：把该次导入的题整批置回 `pending`。
- `PATCH .../questions/{id}` 补完答案后置 `published`（若原为 pending）。

#### 2.9 接口清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/banks/{bank_id}/import-practice-pdf` | multipart：`file` + `answer_start_page` + `answer_end_page` + 可选 `question_start_page`/`question_end_page` |
| `GET` | `/api/practice-import/jobs/{job_id}` | 进度与统计 |
| `POST` | `/api/practice-import/jobs/{job_id}/retry` | 重试失败页（只重跑这些页的 OCR + 对齐） |
| `GET` | `/api/practice-import/jobs/{job_id}/missing-answers` | 待补答案清单（lesson_no + question_no + 题干） |
| `PATCH` | `/api/practice-import/questions/{question_id}` | 家长补答案 / 改题干；补完后**自动置 `published`** |
| `GET` | `/api/practice-import/lessons?bank_id=` | 已导入课时列表 + 每课时题数（供下拉） |
| `PUT` | `/api/practice/preferences` | 设置 `practice_current_lesson` / `practice_current_document`（对齐 `learning.py:508` 的写法） |
| `POST` | `/api/banks/practice-book` | 新建一个练习册卷（`source="practice_pdf"`, `subject`, `grade`, `title`），返回 `bank_id` |
| `GET` | `/api/practice/today` | 今日题目：按 `bank_id + lesson_no + status=published` 取题；返回 `qtype`/题干/`answer_json.blanks` 空位结构（**绝不下发 answer**）、已完成状态 |
| `POST` | `/api/practice/answer` | 逐题作答：`{question_id, student_answer}`，口算/填空即时判分，返回 `is_correct` |
| `POST` | `/api/practice/answer-photo` | multipart `file` + `question_id`：竖式/脱式/应用题，落盘 `uploads/practice_photos/q{question_id}_{ts}.jpg`，调 `grade_math_work_photo`，写 `PracticeAttempt.ai_*` |
| `POST` | `/api/practice/submit` | 提交今日练习（校验是否全部答完），写 `AnswerRecord(module="daily_practice")` |
| `GET` | `/api/practice/records?child_id=&date=` | 家长查看某天逐题明细（含照片 URL、AI 判定） |
| `GET` | `/api/practice/attempts/{id}/photo` | 带鉴权返回孩子手写照片 |
| `GET` | `/api/practice/summary?child_id=&days=7` | 近 N 天汇总（每天哪课/几题/对几题） |

#### 2.10 导入幂等与清理

`Question` 没有 `document_id` 列，`tags` 又是 LongText，无法可移植地按
「tags 里的 document_id」过滤。因此新增一列：

```python
source_document_id: Mapped[int | None] = mapped_column(
    Integer, ForeignKey("pdf_documents.id", ondelete="SET NULL"), nullable=True)
```

> **`ondelete="SET NULL"` 是必需的**：新库由 `create_all` 建出真外键，
> 若家长删练习册（`DELETE /api/pdf/documents/{id}`，`pdf.py:396`）而未处理题目，
> 会因外键约束报 500。`SET NULL` 让删文档时题目保留（仍可在题库里看到/手动清理）。
> 存量库经 `schema_sync` 补的是**裸 INTEGER 列（无外键）**，行为一致，不会冲突。
>
> `DELETE /api/questions/{id}` 也要先删 `PracticeAttempt` 再删题（或把
> `PracticeAttempt.question_id` 设为 `ondelete="CASCADE"`），否则新库会 500。
>
> **批量清理同样要先删作答**：`DELETE FROM questions WHERE bank_id=? AND source_document_id=?`
> 前先 `DELETE FROM practice_attempts WHERE bank_id=?`（新库有真外键）。
>
> **删练习册（文档）后**：`SET NULL` 会让题「活着但失去出处」且仍是 `published`，
> 孩子会继续被推到这些题、而页图已删无法对照补答案。因此
> `DELETE /api/pdf/documents/{id}` 在 `content_kind="practice"` 时，
> 需先把该 `source_document_id` 的题置 `pending`（并提示家长）。

- 同一 PDF 重复上传：默认**追加**（新 job → 新题）
- 结果页「清理旧题」：`DELETE FROM questions WHERE bank_id = ? AND source_document_id = ?`
- v1 不做自动去重，只给按钮

#### 2.11 练习册不进教材列表、也不进题库练习

**（a）教材列表**：`PdfDocument.content_kind = "practice"`（新增枚举值）
- `GET /api/pdf/documents` 默认**排除** `content_kind="practice"`（`include_practice=true` 才返回）
- 家长端「教材」页不显示练习册

**（b）题库练习列表**：`GET /api/banks/practice`（`bank.py:277`）必须排除练习册卷
- 判断依据：`QuestionBank.source == "practice_pdf"`
- **`bank.source` 必须在 `_persist_drafts` 之后设置**：
  `_persist_drafts` 末尾有 `if ids and bank.source == "manual": bank.source = "third_party"`
  （`bank.py:153-154`）。若导入任务在 persist **之前**把 `source` 设成 `"practice_pdf"`，
  该判断不成立（因为不等于 `"manual"`）而保留；但若先设成别的值再 persist，
  可能被改写。**约定：persist 完成后立刻 `bank.source = "practice_pdf"`。**
- `task_gen.py:364-412` 的 `_gen_bank_practice_tasks` 也要同样排除
  （它按 `tags.include_daily_task` 筛选，练习册导出的题不写该 tag，故天然排除；
  但为保险起见把 `source` 判断也加上）

#### 2.12 磁盘

108 页 300 DPI PNG 约 1–2GB：
- 页图保留（待补答案时家长要对照原页），导入完成后提示占用，提供「清理页图」按钮
- OCR 用低分辨率重渲染：复用 `pdf_split.py:60 _render_page_png(pdf_path, page_index, dpi=150)`，
  **不新增函数**，也不复用 300 DPI 阅读图

### 三、学生端「每日一练」

**入口**：底部新增第 5 个 Tab，**插在「错题本」之后、「我的」之前**，即
`首页(0) / 学习中心(1) / 错题本(2) / 每日一练(3) / 我的(4)`。

**必须同步修改的三处（缺一处就会静默错位或页面脱离底栏）**：

1. **`router.dart` 加 `StatefulShellBranch`**：在 `StatefulShellRoute.indexedStack` 的
   `branches:` 列表**第 4 个位置（index 3）**插入
   ```dart
   StatefulShellBranch(routes: [
     GoRoute(path: '/practice', builder: (_, _) => const PracticePage()),
   ]),
   ```
   位置必须在 `wrongbook` 之后、`profile` 之前。
   ⚠️ 只加顶层 `GoRoute(path:'/practice')` 是**错的**：那样 Tab 点击 `goBranch(3)` 会落到
   `/profile`，而 `/practice` 页面没有底栏。

2. **`router.dart` 的 `_shellPaths` 加入 `/practice`**（`router.dart:33`）：
   否则 `redirect` 会把 `/practice` 打回 `/home`。

3. **`app_shell.dart:35-42` 修正下标副作用**：
   ```dart
   if (to == 0) ref.read(homeControllerProvider.notifier).reload();
   if (to == 2) ref.read(wrongbookControllerProvider.notifier).reload();
   if (to == 3) ref.read(practiceControllerProvider.notifier).reload();  // 新增
   if (to == 4) ref.invalidate(pointsProvider);                          // 原 to==3
   ```
   并补一条测试：5 个 Tab、索引 3 触发 practice reload、索引 4 触发积分刷新。

**页面结构**

```
顶部：第 3 课时 · 小数乘小数      [换一页]  [历史]
进度：今日 12 题 · 已完成 5
──────────────────────────────────────
题 1   8.9 + 4.5 = [____]         ← 口算，输入即判
题 2   3.32 × 2.74 = [拍照提交]    ← 竖式
题 3   (72÷18+8)×28 = [拍照提交]   ← 脱式
题 4   应用题 ……    [拍照提交]
──────────────────────────────────────
              [提交今日练习]
```

**判分**（按 §2.5 的 `qtype` 分派，复用现有函数）

| qtype | 交互 | 判分 |
| --- | --- | --- |
| `oral` | 数字键盘输入 | `grade_math_answer()` |
| `fill_blank` | 逐空输入 | `answer_json.blanks` 逐空比较 |
| `calculation` / `application` | 拍照 | `grade_math_work_photo()`，结果写 `PracticeAttempt.ai_*` |

**取题规则**

1. 读 `practice_current_document`（哪本练习册）+ `practice_current_lesson`，
   取 `bank_id = current_document AND lesson_no = current_lesson AND status = "published"`
   （正好走 `ix_questions_bank_lesson` 索引）。
   **必须带 `bank_id`**：否则导入第二本练习册后，同号课时的题会混在一起。
2. 若今天该课时已全部答完 → 提示「今天这页练完了，去下一课时？」
3. 家长「指定今天练第 N 课时」→ **写 `ChildConfig`**（`practice_current_lesson`，
   不是请求参数），下次仍生效
4. `[换一页]` 语义：**切到下一个有题（published 数 > 0）的课时**，
   并写回 `practice_current_lesson`（即推进进度）。不提供同课时内换组。
5. 若该课时无题 → 「当前课时还没有题目，请家长导入或换个课时」

**提交**
- 逐题写 `PracticeAttempt`（唯一约束 `user_id + question_id + date`）
  - **upsert 写法**（SQLite/MySQL 无通用 ORM upsert）：
    `row = db.query(PracticeAttempt).filter_by(user_id=..., question_id=..., date=...).first()`
    → 有则更新字段，无则 `db.add(...)`
- 同时写 `AnswerRecord`，**`module="daily_practice"`**（避免与题库练习的 `"practice"` 混淆）
- 全部题答完才算「今日完成」；部分完成显示进度

**不给积分**。

### 四、家长端、容错与测试

**家长端「练习册导入」子视图**
- **先新建/选择练习册卷**：`POST /api/banks/practice-book`（填标题/学科/年级），
  得到 `bank_id` 后才能上传（家长端提供「新建练习册」按钮 + 已有卷下拉）
- 上传 PDF + **必填答案页起止页**（带说明：扫描版无法自动识别）
- 进度卡片：`第 37/108 页 · 已识别 214 题 · 已对齐 198 题 · 已发布 198 题`
- 完成后：待补答案清单（可逐题填）、失败页重试、撤销发布、清理页图
- **当前课时**下拉：调 `GET /api/practice-import/lessons?bank_id=`，显示「第N课时 标题（M题）」

**容错**

| 场景 | 处理 |
| --- | --- |
| 视觉模型不可用 | 判 `r = resolve(db,"llm")`，当 `r.provider == "fake"` 或 `not (r.api_key and r.base_url)` → 400「需要配置 OpenAI 兼容 / 中转站的 llm 档（deepseek、glm 这类内置 base_url 的 provider 无法用于 OCR）」。**注意 `Resolved` 没有 `.name` 属性**（`model_config.py:15-23` 的 dataclass 只有 `provider` 字符串），写成 `.provider.name` 会 AttributeError |
| 答案页范围缺失/越界 | 400，提示必须填且 `1 ≤ answer_start ≤ answer_end ≤ total_pages` |
| PDF 无法解析 | 400 |
| 单页 OCR 返回空 | 记失败页，继续下一页，最后汇总 |
| 整本一个课时都没解析出 | job → `failed`，提示「未识别到课时结构，请检查页码范围或改用拍照录题」 |
| 服务重启时任务进行中 | 启动时把 `rendering/ocr/aligning` 的 job 置 `failed`，`error="服务重启，请重试"`（重试走 `/retry`），家长可点重试。**不要置 pending**（避免和「从没跑过」混淆） |
| 学生端无题可练 | 「当前课时还没有题目，请家长导入或换个课时」 |
| 拍照判题 AI 失败 | 写 `ai_status="failed"`，提示重拍；`ai_status="pending_review"` 时显示「等家长确认」 |
| 提交网络失败 | 保留已作答，可重试 |

**测试**

后端 pytest
- `tests/test_practice_import.py`
  - **`user_id` 落库**：导入后 `Question.user_id == bank.user_id`（非 NULL）
  - **重启不丢题**（关键回归）：创建题 → 跑 `migrate_grade_buckets.migrate()` → 题数不变
  - 题型映射：`kind → qtype` 六种（含多空填空 → `fill_blank` + `blanks`）
  - 答案对齐：`(lesson_no, question_no)` 命中 / 未命中进待补清单
  - 发布：导入后题 `status == "published"`；撤销后回 `pending`；PATCH 补答案后自动 published
  - 幂等清理：按 `source_document_id` 删旧题
  - 任务执行器注入：monkeypatch `run_import_job`，验证 `done_pages` 递增与失败页记录
  - 视觉模型校验：fake provider → 400
  - 鉴权：别的家长的卷不可导入/查看
  - 练习册卷不出现在 `GET /api/banks/practice`
  - 练习册文档不出现在 `GET /api/pdf/documents`
- `tests/test_practice.py`
  - 取题：按 `practice_current_lesson` 返回该课时 `published` 题
  - 判分：`oral` 走 `grade_math_answer`；`calculation` 走 `grade_math_work_photo`（mock）
  - 提交：写 `PracticeAttempt` + `AnswerRecord(module="daily_practice")`；同日重复 upsert
  - 鉴权
- `tests/test_pdf_router.py`（补充）：`content_kind="practice"` 不出现在教材列表

Flutter
- `test/features/practice/`：渲染题目、口算输入判分、拍照按钮、已完成状态、换一页
- `test/features/shell/`：**5 个 Tab**、索引 3 触发每日一练 reload、索引 4 触发积分刷新
- 既有 4 Tab 相关测试同步更新

### 五、改动文件清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/models.py` | `Question` 加 `lesson_no`/`lesson_title`/`question_no`/`source_document_id` + 索引；新增 `PracticeImportJob`、`PracticeAttempt` |
| `backend/app/core/source_adapter.py` | `QuestionDraft` 加 `lesson_no`/`lesson_title`/`question_no`/`source_document_id` |
| `backend/app/routers/bank.py` | `_persist_drafts` 透传课时字段 + `source_document_id` + **`user_id=bank.user_id`**；`list_practice_banks` 排除 `source="practice_pdf"` |
| `backend/app/migrate_practice_import.py` | 新增：`ALTER TABLE` 加 3 列 + `CREATE INDEX`（各自 try/except 幂等） |
| `backend/app/routers/practice_import.py` | 新增：上传/进度/重试/待补/补答案/课时列表 |
| `backend/app/routers/practice.py` | 新增：取题/判分/提交/preferences |
| `backend/app/services/practice_import.py` | 新增：页码范围校验、OCR 编排、课时/题号解析、答案对齐、发布、`run_import_job` |
| `backend/app/routers/pdf.py` | `content_kind="practice"` 默认从教材列表排除 |
| `backend/app/main.py` | include 两个 router；启动时跑迁移 + 清理卡住的 job |
| `parent-web/app.js` / `index.html` | 「练习册导入」子视图 + 当前课时设置；报告 Tab 加「每日一练」查看子视图；`MODULE_LABEL` 加 `daily_practice` || `student-app/lib/features/practice/` | 新增：每日一练页 + controller + repository + 模型 |
| `student-app/lib/core/router.dart` | `/practice` 的 **`StatefulShellBranch`（index 3）** + `_shellPaths` 加入 |
| `student-app/lib/features/shell/app_shell.dart` | 第 5 Tab + 修正索引副作用 |
| `student-app/lib/features/shell/task_nav.dart` | `_allowedReturnTo` 加入 `/practice`（若从首页/任务页带 `returnTo` 跳转） |
| `backend/tests/test_practice_import.py` | 新增 |
| `backend/tests/test_practice.py` | 新增 |
| `student-app/test/features/practice/` | 新增 |
| `student-app/test/features/shell/` | 更新 Tab 数量与索引断言 |

## 后续可扩展（不在本次范围）

- 积分奖励与连练激励
- 错题自动进入错题本并重练
- 多本练习册混合推送
- 从阅读进度自动推断当前课时
- OCR 置信度打分与自动复核
- 页图自动清理策略（按 N 天未访问）

## 实施建议：拆成两个计划

本 spec 覆盖后端导入流水线 + 新表/迁移 + 家长端子视图 + Flutter 新增第 5 Tab，
约 18 个文件、三种前端，作为**单个计划偏大**。建议按依赖顺序拆成两步：

1. **计划一：导入流水线**（后端 models/迁移/`practice_import` 服务与路由 + 家长端子视图）
   —— 产出「已发布题目」这一可验证成果
2. **计划二：学生端每日一练**（`practice` 路由 + Flutter 第 5 Tab + 导航改造 + 测试）
   —— 复用计划一的题目

每步都能独立验证、独立回滚。
