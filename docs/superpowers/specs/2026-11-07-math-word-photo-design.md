# 数学应用题纸上作答 + AI 批改与家长审核

日期：2026-11-07  
状态：设计已定稿，待实现  
范围：数学每日任务；家长学习配置；Flutter 学生端 MVP；`parent-web` 审核 UI。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 应用题 | 纸上写过程+答案，**一题一张**照片 |
| 计算题 | 屏上填数字，**即时自动判分**（现逻辑） |
| AI | 答案+过程均需合理；不确定 → `pending_review`，**孩子不先看到终局对错** |
| 家长 | **通过（confirm）/ 打回重做（reject）**，对齐听写打卡 |
| 题量 | **`task_math_calc_count` + `task_math_word_count`** 分开配置 |
| 终局 | 须家长 **confirm** 后计完成任务/积分；AI 高置信也不单独完结 |

## 成功标准

1. 家长在学习配置中为当前孩子设置计算题数、应用题数；force 重生后 `Task.content` 含 `calc[]`、`word[]` 且长度正确。
2. 听写作答方式在同一 Tab 对**当前孩子**可见、可保存（`dictation_input_mode`）。
3. 孩子完成计算题屏上判分；应用题逐题拍照上传后 AI 写回状态；整份 submit 后进家长待审核。
4. 家长 confirm 发积分；reject 后孩子可重传重做。
5. Vision 未配置时应用题仍走「待家长确认」降级路径。

---

## §1 家长学习配置

### 1.1 听写作答方式（修复/规范）

- UI：`parent-web`「学习配置」保留听写方式下拉。
- **必须已选当前孩子 `uid`** 才展示可保存项；未选孩子时提示并禁用保存。
- 加载：`loadConfig()` + `loadLearningPreferences()`；保存：题数 `POST /api/config`，听写 `PUT /api/learning/preferences`（`user_id: uid`）。

### 1.2 数学题数

- 键（`ChildConfig`，与 `task_dictation_count_*` 同模式）：  
  - `task_math_calc_count`（默认 **2**，建议 0–10）  
  - `task_math_word_count`（默认 **2**，建议 0–10）
- 保留 `difficulty_数学` 影响出题 prompt。

### 1.3 出题

- `task_gen._gen_math_practice`：`content` 示例：

```json
{
  "calc": [{"question": "3+5=？", "answer": "8"}],
  "word": [{"id": "w1", "question": "小明有…", "answer": "5"}]
}
```

- `math_gen`：拆分或一次生成两类题；应用题答案仍为**单一数字字符串**（无单位）。

---

## §2 孩子端流程（Flutter MVP）

### 2.1 计算题

- 数字输入；提交 `POST /api/math/task/{id}/grade`（仅 calc）；**当场**对错反馈。

### 2.2 应用题

- 无答案输入框；题干 + 拍照指引。
- 每题：`upload-photo`（带 `word_index`）→ AI → 状态写入 `content.word[i]`。
- 孩子文案：仅「批改中 / 等待家长确认 / 请重新拍照」；**不展示**最终对错与积分。

### 2.3 每题状态（`content.word[i]`）

| 字段 | 说明 |
|------|------|
| `photo_path` | 本题照片 |
| `ai_status` | `ok` \| `pending_review` \| `failed` |
| `ai_correct` | AI 判定（不对孩子暴露终局） |
| `ai_notes` | 给家长看的摘要 |
| `parent_status` | `none` \| `approved` \| `rejected` |

### 2.4 整份 submit

- 条件：calc 已全部判分；每道 word 有图且 AI 已结束（含 pending/failed）。
- `submit_status=submitted`；数学 **不要求** 单一 `Task.photo_path`（听写仍可用）。

### 2.5 打回

- 家长 reject → 对应题或整份 `parent_status=rejected`，清可重拍字段；孩子重做上传与 submit。

### 2.6 范围

- **Flutter**：完整实现。  
- **frontend 8766**：P2，可选同版。

---

## §3 后端 API 与 AI

### 3.1 端点

| 端点 | 说明 |
|------|------|
| `GET …/material` | 返回 `calc`+`word`；**word 标准答案不下发孩子端**（或不下发，仅服务端 AI 用） |
| `POST /api/math/task/{id}/grade` | 仅 `calc_answers[]` |
| `POST /api/tasks/{id}/upload-photo` | 扩展 `word_index`；写路径并触发批改 |
| `POST /api/tasks/{id}/submit` | 数学校验 calc+word 完成度 |
| `POST /api/tasks/{id}/confirm` | 家长通过；数学不强制 `Task.photo_path` |
| `POST /api/tasks/{id}/reject` | **新增**；`scope: task`（MVP）；打回重做 |

### 3.2 `grade_math_work_photo`

- 输入：图、题干、`expected_answer`、`difficulty`（可选）。
- 输出：`final_answer`, `steps_plausible`, `confidence`, `reason`。
- 逻辑：  
  - 标答比对 `normalize_answer`；  
  - `steps_plausible && answer_match && confidence >= T` → `ai_status=ok`；  
  - 否则 `pending_review`；读图失败 → `failed`（视同待家长）。  
- `fake` provider：固定 JSON 便于测试。

### 3.3 兼容

- 旧 content 为 flat `[{question,answer}]` → 视为全 `calc` 或 force 重生。

### 3.4 错题本

- 计算题：即时错收录。  
- 应用题：家长 confirm 后定错再收录（或 confirm 时按 AI+家长结果）。

---

## §4 家长 UI、错误与发布

### 4.1 学习配置 Tab

- 听写方式 + 数学两题数；孩子未选时不可保存。

### 4.2 任务待审核

- 数学：计算摘要 + 应用题缩略图与 AI 标签；**确认完成** / **打回重做**。
- 听写逻辑不变。

### 4.3 降级

- 无 vision：应用题 `failed` → 家长人工 confirm。  
- `word_count=0` 或 `calc_count=0`：单边模式。

### 4.4 发布

- 部署说明：家长 **force 生成本日任务** 以应用新题结构与配置。

### 4.5 P2（本期不做）

- 单题 reject、admin math-checkins、Web 学生端数学拍照、AI 逐步讲解。

---

## §5 测试要点

- ChildConfig 题数与生成形状。  
- 上传 `word_index`、AI 三分支、孩子 API 不泄 word 答案。  
- submit / confirm / reject 与积分幂等。  
- 家长偏好与听写配置在 `uid` 存在时读写正确。

## 参考

- 听写纸上打卡：[2026-11-07-dictation-photo-checkin-design.md](./2026-11-07-dictation-photo-checkin-design.md)  
- 现有数学：`services/math_gen.py`、`routers/math.py`、`features/math_exercise/`
