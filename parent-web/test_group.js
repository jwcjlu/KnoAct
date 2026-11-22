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
