# 教材配套真人音频（跟读 / 磨耳朵）设计

日期：2026-11-16
状态：待评审

## 背景与目标

KnoAct 目前的「音频」只有两类：AI 合成的 TTS（生词 / 单词朗读）和 AI 生成的
听力练习（`listening` task），没有**真人教材配套音频**。孩子想跟读课文 / 磨耳朵
时，只能听 TTS，无法听原版朗读。

本次目标：把下载好的教材配套真人音频（`Unit 1–8 + Word list`，每个 Unit 一个
约 10MB 的 MP3）导入 KnoAct，并配套到教材，使孩子能在**学生端**按 Unit 播放真人
课文音频、跟读、循环磨耳朵。

已确认的决策：

- **核心用法**：课文真人音频跟读 / 磨耳朵（非切分做听力题）。
- **粒度**：Unit 整体 + 时间点标记（不切文件，用 `start_sec` 分段跳播）。
- **关联锚点**：按文件名 `Unit N` 自动匹配 `Lesson`，并支持家长端手动纠正。
- **播放入口**：学生端**阅读器内** + **独立磨耳朵页**，两处都要。
- **时间点标记工具**：本期做，放家长端，**精确版（波形拖拽定位）**。
- **管理入口**：家长端（parent-web）「教材音频」管理区。

## 现状梳理

- `Textbook` 模型（`subject` / `unit`）存在但从未被创建——是死表，本次不用它。
- Unit 拆解靠 `Lesson`：`services/pdf_split.py` 的 `detect_lessons` 按
  `(Unit|Lesson)\s*\d+` 锚点拆出，`Lesson.title` 形如 `Unit 1 …`（英语学科）。
- 学生端已依赖 `audioplayers: 6.8.1`；家长端用 `new Audio(url)` 播放。
- 后端 `main.py` 已 `app.mount("/uploads", StaticFiles(...))`，静态文件可直达。

## 数据模型（新增一表 `LessonAudio`）

| 字段          | 类型      | 说明                                                        |
| ------------- | --------- | ----------------------------------------------------------- |
| `id`          | PK        |                                                             |
| `lesson_id`   | FK → lessons.id, nullable | 关联课；`Word list` 等非课音频为 NULL |
| `document_id` | FK → pdf_documents.id | 归属教材（冗余，便于按教材聚合/鉴权） |
| `unit_label`  | String(255) | 展示名，如 `Unit 1` / `Word list`                         |
| `audio_path`  | String    | 相对路径 `uploads/audio/{doc.id}_{安全名}.mp3`              |
| `marks_json`  | LongText  | 时间点标记 `[{"label":"Lesson A","start_sec":12.5}, …]`，空 `[]` 整段播放 |
| `created_at`  | DateTime  |                                                             |

索引：`document_id`；`lesson_id`。

## 后端（新增 `routers/lesson_audio.py`）

鉴权沿用现有 `require_role` / `resolve_target_user_id` / `ensure_pdf_document_access`
（家长上传管理，孩子只读，且只能读本人已绑定教材的音频）。

| 端点 | 方法 | 说明 |
| --- | --- | --- |
| `/api/lesson-audio` | POST（multipart） | 家长上传 MP3 → 存 `uploads/audio/` → 按文件名 `Unit N` 自动匹配 Lesson，写 `lesson_id`；匹配不到则 NULL |
| `/api/lesson-audio?document_id=` | GET | 按教材列音频（含 `lesson_id`、`unit_label`、`marks`） |
| `/api/lesson-audio/{id}` | PATCH | 手动纠正 `lesson_id` / `unit_label` |
| `/api/lesson-audio/{id}/marks` | PUT | 保存时间点标记 `marks_json` |

- 播放不建流式端点：前端拿 `audio_path` 拼 `/uploads/…` 直读静态文件。
- 文件名解析：`^(\d+)_Unit\s*(\d+)$` → `Unit {n}`；`Word list` → `unit_label="Word list"`。
- 自动匹配：`db.query(Lesson).filter_by(document_id=..., subject="英语")`，按 title 含
  `Unit {n}` 匹配；多个 / 零个匹配都回落到手动纠正。

## 前端

### 家长端（parent-web，单文件原生 JS）

新增「教材音频」管理区（挂在教材管理附近）：

1. 选教材 → 上传 Unit 音频（可批量）。
2. 列表展示：`unit_label` + 自动匹配到的课 + 状态（已匹配 / 未匹配）。
3. 手动纠正：未匹配的音频选一个 Lesson 绑定；已匹配的可改。
4. **标记工具（精确版）**：
   - `<audio>` 试听；用 Web Audio API（`decodeAudioData` + `OfflineAudioContext` 或
     `canvas` 波形）渲染波形图。
   - 拖拽播放头定位到精确毫秒，点「设为第 N 课起点」写入 `marks_json`。
   - 支持对已存标记的删除 / 微调。

### 学生端（Flutter，`student-app/`）

两处入口，共用一个新的 `lesson_audio` feature（repository + controller）：

1. **阅读器内**（`features/reader/pdf_lesson_reader.dart`）：当前 Unit 有音频时，
   顶部出现「课文音频」播放条（`audioplayers`）；有 `marks` 则分段（点某课从
   `start_sec` 起播），无则整段。
2. **独立磨耳朵页**：教材 → Unit 列表 → 播放 / 单曲循环，可离开阅读器连续听。
   入口放在学生端 home / center 的合适位置。

音频 URL 解析复用 `core/config.dart` 的 `API_BASE` 规则（Web 同源 / 安卓模拟器
`10.0.2.2`），`audio_path` 拼到后端 base。

## 错误处理

- 上传非 MP3 / 超限：拒绝并提示。
- 文件名无法解析 Unit：仍入库（`unit_label` 取文件名去扩展名），`lesson_id=NULL`，
  靠手动纠正。
- 音频文件缺失（磁盘被清理）：GET 返回时 `audio_path` 仍下发，前端播放失败给出
  「音频不可用」提示，不崩。
- 孩子访问未绑定教材的音频：鉴权拒绝（复用文档访问控制）。

## 测试

- 后端 pytest：文件名解析、自动匹配（命中 / 多命中 / 零命中）、marks 读写、
  权限（家长 vs 孩子 vs 未绑定）。
- 前端：Flutter `lesson_audio` controller 单测（URL 拼接、marks 分段逻辑）；
  家长端标记工具的秒数存取逻辑若可抽成纯函数则单测。

## 范围与非目标

**做**：LessonAudio 表 + 后端 CRUD + 家长端管理/标记工具 + 学生端两处播放入口。

**不做**（后续）：按课自动切割音频文件、自动识别课起点（AI/静音检测）、
波形标记在移动端的编辑、`Textbook` 表启用 / 迁移。
