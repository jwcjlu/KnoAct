"""题型注册表：answer_kind（判分方式）+ input_ui（前端交互）。

仿 `provider_registry` 的声明式写法。新增题型只加一行 `WorkModeSpec`，
判分按 `answer_kind` 分派、前端按 `input_ui` 渲染，两侧都不用改代码。
"""
from dataclasses import dataclass

# 判分方式（math_grade.grade_by_answer_kind 的分派键）
ANSWER_KINDS = ("number", "numeric_list", "symbol", "choice", "text", "photo")
# 前端交互形态
INPUT_UIS = ("keypad", "chooser", "camera")


@dataclass(frozen=True)
class WorkModeSpec:
    id: str            # oral | step | compare | ...
    label: str         # 口算 | 脱式/简算 | 比较大小
    answer_kind: str   # 见 ANSWER_KINDS
    input_ui: str      # 见 INPUT_UIS
    legacy_qtype: str  # 映射到 Question.qtype，复用既有 taxonomy


MATH_WORK_MODES: tuple[WorkModeSpec, ...] = (
    WorkModeSpec("oral", "口算", "number", "keypad", "oral"),
    WorkModeSpec("vertical", "竖式", "photo", "camera", "calculation"),
    WorkModeSpec("step", "脱式/简算", "photo", "camera", "calculation"),
    WorkModeSpec("equation", "解方程", "number", "keypad", "fill_blank"),
    WorkModeSpec("pattern", "找规律", "numeric_list", "keypad", "fill_blank"),
    WorkModeSpec("compare", "比较大小", "symbol", "chooser", "fill_blank"),
    WorkModeSpec("unit_compare", "单位换算比较", "symbol", "chooser", "fill_blank"),
    WorkModeSpec("fill_vertical", "填空竖式", "photo", "camera", "calculation"),
    WorkModeSpec("letter_pattern", "字母规律", "numeric_list", "keypad", "fill_blank"),
    WorkModeSpec("geometry", "图形题", "photo", "camera", "application"),
    WorkModeSpec("app", "应用题", "photo", "camera", "application"),
    WorkModeSpec("choice", "选择题", "choice", "chooser", "single_choice"),
    WorkModeSpec("judge", "判断题", "choice", "chooser", "true_false"),
    WorkModeSpec("other", "其他/未识别", "text", "keypad", "short_answer"),
)

REGISTRY: dict[str, WorkModeSpec] = {m.id: m for m in MATH_WORK_MODES}

# 兜底 id：未知题型一律归这里，绝不抛异常
FALLBACK_ID = "other"


def spec_of(work_mode: str | None) -> WorkModeSpec:
    """查不到（空串/None/未知）一律回落 other。"""
    return REGISTRY.get((work_mode or "").strip(), REGISTRY[FALLBACK_ID])


def answer_kind_of(work_mode: str | None) -> str:
    return spec_of(work_mode).answer_kind


def input_ui_of(work_mode: str | None) -> str:
    return spec_of(work_mode).input_ui


def legacy_qtype_of(work_mode: str | None) -> str:
    return spec_of(work_mode).legacy_qtype