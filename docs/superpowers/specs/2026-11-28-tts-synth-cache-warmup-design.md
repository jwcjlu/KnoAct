# 商业 TTS 磁盘缓存 + 听写任务后预热

日期：2026-11-28  
状态：已确认

## 背景与目标

听写会反复点「听发音」。真人词典路径（`word_audio` → `uploads/tts_cache/`）已有磁盘缓存；**商业合成**（MiniMax / 讯飞 / OpenAI / 千问等）每次都打上游，既慢又费。课堂报读上线后，同一课的 `speak_text` / 生词 / cue 更会被多次请求。

本期目标：

1. 为**商业 TTS 合成**增加磁盘缓存（命中直接读盘）。
2. 听写任务生成成功后，**后台预热**当日相关可播文本，降低孩子首听冷启动。

## 决策记录（已与用户确认）

| 项 | 选择 |
|----|------|
| 范围 | 磁盘缓存 + 任务生成后后台预热 |
| 缓存键 | `text + provider + model + voice + speed` |
| 预热失败 | 静默跳过；不挡任务、不展示 |
| 预热文本 | 孩子端实际会打到 `/api/tts/synthesize` 的串：`speak_text`（有则）+ `word`（与 speak_text 不同或缺失时）；**不**把 `dictation_cue` JSON 整段拿去合成 |
| 淘汰 | MVP 不做；只写缓存，运维/手工清盘 |
| 方案 | 商业 TTS 统一缓存层 + 生成后后台预热（方案 2） |

## 现状

- `/api/tts/synthesize`（`tts_router.py`）：真人词典 → 商用 `tts.synthesize` → `synthesize_public_mp3` → browser TTS。
- `uploads/tts_cache/` **仅**服务 `word_audio`（真人/公开词典跟读），键为 `lang:text`，**不含** provider/voice/speed。
- 商用合成路径目前**无**落盘；`fake` 与公开朗读兜底也不应与商用缓存混用。
- 听写任务由 `task_gen._gen_dictation` / `generate_daily_tasks` 落库；课堂报读字段见 `2026-11-28-dictation-classroom-speak-design.md`。

## 架构

```
孩子端 GET /api/tts/synthesize?text=…
        │
        ├─ real=true → word_audio（uploads/tts_cache）命中则返回
        │
        ▼
商用 get_tts(db)
        │
        ├─ tts_synth_cache 命中 → 直接返回字节
        │
        └─ miss → provider.synthesize → 写 uploads/tts_synth_cache/ → 返回
                （失败仍走 public mp3 → browser，且不写 synth 缓存）

听写任务落库成功
        │
        ▼
BackgroundTasks / 短命后台线程
        │
        ▼
收集去重文本（speak_text / word）
        │
        ▼
串行：商用 synthesize + 写 tts_synth_cache（失败 continue）
```

| 单元 | 职责 |
|------|------|
| `tts_synth_cache` 读写 | 键、路径、原子写；与 `tts_cache` 目录分离 |
| `tts_router.synthesize` | 商用路径：先查缓存再合成；命中跳过上游 |
| 预热入口 | 听写任务写入成功后触发；调度路径用后台线程（自开 `SessionLocal`，不复用已关闭 session） |
| 文本收集 | 从当日听写 task `content` 取 `speak_text` / `word` 并去重 |

**与课堂报读的关系**：`speak_text` 来自 `2026-11-28-dictation-classroom-speak`。该字段尚未写入旧任务时，预热仍应对每条 `word` 生效。

## 1. 缓存层

**插入点**：`tts_router.synthesize` 在「真人 miss → 商用 synthesize」之间。不改各 provider 内部实现。

**目录**：`uploads/tts_synth_cache/`（与 `uploads/tts_cache/` 分开）。

**键与文件名**：

```
sha1(f"{provider}|{model}|{voice}|{speed:.2f}|{text}")[:24]
→ uploads/tts_synth_cache/{provider}_{hash}.{ext}
```

- `provider` / `model`：当前 `get_tts` / `resolve(db, "tts")` 结果。
- `voice`：请求参数；空则用 profile 默认音色。
- `speed`：请求显式值，否则 `_configured_speed(db)`（与现路由一致）。
- `ext`：按 `sniff_audio_media_type`（`.mp3` / `.wav` 等）；读取时仍 sniff。

**读写**：复用现有原子写模式（tmp → `os.replace`）；文件过小（如 ≤200 字节）视为无效。

**不写此缓存**：`fake`、公开朗读兜底、真人 `word_audio`。

**不做**：TTL、大小淘汰、跨机共享、DB 索引。

## 2. 预热触发

**时机**：听写任务**写入成功之后**；不在拆课、不在同步 HTTP 关键路径里阻塞。

**触发方式**：

- 有请求生命周期：FastAPI `BackgroundTasks`。
- 每日调度 `generate_daily_tasks`（无 HTTP）：短命 daemon 线程（对齐 `main.py` 拆课续跑），异常吞掉。

**文本收集**（去重后串行）：

1. 每条 item 的 `speak_text`（有且非空）
2. 每条 item 的 `word`（当无 `speak_text`，或 `word` ≠ `speak_text` 时）

说明：`WordBank.dictation_cue` 是 JSON（`compound` / `gloss_short` 等），客户端只播 `speak_text ?? word`，**从不**把 cue 整段或字段单独请求 TTS。组词/短释义已编进 `speak_text`，故预热**不**再单独合成 cue / compound / gloss_short，避免无命中的商用调用。

**合成路径**：与商用 synthesize + 写 `tts_synth_cache` 同一逻辑；跳过真人与浏览器兜底。`voice`/`speed` 用当前 TTS profile 默认，与孩子端未显式传参时的键一致。

对 `word` 的商用预热是**兜底**：孩子端 `real=true` 时词条优先 `word_audio`；商用缓存主要加速 `speak_text`（整句）以及真人 miss 时的词条合成。成功标准不以「词条首听必走商用缓存」计量。

**限流**：同一预热批内串行；单条超时/异常 `continue`；整批上限约 40 条文本。

**不做**：家长可见状态、重试队列、跨用户全局去重调度器。

## 3. 失败、观测与边界

**失败**：预热任一条失败 → debug/info 日志；不抛、不写任务字段、不进家长端。孩子首听仍走 `/api/tts/synthesize`（miss 则现合成再落盘）。

**观测（最小）**：

- 日志：`tts_synth_cache hit|miss|write`；`warmup start|item_fail|done`（含 user/task/文本长度，**不含**全文）。
- 无新 API、无 metrics 面板。

**前端**：不改。

## 测试要点

- 同键第二次 synthesize **不**调 provider。
- 改 `speed` / `voice` / `provider`（或 model）各应 miss 一次。
- 预热：mock synthesize，断言当日应收集的 `speak_text` / `word` 被请求且写盘；**不**对 cue JSON 发起合成。
- 预热失败：provider 抛错 → 听写任务仍存在、无异常冒泡。

## 非目标（本期不做）

- TTL / 自动淘汰
- 跨机共享盘 / 对象存储
- 预热进度 UI / 家长「音频预热未齐」
- 把公开朗读或真人录音并入 synth 缓存
- 任务生成时**同步**合成音频
- 改 Flutter / 旧版前端播报协议

## 成功标准

1. 商用 TTS 相同键重复请求读盘，上游调用次数下降。
2. 听写任务生成后，后台尽量预热当日可播文本；失败不影响任务可用。
3. 真人词典缓存与商用 synth 缓存目录、键空间互不干扰。
4. 上述测试要点有自动化覆盖。
