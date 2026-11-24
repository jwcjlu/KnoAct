# KnoAct（知学伴）— Architecture

> **定位说明**：KnoAct 目前**不是 agent-native**。AI 以「一次性函数调用」形态
> 散落在后端各处，没有 turn 引擎、没有 capability 编排、没有工具注册表。
> 前端虽已有对话/可视化/解题三种「模式」的界面，但后端实现只是**换一个
> system 提示词字符串再单次 `generate`**，并非真正的 agent 能力。
> 本文如实记录现状，并在最后给出向 agent-native 演进的差距与路径（见
> [Agent-Native Roadmap](#agent-native-roadmap)）。

## Overview

KnoAct（知学伴）是一个面向小学生的 AI 学习伙伴：上传 PDF 教材 →
自动拆课 → AI 提取生词/知识点/课文 → 孩子端做听写、听力、阅读、边读边问测验，
家长端管理教材/目标/任务/规则。后端是 **FastAPI + SQLAlchemy**。前端有三个：
`student-app/` 是 **Flutter 学生端**（Web + Android，Riverpod + go_router），逐步
替代旧版；另有两个**单文件原生 JS** 应用（无框架，`render*()` 函数拼 HTML 字符串）：
`frontend/` 是旧版学生端 Web（已冻结，将由 Flutter 学生 App 取代），`parent-web/`
是独立的家长端。三者均直接调用后端 `/api`。数据库本地开发用 SQLite，
docker-compose 部署用内置的 MySQL 8.4（长文本列在 MySQL 上为 MEDIUMTEXT），所有 AI/语音能力都走可配置的 provider 抽象层，未配置时
回落本地 `fake` 兜底，保证任何环境下都能跑起来。

## 学习第一性原理（设计裁判标准）

> 这一节不是功能描述，而是**裁决标准**。任何涉及学习内容的新功能或改动，
> 先用这里的规则判定，答不出就不进入实现。完整决策记录见
> `docs/superpowers/specs/2026-11-24-learning-first-principles-design.md`。

**原理本体：学习的本质是思考。**

> 学习 = 在**关系**上做一次**信息增量**（压缩 / 反事实 / 生成），且这次增量**由孩子本人完成**。

思考不可直接观测，所以唯一可用的判据是：

> **孩子的这个答案，能不能靠「照搬输入」复现？能 → 不是思考。**

| | 检索（非思考） | 思考 |
| --- | --- | --- |
| 输出与输入的关系 | 输出 ⊆ 输入（搬运） | 输出 ⊄ 输入（变换） |
| 信息量 | 不变 | 必须增加 |
| 例 | 默写「比喻 = 本体 + 比喻词 + 喻体」 | 判断「他长得像他爸爸」为什么不算比喻 |

**结构 / 冲突 / 提取 三层只是思考的可观测痕迹，不是原理本体。** 单靠它们会漏判：
孩子把背下来的结论默写出来（过结构层）、被陷阱题打中一次（过冲突层）、再把答案写出来
（过提取层），三层全过而零思考——因为三层都是**产物**，产物可以搬运。

**三种可观测变换**（任一被观测到才算发生思考）：

| 变换 | 含义 | 仓库对应 |
| --- | --- | --- |
| 压缩 | 多个例子 → 一条更短的规则 | `guide` 末轮填空归纳 |
| 反事实 | 改变一个条件会怎样 | `trap` |
| 生成 | 用规则造出教材里没有的东西 | **缺**（造句/举新例/自编题） |

**反检索否决条款**：思考层的通过证据，若能被「检索原话」解释，一律不算通过。
逐字复现教材/AI 原话 → 不算；同一知识点至少两种问法都答对 → 才算；
能答「为什么」「什么情况下不成立」→ 才算。**同一变换至少测两次，第二次换表象**——
抄的、猜的都可能有一次增量表象。注意：「努力感」不是思考（回忆一个词很费劲但信息量不增，那是检索）。

**两层结构（记住与想通都是必要的，目标不同）：**

| 层 | 内容 | 本质 | 达标判据 | 禁止宣称 |
| --- | --- | --- | --- | --- |
| **原料层** | 生字、单词、古诗、短语 | 检索自动化（秒取） | 无提示、隔期仍能取（SRS） | **不得宣称理解 / 会用** |
| **思考层** | 规律、句型、原理、修辞 | 信息增量的变换（能推） | 压缩/反事实/生成任一 + 过反检索 | — |

**但两层不是分类，是阶段**：`未想通 → 想通（思考）→ 反复用（自动化）→ 秒取（原料）`。
今天的思考是明天的检索——生字的「秒取」最初靠字形分析，一条规律想通几次后会变成直觉。

**硬规则：只自动化已经想通的东西。** 死记硬背 = 把「没想通」的东西提前自动化。危害不止「没用」，
是**会锁住**：流畅的检索通道一旦建立，想修正要先拆掉旧通道，而孩子已对它有信心——
这比「没学过」更难办。判断顺序必须是「想通 → 再自动」，不能颠倒。
推论：识记型的对象是**那些无需推理的约定**（字形、拼写、诗），**不是「所有暂时想不通的东西」**。

一句话：**检索降低提取成本，思考增加信息量。没有可检索的原料就没有可压缩的句子；
但只有原料，永远不会有句子。**

**思考的对象是关系，不是元素。** 孩子想不出，几乎从不是因为缺元素：「他长得像他爸爸」里
「像」「爸爸」「同类」他都知道，缺的是「『像』同时承载比喻与同类比较两种关系」。
**禁止条款：不得用「加同类题」应对关系缺口**——关系缺口上加量只带来更多同类失败，
孩子会据此认定「我就是不会」。要换视角重排关系，而不是加量。

**思考的起点是失衡。** 思考只在**预期遇到冲突**时启动——没有预期就没有可打破的东西，
反例只会成为另一条要记住的信息。故**先让孩子预测，再给反例**（`trap` 现在缺预测步，
冲突强度靠运气）。

**错误规则是功能性的，有适用范围。** 孩子的错误规则几乎总是有用的——在他遇到的范围内一直有效
（「乘法让数变大」在正整数内成立；「『像』就是比喻」在大多数句子成立）。
**纠正 = 让旧规则在边界上失效，不是叠加新规则**——讲解为什么没用：它是叠加，
两条规则同时存在，做题时仍用那条更快、更自动的。**反例必须打在旧规则的适用边界上**
（「0.5×4=2，比 4 小，为什么？」有效；「2×3=6，乘法让数变大了吗？」无效）。
**能说出「这条规则什么时候不成立」，才是真的修正了它。**

**产出不等于「说」。** 产出是**多通道**的：语言、图形、动作、选择。
低年级孩子常是「想通了但说不出来」或「用动作/图示表达」——只用语言判定会**系统性冤枉**他们。
**判据要准，不是要严**——但「准」不等于「松」，两者的区别见下面的「允许未决」。

---

### 核心原则：允许未决

> **判据侧测不准时不强行判决（记为未决）；内容侧学不会时不强行通过（记为悬置）。
> 这是同一条原则的两个场合——承认第三种状态。**

二元判决在信息不足时**必然出错**，而唯一的修法不是选哪一边，是**不判决**。

**「准」是可分解的三个能力，不是一个阈值**：

| 能力 | 含义 | 怎么测 |
| --- | --- | --- |
| **信度** | 同一状态重复测，结论一致 | 隔期重测同一知识点 |
| **收敛效度** | 不同通道测，结论一致 | 说对 + 指对 + 做对 |
| **区分效度** | 能分开「想通」与「背下」 | 换问法 + 反检索 |

缺第三项时，放宽阈值不会让它变准，只会**换一种方式不准**（这就是为什么「多给点分」是错解法）。

**假阴性与假阳性的危害不对称，但按内容层级区分**（不可绝对化）：

| 层级 | 假阳性（放过）成本 | 假阴性（冤枉）成本 | 该往哪偏 |
| --- | --- | --- | --- |
| **原料层**（生字/单词） | 低——多练几次自然暴露 | **高**——重复学已会的很烦 | **宁松** |
| **思考层**（规律/原理） | **高**——错误规则被自动化、会锁住 | 中——浪费时间是可恢复的 | **宁紧，但先换通道** |
| **发展性未到** | — | — | **该悬置，两边都不判** |

思考层宁紧的理由是「只自动化想通的」那条硬规则：放过一个没想通的孩子，等于让他把错误规则
练成自动化，之后修正要先拆旧通道——这个成本高于多教一遍。

**准度预算按「判决后果」分配**（准要花钱，不能每题测三遍）：

| 场合 | 预算 | 理由 |
| --- | --- | --- |
| 首次判定未掌握 / 决定能否推进进度 | **高**（双通道 + 两次呈现 + 一次变式） | 决定后续全部路径，错了连锁 |
| 日常复习 / 原料层练习 | **低**（单次即可） | 多测一次机会，粗判没事 |
| 发展性未到 | **极高但做不到** | 只能悬置 |

**测不准时的正确动作**：不判通过、不判不通过，**记为「未决」，下次带更强证据再判**。
这不是偷懒——是信息不足时唯一不犯错的选项。

#### 未决的生命周期

| 阶段 | 规则 |
| --- | --- |
| **产生** | 证据不足（只答一次、通道单一、用时极端）；或 ≥2 次不同表征后仍失败 |
| **粒度** | **一条可陈述的规律或一个知识点**，不是单个字词（原料层只需间隔，不需悬置） |
| **发起方** | 孩子自己（「这个我还想再想想」）→ 需系统复核后生效，防滥用；系统判定 → **必须告知并给孩子否决权**；家长 → **只能建议，不能强制** |
| **上限** | 同时悬置 ≤ 3 个知识点，且不超过当前课知识点的 30%；最短停留 ≥ 3 天 |
| **回归** | **混在正常内容里，不标注、不提「复习」**——明确提示会唤起自我威胁 |
| **到期动作** | **改内容**（换表征/拆小/补前置/降难度），不是再测孩子一次 |
| **归属** | 必须归属到**内容问题 / 教学问题 / 时间问题**之一，否则算系统失职 |

**「发展性未到」不是诊断，是事后归类。** 你无法在当下区分「这次没懂」和「认知还没到」——
两者当天表现完全一样。区分方式只有换个时间再试：

| 时间点 | 表现 | 事后归类 |
| --- | --- | --- |
| 当下 | 换 3 种表征仍失败 | 未决 |
| 3–7 天后 | 换表征后通了 | **学了没懂**（表征问题） |
| 1–3 个月后 | 自然通了 | **发展性未到**（时间问题） |

所以机制只需**两档重试间隔**，靠结果反推归类——不需要任何前瞻诊断。

**未决不进任何百分比。** 它不进分母，是**带原因和回归时间的待办事项**。
家长端据此从「度量」（掌握度 62%）改为「决策」（下周做这 3 件事、暂时放下 2 项）。

**必须防的退化：从「判不准」滑向「不敢判」**——系统对所有难判的都记未决，永远不推进，
表现是进度停滞而非崩溃。防线两条：**未决必须到期**；**到期默认改内容而不是再判一次**
（否则什么都没变，大概率还是未决）。

---

**主体性条款（软）**：AI 能完成全部三种变换且做得更好，一旦 AI 先做
（提问 → AI 归纳 → 孩子点头），信息增量发生在 AI 那边，这**只构成演示，不构成学习**。
变换应优先由孩子产出，AI 首先是**引发者与裁判**（反问、给反例、判语义等价），而非讲解者；
允许必要时先讲，但**讲完必须收一次孩子自己的产出**，否则该次交互只记 L0。

**「卡住」是思考正在发生的唯一外部征兆。** 一路顺畅、从未卡过，说明不是在学，是在表演已会。

| 卡住之后 | 含义 | 数据痕迹 |
| --- | --- | --- |
| 乱试 | 有路径，在搜索 | 试错多但间隔短 |
| 停住不动 | 无路径，也没意识到 | 长时间无操作 |
| 退出 | 判定自己不行 | 放弃点 |
| 提问 | **知道缺什么，会求助** | 提问的具体程度 |

能说出「我卡在哪」本身就是思考的证据（比答对一题更能说明问题）。所以从属原理的
「别让孩子挫败」与「必须让他卡」不靠折中解决，靠**区分卡的类别**：

- **有救的卡**：卡在关系上，且他能说出卡在哪 → 让他多卡一会儿，只给最小提示（一句反问，不给答案）。
- **没救的卡**：缺前置原料（生字不认识、题意没读懂）→ 立刻补支撑，别让他耗。

**从属原理（愿意学、学得下去）**，顺序即优先级：
低门槛开始（5–8 分钟）> 难度适配（由数据决定，不由年级）> 错误安全
（错误无惩罚反馈，家长端不得把掌握度变成考核指标）> **允许不会**（有些内容当前不该出现，
不是难度问题）。从属原理只裁定「愿不愿学」，**不裁定「学会了没」**。

**「不会」有五种，系统现在当成一种。** 系统里没有「不会」这个状态：`WordMastery.is_weak` 是二元的
（错过一次就 True，直到掌握度 0.9）、`Task.submit_status` 没有「先放下」、`Mistake` 只有
「答对 3 次移出」、`_gen_dictation` 注释写着「所有词永不移出」。

| 类型 | 正确响应 | 现在会怎样 |
| --- | --- | --- |
| 没学过 | 教它 | 混在错词里 |
| 学了没懂 | 换表征/给反例 | 加同类题 |
| 懂了没记住 | 间隔复习 | 加同类题 ✓（对的） |
| **发展性未到** | 等，并降优先级 | **反复轰炸** ❌ |
| 不必会 | 移出，不再出现 | 永远占用名额 ❌ |

只有第三行是「多练就能好」的，其余四种的病根都不在练习量上。「发展性未到」被当成「薄弱」最伤人：
分数、负数、周长面积这类「现在讲不通、半年后自然通」的内容，系统判为薄弱 → 反复出题 →
`is_weak` 永远 True → 继续出，孩子得到的信息是「这一块我天生不行」。

**不放弃等于摊薄**：`_gen_dictation` 错词档按 `-mistake_count` 排序，一个永远学不会的词会长期
占据名额（默认 7 个里的 4 个），**挤掉本可以学会的新词**；错词池只增不减，学期过半孩子可能
每天做的都是那几个顽固错词。**不允许「不会」的真实代价，不是多练几个词，是挤掉了本该学的东西。**

**允许不会 ≠ 放任**：需**有复核时机**、**有数量上限**、**有理由**（详见上文「允许未决」）。
且**只有「不会」可以合法停留，孩子才会如实暴露「我不会」**——若规则是「每个点都必须通过」，
他的最优策略是假装通过或直接退出（系统连「卡住过」都记不到）。按钮文案决定使用率：
「我不会」几乎没人点，「这个我还想再想想」使用率最高——**同一件事，措辞把它从承认失败
变成主动安排**。

**理解的四级证据**（理解不是前置条件，而是提取的中间档位；每级都要过反检索）：

- **L0 复述**（重复原文或 AI 的话，输出 ⊆ 输入）→ **不算理解**。现状：对话唯一留下的痕迹
- **L1 重述**（无原文提示，用自己的话说出核心，语义等价且表述不同于原文）→ 现状：**缺**
- **L2 举例/辨正反例** → 已有：`explore.classify`
- **L3 迁移**（新情境/变式/陷阱中用对）→ 已有：`trap`、练习册变式

辅导式对话（`/api/ask`）**能产生理解**，但理解必须可出示：对话结束可选收一个
「你说说看」（AI 只判语义等价，不许再讲解）落成 L1；跳过则只记 L0、不计入理解证据。
**待整改**：目前 `/api/ask` 不留 L1 证据，且主体是 AI（孩子未先产出）。它的成功指标
不是对话轮次，而是「对话后同一知识点的 L2/L3 首次正确率是否高于未对话对照」。

**分层裁判**——不同内容用不同标准，禁止交叉套用。**内容类型 × 年龄是二维的**，
同一条内容在不同年龄的可达上限不同：

| 类型 | 适用内容 | 达标要求 | 通过判据 |
| --- | --- | --- | --- |
| 探究型 | 数学规律、句型、修辞、周长面积 | 三种变换至少一种 + 过反检索 | 引导链归纳（压缩）+ 归类（反例）+ 陷阱（反事实） |
| 识记型 | 生字、单词、古诗、短语 | **不要求变换**，要求检索自动化 | 无提示产出、隔期仍能取（认→背→测） |
| 习惯/情感型 | 按时开始、不畏难、敢提问 | 不受原理本体裁定 | 只受从属原理裁定 |

**年龄维度**：低年级（1–2）冲突用「**先猜再看结果**」（不需维持假设世界），
中年级（3–4）用「反例打破规则」，高年级（5–6）用「自己构造反例」——三者是同一条发展线上的台阶。
**`trap` 是中高年级的冲突形式，不适用低年级**：低龄孩子在需要抑制现实、维持假设世界的情境里会
系统性失败，**陷阱题在低年级测的可能是抑制控制，不是理解**。低年级的产出通道以**动作/图形为主**，
语言为辅；「教 AI」3 年级以上才适用。

**工作记忆预算**：低年级约 4 个组块。一道题若要同时握住 6 个元素才能看见 1 条关系，它不可完成，
与聪明无关。**「想不出来」时先换表征，不是重复讲解**——重复讲解是在元素维度上加量，缺口在表征维度。
竖式之重要不在「规范」，而在它把**进位**画成了位置；数轴让「负数比正数小」从一句话变成一个方向。
这也解释了**对识字量不足的孩子，「引导他看结构」是无效的**：解码层吃满预算，他没有可用的算力。

现有裁定：`guide` = **思考层达标（样板）**；`trap` = **思考层达标但仅中高年级**（缺预测步、
反例未打边界）；识记「认→背→测」/ 听写 = **原料层达标**（不得宣称理解）；
`classify`（有辨认无压缩）、阅读理解题（无层面约束、不要求指出处）、
`/api/ask`（主体是 AI、无 L1、无节奏）= **部分**；思维训练小游戏、积分 = **不受裁定**（动机工具）；
`weakness_report`（只统计题型计数，是计数不是诊断）、`is_weak` 二元状态 = **不达标**。
**积分只能影响「愿不愿学」，绝不能参与判定「学会了没」；听写全对不得宣称「会用这个词」。**

**新功能开工前必答 9 问**（答不出不进入实现）：

1. 属于哪一类（探究 / 识记 / 习惯）？答「都涉及」＝没定类，退回。
2. 训练的**哪个关系**是什么？能用一句话说出吗？（「练习阅读能力」＝无关系）
3. 孩子要做哪种变换（压缩 / 反事实 / 生成）？原料层须明写「无变换，不得宣称理解」。
4. **通过**证据在**无提示**下怎么取到？**能否被「照搬输入」解释**？（能 = 不算通过）
5. 这个变换**由谁先完成**，孩子还是 AI？（「AI 归纳、孩子点头」＝演示）
6. **产出通道**是什么？语言是不是唯一通道？（只用语言 → 会冤枉低龄孩子）
7. **适用年龄**是多少？冲突形式匹配吗？（低年级上反事实题 = 测抑制控制）
8. **测不准时怎么办？**能不能记「未决」而非强行判？悬置如何回归、何时到期？
   （答「多给点分」= 错解法；正确动作是到期改内容）
9. 它影响「愿意学」还是「学会了没」？**两者不得混**。

七条硬约束：**成功指标必须落在已有数据表上**（`WordMastery` / `KnowledgeMastery` /
`AnswerRecord` / `BrainGameResult` / `Annotation` / `Mistake` 等），落不上去说明测不出东西，先别做；
**不得交叉套用标准**（不得用探究型标准要求识记型，不得用识记型标准放过探究型，
不得用原料层达标宣称理解）；**不得用积分/时长代表掌握度**；**不得用「加同类题」应对关系缺口**；
**不自动化学没想通的东西**（顺序必须是「想通 → 再自动」）；**不得省略年龄维度**；
**不得把「未决」当免责话术**（每个未决必须到期、必须归属，否则算系统失职）。

**家长端看决策，不是度量。** `parent-web` 现在给家长的是「已掌握 12 · 薄弱 8 · 共 20」和
「掌握度 62%」——**一个数不能同时表示值和方差**，所以「未决」无处安放，只能被塞进「会/不会」。
且目标页的进度是硬编码的（`pending/in_progress/done` → `0%/50%/100%`），背后没有任何测量。
`mastery` 这个 float 实际算的是「最近几次对得多不多」，**是近期正确率，不是掌握度**。

应改为回答**「下周该做什么」**：本周要做的 3 件事、「像」这条规则还在用旧理解（已安排 2 道反例）、
暂时放下 2 项（等 3 周再试）。**未决不进百分比，而是带原因和回归时间的待办**——
家长看到的是「有安排」，不是「不知道」。

**悬置率是内容质量的指标。** 一个知识点被大量孩子悬置，不是孩子的问题，是**拆课/讲解/超纲**的
问题；只有个别孩子悬置才是个体差异。这让悬置数据有了第二个用途：**反向检验拆课与 AI 出题质量**
——现在的系统对这两者完全没有反馈回路。这个指标该给**运营/教研**看，不给家长看。

**判据工具箱**——下面五项全部落在**已有数据**上，不需要新埋点。数据一直在库里，只是没人读：

| 判据 | 做法 | 补上的漏洞 |
| --- | --- | --- |
| **答 + 指** | 答完让孩子指出「从哪里看出来的」（`quiz.py` 的 evidence 机制只对准了 AI，没对准孩子） | 同时堵住**蒙对**（答案对出处错）与**假阴性**（答案错出处对 = 理解对、表达弱） |
| **错误诊断** | `AnswerRecord` 已存 `student_answer` 原文，但 `grade_answer` 返回 `bool` 就丢掉了；`Mistake` 每次再错**覆盖**上次错答，「同一错答案反复出现」存不下来 | **稳定的错误比偶然的正确信息量大得多**——它暴露完整错误路径。读已存数据即可，最便宜 |
| **读 `duration_ms`** | 字段存在，全链路不读 | 1 秒答对 = 已自动化；40 秒答对 = 还在推导。**这两件事现在记成同一个 `is_correct=True`** |
| **迁移缺口** | `KnowledgePointPool.extra` 的 `example`（原文）与 `content`（独立表述）可同点两呈现（带语境 / 脱离语境）。⚠️ 早期文档误写为 `KnowledgePoint.original_sentence`，该字段不存在 | 正确率差 = 迁移缺口，`AnswerRecord.source_type/source_id` 已足够关联 |
| **标注画像** | `Annotation` 存了 `kind` / `quote` / 页号，**全系统唯一免费的注意力测量** | 划得越多越说明「没看出哪里重要」（选择性本质是排除）；划短=卡在解码层，有 `note`=在做加工 |

**关于「教 AI」**（最强的判据之一，但成本最高）：孩子教 AI、AI 装不懂只追问，再用**孩子讲的内容**
做一道新题。一次交互同时测**压缩 + 迁移 + 表述完整性**。但必须实现**差分判定**——
同一道题跑两次（带/不带孩子的解释），两次答案一样就说明 AI 本来就会、解释没起作用、**不记通过**。
**没有差分，整个机制不可信。** AI 追问也不得包含答案里的关键概念词（指出缺口可以，填上缺口禁止）。
架构缺口：`UnifiedContext` 无对话历史，`TurnEngine` 是单轮闭合，需要**跨 turn 会话层**——
这是结构性改动，不要为一个功能仓促引入。

**节奏**：系统现在的目标是「尽快」，而学习需要在三个位置各停一次——**答案之前**（先让孩子尝试/预测，
否则他的第一次产出被系统性跳过）、**卡住之中**（给时间不给答案）、**答案之后**（先自己说）。
**慢不是目的，把延迟换成动作才是**：真等待要求孩子做一个动作，假等待只是让时间流逝（`sleep(2)` 是剧场）。
注意流式输出在此处是双刃：工具提示（`正在查生词释义…`）应保留，但**最终答案逐字推流会训练被动**——
阅读速度由模型决定，孩子唯一的动作是「看」，而等待原本是他唯一能插入自己思考的缝隙。

**注意力**：问题塑造知觉，不是反过来——「你要看结构」对孩子没用，但每次被问「作者为什么先写这个」，
做够几次后安排本身就会变得可见。所以**不要做「阅读方法」课程，要改题目本身**。
现有 `question_gen.py` 对「问什么层面」无任何约束，兜底题是「文中作者表达了什么感情？」
—— 最难验证、最容易蒙、最不需要看具体位置，训练的是「扫全文抓整体印象」。

## Architecture（现状）

```
  student-app/  Flutter 学生端 (Web + Android)
  Riverpod + go_router + dio (docker :8082，nginx 反代 /api)
        │
        │   frontend/  旧版学生端 Web (冻结，待 Flutter 取代)    parent-web/  家长端 (独立)
        │   index.html + app.js (原生 JS，静态托管 :8766)      index.html + app.js (原生 JS，:8767)
        │         │                                                  │
        └─────────┴────────── fetch → http://127.0.0.1:8010/api ─────┘
                               │
                               ▼
┌──────────────────────────────────────────────┐
│            FastAPI (main.py)                 │
│  CORS 全开 · /uploads 静态挂载 · 每日任务调度   │
└──────────────┬───────────────────────────────┘
               │  include_router(...)
┌──────────────┼───────────────────────────────────────────────┐
│   routers/   │                                               │
│  auth config pdf progress notes points learning goals        │
│  mistakes knowledge questions tts annotations home tasks     │
│  quiz mastery users                                          │
└──────────────┼───────────────────────────────────────────────┘
               │  Depends(get_db) · Session
┌──────────────▼───────────────────────────────────────────────┐
│             models.py  (SQLAlchemy ORM)                      │
└──────────────┬───────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────┐
│                    services/                                 │
│   ai (LLM 客户端封装) · model_config (resolve) · mastery      │
│   scheduler · quiz · question_gen · task_gen ·                │
│   lesson_extract · pdf_split · tts                           │
└──────────────────────────────────────────────────────────────┘
```

关键约束：**数据库路径由进程 cwd 决定**。`DATABASE_URL` 默认是
`sqlite:///./zhixueban.db`（相对路径），真实库在 `backend/zhixueban.db`。
启动后端必须从 `backend/` 目录跑（或用绝对 `DATABASE_URL`），否则会在别的
目录生成一个 0 字节空库，看起来「返回空数据」其实是读错了库。

## AI 调用现状：prompt-in-code

当前 AI 有**两种形态**。`/api/ask` 已升级为 **agent-native**：经
`runtime/orchestrator.py` 的 `route_to_capability` → `capabilities/` 选中的
capability → `runtime/turn_engine.py` 的 `TurnEngine` 多步工具循环（调
`tools/` 里注册的 `lookup_word` / `search_text` / `render_mermaid`），并把
`Turn` / `ToolCall` 落库；不再使用 `_MODE_SYSTEM` + 单次 `generate()`。

其余 7 处仍是「构造 prompt → 单次 `generate()` → 解析返回」，
由业务代码直接发起，没有 agent 循环、没有工具调用、没有多步推理。

| 调用点                                | 角色 / 提示词                    | 形态                     |
| ------------------------------------- | -------------------------------- | ------------------------ |
| `routers/notes.py` `/api/ask`         | 学习助手（chat/visualize/solve） | **agent-native**（见下） |
| `routers/quiz.py` 出题 / 判分         | 阅读理解出题 + 判分              | `generate(json_mode)`    |
| `routers/learning.py` 阅读 / 听力材料 | 实时出阅读/听力题（慢，无缓存）   | `generate`               |
| `routers/annotations.py` 生词释义     | 划词查释义                       | `generate`               |
| `services/question_gen.py`            | 阅读理解题（入库/后台，兜底）    | `generate(json_mode)`    |
| `services/quiz.py` `generate_quiz`    | 出题 + evidence 证据校验         | `generate(json_mode)`    |
| `services/lesson_extract.py`          | 拆课提取（生词/知识点/课文）     | `generate` + 正则兜底    |
| `services/ai.py` `ocr_image`          | 扫描版页面 OCR                   | 视觉模型单次调用         |

### 「伪 capability」的现状 —— 已解决

> 此节所述问题**已解决**。三种模式（`chat` / `visualize` / `solve`）现在是
> `capabilities/chat.py` 里的真实 capability（`ChatCapability` /
> `VisualizeCapability` / `SolveCapability`，共同继承 `AgenticChatCapability`），
> 由 `TurnEngine` 多步工具循环驱动，`_MODE_SYSTEM` 已删除。详见下文
> [Agent-Native Roadmap](#agent-native-roadmap) 第 1–3 步已 DONE。

（历史记录）此前 `frontend/app.js` 有对话栏（`chatMessages`/`chatBusy`）、三种
模式 `CHAT_MODES = [chat, visualize, solve]`、模型切换、citations 定位——这些是
**agent-native 的界面雏形**。但后端 `/api/ask` 对「模式」的处理仅是换一段
`_MODE_SYSTEM` 的 system 提示词 + 单次 `generate`：`visualize` 只是靠提示词诱导
模型输出 mermaid 文本，`solve` 只是靠提示词诱导分步，**没有真正的工具在模型
背后执行**。现在这些工具（`render_mermaid` 等）已作为真实工具注册，由 LLM 在
turn 内按需调用。

## Model Configuration Layer

所有 AI/语音能力通过 **三级降级** 解析，入口是
`services/model_config.py` 的 `resolve(db, role)`，绝不抛异常：

```
binding (ModelProfile + ModelConnection)  →  legacy (ModelConfig 老键)  →  default (fake)
```

- **Role**（`provider_registry.REGISTRY` 的 key）：`llm | task | embedding |
  search | tts | stt | imagegen`。`task` 默认**继承 llm**，除非显式配了 profile。
- **Provider**（`provider_registry.ProviderSpec`）：`openai`（中转站/OpenAI 兼容，
  需 `base_url`）、`deepseek`、`glm`、`minimax`、`xunfei`、`fake`（本地兜底）。
- `services/ai.py` 的 `get_provider(db)` 返回 `AIProvider` 子类，统一
  `generate(prompt, system="", json_mode=False)`。OCR 走 `ocr_image(db, image_bytes)`
  （视觉模型取 llm 档的 `options.vision_model`）。
- 密钥掩码：`redact()` / `restore()` 用 `***` 往返，前端保存时不回传明文。

## Domain Services

| Service               | 职责                                                            |
| --------------------- | -------------------------------------------------------------- |
| `pdf_split.py`        | 按学科锚点拆课（`SUBJECT_RULES`）；扫描版走 OCR；`render_pages` 预渲染 PNG |
| `lesson_extract.py`   | 提取课文/生词/知识点，AI 失败回退正则兜底                              |
| `question_gen.py`     | 阅读理解题，任何异常回退 `FALLBACK_QUESTIONS`                          |
| `quiz.py`             | 出题（`generate_quiz`）+ 纯比较判分（`grade_answers`，无 LLM）          |
| `mastery.py`          | 掌握度 `compute_mastery` / 判分 `grade_answer`（逐字复制自 DeepTutor） |
| `scheduler.py`        | 艾宾浩斯复习间隔（`INTERVALS`）+ `next_review_after` / `select_words`  |
| `task_gen.py`         | 每日任务生成（幂等，`generate_daily_tasks` 由 main.py 03:00 触发）      |
| `tts.py`              | TTS provider 抽象（MiniMax / 讯飞 / OpenAI / fake）                     |

## Data Model

见 `backend/app/models.py`。核心关系：

- `PdfDocument` → `Lesson`（拆课结果）→ `WordBank` / `KnowledgePoint` / `Text` /
  `Question` / `Quiz` / `Note` / `Annotation`。
- 掌握度分两层：`WordMastery`（生词，保留旧字段 `correct_count/mistake_count/is_weak`）
  与 `KnowledgeMastery`（知识点）。
- `Task` 有 `UniqueConstraint(user_id, subject, date, task_type)`，每日任务幂等。
- 模型配置三表：`ModelConnection`（凭证+端点，可复用）→ `ModelProfile`（角色下的一档）
  → `RoleBinding`（角色当前启用哪一档，主键即 role）。

## Running / Verification

本地验证有几个反复踩坑的环境事实（详见 memory）：

1. **两个 Python**：Bash 的 `python` 装了全部依赖；PowerShell 终端里的 `python`
   是 conda base，**没装 sqlalchemy**。跑后端用 Bash 的 python。
2. **SQLite 路径随 cwd**：`preview_start` 不遵循 launch.json 的 `cwd`，会从仓库根
   目录起服务、读空库。正确启动：
   ```bash
   cd backend && python -m uvicorn app.main:app --port 8010
   ```
   或绝对路径 `DATABASE_URL="sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db"`。
3. **GBK 管道**：`curl … | python -c "json.load(sys.stdin)"` 会把中文按 GBK 重解码
   报 JSONDecodeError。验证 API 用 `urllib`/`requests` 单进程做请求+解析。
4. **JWT 与管理账号（生产）**：`JWT_SECRET` 在生产环境必须设为长随机密钥（默认
   `dev-change-me` 仅本地）；`ADMIN_INITIAL_PASSWORD` 控制种子为无密码用户及默认
   `login_name=admin` 写入的初始密码（默认 `ChangeMe123`）。部署后应尽快在运营后台改
   `admin` 密码。未正确设置时，后端启动日志会 warning（`pytest` 不触发）。详见仓库根
   `README.md`「生产环境：JWT 与管理员密码」与 `.env.example`。

前端静态页：学生端 `python -m http.server 8766 --directory frontend`，家长端
`python -m http.server 8767 --directory parent-web`，运营后台
`python -m http.server 8768 --directory admin-web`（`API` 默认
`http://127.0.0.1:8010`）。运行配置见 `.claude/launch.json`（prototype/backend/frontend/parent-web 四个）。

Flutter 学生端（`student-app/`）：`flutter run -d chrome`（连 `127.0.0.1:8010`），
安卓必须 `--dart-define=API_BASE=http://10.0.2.2:8010`（模拟器）；`API_BASE=` 空值时
Web 走同源。验证：`flutter analyze && flutter test`（Flutter 位于 `E:\dev\flutter`）。

## Key Files

| Path                                      | Purpose                              |
| ----------------------------------------- | ------------------------------------ |
| `backend/app/main.py`                     | FastAPI 装配 + 每日任务调度器        |
| `backend/app/models.py`                   | 全部 SQLAlchemy 模型                 |
| `backend/app/database.py`                 | engine / SessionLocal / get_db       |
| `backend/app/config.py`                   | `DATABASE_URL`（相对路径，随 cwd）   |
| `backend/app/routers/notes.py`            | `/api/ask` 路由（经 orchestrator 转 capability） |
| `backend/app/routers/`                    | 每领域一个 router                    |
| `backend/app/routers/users.py`            | `GET /api/users?role=child`（家长端孩子列表） |
| `backend/app/services/ai.py`              | `AIProvider` 抽象 + `get_provider` / `ocr_image` |
| `backend/app/services/model_config.py`    | `resolve()` 三级降级 + 密钥掩码      |
| `backend/app/services/provider_registry.py` | provider 白名单（代码常量）         |
| `backend/app/services/mastery.py`         | 掌握度 / 判分（复制自 DeepTutor）    |
| `backend/app/services/pdf_split.py`       | 拆课 + 扫描版 OCR + 页面渲染         |
| `backend/app/seed.py`                     | 种子数据（幂等）                     |
| `backend/app/core/`                       | agent 协议层：`tool_protocol.py`（BaseTool/ToolDefinition）、`context.py`（UnifiedContext）、`stream.py`（StreamEvent/StreamBus）、`capability_protocol.py`（TurnCapability/CapabilityManifest） |
| `backend/app/tools/`                      | `registry.py`（ToolRegistry）+ `builtin.py`（lookup_word/search_text/render_mermaid） |
| `backend/app/runtime/`                    | `turn_engine.py`（TurnEngine 多步工具循环）+ `orchestrator.py`（route_to_capability + _persist 落库 Turn/ToolCall） |
| `backend/app/capabilities/`               | `registry.py`（CapabilityRegistry）+ `chat.py`（Chat/Visualize/Solve 三 capability） |
| `backend/tests/`                          | pytest，`conftest.py` + 每领域 test   |
| `student-app/lib/core/`                   | Flutter 学生端：`router.dart`（登录守卫 + 三 Tab Shell）、`api_client.dart`、`config.dart`（`API_BASE` 解析） |
| `student-app/lib/features/`               | `auth` · `home` · `center` · `profile` · `shell` · `reader`（`/reader/view` pdfrx PDF 页内划选 + 标注墨迹，对齐 Web；`pdf_lesson_reader.dart` / `reader_selection_bar.dart`） |
| `student-app/test/`                       | flutter_test：`app_flow_test.dart`（整 App 流程）+ 每功能 test |
| `student-app/Dockerfile` / `nginx.conf`   | Flutter Web 镜像（自带 CanvasKit）与 nginx 反代/缓存配置 |
| `frontend/index.html` / `frontend/app.js` | 旧版学生端 Web（已冻结，待 Flutter 学生 App 取代；含对话栏 UI） |
| `parent-web/index.html` / `parent-web/app.js` | 家长端（独立单文件原生 JS，调用后端 `/api`） |
| `prototype/`                              | 早期原型（静态）                     |

---

## Agent-Native Roadmap

KnoAct 要对齐 DeepTutor 的 agent-native 架构（turn 引擎 + capability + tool），
需要跨越以下差距。此节是**演进蓝图**：第 1–3 步（Tool 抽象、Turn 引擎、
Capability）已在 `/api/ask` 落地，第 4–5 步（流式、收编其余调用点）尚未实现。

### 现状与目标的差距

| 维度          | 现状（prompt-in-code）                       | 目标（agent-native）                         |
| ------------- | -------------------------------------------- | -------------------------------------------- |
| 调用形态      | 业务代码直接 `generate(prompt)`，一次返回    | LLM 通过**工具调用**在 turn 内多步执行        |
| 能力编排      | 无；「模式」= 换 system 提示词               | `Capability` 接管整个 turn（多 stage）        |
| 工具抽象      | 无；OCR/渲染/判分都是散落的普通函数          | `ToolRegistry` + `BaseTool`，LLM 按需选择    |
| 上下文        | 每次拼一段 prompt，无统一 context            | `UnifiedContext` 规范化上下文                |
| 流式/事件     | 同步 `generate`，前端 polling / 一次性返回   | `StreamBus` 事件协议，异步流式回放           |
| 对话持久化    | 前端内存 `chatMessages`，无服务端 turn 状态  | 服务端持久化 turn 状态，可 replay            |

### 演进路径（建议顺序）

1. ✅ **DONE — 抽 Tool 抽象**（`core/tool_protocol.py`）：`BaseTool` + `ToolDefinition`
   已就绪；`tools/builtin.py` 已把生词释义（`lookup_word`）、知识库检索
   （`search_text`）、渲染（`render_mermaid`）收编为工具，`tools/registry.py`
   的 `ToolRegistry` 统一注册。
2. ✅ **DONE — 引入 Turn 运行时**（`runtime/turn_engine.py` + `core/context.py`）：
   `UnifiedContext` 已建立，`TurnEngine` 把一次 `/api/ask` 变成「一个 turn、
   最多 8 步工具调用」，服务端持久化 `Turn`/`ToolCall`（orchestrator `_persist`）。
3. ✅ **DONE — 把「模式」升级为 Capability**（`capabilities/chat.py`）：
   `chat` / `visualize` / `solve` 各自是拥有 `system_prompt` + `tools` 的
   capability（继承 `AgenticChatCapability`），经 `CapabilityRegistry` 路由，
   替换并删除了 `_MODE_SYSTEM`。
4. ✅ **DONE — StreamBus + 流式回放**：新增 `/api/ask/stream` SSE 端点（事件级
   流式：`stage`/`tool_call`/`tool_result`/`final`），`_event_stream` 用
   `asyncio.create_task` 并发跑 capability + 按索引轮询 `StreamBus.events` 实时
   yield（含 provider 异常竞态处理，保证流必终止）；前端 `chatAsk` 用
   `fetch` + `ReadableStream` 读取，`tool_call` 更新「正在…」占位、`final`
   渲染答案。落库复用 `persist_turn`。
5. ✅ **DONE — 收编散落的 prompt 调用点**：出题/材料生成抽成工具
   （`tools/generation.py`：`generate_listening` / `generate_quiz_questions` /
   `generate_diagnostic_questions`），`listening_material`、`quiz_generate`、
   `ask_questions` 三个端点改调工具，`ask_reply` 改走 TurnEngine（`chat`
   capability，AI 未配置时从 503 变为降级返回）。生词释义已是 `lookup_word`
   工具。OCR / 拆课 / 后台出题（单次确定性调用）保持现状。

> 第 1–5 步全部完成，`/api/ask` 已完全 agent 化，其余交互式/出题调用点也已
> 收编进工具层或 TurnEngine。

## 幻觉补强（已落地）

针对 `/api/ask` agent 化后的四个 LLM 幻觉风险，已做如下补强：

1. **出处句号校验**：前端把已切好的句子数组作为 `sentences` 字段传给后端
   （`UnifiedContext.sentences`），`orchestrator._filter_citations` 剔除越界句号
   （`[第N句]` 的 N 必须 ∈ `1..len(sentences)`），杜绝模型伪造不存在的引用。
2. **`search_text` 按句编号**：`search_text` 工具改用 `ctx.sentences`（回退
   `_fallback_split` 复刻前端 `splitSentences` 规则），句号与前端 `jumpToSentence`
   对齐，消除「行号 vs 句号」错位。
3. **`lookup_word` 如实失败**：查词异常回落 `meaning=""` + `error="释义暂不可用"`
   （不再编造「（示例）」假释义）。
4. **`_forced_finish` 补回约束**：兜底收尾 prompt 补回教材上下文 + 「不要编造
   教材里没有的内容」约束，且 history 为空时不输出空「工具结果」段。
5. **`render_mermaid` 严格校验**：子串匹配改为行首图类型声明正则
   （`graph|flowchart|sequenceDiagram|…`），拒绝 `"photograph of a graph"` 之类
   的伪图。
