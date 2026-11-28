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
- **语速**：尽力而为——确认 API 有对应字段才传；否则静默忽略，不因语速报错。
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
  3. 取 output.audio.url → GET 下载 → 多段按序拼接 bytes
        │
        ▼
/api/tts/synthesize 降级链不变
```

| 单元 | 职责 | 依赖 |
|------|------|------|
| `provider_registry.QWEN` | 只进 `REGISTRY["tts"]`；`default_model=qwen3-tts-flash` | 无 |
| `services/qwen_tts.py` | HTTP 协议、切分、语种映射、可选语速字段 | `requests` |
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
| 语速 | 尽力而为 | 有文档支持的字段才写入；否则省略 |
| 文本上限 | 单段 ≤600 字符 | 超长按句切分后逐段合成再拼接 |
| LLM 预留 | 同 id `qwen` + 可复用 Connection | 本期 **不** 改 `llm`/`task` REGISTRY |

运营流程不变：Connection（provider=`qwen`）→ TTS Profile（model/voice）→ RoleBinding(`tts`)。

## HTTP 合成细节

1. 缺 `api_key` → 立即 `RuntimeError`（与 MiniMax 一致）。
2. 对每个文本分片 POST；成功响应取 `output.audio.url`（非流式）。
3. GET 该 URL 得到音频字节；URL 有效期有限（文档约 24h），合成后立刻下载，不缓存 URL。
4. 多段结果按顺序拼接（同格式假设；若上游格式不一致则整次失败并降级）。
5. 业务错误：`status_code != 200` 或响应 `code` 非空 → 抛错，消息截断。

参考文档：[Qwen-TTS API（百炼）](https://help.aliyun.com/zh/model-studio/qwen-tts-api)。

## 错误处理与音频类型

| 情况 | 行为 |
|------|------|
| 未配 key / HTTP 失败 / 无 url / 下载失败 | 抛错 → router 现有降级（public → browser） |
| 空/空白文本 | 与讯飞一致：视为失败 |

**媒体类型修正（本期一并做）：** Qwen-TTS 常返回 WAV，而 `tts_router` 现写死 `audio/mpeg`。合成成功返回时，按下载 `Content-Type` 或魔数（`RIFF`→`audio/wav`，`ID3`/MPEG frame→`audio/mpeg`）设置 `Response.media_type`，避免前端无法播放。真人词典与 public 兜底仍为 mp3。

可选实现方式（实现计划二选一即可）：

- **A（推荐）**：`synthesize` 改为返回 `(bytes, media_type)`，或 Qwen 路径单独让 router 探测；最小化可在 router 对商用结果做魔数探测。
- **B**：仅在 `QwenTTS` 文档约定返回 wav，router 对 `tts.name == "qwen"` 固定 `audio/wav`（脆弱，若上游改 mp3 会错）。

推荐 A：探测一次，兼容所有 provider。

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
- `get_tts` binding `provider=qwen` → `QwenTTS`。
- registry：`tts` 含 `qwen`，`llm` 不含。
- media_type：wav 魔数 → `audio/wav`（可用纯函数单测探测逻辑）。

## 成功标准

1. 运营配置千问 + 有效百炼 Key 后，`/api/tts/synthesize` 能返回可播放音频。
2. Key 无效或上游失败时不 500，降级到 public/browser。
3. 未配置时行为与现网一致（fake / 降级）。

## 后续（非本期）

- 将 `qwen` 加入 `llm`/`task`，复用同一 Connection，走 OpenAI 兼容或百炼 Chat API。
- 若 Qwen-TTS 明确支持语速字段，把 `options.speed` 接上。
- 音色下拉/试听 UI（可选）。
