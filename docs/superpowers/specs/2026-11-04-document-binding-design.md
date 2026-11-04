# 教材绑定（家长选配 + 教材标签辅助）设计

> 日期：2026-11-04
> 状态：与用户逐节确认中

## 背景与目标

KnoAct 目前「孩子 ↔ 教材」没有绑定关系：`PdfDocument.grade`/`edition` 字段已预留但
是「死字段」（上传不写、列表不按它过滤），`GET /api/pdf/documents` 返回全部教材，
每个孩子看到的都是同一个平的教材库。

需求：孩子能看到哪些教材，由**家长在家长端显式选配**，而不是靠「年级/版本自动匹配」。

设计决策（已与用户确认）：

1. **家长选配**：新增「孩子 ↔ 教材」绑定表，家长把某孩子勾选绑定到若干教材；
   一本教材可绑多个孩子（天然实现「教材共享」），一个孩子可绑多本（不限学科/年级）。
2. **教材标签辅助**：`PdfDocument.grade`/`edition` 保留，作为家长端「按年级/版本筛选、
   分组浏览教材库」的辅助标签，**不作为**孩子可见性的强制匹配规则。
3. 孩子可见教材 = 家长勾选绑定的教材集合，与年级/版本无关（升年级后仍按绑定，由家长调整）。

## 核心决策

| 决策 | 结论 |
|------|------|
| 绑定关系 | 新表 `UserDocument`（`user_id` + `document_id`，唯一约束） |
| 教材共享 | 一本教材可绑多个孩子 → 天然共享 |
| 年级/版本字段 | 保留作标签，家长端筛选辅助；不参与自动匹配 |
| 孩子可见性 | `GET /api/pdf/documents?user_id=` 只返回该孩子绑定的教材 |
| 绑定管理 | 家长端在教材管理里勾选孩子；后端 `bind`/`unbind` 接口 |

---

## 第 1 节：数据模型

新增绑定表 `UserDocument`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | PK | |
| `user_id` | FK→users.id | 孩子 |
| `document_id` | FK→pdf_documents.id | 教材 |

`__table_args__` = `UniqueConstraint("user_id", "document_id", name="uq_user_document")`。

> 需注意外键级联：删除教材（`delete_document`）或删除孩子时，要清理 `UserDocument`
> 里对应的行（现有代码是手动 purge，见 `services/cleanup.py` / `delete_document`）。

`PdfDocument.grade`/`edition` 字段保持不变（已有），仅补上传时写入 + 列表返回。

## 第 2 节：后端接口

1. **上传时写标签**：`POST /api/pdf/upload` 加可选 `grade`（int）、`edition`（str）表单参数，
   写入 `PdfDocument`（不填则 `grade=None`、`edition=""`）。

2. **教材列表支持过滤 + 返回标签**：
   - `GET /api/pdf/documents` 加可选 `user_id` 参数：有则只返回该孩子绑定的教材；
     无则返回全部（家长端用）。
   - 返回项增加 `grade`、`edition` 字段。

3. **绑定管理**：
   - `POST /api/pdf/documents/{document_id}/bind`，body `{user_id}` → 建绑定（幂等）。
   - `DELETE /api/pdf/documents/{document_id}/bind?user_id=` → 解绑（幂等）。
   - `GET /api/pdf/documents/{document_id}/bound-users` → 返回已绑定该教材的孩子 id 列表
     （家长端打开某教材时回显勾选状态）。

4. **孩子拉教材**（学生端）：`GET /api/pdf/documents?user_id=<当前孩子id>`。

## 第 3 节：家长端（parent-web）

1. 教材列表 `renderPdfTab` 的每个教材行，增加「已绑定 N 个孩子」的入口；
   点开显示孩子多选框（复用 `children` 列表），勾选即 `bind`、取消即 `unbind`。
2. 上传表单 `renderPdfTab(upload)` 增加「年级」「版本」两个输入（可选），随 `upload_pdf` 提交。
3. 教材列表行显示 `grade`/`edition` 标签（辅助信息）。

## 第 4 节：学生端（student-app）

1. `PdfRepository.documents()` 改为带 `user_id` 参数调用 `GET /api/pdf/documents?user_id=`。
2. `ReaderController.loadDocuments()` 从 `currentChildIdProvider` 取 uid 传入。
3. `PdfDoc` 模型无需改动（学生端不关心标签）。

## 第 5 节：错误处理与边界

- 未登录孩子（uid 为 null）拉教材 → 返回空列表或 401 由前端处理（沿用现有登录守卫）。
- 绑定/解绑不存在的教材或孩子 → 幂等返回 `{"ok": true}`（或 404，沿用现有风格）。
- 删除教材时级联清理 `UserDocument`（补进 `delete_document` 的 purge 逻辑）。
- 升年级不影响绑定（绑定与年级解耦，家长自行调整）。

## 第 6 节：测试

- 后端：绑定/解绑幂等、`user_id` 过滤只返回绑定教材、删除教材清理绑定、上传写标签。
- 前端：学生端带 uid 拉教材；家长端勾选触发 bind/unbind。

---

## 范围边界

- **不做**：教材跨家长全局共享库（仍是每个家长传自己的 PDF，但可通过「绑定多个孩子」在
  同一家长名下共享）。
- **不做**：年级/版本自动匹配孩子可见教材（明确改为家长手动选配）。
- **保留**：`User.edition`（孩子身上的单值版本字段）暂不动；「按学科版本」的 `ChildConfig`
  方案不在本次范围，后续若要「上传时按孩子学科版本预填」再议。
