# 自然拼读发音规则库（GPC Catalog）设计

日期：2026-11-28  
状态：已确认

## 背景与目标

孩子（三年级、五年级）目前不懂自然拼读。目标是先掌握「见词能读」的底层规律，之后背单词更省力。参考某少儿 App 的目录形态（元音 / 辅音 / 字母组合分色入口），但零基础不能只靠目录——还需要一条推荐学习路径。

仓库内尚无自然拼读内容。英语侧已有听写、听力、`WordBank` / `WordMastery`、TTS；**本期不做产品接线**，只建设可复用的内容数据源，并为日后接入预留稳定 `id`。

**一期目标**：以结构化数据为唯一真相，交付完整度达到「小学尽量全」的发音规则库（字母与字母组合 → 主音）+ 分类目录 + 音频资产；练习计划明确放到二期。

## 决策记录（已与用户确认）

| 项 | 决策 |
| --- | --- |
| 范围形态 | 纯教研内容（非本期改 KnoAct 代码） |
| 年级 | 三、五年级共用一套主课纲；同路径，五年级例词更难、节奏可更快 |
| 阶段切分 | 一期：规则库 + 音频；二期：练习计划（挂同一批 `id`） |
| 完整度 | 范围 B：单字母常见音 + 高频/次常见组合 + r 控制 + 常见多音节模式（不含生僻词源规则） |
| 教材口音 | 沪教牛津（上海教育出版社，一年级起点；主编张春柏、施嘉平） |
| 书面标注 | 国际音标为准 + 中文近似辅助（注明近似、不完全准） |
| 一字母多音 | 先只教最常见主音；变音作为**另一条**规则，随后续路径出现 |
| 内容组织 | 目录（查找）+ 推荐学习路径（从零教学） |
| 架构选型 | **方案 B 数据源型**：YAML/JSON 为唯一真相，再生成手册 / 清单 / 可选 HTML |
| 音频 | 家庭自用前提下，例词音尽量使用已有教材配套导出；固定规则音用 TTS 合成固化；缺则 TTS。日后若产品化对外分发，配套音须替换为已授权或 TTS |

## 非目标（一期）

- 练习计划、每日任务、学生端 / 家长端功能开发
- 在同一 `grapheme` 教学卡片上堆全部变音
- 完整发音学词典、生僻词源规则
- 改 FastAPI / Flutter 业务代码
- 在设计或实现文档中提供绕 DRM / 盗版分发步骤（只对接用户能导出的本地文件 + TTS）

## 架构

```
content/phonics/rules.yaml          ← 唯一真相（GPC 条目）
        │
        ├─► 可读手册（按 path_order / 按 category）
        ├─► 目录索引（对齐 App 式分类）
        ├─► audio_manifest.yaml（缺什么、来源是什么）
        └─► TTS 批量合成规则音 → content/phonics/audio/rule/
              例词：配套优先 → audio/word/；否则 TTS
```

| 单元 | 职责 | 依赖 |
| --- | --- | --- |
| `rules.yaml` | 每条 GPC 的字段与稳定 `id` | 无 |
| 路径视图 | 只读 `path_order`，服务零基础教学顺序 | `rules.yaml` |
| 目录视图 | 按 `category` + `grapheme` 聚合，服务查找 | `rules.yaml` |
| `audio_manifest` | 列出应有音频、已有路径、`textbook`/`tts` 来源 | `rules.yaml` + `audio/` |
| 生成脚本（实现期） | 手册、manifest、缺文件合成 | 上述 |

## 数据模型

每条规则一条记录，建议路径：`content/phonics/rules.yaml`。

| 字段 | 含义 |
| --- | --- |
| `id` | 稳定主键，如 `vowel.a.short`、`digraph.ai`；发布后不改语义 |
| `category` | 仅六值：`vowel` \| `consonant` \| `vowel_team` \| `consonant_digraph` \| `r_controlled` \| `syllable_pattern` |
| `grapheme` | 书面形式：`a`、`ai`、`tion`；意识型条目可用符号名如 `closed_syllable` |
| `ipa` | 主音音标，如 `/æ/`。意识型条目（`closed_syllable` / `open_syllable`）可填模式说明音标或留空，以 `notes` + 锚例词为准 |
| `approx_zh` | 中文近似 + 必备注「近似」；意识型条目写模式的中文说明即可 |
| `example_words` | 对象列表，每项至少含 `word`；可选 `grades: [3]` / `[5]` / `[3,5]`、`source: textbook\|common`（**例词出处**，与音频 `source` 不同）。每条规则至少 3 个词；**须同时覆盖三年级可用词与五年级加难词**（可同一词标 `[3,5]`，或分列） |
| `accent` | 固定标记 `oxford_shanghai` |
| `audio` | `{ rule: {path, source}, examples: [{word, path, source}] }`；此处 `source` 仅表示**音频来源** ∈ `textbook` \| `tts`（实现期可细分为 `companion`）。勿与 `example_words[].source` 混用 |
| `path_order` | 推荐路径序号；未入路径可为空 |
| `notes` | 可选：易混提示、五年级可加快等节奏提示、指向后续变音 `id`（如长音见 `vowel.a.magic_e`） |

**年级落库（锁定，禁止分叉）**

- **不设**规则级 `grade_band: g3|g5`（禁止「某条规则只属于某年级」）。
- 三 / 五年级**共用同一 `path_order`**；差异**只**在 `example_words[].grades`（及 `notes` 中的节奏提示）。
- 成功标准「年级可区分」= 手册能按年级过滤例词；不是两套路径。

**约束**

- 一期每个教学面上的 `grapheme` 主音一条记录；变音 = 另一 `id`，较晚进入 `path_order`。
- 目录按 `category`；路径只看 `path_order`。
- `category` 封闭枚举，与下节六类一一对应：`vowel` | `consonant` | `vowel_team` | `consonant_digraph` | `r_controlled` | `syllable_pattern`。

## 分类目录与推荐路径

### 目录（查找，对齐参考 App 并补全范围 B）

与 `category` 枚举一一对应：

1. `vowel` 元音字母  
2. `consonant` 辅音字母  
3. `vowel_team` 元音字母组合  
4. `consonant_digraph` 辅音字母组合  
5. `r_controlled` r 控制  
6. `syllable_pattern` 多音节常见模式（开/闭音节意识、magic e、常见词缀等）

### 范围 B 闭合清单（一期验收用）

下列 grapheme（主音各一条 `id`）为**最低交付集合**；实现期可增补，但不得删减下列条目仍宣称范围 B 完成。变音另立 `id`，不替代下列主音条。

| category | 一期必须覆盖的 grapheme（主音） |
| --- | --- |
| `vowel` | `a` `e` `i` `o` `u` `y`（主音取短元音 / 该字母最常见读法；`y` 作元音主音单独约定） |
| `consonant` | `b` `c` `d` `f` `g` `h` `j` `k` `l` `m` `n` `p` `q` `r` `s` `t` `v` `w` `x` `z`（`c`/`g` 主音取最常见硬音；软音为后续变音条） |
| `consonant_digraph` | `sh` `ch` `th` `ck` `ng` `wh` `ph` `qu`（`th` 若清浊需拆两条 `id`，仍属本集合） |
| `vowel_team` | `ai` `ay` `ee` `ea` `oa` `ow`(主音取常见长音或组合约定之一并 `notes` 指另一条) `oo` `oi` `oy` `ou` `aw` `au` `ew` `ie` `igh` `ue` |
| `r_controlled` | `ar` `or` `er` `ir` `ur` `ore` |
| `syllable_pattern` | `a_e` `e_e` `i_e` `o_e` `u_e`（magic e）+ 条目 `closed_syllable`、`open_syllable`（意识型，各一条）+ `tion` `ture` `le` |

**计数下限**：上表合计不少于 **60** 条主音规则（`th` 拆分则 +1）。手册 TOC 与 `rules.yaml` 条数对照此表勾选即验收。

### 推荐路径（`path_order` 示意阶段）

1. 高频单辅音 + 短元音 → 能拼 CVC  
2. 其余辅音 / 易混音  
3. 辅音 digraph（上表 `consonant_digraph`）  
4. 常见元音组合（上表 `vowel_team` 主体）  
5. r 控制  
6. magic e / 开闭音节意识  
7. 次常见组合 + 多音节模式（`tion` `ture` `le` 等）  

最终 `path_order` 整数在实现期写入；**阶段语义与闭合清单锁定**，编号可调但不改变阶段归属。

## 音频策略

**优先级**

1. 例词：用户已有教材配套可导出文件 → 尽量采用（`source: textbook` / `companion`）  
2. 固定规则音（字位/组合主音示范）→ TTS 合成落盘（`source: tts`）  
3. 仍缺的例词 → TTS 补齐  

**硬约束**

- 孤立音素 TTS 常不准：规则音用固定提示模板（短载体或「字位 + 主音 + 锚例词」一条短音频）；验收以「能跟读且与例词一致」为准。  
- 全库同一 TTS 音色与沪教牛津口音倾向；不按条随意换声。  
- 文件名与 `id` / 词对齐，例如 `audio/rule/vowel.a.short.wav`、`audio/word/cat.wav`。  
- `audio_manifest` 驱动：只合成缺失项；不覆盖已有配套文件。  

**分发边界**

- 本期按**家庭自用**课表建资产。  
- 若日后公开进入 KnoAct 产品或对外分发：配套扒取/导出音不得原样上架，须已授权音源或 TTS。

## 仓库落位

```
content/phonics/
  rules.yaml
  path.yaml                 # 可选：阶段说明；或仅用 rules.path_order
  audio/rule/
  audio/word/
  audio_manifest.yaml
  README.md                 # 目录 vs 路径、近似注音说明、自用声明
docs/superpowers/specs/
  2026-11-28-phonics-gpc-catalog-design.md
```

由数据生成：可读手册（双 TOC）、`audio_manifest`；可选简单 HTML 目录页（仍属内容，非学生 App）。

## 成功标准（一期完成定义）

- 「范围 B 闭合清单」每一 grapheme 均有对应主音 `id`，字段齐全（不低于 60 条）  
- 推荐路径从「能拼 CVC」到「多音节常见模式」无断档，且清单内条目均有 `path_order` 或明确标为路径外附录（默认：清单内全部入路径）  
- 路径内每条规则至少 1 段可播规则音；例词音按可用性挂载，`source` 正确  
- 每条规则的 `example_words` 能按 `grades` 滤出三年级集与五年级集（五年级集允许完全包含三年级词并另有加难词）  
- README 写明家庭自用与产品化时的音频替换要求  

## 与学习第一性原理的关系（裁定摘要）

- **类型**：识记型为主（字母–音素对应是约定）+ 拼读（blending）含「关系上的变换」，但一期交付物是**原料层规则库**，不宣称「会用这个词」或理解语义。  
- **通过证据（二期练习才测）**：无提示看词读出符合规则的词；能被「听过就复读」解释的不算自动化达标。  
- **一期不做判定逻辑**；只保证规则与音频可教、可查。  

## 二期占位

练习计划（听辨 / 拼读 / 看词读 / 简单编码等）一律引用本库 `id`，不平行维护第二套规则表。

## 风险与开放点（实现计划处理）

- 沪教牛津具体册次例词对齐需要抽样教材；一时对不上时用规则清晰的常用词，`example_words[].source: common`（教材对齐则为 `textbook`）。  
- TTS 规则音模板需试听调参（实现期小样验收）。  
- `.gitignore`：若 `audio/` 体积大或含仅自用配套音，实现期决定是否入仓或 LFS / 本地-only。  
- `ow` / `oo` / `th` 等多值字位：闭合清单要求「主音一条 + notes 指向变音条」；变音条可超出「最低集合」计数，但仍建议一期写完常用变音以免路径断档。  
