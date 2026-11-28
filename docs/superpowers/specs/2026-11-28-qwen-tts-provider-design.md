# 千问（Qwen-TTS）供应商设计

日期：2026-11-28  
状态：已确认

## 背景与目标

KnoAct 的 TTS 角色目前支持 `openai` / `minimax` / `xunfei` / `fake`。用户试用阿里云百炼上的千问语音后，认为听感更好，希望接入为可选供应商。

本期目标：在现有 `TTSProvider` + `provider_registry` + `ModelConnection/Profile/RoleBinding` 体系下，增加 **`qwen` TTS 供应商**，运营后台配置百炼 API Key 后，听写/朗读可走千问合成；失败仍走现有 public mp3 → browser TTS 降级链。

## 决策记录（已与用户确认）

- **范围**：本期只做 TTS；LLM/task **不**写入白名单，但同一 `provider id = qwen` 与 Connection 预留给下一期。
- **产品线**：对准 **Qwen-TTS**（如 `qwen3-tts-flash`），不是 CosyVoice。
- **调用方式**：纯 HTTP（`requests`），不引入 `dashscope` SDK。
- **语速**：官方非实时示例无语速字段 → 本期请求不传 speed；不因配置了语速而报错。
- **Provider id**：`qwen`，显示名「千问」。
- **实现结构**：独立 `services/qwen_tts.py`（对齐 `xunfei_tts.py`），`tts.py` 只留薄封装。

## 现状

- `provider_registry.REGISTRY["tts"]` = openai / minimax / xunfei / fake。
- `services/tts.py`：`TTSProvider.synthesize(text, voice, speed) -> bytes`；`get_tts(db)` 经 `resolve(db, "tts")` 选实现。
- `routers/tts_router.py`：真人词典 → 商用合成 → public mp3 → browser；成功时目前写死 `media_type="audio/mpeg"`。
- 讯飞模式：协议细节在 `xunfei_tts.py`，`XunfeiTTS` 为薄封装。

## 架构

```
运营配置 (ModelConnection provider=qwen + Profile role=tts)
        │
        ▼
resolve(db, "tts")  →  api_key / model / voice / base_url? / options
        │
        ▼
get_tts() → QwenTTS（tts.py 薄封装）
        │
        ▼
qwen_tts.synthesize_qwen(...)
  1. 切分文本（单段 ≤600 字，按句）
  2. POST DashScope multimodal-generation
  3. 取 output.audio.url → GET 下载
  4. 多段时做「可播放合并」（见下），禁止朴素 bytes 拼接
        │
        ▼
/api/tts/synthesize 降级链不变
```

| 单元 | 职责 | 依赖 |
|------|------|------|
| `provider_registry.QWEN` | 只进 `REGISTRY["tts"]`；`default_model=qwen3-tts-flash`；`needs_base_url=False`（`base_url` 仅可选覆盖） | 无 |
| `services/qwen_tts.py` | HTTP 协议、切分、语种映射、WAV 安全合并 | `requests` |
| `tts.QwenTTS` | 实现 `TTSProvider.synthesize` | `qwen_tts` |
| `get_tts` | `provider==qwen` 时传入 `model` + 可选 `base_url` | `resolve` |

### 非目标（本期不做）

- LLM / task provider 落地
- 实时 WebSocket / 双向流式
- CosyVoice
- `dashscope` SDK
- 前端/家长端新页面或音色选型 UI（沿用现有 voice 文本配置）

## 配置与默认值

| 项 | 值 | 说明 |
|----|-----|------|
| Provider | `qwen` / 「千问」 | 仅 `tts` 白名单 |
| 凭证 | `api_key`（`Authorization: Bearer`） | 无需讯飞式 app_id / api_secret |
| 默认模型 | `qwen3-tts-flash` | Profile.`model` 可改 |
| 默认音色 | `Cherry`（芊悦） | `options.voice`；区分大小写，按官方 ID |
| Endpoint | `POST {base}/services/aigc/multimodal-generation/generation` | |
| 默认 base | `https://dashscope.aliyuncs.com/api/v1` | Connection.`base_url` 为空时使用；新加坡等可覆盖 |
| 请求体要点 | `model` + `input.text` + `input.voice` + `input.language_type` | 对齐官方非实时 Qwen-TTS HTTP |
| `language_type` | 由文本推断 | 复用 `tts_lang_for_text`：`zh`→`Chinese`，`en`→`English`，否则 `Auto` |
| 语速 | 本期不传 | 官方非实时 Qwen-TTS 示例无语速字段；「尽力而为」落地为省略 `speed`，避免乱传导致 400。后续若文档明确支持再接 `options.speed` |
| 文本上限 | 单段 ≤600 字符 | 超长按句切分；合并规则见「多段音频」 |
| LLM 预留 | 同 id `qwen` + 可复用 Connection | 本期 **不** 改 `llm`/`task` REGISTRY |

运营流程不变：Connection（provider=`qwen`）→ TTS Profile（model/voice）→ RoleBinding(`tts`)。

## HTTP 合成细节

1. 缺 `api_key` → 立即 `RuntimeError`（与 MiniMax 一致）。
2. 对每个文本分片 POST；成功响应取 `output.audio.url`（非流式）。
3. GET 该 URL 得到音频字节；URL 有效期有限（文档约 24h），合成后立刻下载，不缓存 URL。
4. 业务错误：`status_code != 200` 或响应 `code` 非空 → 抛错，消息截断。
5. 请求**不**传语速相关字段（见配置表）。

### 多段音频（禁止朴素拼接）

讯飞路径可 `bytes` 直拼，是因为 MP3 帧可顺序拼接。Qwen-TTS 非流式常见 **WAV**：朴素拼接会留下多份 RIFF 头，播放器往往只播第一段或失败。

规则：

| 段数 / 格式 | 行为 |
|-------------|------|
| 仅 1 段 | 原样返回 |
| 多段且均为 WAV（`RIFF`） | **WAV 安全合并**：解析各段 PCM，按序拼接样本，重写单一 RIFF/fmt/data 头后返回（纯 Python，不引 pydub/ffmpeg） |
| 多段且格式不一致或非 WAV | 整次失败并降级（不猜测拼接） |

听写词条/短句通常远小于 600 字，多数调用走「仅 1 段」；长课文才触发合并。

参考文档：[Qwen-TTS API（百炼）](https://help.aliyun.com/zh/model-studio/qwen-tts-api)。

## 错误处理与音频类型

| 情况 | 行为 |
|------|------|
| 未配 key / HTTP 失败 / 无 url / 下载失败 / 多段合并失败 | 抛错 → router 现有降级（public → browser） |
| 空/空白文本 | 与讯飞一致：视为失败 |

**媒体类型修正（本期一并做）：** Qwen-TTS 常返回 WAV，而 `tts_router` 现写死 `audio/mpeg`。在 **router 对商用合成成功结果做魔数探测**（`RIFF`→`audio/wav`，`ID3`/MPEG→`audio/mpeg`），**不**改 `TTSProvider.synthesize` 的返回类型，避免波及所有 provider。真人词典与 public 兜底仍为 mp3。

## 文件改动（预期）

- 修改 `backend/app/services/provider_registry.py` — 增加 `QWEN`，挂到 `tts`。
- 新增 `backend/app/services/qwen_tts.py` — 协议与切分。
- 修改 `backend/app/services/tts.py` — `QwenTTS` + `PROVIDERS` + `get_tts` 传 model/base_url。
- 修改 `backend/app/routers/tts_router.py` — 成功响应的 media_type 探测。
- 新增 `backend/tests/test_qwen_tts.py` — mock HTTP 单测。
- 视需要更新 `test_model_config` / registry 相关断言。

## 测试

- 语种映射、切分（短句不切 / 超长切开）。
- 缺 key 失败。
- 成功：mock POST 给 url + mock GET 给假音频。
- 多段 WAV 合并：两段合法 WAV → 单一可解析 RIFF，且 PCM 长度≈两段之和。
- `get_tts` binding `provider=qwen` → `QwenTTS`。
- registry：`tts` 含 `qwen`，`llm` 不含；`needs_base_url=False`。
- media_type 探测：wav 魔数 → `audio/wav`（纯函数单测）。

## 成功标准

1. 运营配置千问 + 有效百炼 Key 后，`/api/tts/synthesize` 能返回可播放音频。
2. Key 无效或上游失败时不 500，降级到 public/browser。
3. 未配置时行为与现网一致（fake / 降级）。

## 后续（非本期）

- 将 `qwen` 加入 `llm`/`task`，复用同一 Connection，走 OpenAI 兼容或百炼 Chat API。
- 若 Qwen-TTS 非实时 API 明确支持语速字段，再把 `options.speed` 接上。
- 音色下拉/试听 UI（可选）。
