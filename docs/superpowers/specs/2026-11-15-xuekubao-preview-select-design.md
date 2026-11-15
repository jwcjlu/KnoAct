# 学库宝拉题：预览勾选后再入库

日期：2026-11-15  
状态：设计已定稿，待实现  
范围：`backend/app/routers/bank.py`（+ 少量 adapter/测试）；`parent-web/app.js`（学库宝弹窗两步流）；复用已有 `renderQuestionHtml`。

## 背景与目标

家长在「题库管理」点「学库宝选题」时，选好知识点后点「导入题目」会**整页直接写入**待审核队列，无法先看题干/配图再挑。学库宝题干常含 `<img>` / `<br>`，无预览时更容易误导入。

目标流程：

1. 选教材 / 知识点 / 页码  
2. **拉取预览**（不写库）  
3. 勾选想要的题（默认全选）  
4. 确认后**只入库勾选的题** → 仍进审核台 → 通过后孩子才能练  

## 已锁定决策

| 项 | 决定 |
|----|------|
| 落点 | 家长端导入前预览勾选（非审核台、非孩子端） |
| 入库后状态 | `pending`，仍走审核台；不自动 `published` |
| 跨页 | **不跨页购物车**；只导入**当前预览页**勾选的题；换页重新拉、重新勾选 |
| 方案 | A：预览接口只拉不写；确认接口写勾选草稿 |

## 成功标准

1. 点「拉取预览」后弹窗展示本页题目，题干 HTML（含图）可读，不落库。  
2. 默认全选；可全选/全不选/逐题勾选；未勾选确认时按钮禁用或 toast 提示。  
3. 确认后仅勾选题进入该卷审核队列；toast「已导入 N 道题，请到审核台确认」。  
4. 学科与卷子不一致时，预览阶段即拒绝（与现 `sync-xuekubao` 校验一致）。  
5. 现有「整页 sync」行为可保留为内部实现复用，UI 默认走预览流。

---

## §1 后端

### 1.1 `POST /api/banks/{bank_id}/preview-xuekubao`

请求体与现 `XuekubaoSyncReq` 相同：

```json
{
  "knowledge_id": "15190",
  "page": 2,
  "max_import": 20,
  "qtype_id": null,
  "diff": null,
  "year": null,
  "fetch_answers": true
}
```

行为：

- 鉴权 / 卷子归属与 `sync-xuekubao` 相同。  
- 调用 `xuekubao_adapter.fetch_by_knowledge` + `normalize`，截断 `max_import`（1–50）。  
- **不调用** `_persist_drafts`、不 `commit`。  
- 做与 sync 相同的**学科一致性校验**（任一 draft 的 `tags.subject_name` 与卷子学科冲突 → 400）。  
- 响应：

```json
{
  "drafts": [
    {
      "qtype": "single_choice",
      "question": "...html...",
      "options": [{"label": "...", "value": 0}],
      "answer_json": {},
      "answer": "",
      "analysis": "",
      "difficulty": "medium",
      "tags": {"source": "xuekubao", "xuekubao_id": "..."}
    }
  ],
  "data_count": 120,
  "page": 2
}
```

`drafts` 由 `QuestionDraft` 序列化（`dataclasses.asdict` 或显式 dict）。空列表时 `drafts: []` + 可选 `message`（与 sync 文案对齐）。

### 1.2 `POST /api/banks/{bank_id}/import-drafts`

写入已标准化的草稿列表（避免再走学库宝 `normalize`，也避免把 raw API JSON 在前端往返出错）。

```json
{
  "source": "xuekubao",
  "items": [ /* 与 preview 返回的 draft 对象同形 */ ]
}
```

行为：

- 将每个 `item` 建成 `QuestionDraft`（缺 `question` 的跳过）。  
- 再次做学科校验（防篡改）。  
- `_persist_drafts(db, bank, drafts, source)` → `pending`。  
- 返回 `{ "count", "ids" }`。

上限：单次 `items` ≤ 50。

### 1.3 现有 `sync-xuekubao`

保留（测试 / 脚本 / 兼容）；家长 UI 不再直接调用。实现上可把「fetch + normalize + 学科校验」抽成内部函数，供 preview 与 sync 共用。

### 1.4 测试

- `preview-xuekubao`：mock adapter，断言不增加 `Question` 行、响应含 drafts。  
- `import-drafts`：写入后题目 `status=pending`、`bank_id` 正确。  
- 学科不符：preview / import 均 400。

---

## §2 家长端 UI（`parent-web`）

### 2.1 弹窗状态机

扩展 `xkbPicker`：

| 字段 | 含义 |
|------|------|
| `step` | `'pick'` \| `'preview'` |
| `drafts` | 预览列表 |
| `selected` | `Set` / 对象：下标 → bool，默认全 true |
| `previewLoading` | 拉取中 |
| `dataCount` | 学库宝总条数提示（可选展示） |

### 2.2 步骤 1（现有）

- 文案：主按钮由「导入题目」改为「拉取预览」。  
- `confirmXuekubaoSync` → `loadXuekubaoPreview`：调 `preview-xuekubao`，成功则 `step='preview'`，`selected` 全选。

### 2.3 步骤 2（新建）

- 列表：每题 checkbox + 题型标签 + `renderQuestionHtml(question)` + 选项摘要（同样走 `renderQuestionHtml`）。  
- 工具条：全选 / 全不选；展示「已选 n / m」。  
- 「上一页/换页」：返回步骤 1 改页码再拉，或步骤 2 内改页码触发重新 preview（清空当前勾选）。**不**累加跨页。  
- 主按钮「导入已选 (n)」→ `import-drafts`，成功 toast、关弹窗、`loadBankList` + `render`。  
- 「返回」→ `step='pick'`，可保留上次 drafts 或清空（实现选清空更简单）。

### 2.4 不在本设计范围

- tiku.cn 同步预览（可后续复用同一 preview/import-drafts 模式）。  
- 孩子端练习页改动。  
- 审核台改动（仅继续接收更少、更准的 pending）。

---

## §3 数据流

```
家长选知识点/页码
    → POST preview-xuekubao
    → 弹窗勾选
    → POST import-drafts { source: xuekubao, items: selectedDrafts }
    → Question(status=pending)
    → 审核台通过 → published → 孩子题库练习
```

---

## §4 非目标 / 风险

- **跨页购物车**：明确不做；换页即新预览。  
- **前端伪造草稿**：`import-drafts` 仍做学科校验与长度上限；不信任前端改卷子学科。  
- **图片 CORS**：家长端是原生 HTML `img`，走已有 `renderQuestionHtml`，无 Flutter Web CORS 问题。  
- **大 payload**：单页 ≤ 50 题；题干含图 URL 字符串，体积可接受。

---

## §5 实现顺序建议

1. 后端：抽取 sync 公共逻辑 → `preview-xuekubao` + `import-drafts` + pytest  
2. 前端：`xkbPicker` 两步 UI + API 接线  
3. 手工验证：语文/数学卷各拉一页，勾选子集 → 审核台条数与内容正确  
