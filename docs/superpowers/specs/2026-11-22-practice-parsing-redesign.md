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
  ↓  ai.vision_json(db, png, system, prompt)   ← 新增，图片 + JSON 一次搞定
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
    lesson_no: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # 无课时标题时为 None
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

**页级元信息**（新增表，很小，解决「页码类型可修正」与原始文本追溯）：

```python
class PracticeImportPage(Base):
    """导入时按页记录分析结果，供排查与手动修正页类型。"""
    __tablename__ = "practice_import_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"))
    page_no: Mapped[int] = mapped_column(Integer)
    page_type: Mapped[str] = mapped_column(String(16), default="practice")
    raw_text: Mapped[str] = mapped_column(LongText, default="")     # 该页 AI 原始输出
    group_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok")    # ok | failed
```

家长端可把某页 `page_type` 从 `toc` 改成 `practice` 后重新解析该页。

**`work_mode` 以小题为准**：组级 `work_mode` 是默认值，小题 `Question.work_mode` 非空时优先；
渲染与统计都读小题字段（组级仅作兜底）。

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

**调用契约**：每页一次 `ai.vision_json(db, page_png_bytes, system=_PAGE_SYSTEM, prompt=_PAGE_PROMPT)`
→ 返回 JSON 字符串。

> 为什么必须新增 `vision_json`：`services/ai.py` 现有的 `generate(prompt, system, json_mode)`
> **只接受文本**（无图片入参），`ocr_image(db, image_bytes, instruction)` 能带图
> **但不支持 `json_mode`、也不接受 system**。整页分析两者都要，所以新增一个薄函数
> （内部复用 `ocr_image` 的 `image_url` + base64 组装）。

每页返回：

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
        {"seq": 1, "y": 0.18, "text": "$1.08 \\div 0.9 = 1.2$", "answer_hint": "1.2", "is_example": true},
        {"seq": 2, "y": 0.31, "text": "$11.106 \\div 0.9 = 12.34$", "answer_hint": "12.34", "is_example": true},
        {"seq": 3, "y": 0.44, "text": "$111.06 \\div 0.9 = 123.4$", "answer_hint": "123.4", "is_example": true},
        {"seq": 4, "y": 0.57, "text": "$1111.05 \\div 0.9 =$ ____", "answer_hint": "", "is_example": false}
      ]
    }
  ],
  "image_questions": [{"start": 0.71, "end": 0.86, "title": "求涂色部分的面积"}]
}
```

> 这个示例同时是**提示词的 few-shot 样例**，所以它必须严格遵守 §十 的格式规则：
> 空位用 `____`（不是 `（　）`）、数学式用 `$...$` 包裹、示例行 `is_example: true` 且带
> `answer_hint`、每题给 `y`。改示例时务必与格式测试保持一致。

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

**`_levenshtein` 归属**：放到 `backend/app/services/practice_import.py` 的模块级私有函数
（与 `merge_cross_page_groups` 同文件，无外部依赖，不需要单独 util 文件）。

**`image_questions` 挂靠题组**：每张裁出的图片题**自成一个题组**
（`work_mode="geometry"`，`items` 只有 1 条，`stem` 用该题的标题）。
这样它带题干、能按题组抽题，不会变成 `group_id=NULL` 的孤儿题。

> **图片题的答案从哪来**：裁图题组只有标题、没有题面文字，`solve_math_items` 看不到图，
> 纯文本求答案必然失败。因此图片题**求答案时把裁出的 PNG 一并送视觉模型**
> （调 `ai.vision_json()`，带上题干标题 + 图片；**不是** `provider.generate`，
> 后者无图片入参）；仍失败则该题 `pending`、进「待补答案」由家长手动补。
> **不采用「自动跳过」**——`photo`/`geometry` 的 `answer` 恒非空是发布闸门的前提。

**`practice_image.detect_image_questions` 的调整**：
- 新契约下页级 `image_questions` 由 `parsers/math_page.py` 一次返回（不再是独立调用）
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

```python
merged = []
i = 0
while i < len(groups):
    cur = groups[i]
    merged.append(cur)
    # 合并成功后不前进，继续尝试吞下一组（支持跨 3 页以上）
    while cur.get("continues_next_page") and i + 1 < len(groups):
        nxt = groups[i + 1]
        if nxt["page_start"] != cur["page_end"] + 1 or cur["work_mode"] != nxt["work_mode"]:
            break
        same_stem = (
            not cur["stem"] or not nxt["stem"]
            or cur["stem"] in nxt["stem"] or nxt["stem"] in cur["stem"]
            or _levenshtein(cur["stem"], nxt["stem"])
               <= max(len(cur["stem"]), len(nxt["stem"])) * 0.3
        )
        if not same_stem:
            cur["incomplete"] = True
            cur["continues_next_page"] = False   # 不再尝试吞后续组
            break
        cur["items"].extend(nxt["items"])
        cur["page_end"] = nxt["page_end"]
        cur["continues_next_page"] = nxt.get("continues_next_page", False)
        i += 1                                    # 吞掉 nxt
    i += 1
```

**要点**
- 合并成功后 `i` 只前进 1（吞掉 nxt），外层再 +1，支持连续跨多页
- 合并失败必须把 `continues_next_page` 置 False，否则下一轮还会误吞
- 合并失败标 `incomplete=True`，家长端显示「可能不完整」

**`incomplete` 字段**需要加进 `PracticeQuestionGroup`：

```python
incomplete: Mapped[bool] = mapped_column(Boolean, default=False)
```

### 六、求答案与判分

#### 6.0 入库流程（题组先建，小题后挂）

`_persist_drafts` 只负责写 `Question`，**题组行由调用方先建**：

```python
# services/practice_import.py 里
group_ids: dict[str, int] = {}       # key: 组内唯一标识（如 f"{page_start}-{idx}"）

for g in merged_groups:
    row = PracticeQuestionGroup(
        bank_id=bank.id, user_id=bank.user_id,
        lesson_no=g["lesson_no"], lesson_title=g["lesson_title"],
        stem=g["stem"], instruction=g.get("instruction", ""),
        work_mode=g["work_mode"], need_process=g["need_process"],
        page_start=g["page_start"], page_end=g["page_end"],
        source_document_id=job.document_id,
        incomplete=g.get("incomplete", False),
    )
    db.add(row); db.flush()
    group_ids[g["key"]] = row.id

# 再构造 drafts，把 group_id 填进去
for g in merged_groups:
    for it in g["items"]:
        d = build_draft(it, g, document_id=job.document_id)
        d.group_id = group_ids[g["key"]]
        d.seq_in_group = it["seq"]
        d.is_example = it["is_example"]
        d.work_mode = g["work_mode"]
        drafts.append(d)

_persist_drafts(db, bank, drafts, "practice_pdf")
```

#### 6.1 判分接入点

新判分器 `grade_practice_item()` 必须**接到现有提交入口**：

- `routers/bank.py` 的 `POST /api/banks/submit`（`bank.py:356`）在写
  `AnswerRecord` 前，若该题有 `work_mode`，改走 `grade_practice_item()`；
  无 `work_mode` 的旧题仍走 `grade_question()`
- `routers/practice.py` 的 `POST /api/practice/answer-photo`（**新增**）用于
  `need_process` 与 `photo` 题型：上传照片 → `grade_practice_item(photo_bytes=...)`
  → 写 `PracticeAttempt`

> 现有 Flutter `/bank-exercise` 只支持输入/点选（`bank_exercise_controller.dart`
> 的 `_answerPayload` 按 `qtype_category` 三选一，`setBlank` 恒传 1 个空），
> `photo` 与 `numeric_list` 都提交不了。因此：
> - `bank_exercise_controller.dart` 需支持 `blanks` 数组与拍照上传
> - 或明确「`photo`/`numeric_list` 题型仅在「每日一练」里做，题库练习只支持
>   `number`/`choice`/`symbol`」——**本期选后者**（题库练习保持简单），
>   每日一练（计划三）才实现拍照与多空

**按 `answer_kind` 分派**（不按题型名）：

| answer_kind | 求答案（必写字段） | 判分 |
| --- | --- | --- |
| `number` | `answer` = 数值 | `grade_math_answer()` |
| `numeric_list` | `answer` = 逗号拼接 + `answer_json={"blanks":[...]}` | 逐空比较，全对才算对 |
| `symbol` | `answer` = `>`/`<`/`=` | 精确匹配（先归一化全半角） |
| `choice` | `answer` = 选项文本 + `answer_json={"correct_index":n}` | 精确匹配索引 |
| `text` | `answer` = 参考答案文本 | `grade_subjective()` |
| `photo` | `answer` = AI 算出的数值 + `answer_json={"blanks":[...]}`（若多空） | `grade_math_work_photo()` |

> **`answer` 恒为非空**——这是现有发布闸门 `_is_aligned()` 的第一条判断
> （`practice_import.py:357`）。只写 `answer_json` 不写 `answer` 的题型（原设计的
> `choice`/`judge`）会永久 `pending`，必须同时写 `answer`。

**`_is_aligned()` 改为按 `answer_kind` 判定**（不再按 qtype）：

```python
def _is_aligned(q) -> bool:
    if not (q.answer or "").strip():
        return False
    if not (q.work_mode or "").strip():
        return _is_aligned_legacy(q)          # 旧题（work_mode 为空）走原 qtype 逻辑，行为不变
    kind = answer_kind_of(q.work_mode)        # 从 work_modes 注册表查
    if kind in ("numeric_list",):
        return bool(_blanks_of(q))            # 多空题型要求 blanks 非空
    if kind == "choice":
        return _json(q).get("correct_index") is not None
    return True
```

> **旧题必须保留原路径**：`work_mode` 默认 `""`，存量题库题（`cloze`/`fill_blank`/`short_answer`）
> 若一律走新分支，会因不再检查 `blanks` 而被误发布。`_is_aligned_legacy(q)` 即现有
> `practice_import.py:357` 的实现，原样保留。

> **`build_drafts` 的 `fill_blank → oral` 静默降级要删掉**（`practice_import.py:347-350`）。
> 它会把 `symbol`/`equation` 这类映射到 `fill_blank` 的题降成 `oral`，
> 导致 `qtype_category` 变 `subjective`，判分永远 pending。改为按 `answer_kind` 写
> `answer_json`，不再降级。

**`photo` 一定要有标准答案**：`grade_math_work_photo(db, image_bytes, question, expected_answer)`
在 `expected_answer` 为空时无法判对错（`math_gen.py:248` 起）。所以竖式/脱式/应用题
**也要 AI 算出最终答案**，只是孩子必须拍照提交、判分时同时看过程和答案。
若 AI 求不出答案，该题 `status=pending` 进「待补答案」，家长补了才发布。

**`numeric_list` 的答案形态**

```python
Question.answer = "1.2, 1.44, 1.728, 2.0736"     # 展示用，且满足 _is_aligned 第一条
Question.answer_json = '{"blanks": ["1.2", "1.44", "1.728", "2.0736"]}'  # 判分用
```

**`solve_math_items` 的新返回结构**

现有实现返回 `dict[int, str]`（单值）。改为：

```python
def solve_math_items(db, items: list[dict], *, on_progress=None) -> dict[int, dict]:
    """保留原函数名；仅返回类型由 dict[int, str] 改为 dict[int, dict]。

    返回 {列表下标: {"kind": "number|numeric_list|symbol", "answer": str, "blanks": [...]}}
    """
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
    """返回 {is_correct, ai_status, final_answer, steps_plausible, reason}。

    实现约定：这是 services/math_grade.grade_by_answer_kind() 的**薄包装**——
    仅负责从 Question / PracticeQuestionGroup 取出 answer_kind / work_mode /
    answer / answer_json 等字段，再转交给 grade_by_answer_kind()。
    按 answer_kind 分派的具体逻辑**只有一份**，在 math_grade.py 里。
    """
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
- `work_modes` 注册表完整性：每个 **数学** mode 的 `answer_kind` / `input_ui` / `legacy_qtype` 合法
  （语文/英语占位条目的 id 尚未注册，跳过交叉校验）
- 页面分析 JSON 解析：正常、缺字段、未知 `work_mode`（→`other`）
- `is_example` 过滤：示例不进待做项、不参与求答案、不进待补清单
- `page_type` 过滤：`toc` / `answer_key` / `cover` 不入库
- **密集网格**：同一 `y` 值的 items 聚成一行，按 `y` 排序不乱序
- 跨页合并：`continues_next_page` 且 `work_mode` 相同且 stem 匹配 → 合并；
  不匹配 → 保留两段并标 `incomplete`
- **迁移不删数据**：跑 `migrate()` 后已有练习册题目数量不变
- **重新导入清理**：同一 doc 重导后题组不累积（旧组被显式删除）
- 判分分派：`number` / `numeric_list` / `symbol` / `photo` 各走对分支
- **发布闸门**：每种 `answer_kind` 都能通过 `_is_aligned`（含 `choice`/`symbol`/`equation`）
- **发布闸门（旧题回归）**：`work_mode=""` 的存量题仍走 `_is_aligned_legacy`，空 `blanks`
  的 `cloze` 题依旧不发布（防新分支误放行）
- `photo` 题必须有 `answer` 才发布（空答案进待补）
- `build_drafts` 不再把 `fill_blank` 降级成 `oral`
- **题组入库**：导入后 `group_id` 非空，且题组数 = 跨页合并后的组数
- **重导入幂等**：同一 doc 重导后题组不累积（旧组显式删除）
- **答案页可选**：`answer_start_page=None` 时仍能跑满 `total_pages`
- **回归（对齐 §4 样例）**：找规律题 = 1 个题组、共 **4 个 items**（3 个 `is_example`
  + 1 个待做），且待做项 `question` 以 `____` 结尾
- **回归**：脱式题 `need_process=true`，只填数值不算完成
- **泛化**：`ocr_import` 产出的 draft 带 `work_mode`，判分走 `grade_by_answer_kind`
- **泛化**：`work_modes` / `subjects` 注册表不依赖具体入口，只依赖 `question_types`
- **学科**：上传 `语文`/`英语` 练习册时返回 400「该学科解析器尚未实现」（不静默乱导）
- **格式**：解析出的 `question` 只含白名单标记（`____` / `○` / `□` / `换行缩进` / `$...$` 基础 LaTeX / `![](url)`），
  不含 HTML 标签
- **格式**：竖式题的 `question` 保留 `\n` 与行首空格，且每行各自 `$...$` 成对
- **格式**：比较大小题的 `○` 原样保留，未被 AI 替换成具体符号
- **格式**：`$...$` 成对出现；中文/标点/单位不出现在 `$...$` 内部（防前端把中文渲染成红字回退）
- **格式**：`$` 计数为偶数（对 `build_drafts` 的每个输出做断言）
- **`_strip_answer` + LaTeX**：`$111.06 \div 0.9 = 123.4$` → `$111.06 \div 0.9 =$ ____`（`$` 仍成对）
- **`_strip_answer` + 方程**：`$4x-5.2 = 5.2$` 不截断（含未知数）
- **`_strip_answer` + 示例**：`is_example=True` 的行完全不截断
- **`_strip_answer` 兜底**：截断会导致 `$` 变奇数时，退化为不截断
- **图片题求答案**：`geometry` 题组把裁图 PNG 一并送视觉模型；失败则该题 `pending` 进待补清单

Flutter
- 题组展示：题干 + 示例 + 待做项
- 按 `input_ui` 渲染对应交互（数字键盘 / 符号选择 / 拍照）
- `need_process` 的题必须拍照才能提交
- `math_text` 单元测试：
  - `$x^2$` → 1 个 `WidgetSpan`，其余文本正确
  - **短公式降级**：`$2.5$`（源码 3 字符）→ `TextSpan` 而非 `WidgetSpan`，
    文本为 `2.5`（`$` 已去）
  - **不降级**：`$\frac{3}{4}$`（含 `{`）→ `WidgetSpan`
  - `$` 不配对（`只有 $一个`）→ 全文按普通文本处理，不吞字符
  - 非法 LaTeX（`\frac{1}{2`）→ `onErrorFallback` 生效，不抛异常
  - 多行竖式（两行各一个 `$...$`）→ 2 个 `Math.tex`，行序正确
  - 空串 / 纯中文 → 只产生 `TextSpan`
- `question_html` 回归：题干里的 `$...$` 不再被 `_stripDollars` 静默剥成 `x^2` 源码

parent-web
- `renderQuestionHtml` 对 `$...$` 输出 `<span class="math-tex" data-tex="...">` 而不是剥掉 `$`
- `decorateMath` 在无 `window.katex` 时不崩（降级为等宽原文）
- **Dockerfile 冒烟**：用 `docker run --rm knoact-parent-web ls /usr/share/nginx/html/vendor/katex/`
  断言文件存在（**不要**用 HTTP 200 判断——`nginx.conf` 的 `try_files ... /index.html`
  会把缺失路径回退成 200 + index.html，测不出回归）

**容错**

| 场景 | 处理 |
| --- | --- |
| AI 返回非 JSON | 该页标失败，可重试 |
| `page_type` 拿不准 | 默认 `practice`（宁可多导） |
| `work_mode` 不认识 | 存 `other`，进待家长确认 |
| 跨页合并失败 | 保留两段，标「可能不完整」 |
| 全书无任何题组 | job 标 failed，提示检查 PDF |
| 求答案失败 | 该题 `pending`，进待补清单 |
| 公式渲染失败 | `onErrorFallback` 显示红色原 LaTeX，题目仍可作答 |
| 旧数据 | 重导前明确提示会清空 |

### 八、改动文件清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/core/work_modes.py` | 新增：`WorkModeSpec` + 数学题型注册表 |
| `backend/app/core/subjects.py` | 新增：`SubjectSpec` 学科注册表（数学实现，语文/英语占位） |
| `backend/app/services/parsers/math_page.py` | 新增：数学整页分析——`_PAGE_SYSTEM`/`_PAGE_PROMPT`（含题目格式约束：空位 `____`、竖式 `□` 保留、每行独立 `$...$`、数学式用基础 LaTeX、中文不进 `$`；§四 的 JSON 示例即 few-shot 样例）+ 结果解析 + 调 `ai.vision_json()`。§4/§9.2 引用的「页面分析」都指这个文件 |
| `backend/app/models.py` | 新增 `PracticeQuestionGroup`、`PracticeImportPage`；`Question` 加 4 列（裸 `group_id`） |
| `backend/app/services/ai.py` | **新增 `vision_json(db, image_bytes, system, prompt) -> str`**：现有 `generate()` 只收文本、`ocr_image()` 不支持 JSON，整页分析必须两者兼有。实现照 `ocr_image` 的 `image_url` 组装方式，另加 `response_format={"type":"json_object"}` 与 `system` 消息 |
| `backend/app/migrate_practice_groups.py` | 新增：建表（`create_all` 兜底）+ 加 4 列 + 建 `ix_questions_group`（**不删数据**） |
| `backend/app/core/source_adapter.py` | `QuestionDraft` 加 `group_id`/`seq_in_group`/`is_example`/`work_mode` |
| `backend/app/routers/bank.py` | `_persist_drafts` 透传 4 个新字段；`GET /{bank_id}/questions` 返回题组题干/示例/`work_mode`/`input_ui`/`answer_kind`；`POST /submit` 有 `work_mode` 时改走 `grade_practice_item` |
| `backend/app/services/practice_grade.py` | 新增：按 `answer_kind` 分派判分（`grade_by_answer_kind` 的**薄包装**，负责把 `Question`/`PracticeQuestionGroup` 的字段拆出来） |
| `backend/app/services/math_grade.py` | 新增：**所有数学入口共用的判分门面**（`grade_by_answer_kind`，唯一一份按 `answer_kind` 分派的实现） |
| `backend/app/services/ocr_import.py` | 对齐：`_STRUCTURE_SYSTEM` 增 `work_mode`/`need_process`/`is_example`；`content` 白名单补 `$...$`（与 §十 一致）；判分改走 `math_grade` |
| `backend/app/services/practice_solve.py` | **保留函数名 `solve_math_items`**，返回类型改为 `dict[int, dict]`；同步改 `tests/test_practice_import.py` 的 monkeypatch |
| `backend/app/services/practice_image.py` | **删除** `detect_image_questions()`；保留 `crop_question_image()` |
| `backend/app/services/practice_import.py` | 重写：页面分析 + 跨页合并 + **先建题组再挂小题**；`retry_pages` 同步删旧题组；**`_strip_answer` 加 `is_example` 参数并感知 `$` 边界**（见 §10.2）；同时移除 `_IMAGE_HINT_RE`（在旧文件第 479 行）；**删除** `parse_lesson_page`/`_split_row`/`parse_answer_page`/`align_answers`/`align_by_order` 及其测试 |
| `backend/app/routers/practice_import.py` | 题组浏览；待补清单过滤 `is_example`；页类型查询与修改；重新导入清理入口 |
| `backend/app/routers/practice.py` | `/preview` 返回题组题干；**新增** `/records` 与 `/answer-photo` |
| `backend/app/routers/pdf.py` | `delete_document` 时显式删除该 doc 的题组与页记录 |
| `backend/app/services/task_gen.py` | 抽题按**小题**，带出题组题干与示例 |
| `backend/app/main.py` | 启动跑新迁移（仅 schema）；续跑范围回退到 `total_pages` |
| `parent-web/app.js` | 题组形式展示；页类型可修正；重新导入二次确认；答案页改为可选；`renderQuestionHtml` 不再剥 `$`，输出 `<span class="math-tex" data-tex>` 并由新增的 `decorateMath(root)` 调 `katex.render`；`____`→下划线、`○`→符号占位、`□`→小空框 |
| `student-app/lib/features/bank_exercise/data/bank_models.dart` | 题目模型加 `groupStem`/`examples`/`workMode`/`inputUi`/`answerKind` |
| `student-app/lib/core/widgets/math_text.dart` | 新增：`$...$` 切分 + `Math.tex` 行内渲染 + 短公式降级纯文本 + `onErrorFallback` |
| `student-app/lib/features/bank_exercise/question_html.dart` | 新增 `____`→输入框、`○`→符号按钮、`□`→小输入框（竖式用）、竖式行首空白保留；`_stripDollars` 改为委托 `math_text`（不再静默剥 `$`） |
| `student-app/lib/features/bank_exercise/ui/bank_exercise_page.dart` | 题组展示 + 按 `inputUi` 渲染 |
| `student-app/lib/features/practice/`（新增） | 每日一练：题组式、多空、拍照（`photo`/`numeric_list` 只在这里做） |
| `student-app/pubspec.yaml` | **已加** `flutter_math_fork: ^0.7.4`（工作区现有改动，KaTeX 字体随包 617 KB） |
| `parent-web/vendor/katex/`（新增） | `katex.min.js` + `katex.min.css` + `fonts/`（本地内置，不走 CDN） |
| `parent-web/index.html` | 引入 `vendor/katex/katex.min.css` 与 `katex.min.js` |
| `parent-web/Dockerfile` | **必须改**：`COPY index.html app.js ./` + `COPY vendor/ .../vendor/`（否则镜像 404 静默降级） |
| `backend/tests/test_practice_groups.py` | 新增，含格式标记测试 |

**关于答案页范围**：新流程用 AI 求答案，`answer_start_page`/`answer_end_page` 不再必需，
降级为**可选**（家长若提供，则用答案页做交叉校验；不提供则纯 AI 求答案）。
上传接口与 parent-web 表单都要把这两项从「必填」改成「可选」。

⚠️ **可选化必须同步改三处派生逻辑，否则不填答案页会导入 0 页**：

```python
# practice_import.py:559 与 _job_payload、main.py 的断点续跑共用同一表达式
q_end = job.question_end_page or (job.answer_start_page or 1) - 1   # ❌ answer_start 为 None → q_end=0
# 改为：
q_end = (job.question_end_page
         or ((job.answer_start_page - 1) if job.answer_start_page else job.total_pages))
```

需要改的三处：
1. `services/practice_import.py:run_import_job()` 计算 `q_end`
2. `routers/practice_import.py:_job_payload()` 计算 `question_pages`
3. `main.py` 启动续跑时计算 `failed_pages` 范围

### 九、按学科泛化

**本期只做数学**，但结构按学科预留，以后加语文/英语不用重构。

#### 9.1 学科注册表

```python
# core/subjects.py
@dataclass(frozen=True)
class SubjectSpec:
    id: str                        # 数学 | 语文 | 英语
    label: str
    parser_id: str                 # 该学科用哪个页面解析器
    work_mode_ids: tuple[str, ...]  # 该学科可用的题型（来自 work_modes 注册表）

SUBJECTS: dict[str, SubjectSpec] = {
    "数学": SubjectSpec("数学", "数学", "math_page", (
        "oral", "vertical", "step", "equation", "pattern", "compare",
        "unit_compare", "fill_vertical", "letter_pattern", "geometry",
        "app", "choice", "judge", "other")),
    # 以下本期不实现，仅占位表明扩展点。work_mode_ids 里的 id 尚未注册到
    # work_modes（等实现语文/英语时一起加），因此「注册表完整性」测试只校验数学。
    "语文": SubjectSpec("语文", "语文", "text_page", (
        "pinyin", "dictation", "fill_blank", "reading", "comprehension", "other")),
    "英语": SubjectSpec("英语", "英语", "text_page", (
        "word_spelling", "listening", "cloze", "reading", "choice", "other")),
}
```

#### 9.2 分层：通用编排 + 学科专用解析

```
services/practice_import.py          通用编排（建组/跨页合并/求答案/发布/待补）
      │  按 subject 取 parser_id
      ├─ services/parsers/math_page.py      ← 本期实现
      └─ services/parsers/text_page.py      ← 语文/英语，以后实现
```

| 层 | 是否学科无关 | 本期状态 |
| --- | --- | --- |
| 导入编排（建组、跨页、发布、待补） | **是** | 实现（通用） |
| 数据模型 `PracticeQuestionGroup` + `Question` | **是** | 实现（通用） |
| 题型结构 `WorkModeSpec` | **是**（结构） | 实现（数学 14 种） |
| 页面分析提示词 | 否 | 数学一份 |
| 判分分派 `math_grade.py` | 否 | 数学一份 |
| 学科注册表 `subjects.py` | **是** | 实现（语文/英语仅占位） |

**为什么数据模型可以通用**：题组本身就是「一段题干 + 若干小题」，
语文的「阅读短文 + 5 道小题」、英语的「完形填空 + 若干空」都天然是题组。
判分所需的 `answer_kind` **不落库**，而是由 `work_mode` 查注册表得到
（语文用 `text`；英语填空将来加一个 `blanks` 类 `answer_kind`，届时同步扩
`grade_by_answer_kind` 的分派表）。

#### 9.3 与现有数学入口的关系

| 入口 | 本期处理 |
| --- | --- |
| `services/practice_import.py` | **重写**（走 `math_page` 解析器） |
| `services/ocr_import.py`（卷子拍照） | **对齐**：提示词加 `work_mode`，判分走统一门面 |
| `services/math_gen.py`（现场出题） | 不动（语义是「出题」不是「解析」） |
| `question_gen.py` / `knowledge_quiz.py`（语文英语题） | 不动（本期不碰非数学解析） |

**统一判分门面**（数学本期，其他学科以后加同构的）

```python
# services/math_grade.py
def grade_by_answer_kind(db, question, student_answer="", photo_bytes=None) -> dict:
    """按 answer_kind 分派：number/numeric_list/symbol/choice/text/photo。"""
```

#### 9.4 以后接语文/英语要做什么（不在本期）

1. `work_modes` 加语文/英语题型（如 `pinyin` 拼音、`cloze` 完形）
2. 写 `parsers/text_page.py`（提示词不同，输出结构相同）
3. 写 `language_grade.py`（拼音/书写判分规则与数值不同）
4. **数据模型、导入编排、跨页合并、发布闸门、待补清单零改动**

### 十、题目格式与展示（解析即考虑呈现）

**原则：解析输出的 `content` 必须是「前端能直接渲染」的有限标记文本，不是纯文本。**

现有前端已支持有限标记（`ocr_import._STRUCTURE_SYSTEM` 定义）：
`# ## ** * <u> /ipa/ ____`｜学生端 `question_html.dart` 另有分块解析（题干/选项/子题）。

数学需要补充的标记（本期实现）：

| 场景 | 标记 | 前端渲染 | 本期 |
| --- | --- | --- | --- |
| 填空位 | `____`（已有） | 输入框 | ✅ 已有 |
| 竖式挖空位 | `□` | 输入框（小） | ✅ |
| 比较大小待填 | `○` | 三个按钮 `>` `<` `=` | ✅ |
| **数学式** | **`$...$`（LaTeX）** | **`Math.tex()` 行内渲染** | ✅ |
| 竖式/脱式的多行 | 每行一个 `$...$`，行间用 `\n` | 逐行 `Math.tex` + 行首空格保留（**不用** `\begin{aligned}`） | ✅ |
| 图形 | `![](/uploads/practice_images/xxx.png)` | 现有 `img` 支持 | ✅ 已有 |
| 单位 | 原样（`km`、`m²`、`cm²`） | 正常文本 | ✅ 已有 |
| 表格 | ——（不引入表格标记） | ——（不做） | ⛔ 不做（见下） |

> **表格题本期整块裁图**：练习册里的统计表/方格表用 `image_questions` 裁图，
> 建组时 `work_mode` 用**已注册的 `geometry`**（`photo`/`camera`，判分走拍照），
> 不新增 `table` 题型、不引入 `|` 分隔标记。避免表格还原与竖式标记的双重成本。

#### 10.1 LaTeX 渲染（实测通过）

**决策依据**：已用 CanvasKit + release + `--no-web-resources-cdn`（与生产一致）实测
`flutter_math_fork: ^0.7.4`，结论如下：

| 验证项 | 结果 |
| --- | --- |
| 分式 / 根号 / 上标 / `\left(\right)` | ✅ 全部正确，无 tofu |
| 中文叙述夹行内公式（380px 卡宽） | ✅ 断行正常、基线对齐 |
| 非法公式（`\frac{1}{2` 缺右括号） | ✅ `onErrorFallback` 红字显示原文，不崩 |
| Web release 构建 | ✅ 通过（20s） |

> 包 README 称「CanvasKit 后端预期会破坏」，**该警告已过时**（作者只在 Flutter 早期版本测过）。

**实现约束**

1. **只在数学式位置用 LaTeX**：中文叙述、标点、单位一律普通文本，不塞进 `$...$`。
2. **短公式降级为纯文本（前端行为，不改数据）**：`math_text` 解析时，若某个 `$...$`
   内部的 LaTeX 源码 ≤ 6 字符且不含 `\ \ ^ _ { }` 任一字符（如 `2.5`、`15`、`x`），
   则**去掉 `$` 按普通 `TextSpan` 渲染**，不用 `Math.tex`——避免 `WidgetSpan` 整块换行
   把后面的 `（　　）` 拆到下一行（实测真实出现的瑕疵）。**数据里仍保留 `$`**，
   降级只发生在渲染层，语义不变。
3. **行内公式用 `WidgetSpan(alignment: PlaceholderAlignment.middle)`**。
4. **多行竖式/脱式：一行一个 `$...$`，不要用 `\begin{aligned}`**（`aligned` 属
   `\begin{...}` 家族，已被 AI 约束禁用）。前端按 `\n` 切成多行、每行独立 `Math.tex`，
   行首空格用 `Text` 前导空白 + 等宽字体对齐。
5. **必须给 `onErrorFallback`**：返回原文 `Text`（红色），绝不抛异常。
6. 公式内**不允许换行**；`$` 不配对时按普通文本处理（正则只匹配成对的 `$[^$]+$`）。

**体积代价（实测，可接受）**

| 项 | 数值 |
| --- | --- |
| KaTeX 字体（20 个 TTF，随包产出） | 617 KB |
| `main.dart.js` | 1696 → 2791 KB（gzip 503 → **829 KB，+326 KB**） |

字体由 pubspec 的 asset 自动打包，Web/APK 均无需额外配置。首次加载略慢，之后进缓存。

**AI 输出约束（写进页面分析提示词）**

1. `items[].text` 中的空位**统一用 `____`**（不用「（　）」「(  )」等）；
   **竖式里的方格挖空保留印刷的 `□` 原样**（不改成 `____`，否则竖式对齐会被破坏）
2. 竖式题保留换行与对齐空格，用 `\n` 分隔行、**每行各是一个独立 `$...$`**（不用 `\begin{aligned}`）
3. 比较大小题把待填的 `○` 原样保留
4. **数学式用 `$...$` 包裹 LaTeX**（如 `$\frac{3}{4}$`、`$4x-5.2=5.2$`、
   `$111.06 \div 0.9 = 123.4$`）；中文、标点、单位**不得**放进 `$...$`
5. 只用基础 LaTeX：`\frac \sqrt ^ _ \times \div \pm \left( \right) \underline`；
   **禁用** `\begin{...}` 宏包、`\text{}`、`\color`、`\require` 等需扩展的语法
6. 图形引用用 `![](路径)`，路径由后端裁图后回填

> 提示词里给的 LaTeX 白名单必须与前端 `Math.tex` 实际支持范围一致；超范围语法会走
> `onErrorFallback` 露出红色原文，属可接受的可见失败（比静默显示错公式好）。

#### 10.2 `_strip_answer` 必须感知 `$` 边界（防破坏成对性）

`practice_import._strip_answer()` 现在在第一个 `=` 处截断并返回 `left + " ="`。
对 `$111.06 \div 0.9 = 123.4$` 会截成 `$111.06 \div 0.9 =` —— **留下单个未配对 `$`**，
前端按 10.1 约束 6 会把整段当普通文本，用户直接看到 `\div` 源码。

**规则（必须实现，顺序不可颠倒）**

```python
def _strip_answer(question: str, *, is_example: bool = False) -> str:
```

0. **`is_example=True` → 直接返回原文**（示例本来就要显示答案，任何截断都不做）。
1. **左侧含未知数 → 不截断**（沿用现有 `_has_variable()`，见 `practice_import.py:286`）。
   `$4x-5.2 = 5.2$` 里的 `5.2` 是方程的一部分，截掉就无解。**这条优先于下面所有规则。**
2. **只在 `$...$` 内部判断**：取第一个 `$...$` 的表达式内容做「是否已算出答案」的
   判断（右侧是否以数字开头），而不是对整串做正则。
3. **截断点在公式内部 → 重新闭合 + 补空位**：
   `$111.06 \div 0.9 = 123.4$` → `$111.06 \div 0.9 =$ ____`
   （`$` 数量保持成对，且给出填空提示）。
4. **兜底**：截断后若 `$` 计数为奇数，退化为不截断（宁可露出答案，也不要产生坏标记）。

> `build_drafts` 调用处必须传 `is_example=q.get("is_example", False)`。

> 等价约束：任何进入 `Question.question` / `PracticeQuestionGroup.stem` 的字符串，
> `$` 必须成对。建议在 `build_drafts` 出口加一条断言（测试里必须覆盖）。

**双端展示统一**

| 端 | 渲染方式 |
| --- | --- |
| 学生端 Flutter | 复用 `question_html.dart` 的分块渲染；新增 `____`→输入框、`○`→符号按钮、`$...$`→`Math.tex` |
| 家长端 parent-web | 同一份标记，`white-space: pre-wrap` 保留竖式排版；`____` 显示为下划线；`$...$` 用 **katex.render** |

**家长端公式渲染（选定方案）**

`parent-web/app.js` 现有 `renderQuestionHtml` 用 `.replace(/\$([^$]+)\$/g, '$1')`
**主动剥掉 `$`**（第 593 行），必须改为输出
`<span class="math-tex" data-tex="..."></span>`，再由一个统一收尾函数处理。

- **选定 `katex.render`（显式遍历），不用 `renderMathInElement`**。理由：`renderQuestionHtml`
  返回 HTML 字符串、有 5 处调用点，之后还会 `innerHTML` 重绘；`auto-render` 需要在每次
  重绘后手动重跑，容易漏。改成「渲染完 DOM 后调一次 `decorateMath(root)`」更可控。
- KaTeX **本地内置**（不做 CDN）：`parent-web/vendor/katex/katex.min.js` + `katex.min.css`
  + `fonts/`，`index.html` 用相对路径引入。理由：部署环境可能无外网，且 CDN 与本地
  行为不一致会让「无 KaTeX 时不崩」的测试失去意义。
- **`parent-web/Dockerfile` 必须同步**：现在只 `COPY index.html app.js`，需改成
  `COPY index.html app.js ./` + `COPY vendor/ /usr/share/nginx/html/vendor/`，
  否则镜像里 404、静默降级成裸 LaTeX。
- 无 KaTeX 脚本时（本地直接开 html）`decorateMath` 直接返回，`<span>` 内回退为原文等宽文本。

**`content` 存哪里**：`Question.question`（现有 LongText 字段），保持与题库练习、语文/英语题一致，
**不新增富文本字段**，避免前端出现两套渲染逻辑。

**题组题干同样遵循该标记**：`PracticeQuestionGroup.stem` 也允许上述标记。

## 后续可扩展（不在本次范围）

- 题组嵌套（大题套小问）
- OCR 置信度打分与自动复核
- 多本书合并成一个卷
- 题型级统计（哪类题最常错）
