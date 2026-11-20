# 练习册 PDF 导入 + 每日一练设计

日期：2026-11-20（修订 1）
状态：待评审

## 背景与目标

家长手上有《阳光同学·计算小达人·数学 RJ 五（上）》这类**与教材同步的计算练习册**
（扫描版 PDF，108 页，按课时划分，每页一课时的「每日一练」，末尾约 100–107 页是答案页）。

现在 App 里的数学练习只有两条路：AI 现场生成（`math_gen`），或家长手工/拍照录题进题库。
前者不对应教材进度和题型，后者对一本 108 页的练习册不现实。

目标：家长在家长端上传一本练习册 PDF，后台自动 OCR 拆出「课时 → 题目 → 答案」并入库；
孩子端新增「每日一练」入口，按家长设定的当前课时，每天练一页题；
口算/填空直接输入判分，竖式/脱式/应用题白纸写 + 拍照判过程。

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

#### 2.1 `Question` 增加两个可索引列

```python
lesson_no: Mapped[int | None] = mapped_column(Integer, nullable=True)    # 第N课时
question_no: Mapped[str | None] = mapped_column(String(16), nullable=True)  # "1" / "2(1)"
__table_args__ = (Index("ix_questions_bank_lesson", "bank_id", "lesson_no"),)
```

**理由**：`tags` 是 LongText 存 JSON 字符串，按课时取题只能整卷拉出后在 Python 过滤；
单卷 2000+ 题时不可接受。题号必须落库，否则「重对齐」「待补答案清单回填」都无从做起。

既有数据这两列为 NULL，不影响现有逻辑。

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
    student_answer: Mapped[str] = mapped_column(LongText, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    photo_path: Mapped[str] = mapped_column(String(512), default="")
    ai_status: Mapped[str] = mapped_column(String(16), default="")   # ""|ok|pending_review|failed
    ai_final_answer: Mapped[str] = mapped_column(String(64), default="")
    ai_steps_plausible: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_reason: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

#### 2.4 当前课时（复用 `ChildConfig`）

- `key = "practice_current_lesson"`，`value = "3"`（课时号）
- `key = "practice_current_document"`，`value = "<doc_id>"`（哪本练习册；单本时可缺省）

> `child_config` 按 `user_id` 分孩子存；读时注意 `get_child_config_str` 会回落全局
> `ModelConfig` 同名键，因此 key 前缀带 `practice_` 避免撞车。

#### 2.5 题型映射（`kind` 不进库，落库用 `qtype`）

**不新增 `kind` 字段**，避免与既有 `qtype` 并行冲突。OCR 解析阶段先得到 `kind`，
落库时映射：

| 解析出的 kind | `qtype` | `qtype_category` | 判分方式 |
| --- | --- | --- | --- |
| `oral`（口算，单值） | `oral` | `objective` | `grade_math_answer()` 单值比较 |
| `fill`（多空填空） | `fill_blank` | `objective` | `answer_json.blanks` 逐空比较 |
| `vertical`（竖式） | `calculation` | `subjective` | `grade_math_work_photo()` |
| `step`（脱式/简算） | `calculation` | `subjective` | 同上 |
| `app`（应用题） | `application` | `subjective` | 同上 |

> **关键修正**：原设计把「口算/填空」都当 `oral` 用单值比较判分，**多空填空必然判错**。
> 现拆成 `oral`（单值）与 `fill_blank`（多空，`answer_json.blanks`）。

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

#### 2.8 发布（原设计缺失）

`_persist_drafts()` 写入的是 `status="pending"`，而取题链路只认 `published`。
导入流程**必须**在落库后把本次导入的题置为 `published`：

```python
db.query(Question).filter(Question.id.in_(ids)).update(
    {"status": "published"}, synchronize_session=False)
```

家长端「练习册导入」结果页提供「撤销发布」按钮（置回 pending），便于发现 OCR 错误时下线。

#### 2.9 接口清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/banks/{bank_id}/import-practice-pdf` | multipart：`file` + `answer_start_page` + `answer_end_page` + 可选 `question_start_page`/`question_end_page` |
| `GET` | `/api/practice-import/jobs/{job_id}` | 进度与统计 |
| `POST` | `/api/practice-import/jobs/{job_id}/retry` | 重试失败页（只重跑这些页的 OCR + 对齐） |
| `GET` | `/api/practice-import/jobs/{job_id}/missing-answers` | 待补答案清单（lesson_no + question_no + 题干） |
| `PATCH` | `/api/practice-import/questions/{question_id}` | 家长补答案 / 改题干 |
| `GET` | `/api/practice-import/lessons?bank_id=` | 已导入课时列表 + 每课时题数（供下拉） |
| `PUT` | `/api/practice/preferences` | 设置 `practice_current_lesson`（对齐 `learning.py:508` 的写法） |

#### 2.10 导入幂等

同一 PDF 重复上传：默认**追加**（新 job → 新题）；
若家长在结果页点「清理旧题」，按 `bank_id + tags.source=practice_pdf + document_id` 删除旧题后重导。
v1 只在结果页给按钮，不做自动去重。

#### 2.11 练习册不进教材列表

`PdfDocument.content_kind = "practice"`（新增枚举值），并且：

- `GET /api/pdf/documents` 默认 **排除** `content_kind="practice"`（加 `include_practice=false` 参数才返回）
- 家长端「教材」页不显示练习册；练习册只在「练习册导入」子视图可见

#### 2.12 磁盘

108 页 300 DPI PNG 约 1–2GB。设计上：
- 页图保留（待补答案时需要家长对照原页），但导入完成后提示占用，并提供「清理页图」按钮
- OCR 用 **150 DPI 重渲染**的临时图（`_render_page_for_ocr`），不复用 300 DPI 阅读图

### 三、学生端「每日一练」

**入口**：底部新增第 5 个 Tab，**插在「错题本」之后、「我的」之前**，即
`首页(0) / 学习中心(1) / 错题本(2) / 每日一练(3) / 我的(4)`。

**必须同步修改的两处（否则静默错位）**：
1. `router.dart` 的 `_shellPaths` 加入 `/practice`
2. `app_shell.dart:35-42` 的下标判断：
   `to == 2` 仍是错题本 reload（不变），`to == 3` 改为「每日一练 reload」，
   **`to == 4` 才是 invalidate 积分**（原 `to == 3`）
3. 补一条 shell 测试断言 5 个 Tab 且索引副作用正确

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

1. 读 `practice_current_lesson` → 该课时全部 `published` 题（走 `ix_questions_bank_lesson` 索引）
2. 若今天该课时已全部答完 → 提示「今天这页练完了，去下一课时？」
3. 家长「指定今天练第 N 课时」→ **写 `ChildConfig`**（不是请求参数），下次仍生效
4. 若该课时无题 → 「当前课时还没有题目，请家长导入或换个课时」

**提交**
- 逐题写 `PracticeAttempt`（唯一约束 `user_id + question_id + date`，同日重复作答走 upsert）
- 同时写 `AnswerRecord`，**`module="daily_practice"`**（避免与题库练习的 `"practice"` 混淆）
- 全部题答完才算「今日完成」；部分完成显示进度

**不给积分**。

### 四、家长端、容错与测试

**家长端「练习册导入」子视图**
- 上传 PDF + **必填答案页起止页**（带说明：扫描版无法自动识别）
- 进度卡片：`第 37/108 页 · 已识别 214 题 · 已对齐 198 题 · 已发布 198 题`
- 完成后：待补答案清单（可逐题填）、失败页重试、撤销发布、清理页图
- **当前课时**下拉：调 `GET /api/practice-import/lessons?bank_id=`，显示「第N课时 标题（M题）」

**容错**

| 场景 | 处理 |
| --- | --- |
| 视觉模型不可用 | 判 `resolve(db,"llm")` 的 `provider.name == "fake"` 或 `api_key`/`base_url` 为空 → 400「未配置可用的视觉模型（llm 档）」；不要只看 `options.vision_model`（`ocr_image` 会回落默认模型） |
| 答案页范围缺失/越界 | 400，提示必须填且 `1 ≤ answer_start ≤ answer_end ≤ total_pages` |
| PDF 无法解析 | 400 |
| 单页 OCR 返回空 | 记失败页，继续下一页，最后汇总 |
| 整本一个课时都没解析出 | job → `failed`，提示「未识别到课时结构，请检查页码范围或改用拍照录题」 |
| 服务重启时任务进行中 | 启动时把 `rendering/ocr/aligning` 的 job 置 `failed`，`error="服务重启，请重试"`，家长可点重试 |
| 学生端无题可练 | 「当前课时还没有题目，请家长导入或换个课时」 |
| 拍照判题 AI 失败 | 写 `ai_status="failed"`，提示重拍；`ai_status="pending_review"` 时显示「等家长确认」 |
| 提交网络失败 | 保留已作答，可重试 |

**测试**

后端 pytest
- `tests/test_practice_import.py`
  - 题型映射：`kind → qtype` 六种（含多空填空 → `fill_blank` + `blanks`）
  - 答案对齐：`(lesson_no, question_no)` 命中 / 未命中进待补清单
  - 发布：导入后题 `status == "published"`；撤销后回 `pending`
  - 幂等清理：按 `document_id` 删旧题
  - 任务执行器注入：monkeypatch `run_import_job`，验证 `done_pages` 递增与失败页记录
  - 视觉模型校验：fake provider → 400
  - 鉴权：别的家长的卷不可导入/查看
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
| `backend/app/models.py` | `Question` 加 `lesson_no`/`question_no` + 索引；新增 `PracticeImportJob`、`PracticeAttempt` |
| `backend/app/routers/practice_import.py` | 新增：上传/进度/重试/待补/补答案/课时列表 |
| `backend/app/routers/practice.py` | 新增：取题/判分/提交/preferences |
| `backend/app/services/practice_import.py` | 新增：页码范围校验、OCR 编排、课时/题号解析、答案对齐、发布、`run_import_job` |
| `backend/app/routers/pdf.py` | `content_kind="practice"` 默认从教材列表排除 |
| `backend/app/main.py` | include 两个 router；启动时清理卡住的 job |
| `parent-web/app.js` / `index.html` | 「练习册导入」子视图 + 当前课时设置 |
| `student-app/lib/features/practice/` | 新增：每日一练页 + controller + repository + 模型 |
| `student-app/lib/core/router.dart` | `/practice` 路由 + `_shellPaths` 加入 |
| `student-app/lib/features/shell/app_shell.dart` | 第 5 Tab + 修正索引副作用 |
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
