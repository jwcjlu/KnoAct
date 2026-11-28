# 自然拼读发音规则库（GPC Catalog）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在仓库内建成以 `content/phonics/rules.yaml` 为唯一真相的自然拼读主音规则库（≥60 条闭合清单）+ 推荐路径 + 手册/音频清单生成，规则音可 TTS 落盘；不改 KnoAct 业务代码。

**Architecture:** 内容与工具自包含在 `content/phonics/`。`REQUIRED_GRAPHEMES` 常量对齐设计「范围 B 闭合清单」；校验器保证字段、年级例词、`path_order`；生成器产出可读手册与 `audio_manifest.yaml`；合成脚本只补缺失规则音（支持 `--fake` 以便无 API 时验收管线）。例词配套音频由人工放入 `audio/word/`，不自动化扒取。

**Tech Stack:** Python 3 + PyYAML + pytest；可选复用仓库 TTS（千问）经 HTTP/本地脚本；无 FastAPI 改动。

**Spec:** `docs/superpowers/specs/2026-11-28-phonics-gpc-catalog-design.md`

**测试命令：** 在仓库根目录  
`python -m pytest content/phonics/tests -v`  
（Windows 用 Bash 的 python，避免 conda base 缺依赖；先 `pip install -r content/phonics/requirements.txt`。）

---

## 文件结构

| 文件 | 职责 |
|------|------|
| Create: `content/phonics/requirements.txt` | `PyYAML`、`pytest`（内容工具独立依赖） |
| Create: `content/phonics/tools/inventory.py` | 范围 B 闭合 grapheme 清单常量 + 计数 |
| Create: `content/phonics/tools/schema.py` | 加载/校验单条与全库规则 |
| Create: `content/phonics/tools/generate_handbook.py` | 由 rules 生成 `handbook.md`（路径 TOC + 目录 TOC） |
| Create: `content/phonics/tools/generate_manifest.py` | 由 rules + `audio/` 生成 `audio_manifest.yaml` |
| Create: `content/phonics/tools/synthesize_rule_audio.py` | 按 manifest 合成缺失规则音（`--fake` / 真 TTS） |
| Create: `content/phonics/rules.yaml` | 唯一真相：全部主音规则 |
| Create: `content/phonics/path.yaml` | 七阶段语义说明（与 `path_order` 区间对应） |
| Create: `content/phonics/audio/rule/.gitkeep` | 规则音目录 |
| Create: `content/phonics/audio/word/.gitkeep` | 例词音目录（人工放入配套文件） |
| Create: `content/phonics/README.md` | 用法、目录 vs 路径、自用/产品化音频声明 |
| Create: `content/phonics/tests/test_inventory.py` | 清单条数与结构 |
| Create: `content/phonics/tests/test_schema.py` | 校验器 |
| Create: `content/phonics/tests/test_rules_coverage.py` | 全库对照闭合清单与成功标准 |
| Create: `content/phonics/tests/test_generate.py` | 手册/manifest 生成（tmp_path） |
| Generate: `content/phonics/handbook.md` | 生成物（可提交） |
| Generate: `content/phonics/audio_manifest.yaml` | 生成物（可提交） |

**不做：** `backend/`、`student-app/`、`parent-web/` 改动；练习计划；绕 DRM 扒音脚本。

### 稳定 `id` 命名（全计划锁定）

格式：`{category}.{grapheme}.{variant}`

| 场景 | variant | 示例 |
|------|---------|------|
| 元音字母主音（短元音） | `short` | `vowel.a.short` |
| 辅音 / 组合 / digraph / r 控制主音 | `primary` | `consonant.b.primary`、`vowel_team.ai.primary` |
| magic e | `magic_e` | `syllable_pattern.a_e.magic_e` |
| 意识型 | `awareness` | `syllable_pattern.closed_syllable.awareness` |
| 变音（非 REQUIRED 槽，可选同期写入） | 语义化后缀 | `vowel.a.magic_e` 指针用 notes；`consonant_digraph.th.voiced` |

禁止再用 `vowel.a.primary` 表示短元音主音（与上表冲突）。

---

### Task 1: 内容工具依赖 + 闭合清单常量

**Files:**
- Create: `content/phonics/requirements.txt`
- Create: `content/phonics/tools/__init__.py`（空）
- Create: `content/phonics/tools/inventory.py`
- Test: `content/phonics/tests/test_inventory.py`

- [ ] **Step 1: 写失败测试**

创建 `content/phonics/tests/test_inventory.py`：

```python
from content.phonics.tools.inventory import REQUIRED_BY_CATEGORY, all_required_graphemes, min_rule_count


def test_categories_are_exactly_six():
    assert set(REQUIRED_BY_CATEGORY) == {
        "vowel", "consonant", "vowel_team",
        "consonant_digraph", "r_controlled", "syllable_pattern",
    }


def test_min_count_at_least_60():
    assert min_rule_count() >= 60
    assert len(all_required_graphemes()) >= 60


def test_th_listed_under_digraph():
    assert "th" in REQUIRED_BY_CATEGORY["consonant_digraph"]
```

> 若 `content` 不是包：在 `content/phonics/tests/conftest.py` 把 `content/phonics` 加入 `sys.path`，改为 `from tools.inventory import ...`。计划默认采用 **conftest 加 path**，导入写 `from tools.inventory import ...`（下列测试一律如此）。

- [ ] **Step 2: 跑测试确认失败**

Run: `pip install -r content/phonics/requirements.txt && python -m pytest content/phonics/tests/test_inventory.py -v`  
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 inventory + requirements + conftest**

`content/phonics/requirements.txt`：

```
PyYAML==6.0.2
pytest==8.3.4
```

`content/phonics/tests/conftest.py`：

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # content/phonics
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

`content/phonics/tools/inventory.py`（grapheme 列表必须与 spec 闭合表一致；`th` 主音一条即可，清浊变音另 id 不占 REQUIRED 槽）：

```python
REQUIRED_BY_CATEGORY: dict[str, list[str]] = {
    "vowel": ["a", "e", "i", "o", "u", "y"],
    "consonant": list("bcdfghjklmnpqrstvwxz"),
    "consonant_digraph": ["sh", "ch", "th", "ck", "ng", "wh", "ph", "qu"],
    "vowel_team": [
        "ai", "ay", "ee", "ea", "oa", "ow", "oo", "oi", "oy",
        "ou", "aw", "au", "ew", "ie", "igh", "ue",
    ],
    "r_controlled": ["ar", "or", "er", "ir", "ur", "ore"],
    "syllable_pattern": [
        "a_e", "e_e", "i_e", "o_e", "u_e",
        "closed_syllable", "open_syllable",
        "tion", "ture", "le",
    ],
}


def all_required_graphemes() -> list[str]:
    out: list[str] = []
    for cat in (
        "vowel", "consonant", "consonant_digraph",
        "vowel_team", "r_controlled", "syllable_pattern",
    ):
        out.extend(REQUIRED_BY_CATEGORY[cat])
    return out


def min_rule_count() -> int:
    return len(all_required_graphemes())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest content/phonics/tests/test_inventory.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add content/phonics/requirements.txt content/phonics/tools content/phonics/tests
git commit -m "feat(phonics): 范围 B 闭合清单常量与内容工具依赖"
```

---

### Task 2: 规则 schema 校验器

**Files:**
- Create: `content/phonics/tools/schema.py`
- Test: `content/phonics/tests/test_schema.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from tools.schema import validate_rule, ValidationError, CATEGORIES


def _ok_rule(**over):
    base = {
        "id": "vowel.a.short",
        "category": "vowel",
        "grapheme": "a",
        "ipa": "/æ/",
        "approx_zh": "近似「啊」（短）",
        "example_words": [
            {"word": "cat", "grades": [3, 5], "source": "common"},
            {"word": "map", "grades": [3], "source": "common"},
            {"word": "fantastic", "grades": [5], "source": "common"},
        ],
        "accent": "oxford_shanghai",
        "audio": {
            "rule": {"path": "audio/rule/vowel.a.short.wav", "source": "tts"},
            "examples": [],
        },
        "path_order": 1,
        "notes": "",
    }
    base.update(over)
    return base


def test_valid_rule_passes():
    validate_rule(_ok_rule())


def test_rejects_bad_category():
    with pytest.raises(ValidationError):
        validate_rule(_ok_rule(category="vowel_letter"))


def test_requires_grade3_and_grade5_coverage():
    with pytest.raises(ValidationError):
        validate_rule(_ok_rule(example_words=[
            {"word": "cat", "grades": [3], "source": "common"},
            {"word": "map", "grades": [3], "source": "common"},
            {"word": "bat", "grades": [3], "source": "common"},
        ]))


def test_awareness_may_omit_ipa():
    validate_rule(_ok_rule(
        id="syllable_pattern.closed_syllable.awareness",
        category="syllable_pattern",
        grapheme="closed_syllable",
        ipa="",
        approx_zh="闭音节：元音发短音（说明）",
        path_order=40,
    ))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest content/phonics/tests/test_schema.py -v`  
Expected: FAIL（`tools.schema` 不存在）

- [ ] **Step 3: 实现 `schema.py`**

```python
CATEGORIES = frozenset({
    "vowel", "consonant", "vowel_team",
    "consonant_digraph", "r_controlled", "syllable_pattern",
})
AWARENESS = frozenset({"closed_syllable", "open_syllable"})


class ValidationError(ValueError):
    pass


def validate_rule(rule: dict) -> None:
    for key in ("id", "category", "grapheme", "approx_zh", "example_words", "accent", "audio"):
        if key not in rule:
            raise ValidationError(f"missing {key}")
    if rule["category"] not in CATEGORIES:
        raise ValidationError(f"bad category: {rule['category']}")
    if rule["accent"] != "oxford_shanghai":
        raise ValidationError("accent must be oxford_shanghai")
    ipa = rule.get("ipa") or ""
    if rule["grapheme"] not in AWARENESS and not ipa:
        raise ValidationError("ipa required for non-awareness rules")
    words = rule["example_words"]
    if len(words) < 3:
        raise ValidationError("need >=3 example_words")
    grades = set()
    for w in words:
        if "word" not in w:
            raise ValidationError("example missing word")
        g = w.get("grades") or [3, 5]
        grades.update(g)
        src = w.get("source", "common")
        if src not in ("textbook", "common"):
            raise ValidationError("example source must be textbook|common")
    if 3 not in grades or 5 not in grades:
        raise ValidationError("examples must cover grades 3 and 5")
    audio = rule["audio"]
    if "rule" not in audio or "path" not in audio["rule"] or "source" not in audio["rule"]:
        raise ValidationError("audio.rule.path/source required")
    if audio["rule"]["source"] not in ("textbook", "tts", "companion"):
        raise ValidationError("bad audio.rule.source")


def load_rules(path) -> list[dict]:
    import yaml
    from pathlib import Path
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "rules" not in data:
        raise ValidationError("root must be {rules: [...]}")
    rules = data["rules"]
    ids = [r["id"] for r in rules]
    if len(ids) != len(set(ids)):
        raise ValidationError("duplicate id")
    for r in rules:
        validate_rule(r)
    return rules
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest content/phonics/tests/test_schema.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add content/phonics/tools/schema.py content/phonics/tests/test_schema.py
git commit -m "feat(phonics): 规则 schema 校验器"
```

---

### Task 3: 脚手架目录 + `rules.yaml` 骨架（空列表可测加载）

**Files:**
- Create: `content/phonics/rules.yaml`
- Create: `content/phonics/path.yaml`
- Create: `content/phonics/audio/rule/.gitkeep`
- Create: `content/phonics/audio/word/.gitkeep`

- [ ] **Step 1: 写入最小合法文件**

`rules.yaml`：

```yaml
rules: []
```

`path.yaml`：

```yaml
stages:
  - { id: 1, name: "高频单辅音 + 短元音（CVC）", path_order_min: 1, path_order_max: 20 }
  - { id: 2, name: "其余辅音 / 易混音", path_order_min: 21, path_order_max: 35 }
  - { id: 3, name: "辅音 digraph", path_order_min: 36, path_order_max: 50 }
  - { id: 4, name: "常见元音组合", path_order_min: 51, path_order_max: 75 }
  - { id: 5, name: "r 控制", path_order_min: 76, path_order_max: 90 }
  - { id: 6, name: "magic e / 开闭音节", path_order_min: 91, path_order_max: 105 }
  - { id: 7, name: "次常见组合 + 多音节模式", path_order_min: 106, path_order_max: 130 }
```

（实现填内容时把每条 `path_order` 落入对应区间；区间可微调但阶段语义不变。）

- [ ] **Step 2: 确认空库可加载**

Run: `python -c "from pathlib import Path; import sys; sys.path.insert(0,'content/phonics'); from tools.schema import load_rules; print(len(load_rules('content/phonics/rules.yaml')))"`  
Expected: `0`

- [ ] **Step 3: Commit**

```bash
git add content/phonics/rules.yaml content/phonics/path.yaml content/phonics/audio
git commit -m "chore(phonics): 规则库与音频目录脚手架"
```

---

### Task 4: 填入 `vowel` + `consonant` 主音条目

**Files:**
- Modify: `content/phonics/rules.yaml`
- Test: `content/phonics/tests/test_rules_coverage.py`（本 Task 先写部分断言，后续 Task 扩展）

- [ ] **Step 1: 写覆盖测试（先只断言元音+辅音）**

```python
from pathlib import Path
from tools.schema import load_rules
from tools.inventory import REQUIRED_BY_CATEGORY

RULES = Path(__file__).resolve().parents[1] / "rules.yaml"


def _by_cat(cat: str) -> set[str]:
    rules = load_rules(RULES)
    return {r["grapheme"] for r in rules if r["category"] == cat}


def test_vowels_complete():
    assert _by_cat("vowel") >= set(REQUIRED_BY_CATEGORY["vowel"])


def test_consonants_complete():
    assert _by_cat("consonant") >= set(REQUIRED_BY_CATEGORY["consonant"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest content/phonics/tests/test_rules_coverage.py::test_vowels_complete -v`  
Expected: FAIL

- [ ] **Step 3: 写入全部 vowel + consonant 规则**

对每个 grapheme 一条记录，约定：

- `id`：严格按上文「稳定 id 命名」——元音 `vowel.{g}.short`，辅音 `consonant.{g}.primary`（`y` 作元音用 `vowel.y.short`）
- 短元音 IPA（全库统一，写入 README）：`a=/æ/` `e=/e/` `i=/ɪ/` `o=/ɒ/` `u=/ʌ/`；`y` 元音主音 `/ɪ/`（如 happy 尾），`notes` 可指后续变音
- 辅音：`c`→`/k/`，`g`→`/g/`，`q` 常与 u 出现，`approx_zh` 写清；每条 ≥3 例词且 grades 覆盖 3 与 5
- `path_order`：短元音 + 高频辅音（s a t p i n 等）落在 stage 1；其余辅音 stage 2
- `audio.rule.path`: `audio/rule/{id}.wav`（id 中的点保留，如 `audio/rule/vowel.a.short.wav`），`source: tts`（文件在 Task 8/10 合成）

可按字母分批粘贴进 `rules:` 列表；每加一批跑一次 `load_rules` 防 YAML 语法错误。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest content/phonics/tests/test_rules_coverage.py -v`  
Expected: PASS（本文件当前两条）

- [ ] **Step 5: Commit**

```bash
git add content/phonics/rules.yaml content/phonics/tests/test_rules_coverage.py
git commit -m "feat(phonics): 填入元音与辅音主音规则"
```

---

### Task 5: 填入 digraph + vowel_team + r_controlled + syllable_pattern

**Files:**
- Modify: `content/phonics/rules.yaml`
- Modify: `content/phonics/tests/test_rules_coverage.py`

- [ ] **Step 1: 扩展覆盖测试至全闭合清单**

```python
def test_full_required_coverage():
    rules = load_rules(RULES)
    by_cat: dict[str, set[str]] = {}
    for r in rules:
        by_cat.setdefault(r["category"], set()).add(r["grapheme"])
    for cat, needed in REQUIRED_BY_CATEGORY.items():
        missing = set(needed) - by_cat.get(cat, set())
        assert not missing, f"{cat} missing {missing}"


def test_at_least_60_rules():
    assert len(load_rules(RULES)) >= 60


def test_every_rule_has_path_order():
    for r in load_rules(RULES):
        assert r.get("path_order") is not None


def test_ids_unique_and_stable_shape():
    rules = load_rules(RULES)
    ids = [r["id"] for r in rules]
    assert len(ids) == len(set(ids))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest content/phonics/tests/test_rules_coverage.py::test_full_required_coverage -v`  
Expected: FAIL（缺 digraph 等）

- [ ] **Step 3: 补全剩余类别**

注意：

- `id`：`vowel_team.{g}.primary`、`consonant_digraph.{g}.primary`、`r_controlled.{g}.primary`；magic e → `syllable_pattern.{g}.magic_e`；意识型 → `….awareness`；`tion`/`ture`/`le` → `….primary`
- `ow` / `oo` / `ea`：主音各一条（建议主音：`ow=/aʊ/` 或 `/oʊ/` 选定并写 notes；`oo=/uː/`；`ea=/iː/`）；变音另 id
- `th`：一期主音 `/θ/`（`….primary`），浊音 `….voiced` 可选
- magic e：`a_e`…`u_e`；意识型允许空 `ipa`
- 全部赋予 `path_order`（落入 `path.yaml` 阶段区间）

- [ ] **Step 4: 跑全覆盖测试**

Run: `python -m pytest content/phonics/tests/test_rules_coverage.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add content/phonics/rules.yaml content/phonics/tests/test_rules_coverage.py
git commit -m "feat(phonics): 补全 digraph/元音组合/r控制/多音节主音规则"
```

---

### Task 6: 生成可读手册

**Files:**
- Create: `content/phonics/tools/generate_handbook.py`
- Create: `content/phonics/handbook.md`（生成）
- Test: `content/phonics/tests/test_generate.py`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path
from tools.generate_handbook import render_handbook


def test_handbook_has_path_and_catalog_sections(tmp_path: Path):
    # 使用仓库真实 rules（Task 5 后已满）或最小 fixture
    root = Path(__file__).resolve().parents[1]
    text = render_handbook(root / "rules.yaml", root / "path.yaml")
    assert "## 推荐学习路径" in text
    assert "## 分类目录" in text
    assert "oxford_shanghai" not in text or "口音" in text  # 手册面向家长，可不回显内部 accent 字段
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest content/phonics/tests/test_generate.py::test_handbook_has_path_and_catalog_sections -v`  
Expected: FAIL

- [ ] **Step 3: 实现生成器并写出 `handbook.md`**

`render_handbook`：按 `path_order` 排序输出路径篇；再按六类 category 输出目录篇。每条含 grapheme、ipa、approx_zh、按 grades 分列例词、notes。

CLI：

```bash
python content/phonics/tools/generate_handbook.py \
  --rules content/phonics/rules.yaml \
  --path content/phonics/path.yaml \
  --out content/phonics/handbook.md
```

（脚本内同样 `sys.path` 处理或作为模块 `python -m`；保持与测试同一 `render_handbook`。）

- [ ] **Step 4: 跑测试 + 生成文件**

Run: `python -m pytest content/phonics/tests/test_generate.py -v`  
然后跑 CLI 生成 `handbook.md`。  
Expected: PASS；`handbook.md` 存在且含双 TOC

- [ ] **Step 5: Commit**

```bash
git add content/phonics/tools/generate_handbook.py content/phonics/handbook.md content/phonics/tests/test_generate.py
git commit -m "feat(phonics): 由规则生成可读手册"
```

---

### Task 7: 生成 `audio_manifest.yaml`

**Files:**
- Create: `content/phonics/tools/generate_manifest.py`
- Modify: `content/phonics/tests/test_generate.py`
- Create: `content/phonics/audio_manifest.yaml`

- [ ] **Step 1: 写测试**

```python
from tools.generate_manifest import build_manifest


def test_manifest_lists_each_rule_audio(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    from tools.schema import load_rules
    man = build_manifest(root / "rules.yaml", root / "audio")
    assert "rules" in man
    assert len(man["rules"]) == len(load_rules(root / "rules.yaml"))
    row = man["rules"][0]
    assert "id" in row and "expected_path" in row and "exists" in row and "source" in row
    assert "examples" in row and len(row["examples"]) >= 3
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest content/phonics/tests/test_generate.py::test_manifest_lists_each_rule_audio -v`  
Expected: FAIL

- [ ] **Step 3: 实现 `build_manifest` + CLI**

对每条规则：

- 规则音：`expected_path` = `audio.rule.path`（相对 `content/phonics/`）；`exists` = 文件是否存在；`source` = `audio.rule.source`
- **例词行（锁定）**：以 `example_words` 为权威枚举；默认期望路径 `audio/word/{word}.wav`（word 小写）。若 `audio.examples` 中已有同词条目，则用其 `path`/`source` 覆盖默认。这样即使 `audio.examples` 仍为空，manifest 也能列出例词缺口。
- `examples[]` 每项：`word`、`expected_path`、`exists`、`source`（未挂载且无文件时 `source` 可先标 `tts` 表示「缺则拟用 TTS」）

不覆盖已存在文件的策略在合成脚本里执行；manifest 只报告。

- [ ] **Step 4: 生成并测试**

Run: pytest 对应用例 + CLI 写出 `audio_manifest.yaml`  
Expected: PASS；manifest 条数 = 规则数

- [ ] **Step 5: Commit**

```bash
git add content/phonics/tools/generate_manifest.py content/phonics/audio_manifest.yaml content/phonics/tests/test_generate.py
git commit -m "feat(phonics): 生成音频缺失清单 manifest"
```

---

### Task 8: 规则音合成脚本（fake + 真 TTS 钩子）

**Files:**
- Create: `content/phonics/tools/synthesize_rule_audio.py`
- Test: `content/phonics/tests/test_synthesize.py`

- [ ] **Step 1: 写失败测试（fake 模式）**

```python
from pathlib import Path
from tools.synthesize_rule_audio import synthesize_missing


def test_fake_writes_only_missing(tmp_path: Path):
    root = tmp_path / "phonics"
    (root / "audio" / "rule").mkdir(parents=True)
    rules = root / "rules.yaml"
    rules.write_text(
        """
rules:
  - id: vowel.a.short
    category: vowel
    grapheme: a
    ipa: "/æ/"
    approx_zh: "近似啊"
    example_words:
      - {word: cat, grades: [3, 5], source: common}
      - {word: map, grades: [3], source: common}
      - {word: abstract, grades: [5], source: common}
    accent: oxford_shanghai
    audio:
      rule: {path: audio/rule/vowel.a.short.wav, source: tts}
      examples: []
    path_order: 1
""",
        encoding="utf-8",
    )
    written = synthesize_missing(root, fake=True)
    assert written == 1
    assert (root / "audio/rule/vowel.a.short.wav").is_file()
    written2 = synthesize_missing(root, fake=True)
    assert written2 == 0  # 不覆盖
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest content/phonics/tests/test_synthesize.py -v`  
Expected: FAIL

- [ ] **Step 3: 实现合成**

- `--fake`：写入最小合法 WAV 头+静音（或占位 bytes），仅用于管线验收  
- 默认/真模式：用固定模板文本调用 TTS，例如  
  `"{grapheme}. Sound {ipa}. As in {anchor_word}."`  
  实现可：  
  1) 环境变量 `PHONICS_TTS=http` 调已配置的后端 `/api/tts/synthesize`，或  
  2) 直接调 `backend` 的 `qwen_tts`（需 `PYTHONPATH=backend` + 密钥）  
  一期计划要求：**接口抽成 `tts_synthesize(text) -> bytes`**，假实现与真实现可切换；无密钥时文档写明只用 `--fake`。  
- **绝不覆盖**已存在文件  
- 仅处理 `audio.rule.source` 为 `tts` 且文件缺失的项

- [ ] **Step 4: 跑测试通过；对本库执行一次 fake 冒烟（可选）**

Run: `python -m pytest content/phonics/tests/test_synthesize.py -v`  
Expected: PASS

真人听感验收（手动）：对 3 条规则跑真 TTS，家长试听「能跟读」；不行则改模板后再批量。

- [ ] **Step 5: Commit**

```bash
git add content/phonics/tools/synthesize_rule_audio.py content/phonics/tests/test_synthesize.py
git commit -m "feat(phonics): 规则音合成脚本（fake/真 TTS，不覆盖已有）"
```

---

### Task 9: README + 音频策略说明 + 可选 gitignore

**Files:**
- Create: `content/phonics/README.md`
- Modify: `.gitignore`（仅当决定不提交大体积/仅自用配套音时）

- [ ] **Step 1: 写 README**

必须包含：

1. 目录 vs 推荐路径怎么用  
2. 音标为准、中文近似仅辅助  
3. 如何校验：`pytest content/phonics/tests -v`  
4. 如何生成手册 / manifest / 合成规则音命令  
5. **家庭自用**声明；产品化须替换 `source: textbook|companion` 音频  
6. 例词配套音：自行导出后放入 `audio/word/`，再跑 manifest  
7. 口音：`oxford_shanghai`；IPA 短元音约定与 rules 一致  

- [ ] **Step 2: gitignore 决策**

若 fake/真 WAV 体积大或含配套音：在 `.gitignore` 增加例如  

```
content/phonics/audio/word/*
!content/phonics/audio/word/.gitkeep
```

规则音若用 fake 占位可不提交；真 TTS 小样可提交。在 README 写清。

- [ ] **Step 3: Commit**

```bash
git add content/phonics/README.md .gitignore
git commit -m "docs(phonics): 规则库使用说明与音频自用边界"
```

---

### Task 10: 端到端验收

**Files:** 无新代码（跑命令 + 勾选）

- [ ] **Step 1: 全量测试**

Run: `python -m pytest content/phonics/tests -v`  
Expected: 全部 PASS

- [ ] **Step 2: 再生手册与 manifest**

```bash
python content/phonics/tools/generate_handbook.py --rules content/phonics/rules.yaml --path content/phonics/path.yaml --out content/phonics/handbook.md
python content/phonics/tools/generate_manifest.py --rules content/phonics/rules.yaml --audio-root content/phonics/audio --out content/phonics/audio_manifest.yaml
```

- [ ] **Step 3: 全库规则音至少 fake 落盘（硬门槛）**

```bash
python content/phonics/tools/synthesize_rule_audio.py --root content/phonics --fake
python content/phonics/tools/generate_manifest.py --rules content/phonics/rules.yaml --audio-root content/phonics/audio --out content/phonics/audio_manifest.yaml
python -c "import yaml; from pathlib import Path; m=yaml.safe_load(Path('content/phonics/audio_manifest.yaml').read_text(encoding='utf-8')); bad=[r for r in m['rules'] if not r['exists']]; assert not bad, bad[:5]"
```

Expected: 断言通过（路径内每条规则音 `exists == true`）。真 TTS 小样听感仍可选，但不替代本步。

- [ ] **Step 4: 人工对照 spec 成功标准**

- [ ] 闭合清单 grapheme 全覆盖且 `len(rules) >= 60`  
- [ ] 路径阶段 1→7 无断档（`path_order` 落入 `path.yaml`）  
- [ ] 每条可按 grades 滤出 3 与 5  
- [ ] README 含自用/产品化音频声明  
- [ ] 规则音全库 `exists`（Step 3）  
- [ ] （可选）真 TTS 至少 3 条规则音可跟读  

- [ ] **Step 5: 若有生成物变更则提交**

```bash
git add content/phonics/handbook.md content/phonics/audio_manifest.yaml
git commit -m "chore(phonics): 刷新手册与音频清单"
```

---

## 执行手顺提醒

- 内容条目（Task 4–5）工作量大：可按 category 多次 commit，但测试须最终全绿。  
- 不要在本期改 `backend/` 路由或 Flutter。  
- 配套音频「能拿尽量拿」= 人工导出放入 `audio/word/`，计划不包含破解步骤。  
