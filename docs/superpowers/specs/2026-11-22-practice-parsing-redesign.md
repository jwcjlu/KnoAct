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
    input_ui: str      # keypad | chooser | camera | table | special
    grade_band: str    # lower(1-2) | middle(3-4) | upper(5-6)
    legacy_qtype: str  # 映射到 Question.qtype，复用既有判分
```

初始注册项：

| id | label | answer_kind | input_ui | grade_band | legacy_qtype |
| --- | --- | --- | --- | --- | --- |
| `oral` | 口算 | number | keypad | lower | oral |
| `vertical` | 竖式 | photo | camera | middle | calculation |
| `step` | 脱式/简算 | photo | camera | middle | calculation |
| `equation` | 解方程 | number | keypad | middle | fill_blank |
| `pattern` | 找规律 | numeric_list | keypad | middle | fill_blank |
| `compare` | 比较大小 | symbol | chooser | lower | fill_blank |
| `unit_compare` | 单位换算比较 | symbol | chooser | middle | fill_blank |
| `fill_vertical` | 填空竖式 | photo | camera | middle | calculation |
| `letter_pattern` | 字母规律 | numeric_list | keypad | upper | fill_blank |
| `geometry` | 图形题 | photo | camera | upper | application |
| `app` | 应用题 | photo | camera | middle | application |
| `choice` | 选择题 | choice | chooser | lower | single_choice |
| `judge` | 判断题 | choice | chooser | lower | true_false |
| `other` | 其他/未识别 | text | keypad | middle | short_answer |

**扩展方式**：新题型（分式运算、单位换算、作图题、数轴标点…）只加一行
`WorkModeSpec`，判分按 `answer_kind` 分派、前端按 `input_ui` 渲染，两侧都不用改代码。

`extra` 字段预留（dict），承载「必须写过程」「允许多解」等未来属性，不破坏既有 spec。

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
    raw_pages: Mapped[str] = mapped_column(LongText, default="[]")  # 原始 OCR 文本（排查）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

#### 3.2 `Question` 加字段

```python
group_id: Mapped[int | None] = mapped_column(
    ForeignKey("practice_question_groups.id", ondelete="CASCADE"), nullable=True)
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
| `groups[].work_mode` | 取自注册表；拿不准填 `other` |
| `groups[].need_process` | 脱式/竖式/应用题为 `true` |
| `groups[].continues_next_page` | 页尾被截断时为 `true` |
| `items[].text` | 原样抄录，**严禁计算** |
| `items[].answer_hint` | 仅当页面印了答案（示例行）才填 |
| `items[].is_example` | 示例行 `true`，不入待做项 |
| `image_questions[]` | 需看图的题，给纵向比例（沿用现有裁图逻辑） |

**硬约束（写进 system prompt）**

1. 严禁计算、严禁把答案写进 `text`（此前踩过坑）
2. 一页有几个大题就返回几个 group，不许自行合并或拆分
3. `answer_hint` 只抄页面已印内容
4. 拿不准时 `work_mode = "other"`，不要猜

### 五、跨页合并

全书扫描完成后统一处理：

```
遍历相邻页：
  if prev.groups[-1].continues_next_page and next.groups[0].stem 相近(编辑距离/包含):
      合并 items，重编 seq；group.page_end = next_page
```

合并失败（stem 不匹配）时保留为两个题组，标 `incomplete=true` 提示家长。

### 六、求答案与判分

**按 `answer_kind` 分派**（不按题型名）：

| answer_kind | 求答案 | 判分 |
| --- | --- | --- |
| `number` | AI 批量算数值 | `grade_math_answer()` |
| `numeric_list` | AI 算多个空 | 逐空比较，全对才算对 |
| `symbol` | AI 判 > < = | 精确匹配 |
| `choice` | 从选项挑 | 精确匹配索引 |
| `text` | AI 生成参考答案 | `grade_subjective()` |
| `photo` | 不求答案（家长补） | `grade_math_work_photo()` |

**示例行（`is_example=true`）跳过求答案**（页面已印）。

**`need_process=true` 的题**：AI 仍算出标准答案用于判对错，但孩子**必须拍照提交**，
只填数值不算完成；判分 = 最终答案对 **且** 过程合理。

**统一入口**：新建 `services/practice_grade.py`

```python
def grade_practice_item(db, question, student_answer="", photo_bytes=None) -> dict:
    """返回 {is_correct, ai_status, final_answer, steps_plausible, reason}。"""
```

**未求到答案** → `status=pending`，进「待补答案」清单，不发布。

**抽题规则**（每日一练）：按**小题**抽，展示时带上所属题组题干与示例。
这样「40 道口算」可以每天抽 3 道，孩子能看到「直接写出得数」的引导语。

### 七、迁移与测试

**迁移**（新增 `migrate_practice_groups.py`）

1. 建 `practice_question_groups` 表
2. `questions` 加 4 列（`group_id` / `seq_in_group` / `is_example` / `work_mode`）
3. 清空旧练习册数据：`DELETE FROM questions WHERE source_document_id IS NOT NULL`
4. 家长端重新导入

**测试**

后端 pytest（`tests/test_practice_groups.py` + 扩展 `test_practice_import.py`）
- `work_modes` 注册表完整性：每个 mode 的 `answer_kind` / `input_ui` / `legacy_qtype` 合法
- 页面分析 JSON 解析：正常、缺字段、未知 `work_mode`（→`other`）
- `is_example` 过滤：示例不进待做项、不参与求答案
- `page_type` 过滤：`toc` / `answer_key` / `cover` 不入库
- 跨页合并：`continues_next_page=true` 且 stem 匹配 → 合并；不匹配 → 保留两段并标 incomplete
- 判分分派：`number` / `numeric_list` / `symbol` / `photo` 各走对分支
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
| `backend/app/models.py` | 新增 `PracticeQuestionGroup`；`Question` 加 4 列 |
| `backend/app/migrate_practice_groups.py` | 新增：建表 + 加列 + 清旧数据 |
| `backend/app/services/practice_page_ai.py` | 新增：整页视觉分析（OCR + 结构化合并） |
| `backend/app/services/practice_import.py` | 重写：改用页面分析结果 + 跨页合并 |
| `backend/app/services/practice_grade.py` | 新增：按 `answer_kind` 分派判分 |
| `backend/app/services/practice_solve.py` | 扩展：支持 `numeric_list` / `symbol` |
| `backend/app/routers/practice_import.py` | 题组浏览、待补清单按题组展示 |
| `backend/app/services/task_gen.py` | 抽题按小题，带题组题干 |
| `backend/app/main.py` | 启动跑新迁移 |
| `parent-web/app.js` | 题组形式展示题目；页面类型可手动修正 |
| `student-app/lib/features/...` | 题组展示 + 按 `input_ui` 渲染 + `need_process` 强制拍照 |

## 后续可扩展（不在本次范围）

- 题组嵌套（大题套小问）
- OCR 置信度打分与自动复核
- 多本书合并成一个卷
- 题型级统计（哪类题最常错）
