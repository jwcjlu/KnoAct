// ===== 知学伴 · 家长端 =====
// 后端地址：config.js 可设置 window.KNOACT_API_BASE 覆盖（docker 部署设为 '' 走 nginx 同源反代）
const API = window.KNOACT_API_BASE ?? 'http://127.0.0.1:8010';


// ===== 图标 =====
const ICONS = {
  home:'<path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10M9 20v-6h6v6"/>',
  brain:'<path d="M9.5 4.5A3 3 0 0 0 4.8 8a3.2 3.2 0 0 0-.3 6 3 3 0 0 0 5 3.5ZM14.5 4.5A3 3 0 0 1 19.2 8a3.2 3.2 0 0 1 .3 6 3 3 0 0 1-5 3.5Z"/><path d="M9.5 4.5v15M14.5 4.5v15M7 10h2.5M14.5 14H17"/>',
  book:'<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H11v18H6.5A2.5 2.5 0 0 0 4 22Z"/><path d="M20 4.5A2.5 2.5 0 0 0 17.5 2H13v18h4.5A2.5 2.5 0 0 1 20 22Z"/>',
  pen:'<path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10Z"/><path d="m14 7 3 3"/>',
  chart:'<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  gift:'<path d="M3 9h18v4H3zM5 13v8h14v-8M12 9v12"/><path d="M12 9H8.5A2.5 2.5 0 1 1 11 6.5ZM12 9h3.5A2.5 2.5 0 1 0 13 6.5Z"/>',
  star:'<path d="m12 2.5 2.9 5.9 6.5.9-4.7 4.6 1.1 6.5-5.8-3-5.8 3 1.1-6.5-4.7-4.6 6.5-.9Z"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  text:'<path d="M4 6h16M4 12h10M4 18h7"/>',
  arrow:'<path d="M5 12h14M14 7l5 5-5 5"/>',
  'arrow-left':'<path d="M19 12H5M10 7l-5 5 5 5"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  sparkles:'<path d="m12 3 1.3 3.7L17 8l-3.7 1.3L12 13l-1.3-3.7L7 8l3.7-1.3ZM5 15l.8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8ZM19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8Z"/>',
  tablet:'<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M11 18h2"/>',
  phone:'<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
  flame:'<path d="M12 22c4 0 7-2.7 7-6.5 0-2.6-1.4-4.8-3.8-7.5-.2 2-1.3 3.1-2.4 3.7.3-3.7-1.7-7-5-9.7.2 4-2.8 6.4-2.8 10.4C5 18 8 22 12 22Z"/>',
  headphones:'<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><path d="M4 14h3v6H5a1 1 0 0 1-1-1ZM20 14h-3v6h2a1 1 0 0 0 1-1Z"/>',
  play:'<circle cx="12" cy="12" r="9"/><path d="m10 8 6 4-6 4Z"/>',
  search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  menu:'<circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>',
  'panel-left':'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
  'panel-right':'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
  expand:'<path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3"/>',
  volume:'<path d="M11 5 6 9H2v6h4l5 4Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
  list:'<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  chat:'<path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8Z"/><path d="M9 11h.01M12 11h.01M15 11h.01"/>',
  highlighter:'<path d="M9 3 4 8l3 3-1 1a2 2 0 0 0 0 2.8l3.2 3.2a2 2 0 0 0 2.8 0l1-1 3 3L21 15l-3-3 1-1a2 2 0 0 0 0-2.8L15.8 5a2 2 0 0 0-2.8 0l-1-1Z"/>',
  underline:'<path d="M6 4v6a6 6 0 0 0 12 0V4"/><path d="M4 20h16"/>',
  note:'<path d="M15 3h5v5"/><path d="M20 8 9 19l-4 1 1-4L17 5Z"/><path d="M7 14l3 3"/>',
  camera:'<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3Z"/><circle cx="12" cy="13" r="3"/>'
};
function icon(name, size=18){
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]||''}</svg>`;
}

// ===== 通用状态 =====
const PARENT_TABS = [
  ['教材','book'],['知识点','brain'],['题目审核台','list'],['目标','star'],['报告','chart'],
  ['任务','pen'],['规则','gift'],['学习配置','grid'],['设置','menu']
];
const CHILD_TABS = ['目标','报告','任务'];   // 依赖当前孩子（uid）的 Tab
const CHILD_KEY = 'knoact_parent_child_id';
const PARENT_KEY = 'knoact_parent_id';
let parentId = null;       // 当前登录家长 id（localStorage 持久化）
let parentName = '';
let uid = null;            // 当前孩子 id，由孩子列表决定；确定前不发依赖孩子的请求
let children = [];         // [{id, name, role, grade, edition}]
let buckets = [];          // [{id, grade, school_year, status}] 当前孩子的学年桶
let bucketId = null;       // 当前选中桶（默认 active 桶）
let childSwitching = false;
let parentTab = '教材';

// 家长端数据缓存
let pdfDocs = [];
let pdfTab = null; // null | 'upload' | 'confirm'
let confirmDocId = null;
let knowledgeRows = [];
let goalRows = [];
let reportRows = [];
let masteryReport = null;
async function loadMasteryReport(){
  if(!uid){ masteryReport = null; return null; }
  const u = uid, b = bucketId;
  const q = b ? `&bucket_id=${b}` : '';
  const report = await api(`/api/mastery/report?user_id=${u}${q}`);
  if(u === uid) masteryReport = report;
  return masteryReport;
}
let configMap = {};
let aiConfig = {provider:'deepseek', model:'deepseek-chat', key:'', baseUrl:''};
let aiModelOptions = [];  // 中转站拉取到的动态模型列表
let ttsModelOptions = []; // 中转站拉取到的动态语音模型列表
let ttsConfig = {provider:'minimax', voice:'清澈男声', key:'', baseUrl:'', model:'speech-2.8-hd', speed:1.0, repeat:2};

// 家长端任务审核
let parentTaskDate = '';   // 家长端任务查看的日期（默认今天）
let parentTasks = [];      // 当天全部任务（含待审核）

const aiProviders = [
  {id:'deepseek',name:'DeepSeek',models:['deepseek-chat','deepseek-reasoner'],needsBaseUrl:false},
  {id:'glm',name:'GLM（智谱）',models:['glm-4-plus','glm-4-flash'],needsBaseUrl:false},
  {id:'openai',name:'中转站 / OpenAI 兼容',models:['gpt-4o','gpt-4o-mini','deepseek-chat','claude-sonnet-4-5'],needsBaseUrl:true}
];
const ttsProviders = [
  {id:'minimax',name:'MiniMax',voices:['清澈男声','温柔女声','标准童声'],needsBaseUrl:false},
  {id:'xunfei',name:'科大讯飞',voices:['讯飞女声','讯飞男声','标准普通话'],needsBaseUrl:false},
  {id:'openai',name:'中转站 / OpenAI 兼容',voices:['alloy','echo','fable','onyx','nova','shimmer'],needsBaseUrl:true}
];

function toast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg; t.style.display='block';
  clearTimeout(t._timer);
  t._timer = setTimeout(()=>t.style.display='none',2400);
}

async function api(path, opts={}){
  const init = {headers:{'Content-Type':'application/json'}, ...opts};
  if(opts.body) init.body = JSON.stringify(opts.body);
  const r = await fetch(API + path, init);
  const ct = r.headers.get('content-type')||'';
  return ct.includes('json') ? r.json() : r.text();
}
const sleep = ms => new Promise(res=>setTimeout(res,ms));
async function apiForm(path, formData){
  const r = await fetch(API + path, {method:'POST', body:formData});
  const ct = r.headers.get('content-type')||'';
  return ct.includes('json') ? r.json() : r.text();
}

function escapeAttr(s){
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,'&#39;');
}

function browserSpeak(text){
  if(window.speechSynthesis){
    const u = new SpeechSynthesisUtterance(text);
    u.lang = /[a-zA-Z]/.test(text)?'en-US':'zh-CN'; u.rate = 0.9;
    speechSynthesis.cancel(); speechSynthesis.speak(u);
  }
}

// ===== 渲染入口 =====
function renderNav(){
  document.getElementById('nav').innerHTML = PARENT_TABS.map(([label,ic])=>
    `<button class="nav-item ${parentTab===label?'active':''}" onclick="setParentTab('${label}')">${icon(ic,19)}${label}</button>`
  ).join('');
}
function render(){
  document.getElementById('main').innerHTML = renderParent();
}

// ===== 家长端 =====
// ---- 当前孩子 ----
async function loadChildren(){
  const q = parentId ? `&parent_id=${parentId}` : '';
  const list = await api(`/api/users?role=child${q}`);
  if(!Array.isArray(list)) throw new Error('孩子列表接口返回异常');
  children = list;
  let saved = null;
  try{ saved = Number(localStorage.getItem(CHILD_KEY)); }catch(e){}
  const hit = children.find(c => c.id === saved);
  uid = hit ? hit.id : (children[0] ? children[0].id : null);
  await loadBuckets();
}
async function loadBuckets(){
  if(!uid){ buckets = []; bucketId = null; return; }
  const u = uid;
  const list = await api(`/api/buckets?user_id=${u}`);
  if(u !== uid) return;
  buckets = Array.isArray(list) ? list : [];
  const active = buckets.find(b => b.status === 'active');
  bucketId = active ? active.id : (buckets[0] ? buckets[0].id : null);
}
async function reloadChildData(){
  if(parentTab==='目标') await loadGoals();
  else if(parentTab==='报告') await Promise.all([loadReport(), loadMasteryReport()]);
  else if(parentTab==='任务') await loadParentTasks();
}
// 切换期间禁用下拉框，避免快速连续切换时旧请求覆盖新数据
async function switchChild(id){
  if(childSwitching) return;
  uid = Number(id) || null;
  try{ localStorage.setItem(CHILD_KEY, String(uid)); }catch(e){}
  goalRows = []; reportRows = []; masteryReport = null; parentTasks = [];
  buckets = []; bucketId = null;
  await loadBuckets();
  // 非孩子 Tab 只刷新下拉框，避免整页重绘冲掉未保存的输入
  childSwitching = true; CHILD_TABS.includes(parentTab) ? render() : renderChildSelect();
  try{ await reloadChildData(); }
  catch(e){ toast('加载孩子数据失败，请稍后重试'); }
  finally { childSwitching = false; CHILD_TABS.includes(parentTab) ? render() : renderChildSelect(); }
}
function renderChildSelect(){
  const host = document.getElementById('child-select-host');
  if(host) host.innerHTML = childSelectHtml();
}
function childSelectHtml(){
  if(!children.length){
    return `<span class="child-empty">暂无孩子</span>
      <button class="btn-ghost" style="padding:6px 12px" onclick="showAddChild()" title="新建孩子档案">${icon('check',14)} 新建孩子</button>`;
  }
  const bucketOpts = buckets.map(b=>
    `<option value="${b.id}" ${b.id===bucketId?'selected':''}>${escapeAttr(b.school_year)} · ${escapeAttr(b.grade)}年级${b.status==='active'?'（当前）':''}</option>`
  ).join('');
  const bucketSel = buckets.length > 1
    ? `<select onchange="switchBucket(this.value)" ${childSwitching?'disabled':''} title="查看不同学年数据">${bucketOpts}</select>`
    : (buckets.length === 1 ? `<span class="child-bucket-tag">${escapeAttr(buckets[0].school_year)}</span>` : '');
  return `<label class="child-select">当前孩子
    <select onchange="switchChild(this.value)" ${childSwitching?'disabled':''}>
      ${children.map(c=>`<option value="${c.id}" ${c.id===uid?'selected':''}>${escapeAttr(c.name)}</option>`).join('')}
    </select>
  </label>
  ${bucketSel?`<label class="child-select">学年 ${bucketSel}</label>`:''}
  <button class="btn-ghost" style="padding:6px 12px" onclick="promoteChild()" title="将当前孩子升到下一学年">${icon('arrow',14)} 升年级</button>
  <button class="btn-ghost" style="padding:6px 12px" onclick="showAddChild()" title="新建孩子档案">${icon('check',14)} 新建孩子</button>`;
}
function switchBucket(id){
  bucketId = Number(id) || null;
  goalRows = []; reportRows = []; masteryReport = null; parentTasks = [];
  reloadChildData().catch(()=>toast('加载孩子数据失败，请稍后重试'));
  if(CHILD_TABS.includes(parentTab)) render(); else renderChildSelect();
}
async function promoteChild(){
  if(!uid) return;
  if(!confirm('将当前孩子升到下一学年（旧学年数据会保留在历史桶中）。确定吗？')) return;
  await api(`/api/children/${uid}/promote`, {method:'POST'});
  toast('已升年级');
  await loadChildren();
  render();
}
function showAddChild(){
  if(!parentId){ toast('请先登录家长账号'); return; }
  const name = prompt('孩子姓名');
  if(!name || !name.trim()) return;
  const grade = prompt('年级（1-6）', '1');
  if(!grade || isNaN(Number(grade))) return;
  const edition = prompt('教材版本（如 人教/苏教，可留空）', '') || '';
  addChild(name.trim(), Number(grade), edition);
}
async function addChild(name, grade, edition){
  await api('/api/children', {method:'POST', body:{parent_id: parentId, name, grade, edition}});
  toast('孩子已创建');
  await loadChildren();
  render();
}
function setParentTab(t){
  parentTab=t;
  renderNav();
  if(t==='教材'){ loadPdfDocs().then(()=>render()); return; }
  if(t==='知识点'){ loadKnowledge().then(()=>render()); return; }
  if(t==='题目审核台'){ loadReviewQuestions().then(()=>render()); return; }
  if(t==='目标'){ loadGoals().then(()=>render()); return; }
  if(t==='报告'){ Promise.all([loadReport(), loadMasteryReport()]).then(()=>render()); return; }
  if(t==='任务'){ loadParentTasks().then(()=>render()); return; }
  if(t==='学习配置'){ loadConfig().then(()=>render()); return; }
  if(t==='设置'){ loadConfig().then(()=>render()); return; }
  render();
}
async function loadParentData(){ await loadPdfDocs(); }

async function loadPdfDocs(){
  pdfDocs = await api('/api/pdf/documents');
}
async function loadKnowledge(){
  knowledgeRows = await api('/api/knowledge');
}
async function loadGoals(){
  if(!uid){ goalRows = []; return; }
  const u = uid, b = bucketId;
  const q = b ? `&bucket_id=${b}` : '';
  const rows = await api(`/api/goals?user_id=${u}${q}`);
  if(u === uid) goalRows = rows;
}
async function loadReport(){
  if(!uid){ reportRows = []; return; }
  const u = uid, b = bucketId;
  const q = b ? `&bucket_id=${b}` : '';
  const rows = await api(`/api/mistakes/report?user_id=${u}${q}`);
  if(u === uid) reportRows = rows;
}
async function loadConfig(){
  configMap = await api('/api/config');
  aiConfig.provider = configMap.ai_provider || 'deepseek';
  aiConfig.model = configMap.ai_model || 'deepseek-chat';
  aiConfig.key = configMap.ai_key || '';
  aiConfig.baseUrl = configMap.ai_base_url || '';
  ttsConfig.provider = configMap.tts_provider || 'minimax';
  ttsConfig.voice = configMap.tts_voice || '清澈男声';
  ttsConfig.key = configMap.tts_key || '';
  ttsConfig.baseUrl = configMap.tts_base_url || '';
  ttsConfig.model = configMap.tts_model || 'speech-2.8-hd';
  ttsConfig.speed = parseFloat(configMap.tts_speed || '1.0');
  ttsConfig.repeat = parseInt(configMap.tts_repeat || '2');
}

// ---- 题目审核台 ----
const QTYPE_LABEL = {knowledge:'基础知识', listening:'听力', reading:'阅读理解', math:'数学练习'};
let reviewGroups = [];          // [{subject, lesson_id, questions:[{id, qtype, question, answer, extra, task_type}]}]
let expandedLessons = new Set(); // 展开的 lesson_id 集合

function todayStr(){
  const t = new Date();
  return `${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,'0')}-${String(t.getDate()).padStart(2,'0')}`;
}

async function loadReviewQuestions(){
  const d = await api(`/api/questions/review?d=${todayStr()}`);
  reviewGroups = (d && d.groups) || [];
}

async function approveQuestion(id){
  await api(`/api/questions/${id}/approve`, {method:'POST'});
  await loadReviewQuestions(); render();
}
async function rejectQuestion(id){
  await api(`/api/questions/${id}/reject`, {method:'POST'});
  await loadReviewQuestions(); render();
}
async function approveByLesson(lessonId){
  await api(`/api/questions/approve-by-lesson?lesson_id=${lessonId}&d=${todayStr()}`, {method:'POST'});
  await loadReviewQuestions(); render();
}
async function approveBySubject(subject){
  await api(`/api/questions/approve-by-subject?subject=${encodeURIComponent(subject)}&d=${todayStr()}`, {method:'POST'});
  await loadReviewQuestions(); render();
}
async function approveAllQuestions(){
  if(!confirm('将全部通过今日所有待审核题目，确定吗？')) return;
  for(const g of reviewGroups){
    await api(`/api/questions/approve-by-subject?subject=${encodeURIComponent(g.subject)}&d=${todayStr()}`, {method:'POST'});
  }
  await loadReviewQuestions(); render();
}
function toggleLesson(id){
  const key = String(id);  // 统一转字符串，与渲染时 expandedLessons.has(g.lesson_id) 的 g.lesson_id 数字需一致
  if(expandedLessons.has(key)) expandedLessons.delete(key);
  else expandedLessons.add(key);
  render();
}

function formatQuestionExtra(extra){
  // 把 extra（JSON 字符串）解析成友好的结构化展示：对话/知识点原文/关键词
  if(extra==null || extra==='') return '';
  let obj = null;
  try { obj = JSON.parse(extra); } catch(e){ obj = null; }
  if(!obj || typeof obj !== 'object') return `<div style="font-size:12px;color:#778079;margin-top:2px">${extra}</div>`;
  const parts = [];
  if(obj.dialogue){
    parts.push(`<div style="font-size:12px;color:#5c6761;margin-top:4px"><b>对话：</b>${escapeAttr(obj.dialogue)}</div>`);
  }
  if(obj.content){
    parts.push(`<div style="font-size:12px;color:#5c6761;margin-top:4px"><b>原文：</b>${escapeAttr(obj.content)}</div>`);
  }
  if(obj.keywords && Array.isArray(obj.keywords) && obj.keywords.length){
    parts.push(`<div style="font-size:12px;color:#778079;margin-top:4px"><b>关键词：</b>${obj.keywords.map(k=>escapeAttr(k)).join('、')}</div>`);
  }
  return parts.length ? parts.join('') : `<div style="font-size:12px;color:#778079;margin-top:2px">${escapeAttr(extra)}</div>`;
}

function renderQuestionTab(){
  const total = reviewGroups.reduce((n,g)=>n+(g.questions?g.questions.length:0),0);

  const head = `<div class="parent-panel" style="grid-column:1/-1">
    <div class="head">
      <div class="ic blue">${icon('book',20)}</div>
      <div><h3>题目审核台</h3><div class="sub">${todayStr()} · 按学科/课程审核每日生成的题目</div></div>
      <div style="margin-left:auto;display:flex;gap:6px">
        ${total>0?`<button class="btn-ghost" onclick="approveAllQuestions()">全部通过</button>`:''}
      </div>
    </div>
  </div>`;

  if(reviewGroups.length===0 || total===0){
    return `<div class="parent-grid">
      ${head}
      <div class="parent-panel" style="grid-column:1/-1">
        <div class="bd" style="text-align:center;padding:40px 0;color:#8e9691">
          <div style="font-size:15px;font-weight:600;color:#5c6761;margin-bottom:6px">今日暂无待审核题目</div>
          <div style="font-size:13px">每日 03:00 自动出题，通过审核后孩子才能在任务中看到并作答。</div>
        </div>
      </div>
    </div>`;
  }

  // 按 subject 分组（保持后端返回顺序）
  const bySubject = {};
  for(const g of reviewGroups){
    const s = g.subject || '未分类';
    if(!bySubject[s]) bySubject[s] = [];
    bySubject[s].push(g);
  }

  const subjectCards = Object.entries(bySubject).map(([subject, groups])=>{
    const subjTotal = groups.reduce((n,g)=>n+(g.questions?g.questions.length:0),0);
    const subjectIcon = {语文:'语', 数学:'数'}[subject] || subject.slice(0,1);
    const subjectColor = {语文:'#3158e8', 数学:'#2e8b5a'}[subject] || '#dc872d';

    const lessonGroups = groups.map(g=>{
      const qs = g.questions || [];
      const open = expandedLessons.has(String(g.lesson_id));
      const chev = open ? '▾' : '▸';
      const qItems = qs.map(q=>{
        const label = QTYPE_LABEL[q.qtype] || q.task_type || '题目';
        const ansText = (q.answer!=null && q.answer!=='') ? `答案：${q.answer}` : '';
        const extraText = formatQuestionExtra(q.extra);
        return `<div class="q-item" style="display:flex;align-items:flex-start;gap:10px;padding:12px 14px;background:#fafbf9;border:1px solid var(--line3);border-radius:10px;margin-bottom:8px">
          <div style="flex:1;min-width:0">
            <div style="font-size:13px;font-weight:600;color:#333;line-height:1.5"><span class="q-type" style="font-size:10px;font-weight:700;border-radius:5px;padding:1px 6px;margin-right:6px;background:#edf1ff;color:#4566e8">${label}</span>${q.question||''}</div>
            ${ansText?`<div style="font-size:12px;color:#8e9691;margin-top:3px">${ansText}</div>`:''}
            ${extraText}
          </div>
          <div style="display:flex;gap:6px;flex-shrink:0">
            <button class="btn-ghost" style="color:#2e8b5a;padding:4px 10px" onclick="approveQuestion(${q.id})">通过</button>
            <button class="btn-ghost" style="color:#c05b4a;padding:4px 10px" onclick="rejectQuestion(${q.id})">驳回</button>
          </div>
        </div>`;
      }).join('');

      return `<div class="lesson-group" style="border-top:1px solid var(--line2);padding:12px 20px">
        <div style="display:flex;align-items:center;gap:8px;cursor:pointer" onclick="toggleLesson('${g.lesson_id}')">
          <span style="color:#8e9691;font-size:12px">${chev}</span>
          <span style="font-size:14px;font-weight:600">${g.subject||''} · ${g.lesson_title||('课程 '+g.lesson_id)}</span>
          <span style="font-size:12px;color:#8e9691">${qs.length} 题待审</span>
          <div style="margin-left:auto;display:flex;align-items:center;gap:8px" onclick="event.stopPropagation()">
            <button class="btn-ghost" style="padding:4px 10px" onclick="approveByLesson('${g.lesson_id}')">通过本课</button>
          </div>
        </div>
        <div style="margin-top:10px;padding-left:20px;${open?'':'display:none'}">${qItems}</div>
      </div>`;
    }).join('');

    return `<div class="subject-card" style="border:1px solid var(--line);border-radius:16px;background:#fff;margin-bottom:20px;overflow:hidden">
      <div class="subject-head" style="display:flex;align-items:center;gap:10px;padding:16px 20px">
        <div style="width:32px;height:32px;border-radius:8px;background:${subjectColor};color:#fff;display:grid;place-items:center;font-weight:700;font-size:14px">${subjectIcon}</div>
        <span style="font-size:15px;font-weight:700">${subject}</span>
        <span style="font-size:12px;color:#8e9691">${groups.length} 门课 · ${subjTotal} 题待审</span>
        <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
          <span style="font-size:11px;font-weight:600;border-radius:6px;padding:2px 8px;background:#fff2df;color:#c97629">${subjTotal} 待审</span>
          <button class="btn-ghost" style="color:#2e8b5a;padding:6px 14px;font-weight:600" onclick="approveBySubject('${subject.replace(/'/g,"\\'")}')">通过${subject}全部</button>
        </div>
      </div>
      ${lessonGroups}
    </div>`;
  }).join('');

  return `<div class="parent-grid" style="display:block">
    ${head}
    ${subjectCards}
  </div>`;
}

// ---- 任务审核 ----
async function loadParentTasks(){
  if(!uid){ parentTasks = []; return; }
  if(!parentTaskDate){
    const t = new Date();
    parentTaskDate = `${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,'0')}-${String(t.getDate()).padStart(2,'0')}`;
  }
  const u = uid, b = bucketId;
  const q = b ? `&bucket_id=${b}` : '';
  const tasks = await api(`/api/tasks?user_id=${u}&date=${parentTaskDate}&role=parent${q}`);
  if(u === uid) parentTasks = Array.isArray(tasks) ? tasks : [];
}
const TASK_TYPE_LABEL = {
  dictation:'听写', knowledge:'基础练习', review:'复习',
  reading:'阅读理解', listening:'听力理解', custom:'自由任务'
};
function renderTaskTab(){
  const typeChip = tt => `<span style="font-size:11px;font-weight:600;color:#5c6761;background:#eef0ed;border-radius:6px;padding:2px 8px">${TASK_TYPE_LABEL[tt]||tt||'任务'}</span>`;
  const rows = parentTasks.map(t=>{
    let status = '';
    let actions = '';
    if(t.content_status==='pending_review'){
      status = `<span class="g-status" style="background:var(--orange-soft);color:var(--orange2)">待审核</span>`;
      actions = `<button class="btn-primary" style="padding:6px 14px;font-size:12px" onclick="approveTask(${t.id})">通过</button>`;
    } else if(t.submit_status==='submitted'){
      status = `<span class="g-status" style="background:var(--orange-soft);color:var(--orange2)">待完成审核</span>`;
      actions = `<button class="btn-primary" style="padding:6px 14px;font-size:12px" onclick="confirmTask(${t.id})">确认完成</button>` +
        (t.photo_path ? `<a href="${API}/${t.photo_path}" target="_blank" style="font-size:12px;color:#3158e8;text-decoration:none;align-self:center">查看照片</a>` : '');
    } else if(t.submit_status==='approved'){
      status = `<span class="g-status" style="background:var(--green-soft2);color:var(--green)">已完成</span>`;
    } else {
      status = `<span class="g-status" style="background:#eef0ed;color:#78817b">已发布</span>`;
    }
    const meta = [
      t.subject||'',
      t.detail||'',
      (t.points!==undefined && t.points!==null) ? `${t.points} 积分` : ''
    ].filter(Boolean).join(' · ');
    return `<div class="goal-item" style="display:flex;align-items:center;gap:12px">
      <div style="flex:1;min-width:0">
        <div class="g-top"><span class="g-name">${t.title||'(无标题)'}</span>${status}</div>
        ${meta?`<div class="g-meta">${meta}</div>`:''}
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-shrink:0">${actions}<button class="btn-ghost" style="color:#c05b4a" onclick="deleteTask(${t.id})">删除</button></div>
    </div>`;
  }).join('');
  return `<div class="parent-grid">
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head">
        <div class="ic blue">${icon('list',20)}</div>
        <div><h3>任务管理</h3><div class="sub">${parentTaskDate} · 内容审核与完成审核</div></div>
        <div style="margin-left:auto;display:flex;gap:8px">
          <button class="btn-ghost" onclick="generateTodayTasks()">生成今日任务</button>
          <button class="btn-ghost" onclick="approveAllTasks()">全部通过</button>
          <button class="btn-primary" style="padding:8px 16px" onclick="showAddTask()">新增任务</button>
        </div>
      </div>
      <div class="bd">
        ${rows ? `<div class="goal-list">${rows}</div>` : '<div style="text-align:center;padding:32px 0;color:#8e9691">暂无任务</div>'}
      </div>
    </div>
  </div>`;
}
async function approveTask(id){ await api(`/api/tasks/${id}/approve`,{method:'POST'}); await loadParentTasks(); render(); }
async function generateTodayTasks(){
  if(!uid) return;
  if(!confirm('将重新生成本日任务（含听写生词/单词），覆盖当前已有任务。确定吗？')) return;
  await api(`/api/tasks/generate?user_id=${uid}&d=${parentTaskDate}&force=true`, {method:'POST'});
  toast('今日任务已重新生成');
  await loadParentTasks(); render();
}
async function approveAllTasks(){ if(!uid) return; await api(`/api/tasks/approve-all`,{method:'POST',body:{user_id:uid,date:parentTaskDate}}); await loadParentTasks(); render(); }
async function deleteTask(id){ await api(`/api/tasks/${id}`,{method:'DELETE'}); await loadParentTasks(); render(); }
async function confirmTask(id){ await api(`/api/tasks/${id}/confirm`,{method:'POST'}); toast('已确认，积分已发放'); await loadParentTasks(); render(); }
async function showAddTask(){
  if(!uid) return;
  const title = prompt('任务标题');
  if(!title) return;
  const subject = prompt('科目（语文/英语）', '语文') || '语文';
  await api(`/api/tasks`,{method:'POST',body:{user_id:uid,date:parentTaskDate,task_type:'custom',subject:subject,title:title,detail:'',points:20}});
  await loadParentTasks(); render();
}

// ---- 家长登录 ----
function renderLogin(){
  return `<div class="parent-grid" style="display:block;max-width:420px;margin:60px auto 0">
    <div class="parent-panel">
      <div class="head"><div class="ic orange">${icon('star',20)}</div>
        <div><h3>家长登录</h3><div class="sub">输入家长姓名，管理您的孩子</div></div></div>
      <div class="bd">
        <div style="display:flex;gap:8px">
          <input id="parentNameInput" placeholder="家长姓名" style="flex:1;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"
            onkeydown="if(event.key==='Enter')doParentLogin()">
          <button class="btn-primary" style="padding:10px 20px" onclick="doParentLogin()">登录</button>
        </div>
      </div>
    </div>
  </div>`;
}
async function doParentLogin(){
  const input = document.getElementById('parentNameInput');
  const name = (input && input.value) ? input.value.trim() : '';
  if(!name){ toast('请输入家长姓名'); return; }
  const r = await api('/api/auth/login', {method:'POST', body:{name, role:'parent'}});
  if(!r || !r.id){ toast('登录失败，请稍后重试'); return; }
  parentId = r.id; parentName = r.name;
  try{ localStorage.setItem(PARENT_KEY, String(parentId)); localStorage.setItem('knoact_parent_name', r.name); }catch(e){}
  document.getElementById('userName').textContent = r.name;
  document.getElementById('userAvatar').textContent = (r.name||'家').slice(0,1);
  await loadChildren();
  render();
}
function logoutParent(){
  parentId = null; parentName = '';
  uid = null; children = []; buckets = []; bucketId = null;
  try{ localStorage.removeItem(PARENT_KEY); localStorage.removeItem('knoact_parent_name'); }catch(e){}
  document.getElementById('userName').textContent = '家长';
  document.getElementById('userAvatar').textContent = '家';
  renderNav();
  render();
}

function renderParent(){
  if(!parentId) return renderLogin();
  const tabs = PARENT_TABS.map(([t])=>
    `<button class="filter-btn ${parentTab===t?'active':''}" style="border-radius:10px;padding:8px 16px;font-size:13px;font-weight:600;color:${parentTab===t?'#3158e8':'#778079'};background:${parentTab===t?'#fff':'transparent'}" onclick="setParentTab('${t}')">${t}</button>`
  ).join('');

  let body='';
  if(parentTab==='教材') body = renderPdfTab();
  else if(parentTab==='知识点') body = renderKnowledgeTab();
  else if(parentTab==='题目审核台') body = renderQuestionTab();
  else if(parentTab==='目标') body = renderGoalsTab();
  else if(parentTab==='报告') body = renderReportTab();
  else if(parentTab==='任务') body = renderTaskTab();
  else if(parentTab==='规则') body = renderRulesTab();
  else if(parentTab==='学习配置') body = renderLearningConfigTab();
  else if(parentTab==='设置') body = renderSettingsTab();

  if(CHILD_TABS.includes(parentTab) && !uid){
    body = `<div class="parent-panel"><div class="bd" style="text-align:center;padding:48px 0;color:#8e9691">暂无孩子：点击右上角「新建孩子」添加，或等孩子首次登录学生端后自动出现</div></div>`;
  }
  return `<div class="parent-banner">
    <div class="l"><div class="ic">${icon('star',20)}</div><div><div class="t">家长端 · 管理学习目标与规则</div><div class="s">在这里录入教材、设定目标、查看薄弱报告</div></div></div>
    <div class="parent-tabs-narrow" style="gap:8px;background:#f2f4f1;border-radius:12px;padding:4px">${tabs}</div>
    <div id="child-select-host">${childSelectHtml()}</div>
  </div>${body}`;
}

// ---- 教材 ----
function renderPdfTab(){
  if(pdfTab==='upload'){
    return `<div class="parent-grid">
      <div class="parent-panel" style="grid-column:1/-1">
        <div class="head"><div class="ic blue">${icon('book',20)}</div><div><h3>上传 PDF 教材</h3><div class="sub">系统自动拆课，并提取生词与知识点</div></div></div>
        <div class="bd">
          <div class="upload-drop" onclick="document.getElementById('pdfFile').click()">
            <div class="ic">${icon('book',28)}</div>
            <div class="t">点击上传 PDF 教材</div>
            <div class="s">支持语文 / 英语 / 数学教材，上传后自动识别目录并拆课</div>
          </div>
          <input type="file" id="pdfFile" accept="application/pdf" style="display:none" onchange="uploadPdf(this)">
          <div style="margin-top:12px;display:flex;gap:8px;align-items:center">
            <span style="font-size:13px;color:var(--gray2)">学科：</span>
            <select id="pdfSubject" style="border:1px solid var(--line3);border-radius:10px;padding:8px 12px;font-size:13px"><option>语文</option><option>英语</option><option>数学</option></select>
          </div>
          <div style="margin-top:12px"><span class="pdf-back" onclick="pdfTab=null;render()">${icon('arrow',14)} 返回教材列表</span></div>
        </div>
      </div>
    </div>`;
  }
  if(pdfTab==='confirm'){
    return renderLessonConfirm();
  }
  const rows = pdfDocs.map(d=>`
    <div class="pdf-row">
      <div class="ic">${icon('book',22)}</div>
      <div><div class="nm">${d.filename}</div><div class="meta">${d.subject} · ${d.lesson_count} 课 · 已审核 ${d.audited_count} 课</div></div>
      <div style="display:flex;gap:6px;margin-left:auto">
        <button class="btn-ghost" onclick="openDoc(${d.id})">查看/审核</button>
        <button class="btn-ghost" onclick="resplitDoc(${d.id})">重新拆分</button>
        <button class="btn-ghost" style="color:#c05b4a" onclick="removeDoc(${d.id})">移除</button>
      </div>
    </div>`).join('');
  const empty = pdfDocs.length===0 ? `<div style="text-align:center;padding:32px 0;color:#8e9691">还没有上传教材，点击下方按钮开始</div>` : rows;
  return `<div class="parent-grid">
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic blue">${icon('book',20)}</div><div><h3>教材管理</h3><div class="sub">上传 PDF，自动拆课；审核通过的课程进入孩子词库</div></div></div>
      <div class="bd">
        <div class="pdf-list">${empty}</div>
        <button class="next-lesson-btn" style="margin-top:16px" onclick="pdfTab='upload';render()">${icon('book',16)} 上传 PDF 教材</button>
      </div>
    </div>
  </div>`;
}

let docLessons = [];
async function openDoc(id){
  confirmDocId = id;
  docLessons = await api(`/api/pdf/documents/${id}/lessons`);
  pdfTab='confirm'; render();
}
async function resplitDoc(id){
  if(!confirm('重新拆分会删除该教材下的旧课程及其生词/知识点，确定吗？')) return;
  toast('正在重新拆分…');
  const r = await api(`/api/pdf/documents/${id}/resplit`, {method:'POST'});
  if(r && r.lessons!==undefined){
    await loadPdfDocs();
    toast('已重新拆分为 ' + r.lessons + ' 课');
  } else {
    toast('拆分失败：' + (r && r.error ? r.error : '未知错误'));
  }
}
async function removeDoc(id){
  if(!confirm('确定移除该教材吗？将同时删除其课程、生词与知识点。')) return;
  toast('正在移除…');
  const r = await api(`/api/pdf/documents/${id}`, {method:'DELETE'});
  if(r && r.ok){
    await loadPdfDocs();
    toast('教材已移除');
  } else {
    toast('移除失败：' + (r && r.error ? r.error : '未知错误'));
  }
}
async function doExtract(){
  toast('开始提取生词/知识点…（后台进行，可稍后刷新查看）');
  await api(`/api/pdf/documents/${confirmDocId}/extract`, {method:'POST'});
  await pollExtract();
}
async function pollExtract(){
  // 轮询提取进度，完成后刷新课程列表
  for(let i=0;i<300;i++){
    await sleep(3000);
    const p = await api(`/api/pdf/documents/${confirmDocId}/extract/progress`);
    if(!p) break;
    if(p.finished){
      docLessons = await api(`/api/pdf/documents/${confirmDocId}/lessons`);
      toast('生词与知识点提取完成');
      render();
      return;
    }
    // 仅当仍在确认页时轻量提示进度
    if(pdfTab==='confirm'){ /* 可加进度条，这里保持简单 */ }
  }
  toast('提取仍在进行，稍后可重新进入教材查看');
}
async function auditLesson(id, action){
  const fd = new FormData();
  fd.append('action', action);
  await apiForm(`/api/pdf/lessons/${id}/audit`, fd);
  docLessons = await api(`/api/pdf/documents/${confirmDocId}/lessons`);
  toast(action==='通过'?'已审核通过、入库':'已驳回');
  render();
}
function renderLessonConfirm(){
  const auditBadge = a => a==='approved'?`<span class="st-badge" style="background:var(--green-soft);color:var(--green)">已通过</span>`
    : a==='rejected'?`<span class="st-badge" style="background:#fff3f0;color:#c05b4a">已驳回</span>`
    : `<span class="st-badge" style="background:var(--orange-soft);color:var(--orange2)">待审核</span>`;
  const items = docLessons.map(l=>`
    <div class="lc-item">
      <div class="top">
        <span class="ttl">${l.title}</span>
        <span class="pg">第 ${l.start_page}–${l.end_page} 页</span>
        ${auditBadge(l.audit_status)}
      </div>
      <div class="extract">
        <div class="ex-row"><span class="ex-lbl">生词表</span><div class="ex-chips">${l.words.map(w=>`<span class="kw-chip">${w.word}</span>`).join('')||'<span style="font-size:12px;color:var(--gray3)">（待提取）</span>'}</div></div>
        <div class="ex-row"><span class="ex-lbl">知识点</span><div class="ex-chips">${l.points.map(p=>`<span class="kw-chip" style="background:var(--purple-soft);color:var(--purple)">${p.content}</span>`).join('')||'<span style="font-size:12px;color:var(--gray3)">（待提取）</span>'}</div></div>
      </div>
      <div class="ex-actions">
        <button class="btn-ghost" onclick="toast('可编辑生词与知识点')">编辑</button>
        ${l.extract_status!=='done'?`<button class="btn-primary" onclick="doExtract()">提取生词/知识点</button>`:''}
        ${l.audit_status==='pending'?`<button class="btn-ghost" style="color:#c05b4a" onclick="auditLesson(${l.id},'驳回')">驳回</button><button class="btn-primary" onclick="auditLesson(${l.id},'通过')">审核通过</button>`
          : l.audit_status==='rejected'?`<button class="btn-primary" onclick="auditLesson(${l.id},'通过')">重新审核</button>`
          : `<button class="btn-ghost" onclick="toast('已审核，可重新编辑后再次审核')">重新审核</button>`}
      </div>
    </div>`).join('');
  return `<div class="parent-grid">
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic blue">${icon('brain',20)}</div><div><h3>拆课结果 · 逐课审核</h3><div class="sub">先提取，再审核；审核通过后课程生词进入孩子听写词库</div></div></div>
      <div class="bd"><div class="lesson-confirm-list">${items}</div></div>
    </div>
    <div style="grid-column:1/-1"><span class="pdf-back" onclick="pdfTab=null;render()">${icon('arrow',14)} 返回教材列表</span></div>
  </div>`;
}
async function uploadPdf(input){
  const f = input.files && input.files[0];
  if(!f) return;
  const subject = document.getElementById('pdfSubject').value;
  const fd = new FormData();
  fd.append('subject', subject);
  fd.append('file', f);
  toast('上传中，正在自动拆课…');
  await apiForm('/api/pdf/upload', fd);
  await loadPdfDocs();
  pdfTab=null; render(); toast('上传完成，已自动拆课');
}

// ---- 知识点 ----
function renderKnowledgeTab(){
  const subjColor = s => s==='语文'?'var(--blue-soft);color:var(--blue2)':(s==='英语'?'var(--orange-soft);color:var(--orange2)':'var(--green-soft2);color:var(--green)');
  const yw = knowledgeRows.filter(p=>p.subject==='语文');
  const en = knowledgeRows.filter(p=>p.subject==='英语');
  const ma = knowledgeRows.filter(p=>p.subject==='数学');
  const block = (subject, rows, color) => {
    const byCat = {};
    rows.forEach(p=>{ (byCat[p.category] = byCat[p.category]||[]).push(p); });
    const cats = Object.keys(byCat).map(c=>`
      <div class="kp-cat">
        <div class="kp-cat-name">${c}</div>
        <div class="ex-chips">${byCat[c].map(p=>`<span class="kw-chip">${p.content}<span class="del" onclick="delKnowledge(${p.id})" style="margin-left:6px">×</span></span>`).join('')}</div>
      </div>`).join('');
    return `<div class="parent-panel">
      <div class="head"><div class="ic" style="background:${color}">${icon('brain',20)}</div><div><h3>${subject}基础知识</h3><div class="sub">按类别分组，供出题与复习</div></div></div>
      <div class="bd">${cats || '<p style="font-size:13px;color:var(--gray2)">暂无知识点</p>'}</div>
    </div>`;
  };
  return `<div class="parent-grid">
    ${block('语文', yw, subjColor('语文'))}
    ${block('英语', en, subjColor('英语'))}
    ${block('数学', ma, subjColor('数学'))}
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic purple">${icon('sparkles',20)}</div><div><h3>添加知识点</h3><div class="sub">手动补充教材外的基础知识，AI 据此出题</div></div></div>
      <div class="bd">
        <div style="display:flex;gap:8px">
          <select id="kpSubject" style="border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"><option>语文</option><option>英语</option><option>数学</option></select>
          <select id="kpCategory" style="border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"><option>字词</option><option>拼音</option><option>句式</option><option>古诗文</option><option>语法</option><option>句型</option><option>计算</option><option>图形</option><option>应用题</option></select>
          <input id="kpContent" placeholder="知识点内容，如：动词第三人称单数加 s" style="flex:1;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px">
          <button class="btn-primary" style="padding:10px 20px" onclick="addKnowledge()">添加</button>
        </div>
      </div>
    </div>
  </div>`;
}
async function addKnowledge(){
  const subject = document.getElementById('kpSubject').value;
  const category = document.getElementById('kpCategory').value;
  const content = document.getElementById('kpContent').value.trim();
  if(!content) return;
  await api('/api/knowledge', {method:'POST', body:{subject, category, content}});
  await loadKnowledge(); render(); toast('知识点已添加');
}
async function delKnowledge(id){
  await api(`/api/knowledge/${id}`, {method:'DELETE'});
  await loadKnowledge(); render(); toast('已删除');
}

// ---- 目标 ----
function renderGoalsTab(){
  const goals = goalRows.map(g=>{
    const statusMap = {pending:['待开始','#eef0ed','#78817b','#d5dad5',0,'尚未开始'], in_progress:['学习中','var(--orange-soft)','var(--orange2)','var(--orange)',50,'进行中'], done:['已掌握','var(--green-soft2)','var(--green)','var(--green)',100,'已达成']};
    const [label,bg,fg,fc,progress,meta] = statusMap[g.status]||statusMap.pending;
    return `<div class="goal-item">
      <div class="g-top"><span class="g-name">${g.content}</span><span class="g-status" style="background:${bg};color:${fg}">${label}</span></div>
      <div class="g-bar"><div class="g-fill" style="width:${progress}%;background:${fc}"></div></div>
      <div class="g-meta">${meta} · 掌握度 ${progress}%</div>
    </div>`;
  }).join('');
  return `<div class="parent-grid">
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic purple">${icon('brain',20)}</div><div><h3>教学目标考核</h3><div class="sub">用一句话设定目标，AI 拆解成知识点并出题考核</div></div></div>
      <div class="bd">
        <div class="goal-list">${goals || '<p style="font-size:13px;color:var(--gray2)">暂无目标</p>'}</div>
        <div style="margin-top:16px;display:flex;gap:8px"><input id="goalInput" placeholder="例如：掌握第 13 课所有生词" style="flex:1;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"><button class="btn-primary" style="padding:10px 20px" onclick="addGoal()">设定目标</button></div>
      </div>
    </div>
  </div>`;
}
async function addGoal(){
  if(!uid) return;
  const content = document.getElementById('goalInput').value.trim();
  if(!content) return;
  await api('/api/goals', {method:'POST', body:{user_id:uid, content}});
  await loadGoals(); render(); toast('目标已设定');
}

// ---- 报告 ----
function renderReportTab(){
  const total = reportRows.total||0;
  const rows = (reportRows.rows||[]).map(r=>{
    const pct = total? Math.round(r.count/total*100):0;
    return `<div class="weak-row"><span class="w-name">${r.name}</span><div class="w-bar"><div class="w-fill" style="width:${Math.max(pct,4)}%"></div></div><span class="w-val">${r.count} 次</span></div>`;
  }).join('');
  return `<div class="parent-grid">
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic green">${icon('chart',20)}</div><div><h3>薄弱环节报告</h3><div class="sub">按题型汇总错误频率，帮助定位薄弱项</div></div></div>
      <div class="bd">
        <div style="font-size:13px;color:var(--gray2);margin-bottom:16px">近 30 天错误频率（知识点级）</div>
        <div class="weak-list">${rows || '<p style="font-size:13px;color:var(--gray2)">暂无错误记录</p>'}</div>
        <p style="margin-top:16px;font-size:12px;color:#8e9691">形近字混淆是当前最薄弱的环节，AI 会相应提高相关生词的复习频率。</p>
      </div>
    </div>
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic purple">${icon('brain',20)}</div>
        <div><h3>掌握度报告</h3><div class="sub">知识点掌握情况（按答题记录计算）</div></div></div>
      <div class="bd">
        <div style="display:flex;gap:16px;align-items:center;margin-bottom:16px">
          <span style="font-size:13px;color:var(--gray2)">已掌握 <b style="color:var(--green2)">${masteryReport?.mastered||0}</b> ·
          薄弱 <b style="color:var(--orange2)">${masteryReport?.weak||0}</b> · 共 ${masteryReport?.total||0}</span>
        </div>
        ${(masteryReport?.rows||[]).map(r=>`
          <div class="weak-row">
            <span class="w-name">${escapeAttr(r.category)} · ${escapeAttr(r.title)}</span>
            <div class="w-bar"><div class="w-fill" style="width:${Math.round(r.mastery*100)}%;background:${r.mastered?'var(--green2)':'var(--orange2)'}"></div></div>
            <span class="w-val">${r.mastered?'✓ ':''}${Math.round(r.mastery*100)}%</span>
          </div>`).join('') || '<p style="font-size:13px;color:var(--gray2)">暂无掌握度记录</p>'}
      </div>
    </div>
  </div>`;
}

// ---- 规则 ----
function renderRulesTab(){
  return `<div class="parent-grid">
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic orange">${icon('gift',20)}</div><div><h3>积分兑换规则</h3><div class="sub">设定积分可兑换的设备使用时间</div></div></div>
      <div class="bd">
        <div class="redeem-rule">
          <div class="rule-row"><div class="r-l">${icon('tablet',22)}<div><div class="r-name">平板 30 分钟</div><div class="r-cost">300 积分</div></div></div><span class="rule-edit" onclick="toast('兑换规则可在此调整')">编辑</span></div>
          <div class="rule-row"><div class="r-l">${icon('phone',22)}<div><div class="r-name">手机 20 分钟</div><div class="r-cost">200 积分</div></div></div><span class="rule-edit" onclick="toast('兑换规则可在此调整')">编辑</span></div>
        </div>
        <p style="margin-top:16px;font-size:12px;color:#8e9691">兑换后，请配合系统家长控制（iOS 屏幕使用时间 / Android Family Link）设置对应限额。</p>
      </div>
    </div>
  </div>`;
}

// ---- 模型与服务（7 角色）----
let msCatalog = null;
let msRoleTab = 'llm';
let msProbe = {};
let msConnEdit = null;
let msSaving = false;
let msLegacyView = false;
let msModelsByConn = {};

const MS_ROLES = [
  {id:'llm',       name:'语言模型',     icon:'brain',      color:'purple', wired:true,  desc:'对话、追问、讲解、出题', model:true},
  {id:'task',      name:'后台任务模型', icon:'clock',      color:'blue',   wired:true,  desc:'任务生成、课文提取、批量出题', model:true},
  {id:'embedding', name:'嵌入模型',     icon:'text',       color:'green',  wired:false, desc:'课文语义检索（为引用定位预留）', model:true},
  {id:'search',    name:'搜索',         icon:'chart',      color:'orange', wired:false, desc:'联网查资料（暂未接入）', model:false},
  {id:'tts',       name:'语音',         icon:'headphones', color:'orange', wired:true,  desc:'听写朗读、课文朗读', model:true},
  {id:'stt',       name:'语音识别',     icon:'headphones', color:'blue',   wired:false, desc:'跟读评测（暂未接入）', model:true},
  {id:'imagegen',  name:'多模态生成',   icon:'sparkles',   color:'green',  wired:false, desc:'课文配图与示意动画（暂未接入）', model:true}
];

async function loadModelCatalog(){
  msCatalog = await api('/api/config/catalog');
  return msCatalog;
}
function msSvc(role){ return (msCatalog && msCatalog.services && msCatalog.services[role]) || {}; }
function msConns(){ return (msCatalog && msCatalog.connections) || []; }
function msConnAt(i){ const c = msConns(); return (typeof i === 'number' && i >= 0 && i < c.length) ? c[i] : null; }
function msRoleMeta(id){ return MS_ROLES.find(r => r.id === id) || MS_ROLES[0]; }
function msStatus(role){
  const svc = msSvc(role);
  if(role === 'task' && (svc.mode || 'inherit') === 'inherit') return 'ok';
  if(svc.connection_index === null || svc.connection_index === undefined) return 'off';
  return svc.model ? 'ok' : 'warn';
}
function msOpts(role){
  const raw = msSvc(role).options || '';
  try { return raw ? JSON.parse(raw) : {}; } catch(e){ return {}; }
}

function renderSettingsTab(){
  if(msLegacyView){ return renderSettingsTabLegacy(); }
  if(!msCatalog){
    loadModelCatalog().then(()=>render()).catch(()=>{ msCatalog = {registry:{}, connections:[], services:{}}; render(); });
    return `<div class="ms-empty" style="margin-top:24px">正在加载模型配置…</div>`;
  }
  return `<div style="display:flex;justify-content:flex-end;margin-bottom:-8px">
      <button class="btn-ghost" onclick="msLegacyView=true;render()">切换到旧版设置</button>
    </div>
    <div class="ms-wrap">${msNavHtml()}${msRoleTab==='connections' ? msConnectionsHtml() : msRoleHtml()}</div>`;
}

function msNavHtml(){
  const items = MS_ROLES.map(r=>{
    const st = msStatus(r.id);
    return `<button class="ms-item ${msRoleTab===r.id?'on':''}" onclick="msSelectRole('${r.id}')">
      ${icon(r.icon,16)}<span>${r.name}</span>
      ${r.wired ? `<span class="dot ${st}"></span>` : `<span class="off-tag">未接入</span>`}
    </button>`;
  }).join('');
  return `<aside class="ms-nav">
    <div class="nav-title">模型与服务</div>
    ${items}
    <div style="border-top:1px solid #eef1ec;margin:10px 0 4px"></div>
    <button class="ms-item ${msRoleTab==='connections'?'on':''}" onclick="msSelectRole('connections')">
      ${icon('book',16)}<span>提供方</span>
    </button>
  </aside>`;
}

function msConnectionsHtml(){
  const cards = msConns().map((c,i)=>{
    const editing = msConnEdit === i;
    return `<div class="ms-card" style="align-items:flex-start">
      <div class="c-l">
        <div class="c-name">${escapeAttr(c.name||'未命名')}<span class="ms-badge idle">${escapeAttr(c.provider)}</span></div>
        <div class="c-meta">${escapeAttr(c.base_url||'默认端点')} · <span class="c-k">${escapeAttr(c.api_key||'未配置')}</span></div>
        ${editing ? `
          <div class="ms-field"><div class="ms-label">名称</div>
            <input class="ms-input" value="${escapeAttr(c.name||'')}" oninput="msConnField(${i},'name',this.value)"></div>
          <div class="ms-field"><div class="ms-label">Base URL</div>
            <input class="ms-input" value="${escapeAttr(c.base_url||'')}" placeholder="留空使用默认端点" oninput="msConnField(${i},'base_url',this.value)"></div>
          <div class="ms-field"><div class="ms-label">API Key</div>
            <input class="ms-input" type="password" value="" placeholder="${c.api_key?'已保存，留空则不修改':'sk-...'}" oninput="msConnField(${i},'_newKey',this.value)">
            <div class="ms-hint">密钥只在提供方录一次，所有角色共用。</div></div>` : ''}
      </div>
      <div style="display:flex;flex-direction:column;gap:8px;align-items:flex-end">
        <button class="btn-ghost" onclick="msToggleConnEdit(${i})">${editing?'收起':'编辑'}</button>
        <button class="btn-ghost" style="color:#c05b4a" onclick="msRemoveConn(${i})">删除</button>
      </div>
    </div>`;
  }).join('');
  return `<section class="ms-main">
    <div class="head"><div class="ic blue">${icon('book',20)}</div>
      <div><h3>提供方</h3><div class="sub">添加提供方与认证信息，然后测试连接</div></div></div>
    <div style="margin-top:18px">${cards || `<div class="ms-empty">还没有提供方，先添加一个吧</div>`}</div>
    <div class="ms-actions">
      <button class="btn-ghost" style="padding:10px 20px" onclick="msAddConn()">＋ 添加提供方</button>
      <button class="btn-primary" style="padding:10px 24px" onclick="msSaveAll()" ${msSaving?'disabled':''}>保存配置</button>
    </div>
  </section>`;
}

function msRoleHtml(){
  const r = msRoleMeta(msRoleTab);
  const svc = msSvc(r.id);
  const st = msStatus(r.id);
  const stText = st==='ok'?'已配置':st==='warn'?'待选模型':'未配置';
  const inherit = r.id==='task' && (svc.mode||'inherit')==='inherit';
  const connOpts = `<option value="">— 不使用连接 —</option>` + msConns().map((c,i)=>
    `<option value="${i}" ${svc.connection_index===i?'selected':''}>${escapeAttr(c.name||c.provider)}</option>`).join('');
  const models = msModelsByConn[svc.connection_index] || [];
  const opts = msOpts(r.id);

  const summary = MS_ROLES.filter(x=>x.wired).map(x=>{
    const s = msSvc(x.id);
    const inh = x.id==='task' && (s.mode||'inherit')==='inherit';
    const eff = s.effective || {};
    const val = inh ? '跟随语言模型' : (eff.provider ? `${eff.provider} · ${eff.model||'未选模型'}` : '未配置');
    return `<div style="display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #f1f4ef">
      <span style="font-size:12px;color:var(--gray2);width:88px;flex-shrink:0">${x.name}</span>
      <span style="font-size:12px;color:var(--ink3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeAttr(val)}</span>
    </div>`;
  }).join('');

  return `<section class="ms-main">
    <div class="head">
      <div class="ic ${r.color}">${icon(r.icon,20)}</div>
      <div><h3>${r.name}</h3><div class="sub">${r.desc}</div></div>
      <span class="ms-badge ${st}">${stText}</span>
    </div>
    ${!r.wired ? `<div class="ms-hint" style="margin-top:14px;background:#f7f8f6;border-radius:12px;padding:10px 12px">
      该角色暂未接入业务，配置会保存，但不会影响现有功能。</div>` : ''}
    ${r.id==='task' ? `<div class="ms-field">
      <label style="display:flex;align-items:center;gap:10px;font-size:14px;font-weight:600;cursor:pointer">
        <input type="checkbox" ${inherit?'checked':''} onchange="msToggleInherit(this.checked)">
        跟随语言模型（推荐）
      </label>
      <div class="ms-hint">开启后后台任务沿用语言模型的配置；只有在想用更便宜 / 更快的模型时才需要单独配置。</div>
    </div>` : ''}
    ${inherit ? '' : `
      <div class="ms-field"><div class="ms-label">提供方</div>
        <select class="ms-select" onchange="msSetConn(this.value)">${connOpts}</select>
        ${msConns().length ? '' : `<div class="ms-hint">先到「提供方」里添加一套凭证，再回到这里选择。</div>`}
      </div>
      ${r.model ? `<div class="ms-field"><div class="ms-label">模型</div>
        <div class="ms-row">
          ${models.length
            ? `<select class="ms-select" onchange="msSetModel(this.value)">
                 <option value="">— 选择模型 —</option>
                 ${models.map(m=>`<option value="${escapeAttr(m)}" ${svc.model===m?'selected':''}>${escapeAttr(m)}</option>`).join('')}
               </select>`
            : `<input class="ms-input" value="${escapeAttr(svc.model||'')}" placeholder="填模型名，或点右侧拉取" oninput="msSetModel(this.value)">`}
          <button class="btn-ghost" style="white-space:nowrap" onclick="msFetchModels()">拉取模型</button>
        </div>
        <div class="ms-hint">${escapeAttr(msProbe[r.id]||'选择提供方后，可拉取该账号下可用的模型列表。')}</div>
      </div>` : ''}
      ${r.id==='tts' ? `<div class="ms-field"><div class="ms-label">音色</div>
        <select class="ms-select" onchange="msSetOption('voice',this.value)">
          ${['male-qn-qingse','female-shaonv','presenter_male','alloy','nova'].map(v=>
            `<option value="${v}" ${(opts.voice||'')===v?'selected':''}>${v}</option>`).join('')}
        </select></div>
        <div class="ms-field">
          <div class="ms-row"><span class="ms-label" style="margin:0;white-space:nowrap">语速</span>
            <input type="range" min="0.5" max="2" step="0.1" value="${opts.speed||1}" style="flex:1"
              oninput="msSetOption('speed',this.value);this.nextElementSibling.textContent=this.value">
            <span style="font-size:13px;width:34px;text-align:right">${opts.speed||1}</span>
          </div>
        </div>` : ''}
      ${r.id==='embedding' ? `<div class="ms-field"><div class="ms-label">向量维度</div>
        <input class="ms-input" value="${escapeAttr(opts.dimension||'')}" placeholder="如 1536"
          oninput="msSetOption('dimension',this.value)"></div>` : ''}
    `}
    <div class="ms-actions">
      ${r.id==='tts' ? `<button class="btn-ghost" style="padding:10px 20px" onclick="testVoice()">试听语音</button>` : ''}
      <button class="btn-ghost" style="padding:10px 20px" onclick="msTestRole('${r.id}')">测试连接</button>
      <button class="btn-primary" style="padding:10px 24px" onclick="msSaveAll()" ${msSaving?'disabled':''}>保存配置</button>
    </div>
    <div style="margin-top:22px;padding-top:18px;border-top:1px solid #eef1ec">
      <div style="font-size:12px;font-weight:700;color:var(--gray2);letter-spacing:.04em;margin-bottom:4px">当前生效配置</div>
      ${summary}
    </div>
  </section>`;
}

// ---- 学习配置 ----
function renderLearningConfigTab(){
  const num = (key, def, label, hint, min='0', max='100', step='1') => `
    <div class="lc-row">
      <div class="lc-label">${label}</div>
      <input class="lc-input" type="number" min="${min}" max="${max}" step="${step}"
             value="${configMap[key] || def}" data-key="${key}" />
      ${hint ? `<div class="lc-hint">${hint}</div>` : ''}
    </div>`;
  const sel = (key, def, label, opts) => `
    <div class="lc-row">
      <div class="lc-label">${label}</div>
      <select class="lc-input" data-key="${key}">
        ${opts.map(o=>`<option value="${o}" ${(configMap[key]||def)===o?'selected':''}>${o}</option>`).join('')}
      </select>
    </div>`;
  const chk = (key, label, hint) => `
    <div class="lc-row">
      <label class="lc-label"><input type="checkbox" data-key="${key}" ${configMap[key]==='true'?'checked':''} /> ${label}</label>
      ${hint ? `<div class="lc-hint">${hint}</div>` : ''}
    </div>`;

  return `
    <div class="parent-grid">
      <div class="parent-panel" style="grid-column:1/-1">
        <div class="head"><div class="ic blue">${icon('chart',20)}</div><div><h3>学习配置</h3><div class="sub">调整每日听写量、新旧比例、作业难度与测试开关</div></div></div>
        <div class="bd">
          ${num('task_dictation_count_语文','7','语文每日听写量','每天听写几个语文生词')}
          ${num('task_dictation_count_英语','7','英语每日听写量','每天听写几个英语单词')}
          ${num('task_new_ratio','5','新/旧比例（新名额）','每日任务里「当天新课」的名额，旧=总量-新')}
          ${num('assignment_question_count','4','作业题数','个性化学习每次作业几道题')}
          ${num('assignment_pass_threshold','0.6','通过正确率','0~1，例如 0.6 表示 60%','0','1','0.1')}
          ${sel('difficulty_语文','中等','语文出题难度',['简单','中等','困难'])}
          ${sel('difficulty_英语','中等','英语出题难度',['简单','中等','困难'])}
          ${sel('difficulty_数学','中等','数学出题难度',['简单','中等','困难'])}
          ${chk('personalized_disable_chat','禁用个性化学习 AI 对话','勾选 = 禁用，不勾选 = 开放（默认）；孩子做作业期间始终暂停对话')}
          <div style="margin-top:16px">
            <button class="btn-primary" onclick="saveLearningConfig()">保存配置</button>
          </div>
        </div>
      </div>
    </div>`;
}

async function saveLearningConfig(){
  // 收集所有 [data-key] 输入框/下拉/勾选框的当前值
  const inputs = document.querySelectorAll('[data-key]');
  for(const el of inputs){
    const key = el.dataset.key;
    let value;
    if(el.type === 'checkbox'){ value = el.checked ? 'true' : 'false'; }
    else { value = el.value; }
    await api('/api/config', {method:'POST', body:{key, value}});
  }
  toast('学习配置已保存');
  await loadConfig();
}

// ---- 设置（旧版，保留作为回滚路径）----
function renderSettingsTabLegacy(){
  const aiOpts = aiProviders.map(p=>{
    // 中转站：模型动态拉取；其他 provider 用内置固定列表
    let modelField = '';
    if(p.id==='openai'){
      const opts = aiModelOptions.map(m=>`<option value="${m}" ${aiConfig.model===m?'selected':''}>${m}</option>`).join('');
      modelField = `<div style="display:flex;gap:10px;align-items:center;margin-top:10px">
        <span style="font-size:13px;color:var(--gray2);white-space:nowrap">模型</span>
        <input type="text" value="${aiConfig.model}" oninput="aiConfig.model=this.value" placeholder="先点右侧拉取，或手动填模型名" style="flex:1;border:1px solid var(--line3);border-radius:10px;padding:8px 10px;font-size:13px">
        ${aiModelOptions.length?`<select onchange="aiConfig.model=this.value" style="max-width:180px;border:1px solid var(--line3);border-radius:10px;padding:8px 10px;font-size:13px"><option value="">从列表选</option>${opts}</select>`:''}
        <button type="button" onclick="fetchAiModels()" style="white-space:nowrap;border:1px solid var(--line3);border-radius:10px;padding:8px 12px;font-size:13px;background:var(--blue2);color:#fff">拉取模型</button>
      </div>`;
    } else {
      const models = p.models.map(m=>`<option value="${m}" ${aiConfig.model===m?'selected':''}>${m}</option>`).join('');
      modelField = `<div style="display:flex;gap:10px;align-items:center;margin-top:10px"><span style="font-size:13px;color:var(--gray2)">模型</span><select style="flex:1;border:1px solid var(--line3);border-radius:10px;padding:8px 10px;font-size:13px" onchange="aiConfig.model=this.value">${models}</select></div>`;
    }
    return `<div class="rule-row" style="flex-direction:column;align-items:stretch;gap:10px">
      <label style="display:flex;align-items:center;gap:10px;font-size:14px;font-weight:700;cursor:pointer"><input type="radio" name="aiProvider" value="${p.id}" ${aiConfig.provider===p.id?'checked':''} onchange="setAiProvider('${p.id}')">${p.name}</label>
      ${aiConfig.provider===p.id?modelField:''}
    </div>`;
  }).join('');
  const ttsOpts = ttsProviders.map(p=>{
    const voices = p.voices.map(v=>`<option value="${v}" ${ttsConfig.provider===p.id&&ttsConfig.voice===v?'selected':''}>${v}</option>`).join('');
    // 中转站：语音模型动态拉取
    let voiceModelField = '';
    if(p.id==='openai'){
      const mopts = ttsModelOptions.map(m=>`<option value="${m}" ${ttsConfig.model===m?'selected':''}>${m}</option>`).join('');
      voiceModelField = `<div style="display:flex;gap:10px;align-items:center;margin-top:10px">
        <span style="font-size:13px;color:var(--gray2);white-space:nowrap">模型</span>
        <input type="text" value="${ttsConfig.model}" oninput="ttsConfig.model=this.value" placeholder="先点右侧拉取，或手动填模型名" style="flex:1;border:1px solid var(--line3);border-radius:10px;padding:8px 10px;font-size:13px">
        ${ttsModelOptions.length?`<select onchange="ttsConfig.model=this.value" style="max-width:180px;border:1px solid var(--line3);border-radius:10px;padding:8px 10px;font-size:13px"><option value="">从列表选</option>${mopts}</select>`:''}
        <button type="button" onclick="fetchTtsModels()" style="white-space:nowrap;border:1px solid var(--line3);border-radius:10px;padding:8px 12px;font-size:13px;background:var(--blue2);color:#fff">拉取模型</button>
      </div>`;
    }
    return `<div class="rule-row" style="flex-direction:column;align-items:stretch;gap:10px">
      <label style="display:flex;align-items:center;gap:10px;font-size:14px;font-weight:700;cursor:pointer"><input type="radio" name="ttsProvider" value="${p.id}" ${ttsConfig.provider===p.id?'checked':''} onchange="setTtsProvider('${p.id}')">${p.name}</label>
      ${ttsConfig.provider===p.id?`<div style="display:flex;gap:10px;align-items:center"><span style="font-size:13px;color:var(--gray2)">音色</span><select style="flex:1;border:1px solid var(--line3);border-radius:10px;padding:8px 10px;font-size:13px" onchange="ttsConfig.voice=this.value">${voices}</select></div>`:''}
      ${ttsConfig.provider===p.id?voiceModelField:''}
    </div>`;
  }).join('');
  const legacyBody = `<div class="parent-grid">
    <div class="parent-panel">
      <div class="head"><div class="ic purple">${icon('brain',20)}</div><div><h3>AI 大模型配置</h3><div class="sub">选择出题 / 批改 / 对话用的默认模型</div></div></div>
      <div class="bd">
        <div class="redeem-rule">${aiOpts}</div>
        ${aiConfig.provider==='openai'?`<div style="margin-top:16px">
          <div style="font-size:13px;color:var(--gray2);margin-bottom:8px">Base URL（中转站接口地址）</div>
          <input type="text" placeholder="https://aiapi.icloudsky.com/v1" value="${aiConfig.baseUrl}" oninput="aiConfig.baseUrl=this.value" style="width:100%;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px">
        </div>`:''}
        <div style="margin-top:16px">
          <div style="font-size:13px;color:var(--gray2);margin-bottom:8px">API Key</div>
          <input type="password" placeholder="sk-..." value="${aiConfig.key}" oninput="aiConfig.key=this.value" style="width:100%;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px">
        </div>
      </div>
    </div>
    <div class="parent-panel">
      <div class="head"><div class="ic orange">${icon('headphones',20)}</div><div><h3>语音合成配置</h3><div class="sub">选择听写朗读用的默认语音</div></div></div>
      <div class="bd">
        <div class="redeem-rule">${ttsOpts}</div>
        ${ttsConfig.provider==='openai'?`<div style="margin-top:16px">
          <div style="font-size:13px;color:var(--gray2);margin-bottom:8px">Base URL（中转站接口地址）</div>
          <input type="text" placeholder="https://aiapi.icloudsky.com/v1" value="${ttsConfig.baseUrl}" oninput="ttsConfig.baseUrl=this.value" style="width:100%;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px">
        </div>`:''}
        <div style="margin-top:16px;display:flex;flex-direction:column;gap:12px">
          <div><div style="font-size:13px;color:var(--gray2);margin-bottom:8px">API Key</div><input type="password" placeholder="语音服务 Key" value="${ttsConfig.key}" oninput="ttsConfig.key=this.value" style="width:100%;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"></div>
          <div style="display:flex;gap:10px;align-items:center"><span style="font-size:13px;color:var(--gray2);white-space:nowrap">语速</span><input type="range" min="0.5" max="2" step="0.1" value="${ttsConfig.speed}" oninput="ttsConfig.speed=this.value;this.nextElementSibling.textContent=this.value" style="flex:1"><span style="font-size:13px;width:32px;text-align:right">${ttsConfig.speed}</span></div>
          <div style="display:flex;gap:10px;align-items:center"><span style="font-size:13px;color:var(--gray2);white-space:nowrap">重复次数</span><input type="range" min="1" max="3" step="1" value="${ttsConfig.repeat}" oninput="ttsConfig.repeat=this.value;this.nextElementSibling.textContent=this.value+' 次'" style="flex:1"><span style="font-size:13px;width:44px;text-align:right">${ttsConfig.repeat} 次</span></div>
        </div>
      </div>
    </div>
    <div style="grid-column:1/-1;display:flex;justify-content:flex-end;gap:10px">
      <button class="btn-ghost" style="padding:10px 20px" onclick="testVoice()">试听语音</button>
      <button class="btn-ghost" style="padding:10px 20px" onclick="testAiConnection()">测试连接</button>
      <button class="btn-primary" style="padding:10px 24px" onclick="saveConfig()">保存配置</button>
    </div>
  </div>`;
  return `<div style="display:flex;justify-content:flex-end;margin-bottom:12px">
      <button class="btn-ghost" onclick="msLegacyView=false;render()">切换到新版设置</button>
    </div>` + legacyBody;
}
function setAiProvider(id){ aiConfig.provider=id; aiConfig.model=aiProviders.find(p=>p.id===id).models[0]; render(); }
function setTtsProvider(id){ ttsConfig.provider=id; ttsConfig.voice=ttsProviders.find(p=>p.id===id).voices[0]; render(); }

// ---- 模型与服务：交互 ----
function msSelectRole(id){ msRoleTab = id; msConnEdit = null; render(); }
function msToggleConnEdit(i){ msConnEdit = msConnEdit === i ? null : i; render(); }
function msConnField(i, field, val){
  const c = msConns()[i]; if(!c) return;
  if(field === '_newKey'){ c._newKey = val; return; }
  c[field] = val;
}
function msAddConn(){
  msCatalog.connections.push({id:null, provider:'openai', name:'新提供方',
    base_url:'', api_key:'', extra_headers:''});
  msConnEdit = msConns().length - 1;
  msRoleTab = 'connections'; render();
}
function msRemoveConn(i){
  msCatalog.connections.splice(i, 1);
  Object.keys(msCatalog.services||{}).forEach(role=>{
    const s = msCatalog.services[role];
    if(s.connection_index === i){ s.connection_index = null; s.model = ''; }
    else if(typeof s.connection_index === 'number' && s.connection_index > i){ s.connection_index -= 1; }
  });
  if(msConnEdit === i) msConnEdit = null;
  else if(msConnEdit !== null && msConnEdit > i) msConnEdit -= 1;
  render();
}
function msSetConn(val){
  const s = msSvc(msRoleTab);
  s.connection_index = val === '' ? null : parseInt(val);
  s.model = '';
  render();
}
function msSetModel(val){ msSvc(msRoleTab).model = val; }
function msSetOption(key, val){
  const s = msSvc(msRoleTab);
  let o = msOpts(msRoleTab);
  o[key] = val;
  s.options = JSON.stringify(o);
}
async function msToggleInherit(on){
  msSvc('task').mode = on ? 'inherit' : 'reference';
  await msSaveAll();
}
async function msFetchModels(){
  const s = msSvc(msRoleTab);
  const conn = msConnAt(s.connection_index);
  if(!conn){ msProbe[msRoleTab] = '请先选择提供方。'; render(); return; }
  msProbe[msRoleTab] = '正在拉取…'; render();
  const r = await api('/api/config/probe', {method:'POST', body:{
    provider: conn.provider, base_url: conn.base_url,
    api_key: conn.api_key, connection_id: conn.id || null
  }});
  if(r.status === 'connected' && r.models && r.models.length){
    msProbe[msRoleTab] = `连接成功 · 可用模型 ${r.models.length} 个`;
    msModelsByConn[s.connection_index] = r.models.map(m=>m.id);
  } else if(r.status === 'connected'){
    msProbe[msRoleTab] = '连接成功，但该提供方没有返回模型列表，请手动填写。';
  } else {
    msProbe[msRoleTab] = `连接失败：${r.status}${r.warning?' · '+r.warning:''}`;
  }
  render();
}
async function msTestRole(role){
  msProbe[role] = '正在测试…'; render();
  const r = await api('/api/config/test', {method:'POST', body:{role}});
  msProbe[role] = r.ok
    ? `测试通过${r.note?'（'+r.note+'）':''}${r.sample?'：'+r.sample.slice(0,30):''}`
    : `测试失败：${r.error||'未知错误'}`;
  render();
}
async function msSaveAll(){
  if(msSaving) return;
  msSaving = true; render();
  const payload = {
    connections: msConns().map(c=>({
      id: c.id || null, provider: c.provider, name: c.name,
      base_url: c.base_url, api_key: c._newKey || c.api_key || '',
      extra_headers: c.extra_headers || ''
    })),
    services: {}
  };
  Object.keys(msCatalog.services||{}).forEach(role=>{
    const s = msCatalog.services[role];
    payload.services[role] = {
      connection_index: s.connection_index === undefined ? null : s.connection_index,
      model: s.model || '', options: s.options || '', mode: s.mode || 'inherit'
    };
  });
  try{
    const r = await api('/api/config/catalog', {method:'PUT', body:payload});
    if(r && r.ok){ await loadModelCatalog(); toast('模型与服务配置已保存'); }
    else { toast('保存失败'); }
  }catch(e){ toast('保存失败：' + e.message); }
  msSaving = false;
  render();
}
async function saveConfig(){
  const kv = [
    ['ai_provider', aiConfig.provider], ['ai_model', aiConfig.model], ['ai_key', aiConfig.key],
    ['ai_base_url', aiConfig.baseUrl],
    ['tts_provider', ttsConfig.provider], ['tts_voice', ttsConfig.voice], ['tts_key', ttsConfig.key],
    ['tts_base_url', ttsConfig.baseUrl], ['tts_model', ttsConfig.model],
    ['tts_speed', String(ttsConfig.speed)], ['tts_repeat', String(ttsConfig.repeat)]
  ];
  for(const [key,value] of kv){ await api('/api/config', {method:'POST', body:{key, value}}); }
  toast('配置已保存');
}
async function fetchAiModels(){
  if(!aiConfig.baseUrl || !aiConfig.key){ toast('请先填写 Base URL 和 API Key'); return; }
  toast('正在拉取模型列表…');
  const r = await api('/api/config/models', {method:'POST', body:{
    provider: aiConfig.provider, api_key: aiConfig.key, base_url: aiConfig.baseUrl, kind: 'chat'
  }});
  if(r.ok && r.models && r.models.length){
    aiModelOptions = r.models;
    if(!aiModelOptions.includes(aiConfig.model)) aiConfig.model = aiModelOptions[0];
    render();
    toast('已拉取 ' + r.models.length + ' 个模型');
  } else {
    toast('拉取失败：' + (r.error||'无模型返回'));
  }
}
async function fetchTtsModels(){
  if(!ttsConfig.baseUrl || !ttsConfig.key){ toast('请先填写 Base URL 和 API Key'); return; }
  toast('正在拉取语音模型列表…');
  const r = await api('/api/config/models', {method:'POST', body:{
    provider: 'openai', api_key: ttsConfig.key, base_url: ttsConfig.baseUrl, kind: 'tts'
  }});
  if(r.ok && r.models && r.models.length){
    ttsModelOptions = r.models;
    if(!ttsModelOptions.includes(ttsConfig.model)) ttsConfig.model = ttsModelOptions[0];
    render();
    toast('已拉取 ' + r.models.length + ' 个语音模型');
  } else {
    toast('拉取失败：' + (r.error||'无语音模型返回'));
  }
}
async function testAiConnection(){
  toast('正在测试连接…');
  const r = await api('/api/config/test', {method:'POST', body:{
    provider: aiConfig.provider, model: aiConfig.model, api_key: aiConfig.key, base_url: aiConfig.baseUrl
  }});
  if(r.ok){ toast('连接成功：' + (r.sample||'').slice(0,40)); }
  else { toast('连接失败：' + (r.error||'未知错误')); }
}
async function testVoice(){
  toast('正在合成试听语音…');
  try{
    const r = await fetch(`${API}/api/tts/synthesize?text=${encodeURIComponent('你好，这是语音合成测试')}`);
    const ct = r.headers.get('content-type')||'';
    if(ct.includes('audio')){
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = new Audio(url); a.onended=()=>URL.revokeObjectURL(url); a.play();
      toast('已播放中转站合成语音');
    } else {
      const d = await r.json().catch(()=>({}));
      if(d && d.use_browser_tts){ browserSpeak('你好，这是语音合成测试'); toast('当前为浏览器合成（未配置真实 TTS）'); }
      else { toast('语音合成失败：' + (d.error||'未知错误')); }
    }
  }catch(e){ toast('语音合成失败：' + e.message); }
}

// ===== 初始化 =====
async function init(){
  renderNav();
  // 恢复家长登录态：仅有 id 时先渲染登录页，登录后拿到名字再更新侧栏
  try{ const savedParent = Number(localStorage.getItem(PARENT_KEY)); if(savedParent) parentId = savedParent; }catch(e){}
  if(parentId){
    try{
      // 用一次 children 请求验证 parent 仍有效（过滤由后端保证）
      await loadChildren();
      // 从孩子列表推导不出家长名字，尽力用缓存；无缓存时侧栏显示占位
      const nm = localStorage.getItem('knoact_parent_name');
      if(nm){ parentName = nm; document.getElementById('userName').textContent = nm; document.getElementById('userAvatar').textContent = nm.slice(0,1); }
    }catch(e){ parentId = null; toast('家长会话已失效，请重新登录'); }
  }
  if(!parentId){ render(); return; }
  try{ await loadConfig(); }catch(e){}
  try{ await loadParentData(); }catch(e){}
  if(!Array.isArray(pdfDocs)) pdfDocs = [];
  try{ await reloadChildData(); }catch(e){}
  render();
}

init();
