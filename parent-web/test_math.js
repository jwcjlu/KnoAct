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

// 6) 公式里的 < > & 不能被二次转义
//    （入参已 escapeHtml，再套 escapeAttr 会让 &lt; 变成 &amp;lt;，
//      浏览器单次解码后 KaTeX 收到字面量 "a&lt;b" 而解析失败）
const out5 = markMath(escapeHtml('$a<b$ 和 $3.6>3.06$'));
assert.ok(!out5.includes('&amp;lt;'), '不应出现 &amp;lt;（二次转义）: ' + out5);
assert.ok(!out5.includes('&amp;gt;'), '不应出现 &amp;gt;（二次转义）: ' + out5);
assert.ok(out5.includes('a&lt;b'), '应得到单次转义的 a&lt;b: ' + out5);

// 7) 双引号仍需挡住，防止属性截断
const out6 = markMath(escapeHtml('$"x"$'));
assert.ok(!out6.includes('data-tex=""x""'), '双引号会截断属性: ' + out6);

console.log('OK  parent-web/test_math.js  全部通过');
