# KnoAct 幻觉补强设计（四个缺口全补）

日期：2026-10-27

## 背景

agent-native 运行时（Tool + TurnEngine + Capability）已落地，但存在四个 LLM 幻觉风险缺口：

1. **出处伪造**（最严重）：模型在 `final_answer` 里写 `[第N句]` 无校验，可编造不存在的句号，前端跳到错误位置。
2. **`lookup_word` 假释义**：异常回落编造 `「{word}」的释义（示例）`，误导孩子。
3. **`_forced_finish` 脱离约束**：兜底路径的 prompt 无教材上下文，模型可脱离原文自由发挥。
4. **`render_mermaid` 校验形同虚设**：子串匹配，垃圾输入能通过。

## 已确认的关键决策

| 决策 | 选择 |
| --- | --- |
| 范围 | 四个缺口全补 |
| 句切分契约 | 前端传句子数组（`sentences` 字段） |
| 契约落地 | 新增 `sentences` 字段，兼容旧 `context`，未传时回退 |
| 出处校验强度 | 句号在 `1..len(sentences)` 范围内（非「必须被 search_text 返回过」） |
| lookup_word 回落 | `meaning=""` + `error` 字段（不编造） |
| render_mermaid | 行首图类型声明正则（非子串） |

## 设计

### 1. 统一句子切分契约

前端 `splitSentences` 按 `/(?<=[。！？!?])|\n+/` 切句（1-based 编号），前端 `jumpToSentence(n)` 按此跳转。本次让**前端把已切好的句子数组传给后端**，后端 `search_text` 工具和 orchestrator 校验都基于同一份数组，彻底消除口径分歧。

改动（3 处）：

- **前端 `chatAsk`**（`app.js:1957`）：body 加 `sentences: splitSentences(ctx)`。
- **后端 `UnifiedContext`**（`core/context.py`）：加 `sentences: list[str] = field(default_factory=list)`。
- **`AskReq`**（`notes.py`）：加 `sentences: list[str] = []`，透传给 `UnifiedContext`。

契约：`sentences[i]` 是第 `i+1` 句（1-based）。未传 `sentences` 时（旧调用/测试），工具回退到 `ctx.text` 简单切分，行为与现状一致。

### 2. 出处校验（orchestrator 层）

`route_to_capability` 提取 citations 后做范围校验——句号必须在 `1..len(ctx.sentences)` 内：

```python
citations = _extract_citations(answer)
if ctx.sentences:
    valid_max = len(ctx.sentences)
    citations = [n for n in citations if 1 <= n <= valid_max]
```

- 校验强度 = 「句号在范围内」，不误杀模型直接引用 prompt 里已见的教材上下文的合理引用。
- `ctx.sentences` 为空时跳过校验（不误伤旧调用）。
- 无论答案来自正常路径还是 `_forced_finish`，都过这层硬校验。

### 3. `search_text` 工具改用 `ctx.sentences`

```python
def run(self, args, ctx):
    query = (args.get("query") or "").strip()
    sentences = ctx.sentences or _fallback_split(ctx.text)
    if not query or not sentences:
        return {"matches": []}
    matches = []
    for idx, s in enumerate(sentences, start=1):
        if query in s:
            matches.append({"sentence_no": idx, "text": s.strip()})
    return {"matches": matches}
```

- `sentence_no` 现在是「句」号（1-based），与前端 `jumpToSentence`、orchestrator 范围校验三者对齐。
- `_fallback_split` 回退：后端复刻前端 `splitSentences` 的切句规则 `/(?<=[。！？!?])|\n+/`。
- 更新工具 `description`，明确「句号对应前端跳转」。

### 4. `lookup_word` 假释义回落

```python
except Exception:
    return {"word": word, "meaning": "", "error": "释义暂不可用"}
```

- 异常不再编造 `（示例）`，而是 `meaning=""` + `error` 字段，模型看到后如实告知孩子「查不到」，而非把占位当真。
- 正常路径（LLM 释义成功）不变。

### 5. `_forced_finish` 补回教材上下文 + 约束

```python
async def _forced_finish(self, ctx, history, stream):
    try:
        context_part = f"教材上下文：{ctx.text or '（无）'}\n"
        history_part = (
            "之前的工具结果如下：\n" + "\n".join(json.dumps(h, ensure_ascii=False) for h in history)
            if history else ""
        )
        prompt = (
            f"{context_part}"
            f"孩子提问：{ctx.question}\n"
            f"{history_part}\n"
            "请只基于上面的教材上下文和工具结果直接给出最终回答（不要再调工具），"
            "不要编造教材里没有的内容。"
        )
        raw = await asyncio.to_thread(self.provider.generate, prompt, self._system(ctx), True)
        ...
```

- 补回教材上下文（原 prompt 缺失）。
- 加「不要编造」软约束。
- 修空 history 边界（原代码 history 为空时会输出空「工具结果」段）。
- 仍是软约束，真正的硬防线是第 2 节的出处校验。

### 6. `render_mermaid` 严格校验

```python
import re

_MERMAID_RE = re.compile(
    r"^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|mindmap|journey)\b",
    re.MULTILINE,
)

def run(self, args, ctx):
    code = (args.get("code") or "").strip()
    if not code:
        return {"ok": False, "error": "code 不能为空"}
    valid = bool(_MERMAID_RE.search(code))
    return {"ok": valid, "code": code} if valid else {"ok": False, "error": "不是有效的 mermaid 图"}
```

- 行首 + 单词边界匹配，`"photograph of a graph"` 会被拒。
- 扩大合法图类型（sequenceDiagram/classDiagram/stateDiagram/erDiagram/gantt/pie/journey），不误杀合理图。
- 仍非完整语法解析（不引第三方库），够挡「编造图类型」的核心幻觉。

## 非目标

- 不给 `lookup_word` 接真实词典/词库（功能增强，非幻觉补强）。
- 不做完整 mermaid 语法解析（引第三方库，超范围）。
- 不改前端 `splitSentences` / `jumpToSentence` 逻辑（它们已经是权威切句）。
