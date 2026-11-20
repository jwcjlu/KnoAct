# 练习册 PDF 导入 + 每日一练设计

日期：2026-11-20
状态：待评审

## 背景与目标

家长手上有《阳光同学·计算小达人·数学 RJ 五（上）》这类**与教材同步的计算练习册**
（扫描版 PDF，108 页，按课时划分，每页一课时的「每日一练」，末尾 100–107 页是答案页）。

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
| 推进度依据 | **家长手动设定「当前课时」**（不做从阅读进度自动推断） |
| 竖式/脱式/应用题 | **白纸写 + 拍照**，AI 判过程 |
| 题目组织 | **整本书一个卷**，用 tag 标课时 |
| 导入过程 | **后台任务 + 进度条**，可关页面稍后再看 |
| 孩子端形态 | **独立「每日一练」入口**，不占每日任务位 |

不做的（YAGNI）：积分奖励、错题自动重练、多本练习册混合推送、离线缓存、
从阅读进度自动推断课时、通用第三方练习册平台适配。

## 现状（已核实）

| 项 | 现状 |
| --- | --- |
| 页图渲染 | `services/pdf_split.py:621 render_pages()`，PyMuPDF 300 DPI → `uploads/{doc_id}_pages/{doc_id}_pN.png` |
| 页图表 | `PdfPage(document_id, page_number, image_path)`（`models.py:42`） |
| OCR | `services/ai.py:120 ocr_image(db, image_bytes, instruction)`，走 llm 档 `options.vision_model` |
| OCR→题目 | `services/ocr_import.py:56 structure_questions_from_text()` → `list[QuestionDraft]`；fake provider 返回空列表 |
| Draft 结构 | `core/source_adapter.py:7 QuestionDraft`（qtype/question/options/answer_json/answer/analysis/tags/passage_*） |
| 落库 | `routers/bank.py:104 _persist_drafts()`，写入 `Question`（status=pending） |
| Question 字段 | 已有 `tags`(JSON) 与 `extra`(JSON) 可承载课时信息，**无需加列** |
| 判分 | `services/math_gen.py:153 grade_math_answer()`（归一化比较）、`:248 grade_math_work_photo()`（视觉判题） |
| 定时任务 | `main.py:142` apscheduler（03:00 生成每日任务），已在用 |
| 学生端 | Flutter + Riverpod + go_router，底部 4 Tab（`/home` `/center` `/wrongbook` `/profile`） |

## 设计

### 一、整体结构

```
家长端「题库管理」→ 新增「练习册导入」子视图
    ├─ 上传 PDF（一本 = 一个卷）
    ├─ 后台任务：渲染页 → OCR 题面页 → OCR 答案页 → 对齐 → 入库
    └─ 进度卡片 + 待补答案清单 + 失败页重试

题库（一个卷 = 一本书）
    └─ 每题 tags 带「第N课时」「口算/竖式/脱式/应用」
         └─ 家长端设定「当前课时」

学生端
    └─ 底部新增第 5 个 Tab「每日一练」
         └─ 每天一页题（按家长设定的当前课时）
              ├─ 口算/填空 → 输入答案，即时判分
              └─ 竖式/脱式/应用 → 白纸写 + 拍照，AI 判过程
```

数据流：
`PDF → PdfPage 页图 → ocr_image() 得到题面文本/答案文本 → structure_questions_from_text() 得 Draft
 → 答案对齐（课时标题 + 题号）→ _persist_drafts() 入 Question → 每日一练按 current_lesson 取题`

### 二、数据模型与导入任务

#### 新表 `PracticeImportJob`

```python
class PracticeImportJob(Base):
    __tablename__ = "practice_import_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)   # 家长
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
    failed_pages: Mapped[str] = mapped_column(LongText, default="[]")  # JSON: [12, 47, ...]
    error: Mapped[str] = mapped_column(String(512), default="")
    created_at / updated_at
```

#### 新表 `PracticeDailyProgress`

```python
class PracticeDailyProgress(Base):
    __tablename__ = "practice_daily_progress"
    __table_args__ = (UniqueConstraint("user_id", "date", "lesson_no"),)
    id, user_id, date (Date), lesson_no (Integer)
    bank_id: int
    total: int          # 该课时题数
    completed: int      # 已完成题数
    submitted_at: Mapped[datetime | None]
```

#### 家长端设定当前课时

复用 `ChildConfig`（已存在，`models.py:365`，`user_id + key + value`）：
- `key = "practice_current_lesson"`，`value = "3"`（课时号）
- 另存 `practice_current_lesson_title` 供展示

不新增表。

#### 题目标记（复用 `Question.tags`）

```json
{"source": "practice_pdf", "lesson_no": 3, "lesson_title": "小数乘小数",
 "kind": "calc", "page": 11}
```

`kind` ∈ `oral`（口算）| `vertical`（竖式）| `step`（脱式）| `app`（应用题）| `other`

#### 答案对齐策略（关键风险点）

1. 题面页 OCR 得到「课时标题 + 题号 + 题干」，课时标题形如 `第3课时 小数乘小数`，
   题号形如 `1.` `2.` `(1)` `(2)`。
2. 答案页 OCR 得到同样形态的「课时标题 + 题号 + 答案」。
3. 按 **课时标题 + 题号** 两层匹配。
4. 匹配不上 → `answer` 留空，记入「待补答案」清单（家长可逐题填）。
5. 答案页里的解题过程整段存入 `analysis`。

**不做静默跳过**：所有未对齐的题必须在家长端可见，否则孩子会练到无答案的题。

#### 任务执行

- `POST /api/banks/{bank_id}/import-practice-pdf`（multipart 上传 PDF）
  → 校验（家长角色、PDF 可解析、视觉模型已配置）
  → 建 `PdfDocument` + `PdfPage`（复用 `render_pages`）
  → 建 `PracticeImportJob(status=pending)`
  → `BackgroundTasks` 异步执行
- `GET /api/practice-import/jobs/{job_id}` 查进度与统计
- `POST /api/practice-import/jobs/{job_id}/retry` 重试失败页
- `GET /api/practice-import/jobs/{job_id}/missing-answers` 待补答案清单
- `PATCH /api/practice-import/questions/{question_id}` 家长补答案

每处理一页更新 `done_pages`，前端每 2 秒轮询。

### 三、学生端「每日一练」

**入口**：底部新增第 5 个 Tab（`/practice`），位于「学习中心」与「错题本」之间。

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

**判分**

| 题型 | 交互 | 判分实现 |
| --- | --- | --- |
| 口算/填空（`oral`） | 数字键盘输入 | `grade_math_answer()`（复用） |
| 竖式/脱式（`vertical`/`step`） | 拍照 | `grade_math_work_photo()`（复用，返回 `final_answer` + `steps_plausible`） |
| 应用题（`app`） | 拍照 | 同上 |
| 选择/判断（若答案页 OCR 出） | 点选项 | 精确匹配（复用题库判分） |

**取题规则**

1. 读 `ChildConfig.practice_current_lesson` → 该课时全部题
2. 若该课时今天已完成 → 提示「今天这页练完了，去下一课时？」
3. 家长可「指定今天练第 N 课时」→ 临时覆盖
4. 若该课时无题 → 「当前课时还没有题目，请家长导入或换个课时」

**提交**
- 写 `AnswerRecord`（`module="practice"`），复用家长端「当天做题明细」
- 更新 `PracticeDailyProgress`（唯一约束防止同日重复计）

**不给积分**：与思维训练一致，先跑起来再谈激励。

### 四、家长端、容错与测试

**家长端「练习册导入」子视图**
- 上传 PDF（≤100MB）
- 进度卡片：`第 37/108 页 · 已识别 214 题 · 已对齐 198 题`
- 完成后：
  - **待补答案清单**（课时 + 题号 + 题干原文），可逐题填答案
  - **失败页清单**，可「重试这些页」
- **当前课时**下拉：从已导入的 `lesson_no` 取值，显示「第N课时 标题」

**容错**

| 场景 | 处理 |
| --- | --- |
| 视觉模型未配置 | 上传时立刻 400，提示「未配置视觉模型（llm 档 options.vision_model）」，任务不启动 |
| PDF 无法解析 / 空页 | 上传时 400；单页渲染失败记为失败页 |
| 单页 OCR 返回空 | 记为失败页，继续下一页，最后汇总 |
| 整本一个课时都没识别出 | job → `failed`，提示「未识别到课时结构，请手动指定页码范围」 |
| 答案页范围不确定 | 自动探测含「参考答案/答案」字样的页；失败则要求家长在导入前手填范围 |
| 学生端无题可练 | 显示「当前课时还没有题目，请家长导入或换个课时」 |
| 拍照判题 AI 失败 | 复用现有 `ai_status=failed`，提示重拍 |
| 提交时网络失败 | 保留已作答状态，可重试 |

**测试**

后端 pytest（`tests/test_practice_import.py`）
- 答案页范围探测：给定页文本样本，正确切出题面/答案区间
- 答案对齐：课时标题 + 题号匹配；缺答案入待补清单（不静默丢弃）
- 进度：`done_pages` 递增、失败页记录
- 取题接口：按 `practice_current_lesson` 返回该课时题目
- 判分复用：口算走 `grade_math_answer`，拍照走 `grade_math_work_photo`（mock 视觉）
- 鉴权：别的家长的卷不可导入/查看

Flutter（`test/features/practice/`）
- 每日一练页：渲染题目、口算输入判分、拍照按钮存在
- 已完成状态与「换一页」逻辑
- 底部 Tab 从 4 个变 5 个后，既有导航测试更新

### 五、改动文件清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/models.py` | 新增 `PracticeImportJob`、`PracticeDailyProgress` |
| `backend/app/routers/practice_import.py` | 新增：上传/进度/重试/待补答案/补答案 |
| `backend/app/routers/practice.py` | 新增：每日一练取题/判分/提交 |
| `backend/app/services/practice_import.py` | 新增：页码探测、答案对齐、任务编排 |
| `backend/app/main.py` | include 两个新 router |
| `parent-web/app.js` / `index.html` | 题库管理内加「练习册导入」子视图 + 当前课时设置 |
| `student-app/lib/features/practice/` | 新增：每日一练页 + controller + repository |
| `student-app/lib/core/router.dart` | 新增 `/practice` 路由与 Tab 分支 |
| `student-app/lib/features/shell/app_shell.dart` | 第 5 个 Tab |
| `backend/tests/test_practice_import.py` | 新增 |
| `student-app/test/features/practice/` | 新增 |

## 后续可扩展（不在本次范围）

- 积分奖励与连练激励
- 错题自动进入错题本并重练
- 多本练习册混合推送
- 从阅读进度自动推断当前课时
- 答案 OCR 置信度打分与自动复核
