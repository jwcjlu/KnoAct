# 练习册解析重构设计（题组 + 可扩展题型）

日期：2026-11-22
状态：待评审

## 背景与目标

现有练习册导入（`services/practice_import.py`）用**行级正则**切题：每行有运算符就当成一道题。
在《计算小达人 RJ 五上》上暴露了多个结构性问题；在对《数学 BS5》（北师大版五上，107 页）
抽样检查后，确认当前抽象**无法覆盖全部题型**。

目标：把解析从「文本行 → 正则」改成「**整页视觉理解 → 题组结构**」，
并建立可扩展的题型注册表，使后续年级/版本的新题型只需加注册项，不用改判分与前端。

## 现状问题（已核实）

| 问题 | 实际证据 |
| --- | --- |
| **一题拆成多题** | 「不计算，运用规律直接写出得数」应是 1 道题（4 个空），被拆成 5 道独立题 |
| **示例当待做** | `111.06 ÷ 0.9 = 123.4` 是题目给的示例，被当成孩子要做的题 |
| **题干丢失** | 「直接写出得数」「运用规律」等引导语不入库，孩子只看到孤立算式 |
| **脱式当填答案** | `12.5×(40＋8)`、`(17＋23)×2.5` 存成 `oral`，孩子只需填数值，不写过程 |
| **跨页题被截断** | 题面跨页时被切断，且出现两次不相干内容拼进一行（p79 实测） |
| **目录/答案页当题目** | BS5 第 9 页是纯目录（「第1课时 校园的落叶 - 74页」），会被当题 |
| **密集网格漏题** | BS5 第 21 页单区块 40 道口算、第 96 页 30 道，按空白切分易漏 |
| **题型枚举不足** | BS5 有「比较大小」（`30.5 ○ 3.05`）、「带单位比较」（`560km ○ 568m`）、「填空竖式」「字母规律题」，现有 qtype 无对应 |

## 决策记录（已与用户确认）

| 议题 | 结论 |
| --- | --- |
| 数据模型 | **题组 + 小题 两级**：题组存题干/引导语/示例，小题存每道算式；抽题按小题、展示带题干 |
| 找规律题 | 归为**一个题组**，示例标 `is_example` 不入待做项 |
| 跨页题 | **全书扫完后统一合并**（不流式拼接） |
| 目录/答案页 | **AI 判页类型**后跳过 |
| 密集网格 | **AI 返回每道题的坐标框**，按位置分行列 |
| AI 调用 | **按需调用，以准确性为目标**，不刻意省调用次数 |
| OCR 步骤 | **合并到一次视觉调用**（OCR + 结构化一起返回） |
| 可扩展性 | **声明式题型注册表**（`WorkModeSpec`），新题型只加一行 |
| 旧数据 | **清空重新导入** |

不做的（YAGNI）：题组嵌套、题目编辑历史、多本书合成一个卷、自动纠错。

## 现状（已核实）

| 项 | 现状 |
| --- | --- |
| 解析入口 | `services/practice_import.py:parse_lesson_page()`，行级正则 `_ITEM_RE` / `_split_row()` |
| 题型枚举 | `core/question_types.py`：`CATEGORY_OF_QTYPE` 仅 4 个 category、11 个 qtype |
| 判分 | `math_gen.grade_math_answer()`（数值）、`grade_math_work_photo()`（视觉）、`grade_question()`（按 qtype 分派） |
| 注册表先例 | `services/provider_registry.py`：`@dataclass(frozen=True)` + `REGISTRY` dict，本设计沿用该模式 |
| 现有题组 | 无。`Question` 平铺，`lesson_no`/`question_no`/`image_path`/`source_document_id` 已加 |
| 图片题 | `services/practice_image.py` 已实现（视觉模型给范围 → PyMuPDF 裁图） |

## 设计

### 一、整体架构

```
PDF 页图
  ↓  每页 1 次视觉调用（OCR + 结构化合并返回）
页面分析结果 { page_type, groups[], image_questions[] }
  ↓  全书扫完，统一跨页合并
题组列表
  ↓  AI 按 answer_kind 求答案（示例行跳过）
  ↓  入库（题组 + 小题）
PracticeQuestionGroup + Question(group_id)
```

### 二、可扩展题型注册表

新建 `core/work_modes.py`，仿 `provider_registry` 的声明式写法：

```python
@dataclass(frozen=True)
class WorkModeSpec:
    id: str            # oral | step | compare | ...
    label: str         # 口算 | 脱式/简算 | 比较大小
    answer_kind: str   # number | numeric_list | symbol | choice | text | photo
    input_ui: str      # keypad | chooser | camera
    legacy_qtype: str  # 映射到 Question.qtype，复用既有判分
```

> 不设 `grade_band`（本期无消费者，YAGNI）；不设 `extra` dict（`frozen` 也挡不住内容被改，
> 等真有需求再加）。`input_ui` 只保留三种实际用到的：`keypad`（输入）、`chooser`（点选）、
> `camera`（拍照）。

初始注册项：

| id | label | answer_kind | input_ui | legacy_qtype |
| --- | --- | --- | --- | --- |
| `oral` | 口算 | number | keypad | oral |
| `vertical` | 竖式 | photo | camera | calculation |
| `step` | 脱式/简算 | photo | camera | calculation |
| `equation` | 解方程 | number | keypad | fill_blank |
| `pattern` | 找规律 | numeric_list | keypad | fill_blank |
| `compare` | 比较大小 | symbol | chooser | fill_blank |
| `unit_compare` | 单位换算比较 | symbol | chooser | fill_blank |
| `fill_vertical` | 填空竖式 | photo | camera | calculation |
| `letter_pattern` | 字母规律 | numeric_list | keypad | fill_blank |
| `geometry` | 图形题 | photo | camera | application |
| `app` | 应用题 | photo | camera | application |
| `choice` | 选择题 | choice | chooser | single_choice |
| `judge` | 判断题 | choice | chooser | true_false |
| `other` | 其他/未识别 | text | keypad | short_answer |

**扩展方式**：新题型（分式运算、作图题…）只加一行 `WorkModeSpec`，
判分按 `answer_kind` 分派、前端按 `input_ui` 渲染，两侧都不用改代码。

### 三、数据模型

#### 3.1 新表 `PracticeQuestionGroup`

```python
class PracticeQuestionGroup(Base):
    __tablename__ = "practice_question_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    lesson_no: Mapped[int] = mapped_column(Integer, index=True)
    lesson_title: Mapped[str] = mapped_column(String(128), default="")
    stem: Mapped[str] = mapped_column(LongText, default="")        # 题干
    instruction: Mapped[str] = mapped_column(LongText, default="") # 引导语/说明
    work_mode: Mapped[str] = mapped_column(String(24), default="oral")
    need_process: Mapped[bool] = mapped_column(Boolean, default=False)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("pdf_documents.id", ondelete="SET NULL"), nullable=True)
    incomplete: Mapped[bool] = mapped_column(Boolean, default=False)  # 跨页合并不确定
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

> `raw_pages` 不放在组上（同页 40 题会存 40 份重复 OCR 文本），改为复用
> `PracticeImportJob` 的原始文本或单独一张页表；本期先用 `PdfPage.image_path` 追溯原页。

#### 3.2 `Question` 加字段

```python
group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 裸 INTEGER，不用 CASCADE
seq_in_group: Mapped[int] = mapped_column(Integer, default=0)
is_example: Mapped[bool] = mapped_column(Boolean, default=False)
work_mode: Mapped[str] = mapped_column(String(24), default="")
```

保留既有 `lesson_no` / `lesson_title` / `question_no` / `image_path` / `source_document_id`。

### 四、AI 页面分析输出约定

每页一次视觉调用，返回：

```json
{
  "page_type": "practice",
  "groups": [
    {
      "stem": "不计算，运用规律直接写出得数",
      "instruction": "",
      "work_mode": "pattern",
      "need_process": false,
      "continues_next_page": false,
      "items": [
        {"seq": 1, "text": "1.08 ÷ 0.9 = 1.2", "answer_hint": "1.2", "is_example": true},
        {"seq": 4, "text": "1111.05 ÷ 0.9 = （　）", "answer_hint": "", "is_example": false}
      ]
    }
  ],
  "image_questions": [{"start": 0.71, "end": 0.86, "title": "求涂色部分的面积"}]
}
```

| 字段 | 约定 |
| --- | --- |
| `page_type` | `practice` \| `toc` \| `answer_key` \| `cover` \| `blank`；非 `practice` 跳过 |
| `groups[].stem` | 题干原文 |
| `groups[].lesson_no` | 该组的课时号（页首「第N课时 标题」）；无则 `null` |
| `groups[].lesson_title` | 课时标题；无则 `""` |
| `groups[].work_mode` | 取自注册表；拿不准填 `other` |
| `groups[].need_process` | 脱式/竖式/应用题为 `true` |
| `groups[].continues_next_page` | 页尾被截断时为 `true` |
| `items[].text` | 原样抄录，**严禁计算** |
| `items[].answer_hint` | 仅当页面印了答案（示例行）才填 |
| `items[].is_example` | 示例行 `true`，不入待做项 |
| `items[].y` | **该题在页面的纵向比例（0~1）**，用于密集网格按位置分行列、跨页顺序还原 |
| `image_questions[]` | 需看图的题，给纵向比例（沿用现有裁图逻辑） |

**`image_questions` 挂靠题组**：每张裁出的图片题**自成一个题组**
（`work_mode="geometry"`，`items` 只有 1 条，`stem` 用该题的标题）。
这样它带题干、能按题组抽题，不会变成 `group_id=NULL` 的孤儿题。

**`practice_image.detect_image_questions` 的调整**：
- 新契约下页级 `image_questions` 由 `practice_page_ai` 一次返回（不再是独立调用）
- 保留 `practice_image.py` 的 `crop_question_image()`（裁图能力不变）
- 废弃 `detect_image_questions()` 与 `_IMAGE_HINT_RE` 门控（新流程逐页分析，无需关键词触发）

**密集网格必须提供 `items[].y`**：一页 40 道口算时，仅靠返回顺序无法还原行列布局
（OCR 顺序可能跳行）。有了 `y` 就能按纵向位置排序，再按同一 y 值聚成一行。

**硬约束（写进 system prompt）**

1. 严禁计算、严禁把答案写进 `text`（此前踩过坑）
2. 一页有几个大题就返回几个 group，不许自行合并或拆分
3. `answer_hint` 只抄页面已印内容
4. 拿不准时 `work_mode = "other"`，不要猜

### 五、跨页合并

全书扫描完成后统一处理（`merge_cross_page_groups(groups)`）：

```
for i in range(len(groups) - 1):
    cur, nxt = groups[i], groups[i+1]
    # 只在同一 bank + 相邻页 + 上一组标记未结束时尝试
    if not cur.continues_next_page:  continue
    if nxt.page_start != cur.page_end + 1:  continue
    if cur.work_mode != nxt.work_mode:  continue      # 题型不同不合并
    # stem 判定：包含 或 编辑距离 ≤ 30%
    same_stem = (
        cur.stem and nxt.stem and
        (cur.stem in nxt.stem or nxt.stem in cur.stem or
         Levenshtein(cur.stem, nxt.stem) <= max(len(cur.stem), len(nxt.stem)) * 0.3)
    )
    if same_stem or not cur.stem or not nxt.stem:
        合并 nxt.items 到 cur.items（重编 seq）
        cur.page_end = nxt.page_end
        cur.continues_next_page = nxt.continues_next_page
        删除 nxt
    else:
        cur.incomplete = True          # 标记可能不完整，家长端可见
```

**合并失败**：保留两段，`cur.incomplete = True`，家长端显示「可能不完整」提示。

**`incomplete` 字段**需要加进 `PracticeQuestionGroup`：

```python
incomplete: Mapped[bool] = mapped_column(Boolean, default=False)
```

### 六、求答案与判分

**按 `answer_kind` 分派**（不按题型名）：

| answer_kind | 求答案 | 判分 |
| --- | --- | --- |
| `number` | AI 批量算数值 → `Question.answer` | `grade_math_answer()` |
| `numeric_list` | AI 算多个空 → `answer_json={"blanks":[...]}` | 逐空比较，全对才算对 |
| `symbol` | AI 判 > < = → `Question.answer` | 精确匹配（先归一化全半角） |
| `choice` | 从选项挑 → `answer_json={"correct_index":n}` | 精确匹配索引 |
| `text` | AI 生成参考答案 → `Question.answer` | `grade_subjective()` |
| `photo` | **仍然求数值答案**（进 `Question.answer`） | `grade_math_work_photo()`，用它判对错 |

> **`photo` 一定要有标准答案**：`grade_math_work_photo(db, image_bytes, question, expected_answer)`
> 在 `expected_answer` 为空时无法判对错（`math_gen.py:248` 起）。所以竖式/脱式/应用题
> **也要 AI 算出最终答案**，只是孩子必须拍照提交、判分时同时看过程和答案。
>
> 若 AI 求不出答案（如纯图形题的答案依赖图中未标注信息），该题 `status=pending`
> 进「待补答案」，家长补了答案才发布。

**`numeric_list` 的答案形态**（复用现有发布闸门）

```python
Question.answer = "1.2, 1.44, 1.728, 2.0736"     # 便于人看
Question.answer_json = '{"blanks": ["1.2", "1.44", "1.728", "2.0736"]}'  # 判分用
```

`_is_aligned()` 已有 `fill_blank/cloze 必须有 blanks` 的判断，`numeric_list` 走同一分支，
不需要新的发布闸门。

**`solve_math_items` 的新返回结构**

现有实现返回 `dict[int, str]`（单值）。改为：

```python
def solve_practice_items(db, items: list[dict], *, on_progress=None) -> dict[int, dict]:
    """返回 {列表下标: {"kind": "number|numeric_list|symbol", "answer": str, "blanks": [...]}}"""
```

- `number` → `{"answer": "13.4"}`
- `numeric_list` → `{"blanks": ["1.2","1.44"]}`，同时拼出 `answer` 供展示
- `symbol` → `{"answer": ">"}`

求答案时把同组的小题**一起**发给模型（带题干，便于理解规律），
返回按 `seq_in_group` 对齐。

**示例行（`is_example=true`）跳过求答案**（页面已印）。

**`need_process=true` 的题**：AI 算出标准答案（存 `Question.answer`）用于判对错，
但孩子**必须拍照提交**，只填数值不算完成；判分 = 最终答案对 **且** 过程合理。

**统一入口**：新建 `services/practice_grade.py`

```python
def grade_practice_item(db, question, student_answer="", photo_bytes=None) -> dict:
    """返回 {is_correct, ai_status, final_answer, steps_plausible, reason}。"""
```

**未求到答案** → `status=pending`，进「待补答案」清单，不发布。
**待补清单过滤 `is_example=false`**（示例行本就不需要孩子做，不该出现在待补里）。

**抽题规则**（每日一练）：按**小题**抽，展示时带上所属题组题干与示例。
这样「40 道口算」可以每天抽 3 道，孩子能看到「直接写出得数」的引导语。

### 七、迁移与测试

**迁移**（新增 `migrate_practice_groups.py`）—— **只做幂等 schema 变更，绝不删数据**

1. 建 `practice_question_groups` 表（`create_all` 已覆盖，迁移里只补索引）
2. `questions` 加 4 列：`group_id`(裸 INTEGER)、`seq_in_group`、`is_example`、`work_mode`（各自 try/except）
3. 加索引 `ix_questions_group` on `(group_id, seq_in_group)`

> ⚠️ **数据清理不能放迁移里**。`DELETE FROM questions WHERE source_document_id IS NOT NULL`
> 若写进启动迁移，每次重启都会清空练习册题目（新导入的题同样带该字段）。
> 清旧数据是一次性动作，由**家长端「重新导入」时的按钮**显式触发，并在界面上明确提示。

**重新导入时的清理顺序**（在 `/retry` 或新导入入口里）

```python
# 1. 先删小题（按 document 找）
db.query(Question).filter(Question.source_document_id == doc_id).delete()
# 2. 再删题组（存量库 group_id 无外键，CASCADE 不生效，必须显式删）
db.query(PracticeQuestionGroup).filter(
    PracticeQuestionGroup.source_document_id == doc_id).delete()
```

**`group_id` 不声明 CASCADE**（`schema_sync` 不补外键、SQLite 默认不校验），
统一在代码里显式删除，保证新旧库行为一致。

**测试**

后端 pytest（`tests/test_practice_groups.py` + 扩展 `test_practice_import.py`）
- `work_modes` 注册表完整性：每个 mode 的 `answer_kind` / `input_ui` / `legacy_qtype` 合法
- 页面分析 JSON 解析：正常、缺字段、未知 `work_mode`（→`other`）
- `is_example` 过滤：示例不进待做项、不参与求答案、不进待补清单
- `page_type` 过滤：`toc` / `answer_key` / `cover` 不入库
- **密集网格**：同一 `y` 值的 items 聚成一行，按 `y` 排序不乱序
- 跨页合并：`continues_next_page` 且 `work_mode` 相同且 stem 匹配 → 合并；
  不匹配 → 保留两段并标 `incomplete`
- **迁移不删数据**：跑 `migrate()` 后已有练习册题目数量不变
- **重新导入清理**：同一 doc 重导后题组不累积（旧组被显式删除）
- 判分分派：`number` / `numeric_list` / `symbol` / `photo` 各走对分支
- `photo` 题必须有 `answer` 才发布（空答案进待补）
- **回归**：找规律题 = 1 个题组 + 4 个待做小题 + 3 个示例
- **回归**：脱式题 `need_process=true`，只填数值不算完成

Flutter
- 题组展示：题干 + 示例 + 待做项
- 按 `input_ui` 渲染对应交互（数字键盘 / 符号选择 / 拍照）
- `need_process` 的题必须拍照才能提交

**容错**

| 场景 | 处理 |
| --- | --- |
| AI 返回非 JSON | 该页标失败，可重试 |
| `page_type` 拿不准 | 默认 `practice`（宁可多导） |
| `work_mode` 不认识 | 存 `other`，进待家长确认 |
| 跨页合并失败 | 保留两段，标「可能不完整」 |
| 全书无任何题组 | job 标 failed，提示检查 PDF |
| 求答案失败 | 该题 `pending`，进待补清单 |
| 旧数据 | 重导前明确提示会清空 |

### 八、改动文件清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/core/work_modes.py` | 新增：`WorkModeSpec` + 注册表 |
| `backend/app/models.py` | 新增 `PracticeQuestionGroup`；`Question` 加 4 列（裸 `group_id`，无 CASCADE） |
| `backend/app/migrate_practice_groups.py` | 新增：建索引 + 加 4 列 + 建 `ix_questions_group`（**不删数据**） |
| `backend/app/core/source_adapter.py` | `QuestionDraft` 加 `group_id`/`seq_in_group`/`is_example`/`work_mode` |
| `backend/app/routers/bank.py` | `_persist_drafts` 透传 4 个新字段；`GET /{bank_id}/questions` 返回题组题干/示例/`work_mode` |
| `backend/app/services/practice_page_ai.py` | 新增：整页视觉分析（OCR + 结构化合并，走 `provider.generate(json_mode=True)`） |
| `backend/app/services/practice_import.py` | 重写：改用页面分析结果 + 跨页合并；`retry_pages` 同步删旧题组 |
| `backend/app/services/practice_grade.py` | 新增：按 `answer_kind` 分派判分 |
| `backend/app/services/practice_solve.py` | 扩展：返回 `dict[int, dict]` 支持多空与符号 |
| `backend/app/routers/practice_import.py` | 题组浏览、待补清单（过滤 `is_example`）、重新导入清理入口 |
| `backend/app/routers/practice.py` | `/preview` 返回题组题干；`/records` 按题组展示 |
| `backend/app/services/task_gen.py` | 抽题按**小题**，带出题组题干与示例 |
| `backend/app/main.py` | 启动跑新迁移（仅 schema） |
| `parent-web/app.js` | 题组形式展示题目；页面类型可手动修正；重新导入需二次确认 |
| `student-app/lib/features/bank_exercise/data/bank_models.dart` | 题目模型加 `groupStem` / `examples` / `workMode` / `needProcess` |
| `student-app/lib/features/bank_exercise/ui/bank_exercise_page.dart` | 题组展示 + 按 `input_ui` 渲染 + `need_process` 强制拍照 |
| `student-app/lib/features/practice/`（新增） | 每日一练页（题组式） |
| `backend/tests/test_practice_groups.py` | 新增 |

**关于答案页范围**：新流程用 AI 求答案，`answer_start_page`/`answer_end_page` 不再必需，
降级为**可选**（家长若提供，则用答案页做交叉校验；不提供则纯 AI 求答案）。
上传接口与 parent-web 表单都要把这两项从「必填」改成「可选」。

## 后续可扩展（不在本次范围）

- 题组嵌套（大题套小问）
- OCR 置信度打分与自动复核
- 多本书合并成一个卷
- 题型级统计（哪类题最常错）
