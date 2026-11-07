# 英语听力题改为选择题（3～5 题 × 4 选 1）设计

日期：2026-11-07  
状态：已确认（brainstorming），待实现  
范围：仅 `task_type=listening` / 学习中心「听力理解」；阅读理解保持简答。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 范围 | 英语听力 only；阅读不改 |
| 题量 | 每套 **3～5** 道，每题 **4 选 1** |
| 语言 | 题干 + 选项 **全英文** |
| 对话展示 | **默认隐藏**正文，仅 TTS（与现 UX 一致）；做完可看原文（可选折叠） |
| 旧数据 | **强制刷新**：发版后家长「重新生成本日任务」`force=true`；不做旧 JSON 懒升级兼容 UI |

## 成功标准

1. 新生成的 listening `Task.content` 含 `dialogue` + `questions[]`（每题 `options[4]` + `correct_index`）。
2. `GET /api/listening/material` 返回上述结构；客户端可渲染选择题。
3. Flutter / Web 听力 Tab：**无**简答输入框；选对/错后错题本记录英文选项文本。
4. 阅读 Tab 行为不变。
5. 文档说明：部署后家长需 force 重生今日任务以替换旧 listening 卷。

---

## 一、数据与后端

### 1.1 JSON  schema（`Task.content` 与生成工具输出）

```json
{
  "dialogue": "A: Hi Tom! B: Hi! ...",
  "questions": [
    {
      "id": "q1",
      "question": "What does Tom want to do?",
      "options": ["Read a book", "Play football", "Sing a song", "Draw a picture"],
      "correct_index": 2
    }
  ]
}
```

- `questions.length` ∈ [3, 5]
- 每题 `len(options) == 4`，`correct_index` ∈ [0, 3]
- 校验失败 → fake 回落（固定对话 + 3 道模板选择题）

### 1.2 `GenerateListeningTool`（`tools/generation.py`）

- 更新 prompt / `json_mode` 输出为新 schema（英文对话略加长以支撑 3～5 题）
- 移除对顶层 `question`/`answer` 的依赖（生成侧）
- 实现 `_normalize_listening(data) -> dict`：裁剪题量、补齐选项、修正 index

### 1.3 `GET /api/listening/material`（`routers/learning.py`）

- 从 `Task.content` 解析新 schema；返回：

```json
{
  "text": "<dialogue>",
  "questions": [ { "id", "question", "options", "correct_index" } ]
}
```

- 若当日 `Task` 存在但 content 为**旧格式**（无 `questions` 数组）：**不**在 GET 内自动升级；视为需家长 force 重生（可实现为：检测旧格式 → 调用 `generate_listening` 写回，仅当产品后续改为 A 懒升级时再启用——**本 spec 采用 C：依赖 force 重生，GET 可对旧格式返回空题 + 提示或仍尝试 regenerate 一次写回，见实现计划二选一并在测试中固定**）

**推荐实现（与 C 一致且避免孩子看到空卷）**：GET 发现旧格式时 **触发一次 regenerate 写回**（等同当日刷新），并在 release note 要求家长 force 重生以批量更新未打开过的任务。

### 1.4 `task_gen._gen_listening`

- `Task.content` = 完整新 JSON
- `Question` 表：`question` 可存首题题干摘要；`extra` 继续可存 `dialogue`；`answer` 存首题正确选项文本或 `correct_index` 字符串（实现择一，保持家长审核可读）

### 1.5 判分与错题

- 无新 REST；客户端本地比对 `selected_index === correct_index`
- 错题：`POST /api/review/submit`，`your_answer` / `correct_answer` 为**选项英文文案**，`source_type=listening`

---

## 二、Flutter

### 2.1 模型 `CenterQuestion` / `CenterMaterial.fromJson`

- 选择题：`options` + `correct_index`
- 简答（阅读）：`answer` 字符串
- 工厂方法区分两种 shape

### 2.2 `center_controller`

- listening：`answer(index, selectedIndex: int)`
- reading：保持 `answer(index, input: String)`
- 错题收录选项全文

### 2.3 UI `center_page`（听力）

- 不展示 `material.text`；播放按钮 TTS
- 每题 4× `RadioListTile`；提交后显示对错
- 全部作答后 `submitTask`（现有 `shouldAutoSubmit`）
- 可选：完成后折叠「Dialogue transcript」

### 2.4 测试

- 模型解析单测
- controller 下标判分
- 听力 widget 无 `TextField`（或 listening 模式下）

---

## 三、Web `frontend/app.js`

- `renderCenter` 听力题：radio 组，存 `centerPick[k]` 为 index 或 option text（比对用 index）
- `centerAnswer`：`listening` 用 `correct_index`；`reading` 不变
- 不渲染对话正文；保留 `playListening()`

---

## 四、发布与迁移

1. 部署后端 + 前端
2. 通知家长：**学习 → 生成今日任务（覆盖）** 至少一次
3. 验证：英语 listening 任务 3～5 道选择题；阅读仍为填空

### 风险

| 风险 | 缓解 |
|------|------|
| LLM 格式错 | `_normalize_listening` + fake |
| 旧客户端 | 同期发 Web + Flutter |
| 全英文难度 | 后续 difficulty 配置（YAGNI） |

---

## 五、实现检查清单

- [ ] `GenerateListeningTool` + 校验/normalize + fake
- [ ] `listening_material` 映射新 schema
- [ ] `task_gen._gen_listening` content 格式
- [ ] Flutter 模型 / controller / 听力 UI
- [ ] Web 听力选择题 UI
- [ ] pytest + flutter test
- [ ] README / 发版说明（force 重生）
