# 练习册解析重构 · 计划二（前端）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让家长端和 Flutter 学生端能正确展示并作答新后端的「题组 + 小题」结构与 `$...$` LaTeX 公式。

**Architecture:** 后端已在计划一完成并通过真实验证（6 题组 / 47 题 / 答案全对）。本计划只改前端：家长端用本地 KaTeX 渲染公式并按题组分组展示；Flutter 新增 `math_text` widget 渲染公式、`bank_models` 加题组字段、按 `input_ui` 渲染交互（keypad / chooser / camera 本期先只做前两种）。

**Tech Stack:** `parent-web/`（原生 JS 单文件 + nginx）、`student-app/`（Flutter 3.47 + Riverpod + go_router）。

**Spec:** `docs/superpowers/specs/2026-11-22-practice-parsing-redesign.md`（§十 题目格式与展示）
**计划一（已完成）:** `docs/superpowers/plans/2026-11-22-practice-parsing-backend.md`

---

## 前置状态（已就绪，不需重做）

| 项 | 状态 |
|---|---|
| 后端 API 返回 `work_mode`/`answer_kind`/`input_ui`/`group_id`/`seq_in_group`/`is_example` | ✅ 已完成（`/api/practice-import/questions`、`/api/banks/{id}/questions`） |
| `GET /api/practice-import/pages`、`PATCH .../pages/{page_no}` | ✅ 已完成 |
| 后端 751 测试全绿 | ✅ |
| `student-app/pubspec.yaml` 已加 `flutter_math_fork: ^0.7.4` | ✅ 未提交（见 Task 1） |
| KaTeX CanvasKit 渲染实测通过 | ✅（详见规格 §10.1） |

## 后端还需要补的一个字段（Task 0）

`/api/practice-import/questions` 返回了 `group_id` 但没有 `group_stem`，家长端要显示「不计算，运用规律直接写出得数」就必须有它。Task 0 补上。

---

## Task 0: 后端补字段（**两个端点都要改**）

**Files:**
- Modify: `backend/app/routers/practice_import.py`（`list_practice_questions`、`_job_payload`）
- Modify: `backend/app/routers/bank.py`（`list_bank_questions` — **Flutter 读的是这个**）
- Test: append to `backend/tests/test_practice_groups.py`

前端需要但后端没返回的字段，一次性补掉：

| 字段 | 加在哪个端点 | 用在哪 | 缺了会怎样 |
|---|---|---|---|
| `group_stem` / `group_instruction` | `practice-import/questions` **和** `banks/{id}/questions` | 家长端 + Flutter 题组展示 | 只看到一堆裸算式 |
| `document_id` | `practice-import/jobs/latest`（`_job_payload`） | 家长端页类型面板 | 面板**静默不渲染** |
| `blank_count` | `banks/{id}/questions`（**Flutter**）、`practice-import/questions` | Flutter 多空输入框 | 多空题只有一个框 → 永久判错 |

> ⚠️ **关键**：Flutter 通过 `bank_repository.dart:29` 读 `/api/banks/{bankId}/questions`
> （`bank.py::list_bank_questions`），**不是** `practice-import/questions`。
> 只改后者的话，`blank_count` 永远缺省为 1，多空题在 Flutter 里仍然只有一个输入框。

- [ ] **Step 1: 写失败测试**

Append to `backend/tests/test_practice_groups.py`:

```python
def test_practice_questions_include_group_and_blank_info(setup_db, db):
    """家长端要按题组展示并渲染多空输入框。"""
    from app.models import PracticeQuestionGroup, Question, QuestionBank
    from conftest import parent_child

    parent, _child, parent_h, _ch = parent_child(db)
    bank = QuestionBank(user_id=parent.id, title="册", subject="数学", grade=5,
                        source="practice_pdf")
    db.add(bank)
    db.flush()
    g = PracticeQuestionGroup(bank_id=bank.id, user_id=parent.id,
                              stem="不计算，运用规律直接写出得数",
                              instruction="", work_mode="pattern",
                              page_start=3, page_end=3)
    db.add(g)
    db.flush()
    db.add(Question(bank_id=bank.id, user_id=parent.id, qtype="fill_blank",
                    qtype_category="blank", question="示例1", answer="1.2",
                    status="published", group_id=g.id, seq_in_group=1,
                    is_example=True, work_mode="pattern"))
    db.add(Question(bank_id=bank.id, user_id=parent.id, qtype="fill_blank",
                    qtype_category="blank", question="待做",
                    answer="1234.5, 12345",
                    answer_json='{"blanks":["1234.5","12345"]}',
                    status="published", group_id=g.id, seq_in_group=2,
                    is_example=False, work_mode="pattern"))
    db.commit()

    r = _practice_client().get(
        f"/api/practice-import/questions?bank_id={bank.id}", headers=parent_h)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["group_stem"] == "不计算，运用规律直接写出得数" for i in items)
    todo = [i for i in items if not i["is_example"]][0]
    assert todo["blank_count"] == 2
    example = [i for i in items if i["is_example"]][0]
    assert example["blank_count"] == 1


def test_bank_questions_include_blank_count(setup_db, db):
    """Flutter 读的是 /api/banks/{id}/questions，blank_count 必须在这里也返回。"""
    from app.models import PracticeQuestionGroup, Question, QuestionBank
    from conftest import parent_child

    _parent, child, _ph, child_h = parent_child(db)
    bank = QuestionBank(user_id=child.id, title="卷", subject="数学", grade=5)
    db.add(bank)
    db.flush()
    g = PracticeQuestionGroup(bank_id=bank.id, user_id=child.id,
                              stem="不计算，运用规律直接写出得数",
                              instruction="", work_mode="pattern",
                              page_start=1, page_end=1)
    db.add(g)
    db.flush()
    db.add(Question(bank_id=bank.id, user_id=child.id, qtype="fill_blank",
                    qtype_category="blank", question="待做",
                    answer="1234.5, 12345",
                    answer_json='{"blanks":["1234.5","12345"]}',
                    status="published", group_id=g.id, seq_in_group=1,
                    is_example=False, work_mode="pattern"))
    db.commit()

    r = _bank_client().get(f"/api/banks/{bank.id}/questions", headers=child_h)
    assert r.status_code == 200
    item = r.json()[0]
    assert item["blank_count"] == 2
    assert item["group_stem"] == "不计算，运用规律直接写出得数"
    assert item["answer"] == "1234.5, 12345"


def test_job_payload_includes_document_id(setup_db, db):
    """/jobs/latest 必须带 document_id，否则家长端页类型面板拿不到数据。"""
    from app.models import PracticeImportJob
    from app.routers.practice_import import _job_payload

    job_id, _bank_id, doc_id = _mk_job(db, "docid", 1, "m.pdf")
    job = db.get(PracticeImportJob, job_id)
    payload = _job_payload(job)
    assert payload["document_id"] == doc_id
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k "blank_info or blank_count or document_id" -v`
Expected: FAIL — `KeyError: 'group_stem'`

- [ ] **Step 3: 建共享的 `blank_count_of`**

**只建一份**，两个 router 都 import 它（避免两份实现漂移）：

`backend/app/core/blank_count.py`：

```python
"""判空数：给前端决定渲染几个输入框。"""
import json


def blank_count_of(q) -> int:
    """该题要填几个空。多空题看 answer_json.blanks，其余算 1。

    不能按 answer 里的逗号数推断：单个答案本身含逗号（如 `1,234`）时会多算空，
    而判分严格要求空数一致，多一个空就是永久判错。
    """
    try:
        data = json.loads(getattr(q, "answer_json", "") or "{}")
    except (ValueError, TypeError):
        return 1
    if not isinstance(data, dict):
        return 1
    blanks = data.get("blanks")
    if isinstance(blanks, list) and blanks:
        return len(blanks)
    return 1
```

两个 router 都加：

```python
from ..core.blank_count import blank_count_of
```

- [ ] **Step 4: 改 `practice-import/questions`**

`list_practice_questions` 里，拿到 `rows` 之后批量查题组：

```python
    gids = {r.group_id for r in rows if r.group_id}
    groups = {}
    if gids:
        from ..models import PracticeQuestionGroup

        for g in db.query(PracticeQuestionGroup).filter(
                PracticeQuestionGroup.id.in_(gids)).all():
            groups[g.id] = g
```

返回体每项补（`answer` 已有，不要重复加）：

```python
                "group_stem": (groups[r.group_id].stem
                               if r.group_id in groups else ""),
                "group_instruction": (groups[r.group_id].instruction
                                      if r.group_id in groups else ""),
                "blank_count": blank_count_of(r),
```

- [ ] **Step 5: 改 `banks/{id}/questions`（Flutter 用的那个）**

`bank.py::list_bank_questions` 里，现有的 `groups` 批量查询已经存在（Task 13 加的）。
在返回体每项里补：

```python
            "blank_count": blank_count_of(item),
```

> `group_stem` / `answer` / `work_mode` / `input_ui` / `answer_kind` /
> `seq_in_group` / `is_example` Task 13 已经加过了，确认存在即可。

- [ ] **Step 6: `_job_payload` 补 `document_id`**

`_job_payload` 的返回 dict 里加：

```python
        "document_id": job.document_id,
```

- [ ] **Step 7: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k "blank_info or blank_count or document_id" -v`
Expected: PASS（3 passed）

- [ ] **Step 8: 全量回归**

Run: `cd backend && python -m pytest -q`
Expected: ALL PASS（754+）

- [ ] **Step 9: 提交**

```bash
git add backend/app/core/blank_count.py backend/app/routers/practice_import.py backend/app/routers/bank.py backend/tests/test_practice_groups.py
git commit -m "feat(practice): 两个题目端点都返回 blank_count，jobs 返回 document_id"
```

---

## Task 1: 家长端 KaTeX 本地内置

**Files:**
- Create: `parent-web/vendor/katex/katex.min.js`、`katex.min.css`、`fonts/`（从 npm 包拷入）
- Modify: `parent-web/index.html`（引入）
- Modify: `parent-web/Dockerfile`（COPY vendor）
- Modify: `parent-web/nginx.conf`（vendor 不参与 SPA 回退）

**为什么本地内置而不走 CDN**：部署环境可能无外网；且 CDN 与本地行为不一致会让「无 KaTeX 时不崩」的测试失去意义。

- [ ] **Step 1: 下载 KaTeX**

```bash
cd parent-web
npm pack katex@0.16.11
tar -xzf katex-0.16.11.tgz
mkdir -p vendor/katex
cp package/dist/katex.min.js vendor/katex/
cp package/dist/katex.min.css vendor/katex/
cp -r package/dist/fonts vendor/katex/
rm -rf package katex-0.16.11.tgz
```

（若 `npm`/`tar` 不可用：直接访问 `https://registry.npmjs.org/katex/-/katex-0.16.11.tgz` 下载后解压。）

> **Windows / PowerShell 版**（上面的 `tar -xzf` + `cp -r` 是 bash 语法）：
> ```powershell
> cd parent-web
> npm pack katex@0.16.11
> tar -xzf katex-0.16.11.tgz          # Windows 10+ 自带 tar
> New-Item -ItemType Directory -Force vendor\katex | Out-Null
> Copy-Item package\dist\katex.min.js, package\dist\katex.min.css vendor\katex\
> Copy-Item -Recurse package\dist\fonts vendor\katex\fonts
> Remove-Item -Recurse -Force package, katex-0.16.11.tgz
> ```

验证：

```bash
ls parent-web/vendor/katex/
# 期望：katex.min.js  katex.min.css  fonts
ls parent-web/vendor/katex/fonts | head -3
# 期望：KaTeX_AMS-Regular.woff2 等
```

- [ ] **Step 2: 在 `index.html` 引入**

在 `<head>` 里、现有样式之后加：

```html
<link rel="stylesheet" href="vendor/katex/katex.min.css">
<script defer src="vendor/katex/katex.min.js"></script>
```

- [ ] **Step 3: Dockerfile 带上 vendor**

`parent-web/Dockerfile` 现在是：

```dockerfile
COPY index.html app.js /usr/share/nginx/html/
```

改成：

```dockerfile
COPY index.html app.js /usr/share/nginx/html/
COPY vendor/ /usr/share/nginx/html/vendor/
```

- [ ] **Step 4: nginx 别让 vendor 走 SPA 回退**

`parent-web/nginx.conf` 末尾现在是：

```nginx
    location / {
        try_files $uri $uri/ /index.html;
    }
```

在它之前插入（`^~` 阻止正则 location 抢匹配，也避免缺失文件回退成 index.html 而静默 200）：

```nginx
    # 静态资源缺失要真 404，不要回退 index.html（否则测不出漏拷）
    location ^~ /vendor/ {
        try_files $uri =404;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }
```

- [ ] **Step 5: 验证**

```bash
docker build -t knoact-parent-web-test ./parent-web
docker run --rm knoact-parent-web-test ls /usr/share/nginx/html/vendor/katex/
# 期望列出 katex.min.js katex.min.css fonts
```

（没装 docker 就跳过，在 Step 6 提交说明里注明。）

- [ ] **Step 6: 提交**

```bash
git add parent-web/vendor parent-web/index.html parent-web/Dockerfile parent-web/nginx.conf
git commit -m "feat(parent-web): 本地内置 KaTeX（不走 CDN），vendor 静态资源不参与 SPA 回退"
```

---

## Task 2: 家长端公式渲染 `decorateMath`

**Files:**
- Modify: `parent-web/app.js`（`renderQuestionHtml` 不再剥 `$`；新增 `decorateMath`）
- Test: `parent-web/test_math.js`（Node 跑的纯函数测试，新建）

**现状（已核实）**：`parent-web/app.js:593` 是
```js
out += escapeHtml(String(n.textContent||'').replace(/\$([^$]+)\$/g, '$1'));
```
——**主动剥掉 `$`**，所以家长现在看到的是 `\frac{3}{4}` 源码。

- [ ] **Step 1: 写失败测试**

新建 `parent-web/test_math.js`：

```js
// 用 node 直接跑：node parent-web/test_math.js
// 只测纯函数（HTML 字符串生成），不碰 DOM。
const assert = require('assert');

// app.js 是浏览器脚本，这里用正则抽出需要的函数体来求值
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/app.js', 'utf8');

function extract(name) {
  const start = src.indexOf('function ' + name);
  if (start < 0) throw new Error('not found: ' + name);
  let depth = 0, i = src.indexOf('{', start), began = false;
  for (; i < src.length; i++) {
    if (src[i] === '{') { depth++; began = true; }
    else if (src[i] === '}') { depth--; if (began && depth === 0) break; }
  }
  return src.slice(start, i + 1);
}

const escapeHtml = eval('(' + extract('escapeHtml') + ')');
const escapeAttr = eval('(' + extract('escapeAttr') + ')');
const markMath = eval('(' + extract('markMath') + ')');

// 1) 公式必须变成占位 span，而不是被剥成纯文本
const out1 = markMath(escapeHtml('计算 $\\frac{3}{4} \\times 2$ 的值'));
assert.ok(out1.includes('class="math-tex"'), '应输出 math-tex 占位: ' + out1);
assert.ok(out1.includes('data-tex'), '应带 data-tex 属性: ' + out1);
// 注意：data-tex 里本来就会含 \frac（那是要给 KaTeX 的源码），
// 所以不能断言「输出里没有 \frac」。要断言的是「可见文本里没有公式源码」。
const visible1 = out1.replace(/<span class="math-tex"[^>]*><\/span>/g, '');
assert.ok(!visible1.includes('frac'),
  '公式源码不应出现在可见文本里，实际可见文本: ' + visible1);

// 2) 中文与公式混排：中文留在 span 外
assert.ok(out1.includes('计算'), '中文应保留');
assert.ok(out1.includes('的值'), '尾部中文应保留');

// 3) 没有 $ 的文本原样返回
const out2 = markMath(escapeHtml('求涂色部分的面积'));
assert.strictEqual(out2, '求涂色部分的面积');

// 4) $ 不成对时按普通文本处理，不吞字符
const out3 = markMath(escapeHtml('只有 $一个 美元符号'));
assert.ok(out3.includes('$一个'), '不配对时不应吞掉 $: ' + out3);
assert.ok(!out3.includes('math-tex'), '不配对时不应生成占位: ' + out3);

// 5) 多个公式
const out4 = markMath(escapeHtml('$a=1$ 和 $b=2$'));
const n = (out4.match(/math-tex/g) || []).length;
assert.strictEqual(n, 2, '应生成 2 个占位，实际 ' + n);

console.log('OK  parent-web/test_math.js  全部通过');
```

- [ ] **Step 2: 运行确认失败**

Run: `node parent-web/test_math.js`
Expected: FAIL — `Error: not found: markMath`

- [ ] **Step 3: 实现 `markMath`**

在 `parent-web/app.js` 里，`escapeHtml` 之后加：

```js
/**
 * 把已转义的文本里的 $...$ 换成 KaTeX 占位 span。
 * 只匹配成对的 $...$（不配对时原样返回，绝不吞字符）。
 * 注意：入参必须是**已经 escapeHtml 过**的文本，否则 XSS。
 */
function markMath(escaped){
  const src = String(escaped || '');
  let out = '';
  let last = 0;
  const re = /\$([^$]+)\$/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    out += src.slice(last, m.index);
    const tex = m[1];
    // data-tex 用 escapeAttr 处理双引号；内容已 escape，安全
    out += `<span class="math-tex" data-tex="${escapeAttr(tex)}"></span>`;
    last = m.index + m[0].length;
  }
  out += src.slice(last);
  return out;
}
```

- [ ] **Step 4: 改 `renderQuestionHtml` 不再剥 `$`**

把那一行：

```js
out += escapeHtml(String(n.textContent||'').replace(/\$([^$]+)\$/g, '$1'));
```

改为：

```js
out += markMath(escapeHtml(String(n.textContent||'')));
```

- [ ] **Step 5: 新增 `decorateMath(root)`**

在 `markMath` 之后加：

```js
/**
 * 把 root 内所有 .math-tex 占位渲染成公式。
 * 没有 KaTeX（例如直接双击打开 index.html）时降级为等宽原文，不抛错。
 */
function decorateMath(root){
  const host = root || document;
  const nodes = host.querySelectorAll('.math-tex:not([data-rendered])');
  for (const el of nodes) {
    const tex = el.getAttribute('data-tex') || '';
    if (window.katex && tex) {
      try {
        katex.render(tex, el, {throwOnError: false, displayMode: false});
        el.setAttribute('data-rendered', '1');
        continue;
      } catch (e) {
        // 落到下面的降级分支
      }
    }
    el.textContent = tex;
    el.style.fontFamily = 'ui-monospace, Menlo, Consolas, monospace';
    el.style.color = '#c05b4a';
    el.setAttribute('data-rendered', '1');
  }
}
```

- [ ] **Step 6: 在 `render()` 末尾调用**

`parent-web/app.js` 的 `render()` 函数末尾，在它写 `innerHTML` 之后调一次
（根元素是 `<main class="main" id="main">`，见 `index.html:971`）：

```js
  decorateMath(document.getElementById('main') || document.body);
```

- [ ] **Step 7: 其它渲染入口也要调（否则公式显示为空白）**

`markMath` 生成的是**空** `<span class="math-tex">`，只有被 `decorateMath` 处理过才有内容。
`#main` 之外的容器（典型是 `paintXkbModal()` 填充的弹窗）必须单独调。

**注意**：`formatQuestionRichDetail()` 返回的是**字符串**而非写 DOM，在它末尾调
`decorateMath` 没有意义。正确做法是在**把它返回的字符串写进 DOM 之后**调。

```js
// 在 paintXkbModal() 把 HTML 写进 #xkbModal 之后加
decorateMath(document.getElementById('xkbModal') || document.body);
```

先用 `rg -n "paintXkbModal|formatQuestionRichDetail" parent-web/app.js` 找到这两个函数。
`formatQuestionRichDetail` 的调用方（通常是 `xkbModal.innerHTML = formatQuestionRichDetail(...)`）
在赋值之后调 `decorateMath(...)`。

不这么做的话，「无 KaTeX 时降级为等宽原文」的承诺只在 `#main` 内成立，
弹窗里的公式会是一片空白。

- [ ] **Step 8: 运行测试**

Run: `node parent-web/test_math.js`
Expected: `OK  parent-web/test_math.js  全部通过`

- [ ] **Step 9: 提交**

```bash
git add parent-web/app.js parent-web/test_math.js
git commit -m "feat(parent-web): 题干 \$...\$ 渲染为 KaTeX（无 KaTeX 时降级原文）"
```

---

## Task 3: 家长端按题组展示题目

**Files:**
- Modify: `parent-web/app.js`（`practiceQuestionRows`）
- Test: `parent-web/test_group.js`（新建）

**现状**：`practiceQuestionRows()` 把每道题平铺成一个 `.pdf-row`。47 道题就是 47 行，看不出「这 15 道都属于『直接写出得数』」。

- [ ] **Step 1: 写失败测试**

新建 `parent-web/test_group.js`：

```js
const assert = require('assert');
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/app.js', 'utf8');

function extract(name) {
  const start = src.indexOf('function ' + name);
  if (start < 0) throw new Error('not found: ' + name);
  let depth = 0, i = src.indexOf('{', start), began = false;
  for (; i < src.length; i++) {
    if (src[i] === '{') { depth++; began = true; }
    else if (src[i] === '}') { depth--; if (began && depth === 0) break; }
  }
  return src.slice(start, i + 1);
}

const escapeHtml = eval('(' + extract('escapeHtml') + ')');
const escapeAttr = eval('(' + extract('escapeAttr') + ')');
const markMath = eval('(' + extract('markMath') + ')');
const groupPracticeQuestions = eval('(' + extract('groupPracticeQuestions') + ')');

// 同一 group_id 的题聚成一组，示例与待做分开
const items = [
  {id:1, group_id:7, group_stem:'不计算，运用规律直接写出得数', seq_in_group:1, is_example:true,  question:'$1.08 \\div 0.9 = 1.2$', answer:'1.2'},
  {id:2, group_id:7, group_stem:'不计算，运用规律直接写出得数', seq_in_group:2, is_example:true,  question:'$11.1 \\div 0.9 = 12.3$', answer:'12.3'},
  {id:3, group_id:7, group_stem:'不计算，运用规律直接写出得数', seq_in_group:3, is_example:false, question:'$111 \\div 0.9 =$ ____', answer:'123'},
  {id:4, group_id:8, group_stem:'用竖式计算', seq_in_group:1, is_example:false, question:'$603-239$', answer:'364'},
];

const grouped = groupPracticeQuestions(items);
assert.strictEqual(grouped.length, 2, '应聚成 2 组');
assert.strictEqual(grouped[0].stem, '不计算，运用规律直接写出得数');
assert.strictEqual(grouped[0].examples.length, 2, '第一组应有 2 个示例');
assert.strictEqual(grouped[0].items.length, 1, '第一组应有 1 个待做');
assert.strictEqual(grouped[1].stem, '用竖式计算');
assert.strictEqual(grouped[1].examples.length, 0);
assert.strictEqual(grouped[1].items.length, 1);

// 没有 group_id 的题（旧数据）单独成组，stem 为空
const legacy = groupPracticeQuestions([
  {id:9, group_id:null, question:'旧题', answer:'1'},
  {id:10, group_id:null, question:'旧题2', answer:'2'},
]);
assert.strictEqual(legacy.length, 1, '无分组的历史题聚成一组');
assert.strictEqual(legacy[0].stem, '');
assert.strictEqual(legacy[0].items.length, 2);

console.log('OK  parent-web/test_group.js  全部通过');
```

- [ ] **Step 2: 运行确认失败**

Run: `node parent-web/test_group.js`
Expected: FAIL — `Error: not found: groupPracticeQuestions`

- [ ] **Step 3: 实现 `groupPracticeQuestions`**

在 `markMath` 之后加：

```js
/**
 * 把扁平的题目数组按 group_id 聚成题组。
 * 无 group_id 的历史题聚成一组（stem 为空），保证旧卷也能显示。
 * 返回 [{groupId, stem, lessonTitle, examples:[], items:[]}, ...]，组内按 seq_in_group 排序。
 */
function groupPracticeQuestions(list){
  const groups = new Map();
  for (const q of (list || [])) {
    const gid = q.group_id == null ? 'legacy' : String(q.group_id);
    if (!groups.has(gid)) {
      groups.set(gid, {
        groupId: q.group_id,
        stem: String(q.group_stem || ''),
        lessonTitle: String(q.lesson_title || ''),
        examples: [],
        items: [],
      });
    }
    const g = groups.get(gid);
    (q.is_example ? g.examples : g.items).push(q);
  }
  const bySeq = (a, b) => (a.seq_in_group || 0) - (b.seq_in_group || 0);
  const out = [];
  for (const g of groups.values()) {
    g.examples.sort(bySeq);
    g.items.sort(bySeq);
    out.push(g);
  }
  return out;
}
```

- [ ] **Step 4: 重写 `practiceQuestionRows`**

```js
function practiceQuestionRows(){
  if(!practiceQuestions.length){
    return '<div style="color:#8e9691;padding:12px 0">还没有题目。导入完成后这里会列出全部题目。</div>';
  }
  const groups = groupPracticeQuestions(practiceQuestions);
  return groups.map(g => {
    const head = g.stem
      ? `<div style="margin:14px 0 6px;font-weight:700;font-size:13px;color:#3b4642">
           ${markMath(escapeHtml(g.stem))}
         </div>`
      : (g.groupId == null
          ? '<div style="margin:14px 0 6px;font-weight:700;font-size:13px;color:#8e9691">历史导入的题目</div>'
          : '');
    const examples = g.examples.length
      ? `<div style="margin:0 0 8px;padding:8px 10px;background:#f6f8f6;border-radius:8px;
                     font-size:12px;color:#5c6761">
           <div style="font-weight:600;margin-bottom:4px">已印好的示例（孩子不用做）</div>
           ${g.examples.map(e => `<div>${markMath(escapeHtml(String(e.question||'')))}</div>`).join('')}
         </div>`
      : '';
    const rows = g.items.map(q => `
      <div class="pdf-row">
        <div class="pdf-info">
          <div class="nm">${markMath(escapeHtml(String(q.question || '')))}</div>
          <div class="meta">
            ${escapeAttr(String(q.lesson_title || ''))}
            · 答案 <b style="color:var(--green2)">${escapeAttr(String(q.answer || '（缺）'))}</b>
          </div>
          ${q.image_url ? `<img src="${API}${escapeAttr(q.image_url)}" alt="题图" loading="lazy"
              style="display:block;margin-top:8px;max-width:360px;width:100%;border:1px solid var(--line3);border-radius:8px">` : ''}
        </div>
        <div class="pdf-actions">
          <span style="font-size:11px;color:${q.status==='published'?'var(--green2)':'#c05b4a'}">
            ${q.status==='published'?'已发布':'未发布'}
          </span>
        </div>
      </div>`).join('');
    return `<div>${head}${examples}${rows}</div>`;
  }).join('');
}
```

> **保留原 `.pdf-row` / `.pdf-info` / `.pdf-actions` 结构**，只是外面多套了题组标题与示例块。这样既有样式不用改。

- [ ] **Step 5: 竖式题要能换行（否则多行竖式被截成一行）**

`parent-web/index.html:451` 的 `.pdf-row .nm` 现在是：

```css
.pdf-row .nm{font-size:14px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}
```

`white-space:nowrap` 会把竖式/脱式的多行排版（`\n` + 行首空格）压成一行并省略。
规格 §10 要求用 `pre-wrap` 保留换行与缩进。改为：

```css
/* 题目正文要保留竖式的换行与行首空格（规格 §10）；行数靠 max-height 兜住 */
.pdf-row .nm{font-size:14px;font-weight:700;white-space:pre-wrap;word-break:break-word;max-width:100%}
```

> 去掉 `overflow:hidden` / `text-overflow:ellipsis` 是有意的：截断竖式比长一点更糟。
> 若担心过长，可加 `max-height:12em; overflow-y:auto`。

- [ ] **Step 6: 运行测试**

Run: `node parent-web/test_group.js && node parent-web/test_math.js`
Expected: 两个都 OK

- [ ] **Step 7: 提交**

```bash
git add parent-web/app.js parent-web/test_group.js parent-web/index.html
git commit -m "feat(parent-web): 题目按题组展示（题干+示例+待做），题干保留竖式换行"
```

- [ ] **Step 8: 已知限制（记进代码注释）**

题目列表是分页的（每页 50 条，`offset > 0` 时追加）。若**一个题组跨过 50 题边界**，
它的标题可能在第一页显示一次、第二页再显示一次（因为分页是服务端切的，前端只拿到
当前页的片段）。

在 `groupPracticeQuestions` 的 docstring 里注明：

```js
/**
 * ...
 * 已知限制：题目列表是分页的（50/页），若一个题组跨过页边界，
 * 它的题干会在两页各显示一次。题组通常只有几道小题，实际很少触发；
 * 若日后需要严格处理，改成服务端按 group_id 聚合返回。
 */
```

---

## Task 4: 家长端页类型修正界面

**Files:**
- Modify: `parent-web/app.js`（`renderPracticeImport` 里加一个页类型区块）

**目的**：目录页被误判成 `toc` 时，那页的题永远导不进来。家长要能看见并改回来。

- [ ] **Step 1: 加载页类型**

加一个状态与加载函数：

```js
let practicePages = [];          // [{page_no, page_type, group_count, status}]

async function loadPracticePages(documentId){
  practicePages = [];
  if(!documentId) return;
  const r = await api(`/api/practice-import/pages?document_id=${documentId}`);
  practicePages = (r && r.pages) || [];
}

async function patchPageType(documentId, pageNo, pageType){
  const r = await api(
    `/api/practice-import/pages/${pageNo}?document_id=${documentId}`,
    {method:'PATCH', body:{page_type: pageType}});
  if(r && r.page_type){
    toast(`第 ${pageNo} 页已改为「${r.page_type}」，请点击「重新导入」生效`);
    await loadPracticePages(documentId);
    render();
  } else {
    toast('修改失败');
  }
}
```

在 `loadLatestPracticeJob` 拿到 job 之后调 `await loadPracticePages(job.document_id)`，
**并给 `practiceDocumentId` 赋值**（缺这一行 `onchange` 会传 null 导致 PATCH 失败）：

```js
async function loadLatestPracticeJob(bankId){
  // ... 现有逻辑拿到 job 之后 ...
  if(job){
    practiceDocumentId = job.document_id || null;
    await loadPracticePages(practiceDocumentId);
  }
}
```

> `_job_payload` 已由 Task 0 补上 `document_id`。

- [ ] **Step 2: 渲染页类型列表**

在 `renderPracticeImport()` 的「④ 已导入题目」区块**之前**插入：

```js
        ${practicePages.length ? `
        <div style="margin-top:24px">
          <div class="bank-list-head"><span>页类型（判断错的可改）</span></div>
          <div style="margin-top:8px;font-size:12px;color:#8e9691">
            非 practice 的页不会导入题目。目录页/答案页被误判时改回 practice 再重新导入。
          </div>
          <div class="pdf-list" style="margin-top:10px">
            ${practicePages.map(p => `
              <div class="pdf-row">
                <div class="pdf-info">
                  <div class="nm">第 ${p.page_no} 页
                    <span style="font-size:11px;color:${p.page_type==='practice'?'var(--green2)':'#c05b4a'}">
                      ${escapeAttr(p.page_type)}
                    </span>
                  </div>
                  <div class="meta">识别到 ${p.group_count} 个题组 · 状态 ${escapeAttr(p.status)}</div>
                </div>
                <div class="pdf-actions">
                  <select style="border:1px solid var(--line3);border-radius:8px;padding:4px 6px;font-size:12px"
                          onchange="patchPageType(${practiceDocumentId}, ${p.page_no}, this.value)">
                    ${['practice','toc','answer_key','cover','blank'].map(t =>
                      `<option value="${t}" ${t===p.page_type?'selected':''}>${t}</option>`
                    ).join('')}
                  </select>
                </div>
              </div>`).join('')}
          </div>
        </div>` : ''}
```

其中 `practiceDocumentId` 需要新增一个模块级变量，在拿到 job 时赋值：

```js
let practiceDocumentId = null;
```

- [ ] **Step 3: 手工验证**

1. `python -m http.server 8767 --directory parent-web`
2. 浏览器打开 `http://127.0.0.1:8767`
3. 进练习册导入 → 选一本已导入的卷
4. 确认：页类型列表出现、公式渲染成数学符号（不是 `\frac`）、题目按题组分组显示、示例块标着「孩子不用做」

- [ ] **Step 4: 提交**

```bash
git add parent-web/app.js
git commit -m "feat(parent-web): 页类型可见可改（误判目录页可改回 practice 重导）"
```

---

## Task 5: Flutter `math_text` 渲染器

**Files:**
- Create: `student-app/lib/core/widgets/math_text.dart`
- Test: `student-app/test/math_text_test.dart`

**设计约束（来自规格 §10.1，实测得出）：**
1. 行内公式用 `WidgetSpan(alignment: PlaceholderAlignment.middle)`
2. **短公式降级为纯文本**：LaTeX 源码 ≤ 6 字符且不含 `\ ^ _ { }` → 去掉 `$` 用 `TextSpan`，避免 `WidgetSpan` 整块换行把后面的「（　）」拆到下一行
3. 必须给 `onErrorFallback`，返回红字原文，绝不抛异常
4. `$` 不配对 → 全文按普通文本处理

- [ ] **Step 1: 写失败测试**

```dart
// student-app/test/math_text_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/core/widgets/math_text.dart';

void main() {
  List<InlineSpan> spansOf(String text) => buildMathSpans(text);

  test('短公式降级为纯文本（不走 Math.tex）', () {
    final spans = spansOf(r'一个数 $2.5$ 倍');
    final widgets = spans.whereType<WidgetSpan>().toList();
    expect(widgets, isEmpty, reason: '2.5 只有 3 字符，应降级');
    final text = spans.whereType<TextSpan>().map((s) => s.text ?? '').join();
    expect(text, contains('2.5'));
    expect(text, isNot(contains(r'$')));
  });

  test('长公式用 WidgetSpan', () {
    final spans = spansOf(r'计算 $\frac{3}{4}$ 的值');
    expect(spans.whereType<WidgetSpan>().length, 1);
  });

  test('不含 \$ 时只产生一个 TextSpan', () {
    final spans = spansOf('求涂色部分的面积');
    expect(spans.whereType<WidgetSpan>(), isEmpty);
    expect(spans.whereType<TextSpan>().length, 1);
  });

  test('\$ 不配对时按普通文本处理，不吞字符', () {
    final spans = spansOf(r'只有 $一个 美元符号');
    expect(spans.whereType<WidgetSpan>(), isEmpty);
    final text = spans.whereType<TextSpan>().map((s) => s.text ?? '').join();
    expect(text, contains(r'$'));
  });

  test('多个长公式产生多个 WidgetSpan', () {
    // 注意：短公式（≤6 字符且无 \ ^ _ { }）会降级成纯文本，
    // 所以这里必须用长公式，否则测不到 WidgetSpan
    final spans = spansOf(r'$\frac{1}{2}+\frac{3}{4}$ 和 $\frac{5}{6}$');
    expect(spans.whereType<WidgetSpan>().length, 2);
  });

  test('空串返回空列表', () {
    expect(spansOf(''), isEmpty);
  });

  test('上标含 ^ 不降级', () {
    final spans = spansOf(r'$x^2$');
    expect(spans.whereType<WidgetSpan>().length, 1);
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd student-app && flutter test test/math_text_test.dart`
Expected: FAIL — 找不到 `math_text.dart`

- [ ] **Step 3: 实现**

```dart
// student-app/lib/core/widgets/math_text.dart
import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';

/// 把「中文 + `$...$` 数学式」混合文本切成 InlineSpan 列表。
///
/// 规则（实测得出，见规格 §10.1）：
/// 1. 只匹配**成对**的 `$...$`；不配对时全文按普通文本处理，绝不吞字符。
/// 2. **短公式降级**：LaTeX 源码 ≤ 6 字符且不含 `\ ^ _ { }`（如 `2.5`、`15`、`x`）
///    去掉 `$` 用普通 TextSpan 渲染，避免 WidgetSpan 整块换行把后面的
///    「（　）」拆到下一行。
/// 3. 长公式用 WidgetSpan 行内渲染，`onErrorFallback` 保证坏公式不崩。
List<InlineSpan> buildMathSpans(String text, {TextStyle? style}) {
  final src = text;
  if (src.isEmpty) return const [];
  final base = style;

  bool shouldDowngrade(String tex) {
    if (tex.length > 6) return false;
    for (final ch in [r'\', '^', '_', '{', '}']) {
      if (tex.contains(ch)) return false;
    }
    return true;
  }

  final spans = <InlineSpan>[];
  final re = RegExp(r'\$([^$]+)\$');
  var last = 0;
  for (final m in re.allMatches(src)) {
    if (m.start > last) {
      spans.add(TextSpan(text: src.substring(last, m.start), style: base));
    }
    final tex = m.group(1) ?? '';
    if (shouldDowngrade(tex)) {
      spans.add(TextSpan(text: tex, style: base));
    } else {
      spans.add(WidgetSpan(
        alignment: PlaceholderAlignment.middle,
        child: Math.tex(
          tex,
          textStyle: base,
          onErrorFallback: (e) => Text(
            tex,
            style: (base ?? const TextStyle()).copyWith(color: Colors.red),
          ),
        ),
      ));
    }
    last = m.end;
  }
  if (last < src.length) {
    spans.add(TextSpan(text: src.substring(last), style: base));
  }
  return spans;
}

/// 渲染一段可能含 `$...$` 的文本。中文与公式混排、自动换行。
class MathText extends StatelessWidget {
  const MathText(this.text, {super.key, this.style, this.maxLines});

  final String text;
  final TextStyle? style;
  final int? maxLines;

  @override
  Widget build(BuildContext context) {
    final spans = buildMathSpans(text, style: style);
    if (spans.isEmpty) return const SizedBox.shrink();
    return Text.rich(
      TextSpan(style: style, children: spans),
      maxLines: maxLines,
      overflow: maxLines == null ? TextOverflow.clip : TextOverflow.ellipsis,
    );
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd student-app && flutter test test/math_text_test.dart`
Expected: PASS（7 passed）

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/core/widgets/math_text.dart student-app/test/math_text_test.dart student-app/pubspec.yaml student-app/pubspec.lock
git commit -m "feat(student-app): 新增 math_text（\$...\$ 渲染 + 短公式降级 + 坏公式降级）"
```

---

## Task 6: Flutter 题目模型加题组字段

**Files:**
- Modify: `student-app/lib/features/bank_exercise/data/bank_models.dart`
- Test: `student-app/test/bank_models_test.dart`（新建）

- [ ] **Step 1: 写失败测试**

```dart
// student-app/test/bank_models_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/bank_exercise/data/bank_models.dart';

void main() {
  test('解析题组字段', () {
    final q = BankQuestion.fromJson({
      'id': 12,
      'qtype': 'fill_blank',
      'qtype_category': 'blank',
      'question': r'$1111.05 \div 0.9 =$ ____',
      'options': [],
      'group_id': 7,
      'group_stem': '不计算，运用规律直接写出得数',
      'seq_in_group': 4,
      'is_example': false,
      'work_mode': 'pattern',
      'input_ui': 'keypad',
      'answer_kind': 'numeric_list',
      'answer': '1234.5, 12345',
      'blank_count': 2,
    });
    expect(q.groupId, 7);
    expect(q.groupStem, '不计算，运用规律直接写出得数');
    expect(q.seqInGroup, 4);
    expect(q.isExample, isFalse);
    expect(q.workMode, 'pattern');
    expect(q.inputUi, 'keypad');
    expect(q.answerKind, 'numeric_list');
    expect(q.answer, '1234.5, 12345');
    expect(q.blankCount, 2);
  });

  test('缺字段时给安全默认值（兼容旧接口）', () {
    final q = BankQuestion.fromJson({
      'id': 1, 'qtype': 'short_answer', 'qtype_category': 'subjective',
      'question': '旧题', 'options': [],
    });
    expect(q.groupId, isNull);
    expect(q.groupStem, '');
    expect(q.seqInGroup, 0);
    expect(q.isExample, isFalse);
    expect(q.workMode, '');
    expect(q.inputUi, '');
    expect(q.answerKind, '');
    expect(q.answer, '');
    expect(q.blankCount, 1);   // 默认单空
  });

  test('示例行标记', () {
    final q = BankQuestion.fromJson({
      'id': 2, 'qtype': 'fill_blank', 'qtype_category': 'blank',
      'question': r'$1.08 \div 0.9 = 1.2$', 'options': [], 'is_example': true,
    });
    expect(q.isExample, isTrue);
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd student-app && flutter test test/bank_models_test.dart`
Expected: FAIL — `The getter 'groupId' isn't defined`

- [ ] **Step 3: 加字段**

`bank_models.dart` 的 `BankQuestion`：

构造参数加：

```dart
    this.groupId,
    this.groupStem = '',
    this.seqInGroup = 0,
    this.isExample = false,
    this.workMode = '',
    this.inputUi = '',
    this.answerKind = '',
    this.answer = '',
    this.blankCount = 1,
```

字段加：

```dart
  final int? groupId;
  final String groupStem;
  final int seqInGroup;
  final bool isExample;
  final String workMode;
  final String inputUi;
  final String answerKind;

  /// 标准答案（多空题为逗号拼接）。家长端/核对用；判分在后端。
  final String answer;

  /// 该题要填几个空（后端 `blank_count`）。多空题据此渲染多个输入框。
  final int blankCount;
```

`fromJson` 里加：

```dart
      groupId: (json['group_id'] as num?)?.toInt(),
      groupStem: '${json['group_stem'] ?? ''}',
      seqInGroup: (json['seq_in_group'] as num?)?.toInt() ?? 0,
      isExample: json['is_example'] == true,
      workMode: '${json['work_mode'] ?? ''}',
      inputUi: '${json['input_ui'] ?? ''}',
      answerKind: '${json['answer_kind'] ?? ''}',
      answer: '${json['answer'] ?? ''}',
      blankCount: (json['blank_count'] as num?)?.toInt() ?? 1,
```

- [ ] **Step 4: 运行确认通过**

Run: `cd student-app && flutter test test/bank_models_test.dart`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/bank_exercise/data/bank_models.dart student-app/test/bank_models_test.dart
git commit -m "feat(student-app): BankQuestion 加题组字段（groupId/groupStem/seqInGroup/isExample/workMode/inputUi/answerKind）"
```

---

## Task 7: Flutter 题组展示与公式渲染接入

**Files:**
- Modify: `student-app/lib/features/bank_exercise/ui/bank_exercise_page.dart`
- Modify: `student-app/lib/features/bank_exercise/question_html.dart`（`_stripDollars` 交给 `math_text`）

**现状问题**：
1. `question_html.dart` 的 `_stripDollars` 把 `$x^2$` 剥成 `x^2`（不渲染）
2. 页面把每道题平铺成一张卡片，示例行也会出现输入框

- [ ] **Step 1: 写失败测试**

```dart
// student-app/test/bank_group_view_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/bank_exercise/data/bank_models.dart';
import 'package:student_app/features/bank_exercise/question_grouping.dart';

void main() {
  test('按 group_id 分组并按 seq 排序', () {
    final qs = [
      BankQuestion.fromJson({'id': 3, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'c', 'options': [], 'group_id': 7, 'seq_in_group': 3,
        'group_stem': '直接写出得数'}),
      BankQuestion.fromJson({'id': 1, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'a', 'options': [], 'group_id': 7, 'seq_in_group': 1,
        'group_stem': '直接写出得数'}),
      BankQuestion.fromJson({'id': 5, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'x', 'options': [], 'group_id': 8, 'seq_in_group': 1,
        'group_stem': '用竖式计算'}),
    ];
    final groups = groupBankQuestions(qs);
    expect(groups.length, 2);
    expect(groups[0].items.map((q) => q.id).toList(), [1, 3]);
    expect(groups[0].stem, '直接写出得数');
    expect(groups[1].items.map((q) => q.id).toList(), [5]);
  });

  test('示例与待做分开', () {
    final qs = [
      BankQuestion.fromJson({'id': 1, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'a', 'options': [], 'group_id': 7, 'seq_in_group': 1,
        'is_example': true}),
      BankQuestion.fromJson({'id': 2, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'b', 'options': [], 'group_id': 7, 'seq_in_group': 2,
        'is_example': false}),
    ];
    final g = groupBankQuestions(qs).first;
    expect(g.examples.map((q) => q.id).toList(), [1]);
    expect(g.items.map((q) => q.id).toList(), [2]);
  });

  test('无 group_id 归到 legacy 组', () {
    final qs = [
      BankQuestion.fromJson({'id': 1, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'a', 'options': []}),
      BankQuestion.fromJson({'id': 2, 'qtype': 'f', 'qtype_category': 'blank',
        'question': 'b', 'options': []}),
    ];
    final groups = groupBankQuestions(qs);
    expect(groups.length, 1);
    expect(groups[0].isLegacy, isTrue);
    expect(groups[0].items.length, 2);
  });
}
```

> **这个测试 import 生产代码** `question_grouping.dart`（Step 3 创建），
> 不是本地复制品。若先跑测试会因文件不存在而编译失败 —— 这是预期的 TDD 红。

- [ ] **Step 2: 建 `question_grouping.dart`（让测试能编译）**

见 Step 3。先建文件再回跑测试。

- [ ] **Step 3: 建 `question_grouping.dart`**

```dart
// student-app/lib/features/bank_exercise/question_grouping.dart
import 'data/bank_models.dart';

/// 一个题组：题干 + 示例行 + 待做小题。
class QuestionGroup {
  QuestionGroup({
    required this.groupId,
    required this.stem,
    required this.examples,
    required this.items,
  });

  final int? groupId;
  final String stem;
  final List<BankQuestion> examples;
  final List<BankQuestion> items;

  /// 没有任何题干也没有示例的历史题，按平铺处理。
  bool get isLegacy => groupId == null && stem.isEmpty;
}

/// 把扁平题目按 group_id 聚组；示例与待做分开，组内按 seq_in_group 排序。
List<QuestionGroup> groupBankQuestions(List<BankQuestion> list) {
  final map = <String, List<BankQuestion>>{};
  for (final q in list) {
    final key = q.groupId?.toString() ?? 'legacy';
    map.putIfAbsent(key, () => []).add(q);
  }
  final out = <QuestionGroup>[];
  for (final entry in map.entries) {
    final all = entry.value
      ..sort((a, b) => a.seqInGroup.compareTo(b.seqInGroup));
    final first = all.first;
    out.add(QuestionGroup(
      groupId: first.groupId,
      stem: first.groupStem,
      examples: all.where((q) => q.isExample).toList(),
      items: all.where((q) => !q.isExample).toList(),
    ));
  }
  return out;
}
```

- [ ] **Step 4: 改 `question_html.dart` 用 `math_text`**

把 `_stripDollars` 的调用改为不剥（保留 `$`），并在渲染时交给 `buildMathSpans`。

具体：
1. 顶部加 `import '../../core/widgets/math_text.dart';`
2. `_emitText` 里 `_stripDollars(decodeHtmlEntities(buf))` → `decodeHtmlEntities(buf)`（不再剥）
3. `QuestionHtmlView` 的 `isCompact` 分支：`TextSpan(text: plain)` → 若 `plain` 含 `$` 则用
   `Text.rich(TextSpan(children: buildMathSpans(plain, style: base)))`
4. 分块渲染的 `spans`：text token 若含 `$`，展开成 `buildMathSpans(t.text, style: blockStyle)`
5. **删掉已经没人用的 `_stripDollars` 函数和 `_dollarRe` 正则**（否则
   `flutter analyze` 报 `unused_element`）：
   ```dart
   final _dollarRe = RegExp(r'\$([^$]+)\$');      // 删
   String _stripDollars(String s) => ...;         // 删
   ```

- [ ] **Step 5: 同步更新 `question_html_test.dart` 的两处断言**

`student-app/test/features/bank_exercise/question_html_test.dart` 硬编码了「剥 \$」的旧行为：

```dart
// 第 12 行
expect(tokens[0].text, '在数线上标出908000');
// 第 23 行
expect(tokens[2].text, '三角形面积为1');
```

改成保留 `$`（tokenizer 不再剥，渲染时才交给 LaTeX）：

```dart
// 第 12 行
expect(tokens[0].text, r'在数线上标出$908000$');
// 第 23 行
expect(tokens[2].text, r'三角形面积为$1$');
```

> 如果不想让 tokenizer 保留 `$`（担心影响别的调用方），另一条路是**保留
> `_stripDollars` 但对含 `$` 的文本打标记**。但那会引入第二套状态，不如直接
> 保留 `$`、渲染层统一处理。**按上面改测试**。

- [ ] **Step 6: 改 `bank_exercise_page.dart` 按题组渲染（**必须保留阅读材料逻辑**）**

⚠️ 现有的 `_buildQuestionBlocks` 里有一段**阅读材料**渲染（`pid`/`shown`，
遇到新的 `passageId` 就插一张 `SectionCard` + `PassageContentView`）。
重写时**不能丢**，否则 `bank_exercise_test.dart` 的
「阅读理解先展示材料再展示子题」会失败（断言 `小蝌蚪找妈妈` / `游游游`）。

完整替换为（注意保留了 passage 分支）：

```dart
  List<Widget> _buildQuestionBlocks({
    required List<BankQuestion> questions,
    required bool submitted,
    required Map<int, BankAnswerResult> resultByQid,
    required Map<int, int?> selectedSingle,
    required Map<int, List<int>> selectedMulti,
    required Map<int, List<String>> blanks,
    required Map<int, String> texts,
    required BankExerciseController ctl,
  }) {
    final widgets = <Widget>[];
    var index = 0;

    // 阅读材料：按 passageId 变化插入一张材料卡（保留原有行为）
    final shown = <int>{};
    void maybePassage(BankQuestion q) {
      final pid = q.passageId;
      if (pid == null || shown.contains(pid)) return;
      shown.add(pid);
      final p = q.passage;
      if (p == null || p.content.isEmpty) return;
      widgets.add(SectionCard(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('阅读材料',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700,
                                 color: AppColors.gray)),
            const SizedBox(height: 8),
            PassageContentView(title: p.title, content: p.content),
          ],
        ),
      ));
      widgets.add(const SizedBox(height: 12));
    }

    for (final g in groupBankQuestions(questions)) {
      if (!g.isLegacy && g.stem.isNotEmpty) {
        widgets.add(Padding(
          padding: const EdgeInsets.only(top: 6, bottom: 8),
          child: MathText(g.stem,
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
        ));
      }
      if (g.examples.isNotEmpty) {
        widgets.add(SectionCard(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('已印好的示例（不用做）',
                  style: TextStyle(fontSize: 11, color: AppColors.gray)),
              const SizedBox(height: 6),
              for (final e in g.examples)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: MathText(e.question,
                      style: const TextStyle(fontSize: 14, height: 1.7)),
                ),
            ],
          ),
        ));
        widgets.add(const SizedBox(height: 12));
      }
      for (final q in g.items) {
        maybePassage(q);
        widgets.add(_QuestionCard(
          index: index++,
          question: q,
          submitted: submitted,
          result: resultByQid[q.id],
          selectedSingle: selectedSingle[q.id],
          selectedMulti: selectedMulti[q.id] ?? const [],
          blankValues: blanks[q.id] ?? const [],
          textAnswer: texts[q.id] ?? '',
          onSingle: submitted ? null : (v) => ctl.setSingle(q.id, v),
          onMulti: submitted ? null : (v, on) => ctl.toggleMulti(q.id, v, on),
          onBlank: submitted ? null : (i, v) => ctl.setBlank(q.id, i, v),
          onText: submitted ? null : (v) => ctl.setText(q.id, v),
        ));
        widgets.add(const SizedBox(height: 12));
      }
    }
    return widgets;
  }
```

`_QuestionCard` 的签名同步改（**这一步不能漏**，否则编译不过）：

```dart
class _QuestionCard extends StatelessWidget {
  const _QuestionCard({
    required this.index,
    required this.question,
    required this.submitted,
    required this.result,
    required this.selectedSingle,
    required this.selectedMulti,
    required this.blankValues,
    required this.textAnswer,
    required this.onSingle,
    required this.onMulti,
    required this.onBlank,
    required this.onText,
  });

  final int index;
  final BankQuestion question;
  final bool submitted;
  final BankAnswerResult? result;
  final int? selectedSingle;
  final List<int> selectedMulti;

  /// 逐空作答值（多空题时长度 = question.blankCount）
  final List<String> blankValues;

  final String textAnswer;
  final ValueChanged<int>? onSingle;
  final void Function(int value, bool on)? onMulti;

  /// (空下标, 值)
  final void Function(int index, String value)? onBlank;

  final ValueChanged<String>? onText;
  // ... build() 见 Task 8
}
```

> 原来的 `blankText`（单个 String）被 `blankValues`（List）取代，
> 原来的 `onBlank`（`ValueChanged<String>`）类型变为 `void Function(int, String)`。
> 单空路径在 Task 8 里处理。

**⚠️ 本步骤必须同时改 `build()` 里那一处调用**，否则类型不匹配编译不过
（`void Function(int,String)?` 赋给 `ValueChanged<String>?`）：

```dart
// build() 里 blank 分支的 TextField（最小改动，完整版见 Task 8）
input = TextField(
  key: ValueKey('bank-blank-${question.id}'),
  decoration: const InputDecoration(
      hintText: '填写答案…', border: OutlineInputBorder(), isDense: true),
  onChanged: onBlank == null ? null : (v) => onBlank!(0, v),
  enabled: onBlank != null,
);
```

同时补上 **import**（`bank_exercise_page.dart` 顶部）：

```dart
import '../../../core/widgets/math_text.dart';
import '../question_grouping.dart';
```

- [ ] **Step 7: 删掉不再用的 `_firstBlank`**

`_BankExercisePageState._firstBlank` 已无人调用，删除。

- [ ] **Step 8: 运行测试**

Run: `cd student-app && flutter test test/bank_group_view_test.dart test/math_text_test.dart test/bank_models_test.dart`
Expected: PASS

- [ ] **Step 9: 全量 analyze + test**

Run: `cd student-app && flutter analyze && flutter test`
Expected: 无 error；测试全过（此前 240+，含「阅读理解先展示材料」那条）

- [ ] **Step 10: 提交**

```bash
git add student-app/lib/features/bank_exercise student-app/test/
git commit -m "feat(student-app): 题组展示（题干+示例+待做）与题干公式渲染"
```

---

## Task 8: Flutter 多空题输入框与 `_QuestionCard` 完整实现

**Files:**
- Modify: `student-app/lib/features/bank_exercise/bank_exercise_controller.dart`
- Modify: `student-app/lib/features/bank_exercise/ui/bank_exercise_page.dart`（`_QuestionCard.build`）

**现状 bug（已核实）**：`_answerPayload` 对 `blank` 类题传 `blanks: state.blanks[q.id] ?? ['']`，
但页面 `onBlank` 恒传下标 0（Task 7 已改为传真实下标）。
多空题（`numeric_list`）若不按 `blankCount` 渲染多个框，永远只有一个空，
`math_grade` 的 `len(got) != len(expected_blanks)` 直接判 `False` —— **答对也是 0 分**。

- [ ] **Step 1: 写失败测试（真实契约，不测假函数）**

```dart
// student-app/test/bank_blank_count_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/bank_exercise/data/bank_models.dart';

void main() {
  test('多空题 blankCount 来自后端', () {
    final q = BankQuestion.fromJson({
      'id': 1, 'qtype': 'fill_blank', 'qtype_category': 'blank',
      'question': r'$1111.05 \div 0.9 =$ ____', 'options': [],
      'work_mode': 'pattern', 'answer_kind': 'numeric_list',
      'answer': '1234.5, 12345', 'blank_count': 2,
    });
    expect(q.blankCount, 2);
  });

  test('单空题 blankCount 为 1', () {
    final q = BankQuestion.fromJson({
      'id': 2, 'qtype': 'calculation', 'qtype_category': 'blank',
      'question': r'$8.9 + 4.5 =$', 'options': [],
      'work_mode': 'oral', 'answer_kind': 'number', 'answer': '13.4',
      'blank_count': 1,
    });
    expect(q.blankCount, 1);
  });

  test('答案本身含逗号时不靠切分推断空数', () {
    // 若用 answer.split(',') 会得到 2 个空，错误；必须信后端 blank_count
    final q = BankQuestion.fromJson({
      'id': 3, 'qtype': 'fill_blank', 'qtype_category': 'blank',
      'question': 'x', 'options': [], 'answer': '1,234', 'blank_count': 1,
    });
    expect(q.blankCount, 1);
  });
}
```

- [ ] **Step 2: 运行确认失败（或通过——若 Task 6 已加 `blankCount`）**

Run: `cd student-app && flutter test test/bank_blank_count_test.dart`
Expected: PASS（Task 6 已加字段）。本测试的作用是**锁死契约**，防止有人日后改成
`answer.split(',')` 推断。

- [ ] **Step 3: 确认 controller 的 `setBlank` 按下标写**

`bank_exercise_controller.dart` 的 `setBlank` 必须按下标写入而不是覆盖整个 list：

```dart
  void setBlank(int qid, int index, String value) {
    final cur = List<String>.from(state.blanks[qid] ?? const <String>[]);
    while (cur.length <= index) {
      cur.add('');
    }
    cur[index] = value;
    state = state.copyWith(blanks: {...state.blanks, qid: cur});
  }
```

（若现有实现已是这种形式，跳过此步。）

- [ ] **Step 4: 合并顺序说明（`symbol` 分支的插入位置）**

规格 §10 要求「比较大小待填 `○` → 三个按钮 `>` `<` `=`」。后端把这类题标为
`answer_kind=symbol`、`input_ui=chooser`，题干里保留 `○`。

⚠️ **不要单独插一段代码**：`symbol` 分支必须出现在下面 Step 6 给出的**完整
`build()`** 里（Step 6 已经包含它）。若先按某处片段插入、再整体替换 `build()`，
`symbol` 分支会被覆盖掉，验收清单里「比较大小题用按钮」就做不出来。

Step 6 的 `build()` 里，`input` 的判定顺序是：

1. `qtypeCategory == 'choice' && options.isNotEmpty` → 单选/多选
2. **`answerKind == 'symbol'` → `>` `<` `=` 三个 ChoiceChip**（Step 6 已含）
3. `qtypeCategory == 'blank'` → 按 `blankCount` 渲染 1 个或多个输入框
4. 其余 → 多行文本

> `symbol` 题按单空处理（`blankValues[0]`），提交时走 `blanks: ['>']`，
> 后端 `grade_by_answer_kind` 的 `symbol` 分支会归一化全半角再比较。

- [ ] **Step 5: `□`（竖式挖空位）本期只当普通字符展示**

`□` 只出现在竖式/脱式题里，而那些题的 `answer_kind` 是 `photo`（拍照作答）。
拍照链路不在本计划范围（见文末），所以 `□` 不需要渲染成输入框——`MathText`
会把它当普通字符显示，视觉上就是一个方框占位，符合预期。

不要为 `□` 加输入框：它会让孩子在竖式里填单格，而实际上应该拍整道竖式。

- [ ] **Step 6: 实现 `_QuestionCard.build` 的输入区**

```dart
  @override
  Widget build(BuildContext context) {
    final correct = result?.isCorrect;
    Color? border;
    if (submitted && correct == true) border = AppColors.greenSoft;
    if (submitted && correct == false) border = Colors.red.shade50;

    Widget input;
    if (question.qtypeCategory == 'choice' && question.options.isNotEmpty) {
      if (question.qtype == 'multi_choice') {
        input = Column(
          children: [
            for (final o in question.options)
              CheckboxListTile(
                dense: true,
                title: QuestionHtmlView(html: o.label),
                value: selectedMulti.contains(o.value),
                onChanged: onMulti == null ? null : (v) => onMulti!(o.value, v == true),
              ),
          ],
        );
      } else {
        input = Column(
          children: [
            for (final o in question.options)
              RadioListTile<int>(
                dense: true,
                title: QuestionHtmlView(html: o.label),
                value: o.value,
                groupValue: selectedSingle ?? 0,
                onChanged: onSingle == null ? null : (v) {
                  if (v != null) onSingle!(v);
                },
              ),
          ],
        );
      }
    } else if (question.answerKind == 'symbol') {
      // 比较大小：`>` `<` `=` 三个按钮（规格 §10）
      const choices = ['>', '<', '='];
      input = Row(
        children: [
          for (final s in choices)
            Padding(
              padding: const EdgeInsets.only(right: 10),
              child: ChoiceChip(
                label: Text(s, style: const TextStyle(fontSize: 18)),
                selected: (blankValues.isNotEmpty ? blankValues[0] : '') == s,
                onSelected: onBlank == null
                    ? null
                    : (on) {
                        if (on) onBlank!(0, s);
                      },
              ),
            ),
        ],
      );
    } else if (question.qtypeCategory == 'blank') {
      final count = question.blankCount;
      if (count <= 1) {
        input = TextField(
          key: ValueKey('bank-blank-${question.id}'),
          decoration: const InputDecoration(
              hintText: '填写答案…', border: OutlineInputBorder(), isDense: true),
          onChanged: onBlank == null ? null : (v) => onBlank!(0, v),
          enabled: onBlank != null,
        );
      } else {
        input = Column(
          children: [
            for (var i = 0; i < count; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: TextField(
                  key: ValueKey('bank-blank-${question.id}-$i'),
                  decoration: InputDecoration(
                    hintText: '第 ${i + 1} 空',
                    border: const OutlineInputBorder(),
                    isDense: true,
                  ),
                  controller: _blankController(i),
                  onChanged: onBlank == null ? null : (v) => onBlank!(i, v),
                  enabled: onBlank != null,
                ),
              ),
          ],
        );
      }
    } else {
      input = TextField(
        key: ValueKey('bank-text-${question.id}'),
        maxLines: 3,
        decoration: const InputDecoration(
            hintText: '写下你的回答…', border: OutlineInputBorder()),
        onChanged: onText,
        enabled: onText != null,
      );
    }

    return SectionCard(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          border: border != null ? Border.all(color: border.withValues(alpha: 0.6)) : null,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ⚠️ 必须继续用 QuestionHtmlView，不要换成 MathText：
            // QuestionHtmlView 负责 HTML 白名单（<br> / <img> / 分块），
            // 换成 MathText 会让学库宝导入的题把 <br> 当字面文本显示
            // （bank_exercise_test.dart 的 `expect(find.textContaining('<br'), findsNothing)` 会挂）。
            // Task 7 Step 4 已经把 buildMathSpans 接进 QuestionHtmlView 内部了。
            QuestionHtmlView(
              html: question.question,
              prefix: '${index + 1}. ',
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 15,
                height: 1.75,
                letterSpacing: 0.15,
                color: Color(0xFF202723),
              ),
            ),
            const SizedBox(height: 14),
            input,
            if (submitted && result != null) ...[
              const SizedBox(height: 8),
              Text(
                correct == null
                    ? '待批改'
                    : (correct
                        ? '回答正确'
                        : '回答不对${result!.correctAnswerText.isNotEmpty ? ' · 参考：${result!.correctAnswerText}' : ''}'),
                style: TextStyle(
                  fontSize: 13,
                  color: correct == true
                      ? AppColors.green
                      : (correct == false ? Colors.red : AppColors.gray),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// 多空题的输入框需要各自持有 controller，避免受控值互相覆盖。
  TextEditingController _blankController(int i) {
    return _controllers.putIfAbsent(i, () => TextEditingController(
      text: i < blankValues.length ? blankValues[i] : '',
    ));
  }
```

`_QuestionCard` 需要改成 `StatefulWidget` 才能持有 `_controllers`：

```dart
class _QuestionCard extends StatefulWidget {
  const _QuestionCard({ /* ...同 Task 7 的构造参数... */ });

  final int index;
  // ... 其余 final 字段同 Task 7 ...

  @override
  State<_QuestionCard> createState() => _QuestionCardState();
}

class _QuestionCardState extends State<_QuestionCard> {
  final _controllers = <int, TextEditingController>{};

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final question = widget.question;
    final submitted = widget.submitted;
    final result = widget.result;
    // ... 用 widget.xxx 替换原来的同名引用 ...
  }
}
```

> **简化选项**：若不想改 StatefulWidget，多空框可以**不用 controller**
> （只靠 `onChanged` 收集），只是提交后无法回填已答内容。本期可接受。
> 选哪个由实施者定，但**必须能编译通过**。

- [ ] **Step 7: 让 `_answerPayload` 把 `blanks` 补齐到 `blankCount`**

`bank_exercise_controller.dart` 的 `_answerPayload` 现在直接送 `state.blanks[q.id] ?? ['']`。
若孩子只碰了第 2 空，`blanks` 可能是 `['', 'x']`（对）；但若一个都没碰就是 `['']`
（长度 1 ≠ 2），判分直接 `False`。

补齐/裁剪到 `q.blankCount`：

```dart
  Map<String, dynamic> _answerPayload(BankQuestion q) {
    if (q.qtypeCategory == 'choice') {
      if (q.qtype == 'multi_choice') {
        return {'question_id': q.id, 'selected_index': state.selectedMulti[q.id] ?? []};
      }
      return {'question_id': q.id, 'selected_index': state.selectedSingle[q.id] ?? 0};
    }
    if (q.qtypeCategory == 'blank') {
      final n = q.blankCount < 1 ? 1 : q.blankCount;
      final cur = List<String>.from(state.blanks[q.id] ?? const <String>[]);
      // 补齐到空数（不足补空串，多余截掉），保证与后端期望的空数一致
      while (cur.length < n) {
        cur.add('');
      }
      return {'question_id': q.id, 'blanks': cur.take(n).toList()};
    }
    return {'question_id': q.id, 'text': state.texts[q.id] ?? ''};
  }
```

- [ ] **Step 8: 运行测试**

Run: `cd student-app && flutter analyze && flutter test`
Expected: 无 error；测试全过

- [ ] **Step 9: 手工验证（关键）**

1. `cd backend && python -m uvicorn app.main:app --port 8010`
2. `cd student-app && flutter run -d chrome`
3. 进一个练习册的题库练习
4. 逐项确认：
   - [ ] 找规律题出现**多个**输入框（`blankCount` 是几就几个）
   - [ ] 示例行只展示，**不出现输入框**
   - [ ] 题干公式渲染成数学符号（不是 `\frac` 源码）
   - [ ] 全部答对 → 得分是满分（而不是 0）

- [ ] **Step 10: 提交**

```bash
git add student-app/lib/features/bank_exercise student-app/test/
git commit -m "feat(student-app): 多空题按 blankCount 渲染输入框并正确提交 blanks"
```

---

## Task 9: 暂不让 `photo` 类题进练习（避免「答了没反馈」）

**Files:**
- Modify: `backend/app/services/task_gen.py`（`_pick_practice_questions`）
- Test: append to `backend/tests/test_practice_groups.py`

**为什么**：`vertical`/`step`/`fill_vertical`/`app`/`geometry` 的 `answer_kind` 是 `photo`，
判分要求「上传作答照片」。但拍照链路（`/api/practice/answer-photo` + 前端拍照组件 +
`PracticeAttempt` 写入）不在本计划范围内。若把它们抽进每日一练，孩子会在文本框里写答案，
提交后后端走 `photo` 分支返回「未上传作答照片」→ `is_correct=None` → **答了没有任何反馈**。

这比「不出这些题」更糟，所以本期先在**每日一练抽题**里排除它们。
题库练习页仍会显示（家长/孩子可以看），只是不会自动布置。

> **替代方案 B**（若你不接受）：让 `photo` 类题用普通输入框、提交时按 `number` 判分，
> 只比最终答案不看过程。代价是「脱式必须看过程」的教学目标落空。
> **默认按 A 实现**；若你要 B，告诉我，我改这一节。

- [ ] **Step 1: 写失败测试**

Append to `backend/tests/test_practice_groups.py`:

```python
def test_pick_practice_questions_excludes_photo_kinds(setup_db, db):
    """拍照类题（vertical/step/app/geometry）本期不布置：没有拍照链路，
    抽到只会让孩子「答了没反馈」。"""
    from datetime import date

    from app.models import Question, QuestionBank
    from app.services.task_gen import _pick_practice_questions
    from conftest import make_account

    child = make_account(db, "tk_photo", role="child")
    bank = QuestionBank(user_id=child.id, title="册", subject="数学", grade=5,
                        source="practice_pdf")
    db.add(bank)
    db.flush()
    # 口算（number，该抽）
    db.add(Question(bank_id=bank.id, user_id=child.id, qtype="oral",
                    qtype_category="subjective", question="口算题", answer="2",
                    status="published", lesson_no=1, is_example=False,
                    work_mode="oral"))
    # 竖式（photo，本期不抽）
    db.add(Question(bank_id=bank.id, user_id=child.id, qtype="calculation",
                    qtype_category="blank", question="竖式题", answer="364",
                    status="published", lesson_no=1, is_example=False,
                    work_mode="vertical"))
    # 应用题（photo，本期不抽）
    db.add(Question(bank_id=bank.id, user_id=child.id, qtype="application",
                    qtype_category="subjective", question="应用题", answer="12",
                    status="published", lesson_no=1, is_example=False,
                    work_mode="app"))
    db.commit()

    picked, _lesson_no, _title = _pick_practice_questions(
        db, bank, child.id, date(2026, 11, 22), 10)
    assert [q.question for q in picked] == ["口算题"], \
        f"photo 类题不该被抽中，实际抽到 {[q.question for q in picked]}"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k excludes_photo -v`
Expected: FAIL — 抽到了 3 道题

- [ ] **Step 3: 实现**

`task_gen.py` 的 `_pick_practice_questions` 里，`base` 查询之后加一层过滤
（不能写进 SQL，因为 `answer_kind` 是从 `work_mode` 查表得来的，不是数据库列）：

```python
    from ..core.work_modes import answer_kind_of

    all_q = [q for q in base.all()
             if answer_kind_of(q.work_mode) != "photo"]
```

把原来那句 `all_q = base.all()` 替换成上面两行。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_practice_groups.py -k excludes_photo -v`
Expected: PASS

- [ ] **Step 5: 回归**

Run: `cd backend && python -m pytest -q -k "task_gen or daily"`
Expected: ALL PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/task_gen.py backend/tests/test_practice_groups.py
git commit -m "feat(practice): 每日一练暂不抽 photo 类题（拍照链路未实现，避免答了没反馈）"
```

---

## 完成标准（计划二验收清单）

- [ ] 家长端：题干里的 `\frac{3}{4}` 渲染成数学符号，不是源码
- [ ] 家长端：题目按题组分组，示例行标着「孩子不用做」
- [ ] 家长端：页类型可见可改，改完能重导
- [ ] 家长端：竖式题的多行排版不被压成一行
- [ ] 家长端：离线 / 无 KaTeX 时不崩（降级为等宽原文），弹窗内也降级
- [ ] Flutter：题干公式渲染正确，短公式不拆行
- [ ] Flutter：题组按「题干 + 示例 + 待做」展示
- [ ] Flutter：阅读材料（`passageId`）仍正常显示（回归 `bank_exercise_test.dart`）
- [ ] Flutter：多空题有多个输入框，提交的 `blanks` 数量 = `blankCount`
- [ ] Flutter：比较大小题（`answer_kind=symbol`）用 `>`/`<`/`=` 按钮
- [ ] Flutter：全部答对 → 得分满分（修复「答对判错」）
- [ ] 后端：**两个**题目端点（`practice-import/questions` 与 `banks/{id}/questions`）都返回 `blank_count`
- [ ] 每日一练不再抽到 `photo` 类题（避免答了没反馈）
- [ ] `flutter analyze` 无 error；`flutter test` 全过
- [ ] `node parent-web/test_math.js && node parent-web/test_group.js` 全过

## 明确不在本计划范围

| 项 | 原因 |
|---|---|
| **拍照作答**（`photo` 类题的 camera 入口） | 需要 `PracticeAttempt` 写入 + 图片上传 + 视觉判分链路，单独一个计划。本期 `photo` 类题（竖式/脱式/应用题/图形题）会在题库练习里显示为普通输入框，提交后返回「未上传作答照片」的待批改状态——**能看到题、能输入，但拿不到自动判分** |
| **`□` 竖式挖空位渲染成输入框** | 只出现在 `photo` 类题里，等拍照链路落地后一起做 |
| **每日一练独立页面** | 目前复用题库练习页，题组结构已够用 |
| **题组跨页去重** | 见 Task 3 Step 8 的已知限制说明 |
| 语文/英语解析器 | 后端注册表已留位 |

> **`photo` 类题的处理**：见 Task 9 —— 本期在每日一练里排除，避免「答了没反馈」。
> 拍照链路（`/api/practice/answer-photo` + `PracticeAttempt` + 拍照组件）单独一个计划。
