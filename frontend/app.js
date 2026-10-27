// ===== 知学伴 前端逻辑（对接真实后端 API）=====
const API = 'http://127.0.0.1:8010';

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
  note:'<path d="M15 3h5v5"/><path d="M20 8 9 19l-4 1 1-4L17 5Z"/><path d="M7 14l3 3"/>'
};
function icon(name, size=18){
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]||''}</svg>`;
}

// 对话栏空态插图：一页纸 + 被选中的一行文字（对齐 DeepTutor CompanionWelcome 的 SelectPassageMark）
function welcomeMark(){
  const line = 'fill="rgba(142,150,145,.22)"';
  const page = 'fill="#fff" stroke="#d8dcd9"';
  const hl = 'fill="rgba(49,88,232,.16)"';
  const bar = 'fill="#3158e8"';
  return `<svg viewBox="0 0 64 72" aria-hidden="true">
    <rect x="8.5" y="4.5" width="47" height="63" rx="7" ${page}/>
    <rect x="17" y="17" width="30" height="3" rx="1.5" ${line}/>
    <rect x="17" y="25" width="26" height="3" rx="1.5" ${line}/>
    <rect x="14.5" y="30.5" width="30" height="10" rx="2.5" ${hl}/>
    <rect x="17" y="34" width="25" height="3" rx="1.5" ${bar}/>
    <path d="M44.5 29v13" stroke="#3158e8" stroke-width="1.5" stroke-linecap="round"/>
    <rect x="17" y="46" width="30" height="3" rx="1.5" ${line}/>
    <rect x="17" y="54" width="18" height="3" rx="1.5" ${line}/>
  </svg>`;
}

// ===== 通用状态 =====
const NAV = [
  ['学习首页','home'],['个性化学习','brain'],['学习中心','book'],['错题本','pen'],['学习报告','chart'],['积分商城','gift']
];
let active = '学习首页';
let points = 0;
let uid = 1;
let isParent = false;
let parentTab = '教材';
let wrongFilter = '全部';
let currentSubject = '语文';   // 首页科目切换：'语文' | '英语'

// 家长端数据缓存
let pdfDocs = [];
let pdfTab = null; // null | 'upload' | 'confirm'
let confirmDocId = null;
let knowledgeRows = [];
let goalRows = [];
let reportRows = [];
let masteryReport = null;
async function loadMasteryReport(){
  masteryReport = await api(`/api/mastery/report?user_id=${uid}`);
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

// 听写状态
let dictWords = [];   // [{id, word, extra}]
let dictState = null; // {idx, phase, wrong:[], correct:0}

// 新课学习状态
let nlState = null;   // {phase:'read'|'quiz', questions:[], picks:[], result:null}
let nlChat = [];
let nlNotes = [];
let nlNoteSel = '';
let currentText = '';
let currentLessonId = 1;

// 学习中心（听力 + 阅读）
let listenMaterial = null;
let readMaterial = null;
let centerTab = '听力理解';

// —— 与 prototype/index.html 一致的展示态（数据仍走后端）——
let completed = [];
const tasks = [
  {id:1,title:'第 12 课生词听写',detail:'今日新学 · 15 个重点生词',meta:'约 8 分钟',icon:'pen',color:'blue',points:20,tag:'当前进度',tagColor:'blue'},
  {id:2,title:'第 12 课阅读理解',detail:'重点段落 · 2 道理解题',meta:'约 12 分钟',icon:'book',color:'orange',points:30,tag:'重点巩固',tagColor:'orange'},
  {id:3,title:'旧课到期复习',detail:'第 8、10 课 · 易错知识点',meta:'约 10 分钟',icon:'brain',color:'green',points:25,tag:'遗忘曲线',tagColor:'green'}
];
let lessonProgress = {current:12, total:28, mastered:11};
let homeSnapshot = null;   // 学习首页快照（来自 /api/home/snapshot）
let dailyTasks = [];       // 今日任务（来自 /api/tasks）
let newLesson = {
  title:'第 13 课 · 精读课文',
  subject:'语文',
  text:'白鹭是一首精巧的诗。色素的配合，身段的大小，一切都很适宜。白鹤太大而嫌生硬，即使如粉红的朱鹭或灰色的苍鹭，也觉得大了一些，而且太不寻常了。然而白鹭却因为它的常见，而被人忘却了它的美。',
  questions:[
    {q:'作者把白鹭比作什么？',opts:['一首精巧的诗','一幅画','一首歌'],ans:0},
    {q:'文中提到"白鹤太大而嫌生硬"，是为了说明什么？',opts:['白鹤不好看','白鹭大小适宜、恰到好处','白鹤很稀有'],ans:1},
    {q:'作者认为白鹭的美被什么所掩盖？',opts:['它的颜色','它的常见','它的叫声'],ans:1}
  ]
};
const vizDemo = {
  math:'<div class="viz-minimap"><div class="viz-node root">分数</div><div class="viz-line"></div><div class="viz-node">分子 / 分母</div><div class="viz-line"></div><div class="viz-branch"><span class="viz-node">真分数</span><span class="viz-node">假分数</span><span class="viz-node">带分数</span></div></div><div class="viz-hint">🧭 思维导图讲解（原型示意）</div>'
};
let excerpt = '', answer = '', question = '';
let chatMessages = [];  // 沉浸页对话记录 [{role:'user'|'ai', text, citations, mode}]
let chatBusy = false;   // 是否正在等待 AI 回复
let thinkingText = '正在思考…';   // 流式期间显示的占位文案
let navOpen = true;     // 沉浸页左栏目录开关
let chatOpen = true;    // 沉浸页右栏对话开关
let navWidth = readPanelWidth('nav', 200);   // 左栏目录宽度（可拖拽）
let chatWidth = readPanelWidth('chat', 380); // 右栏对话宽度（可拖拽）
const NAV_MIN = 184, NAV_MAX = 400, CHAT_MIN = 300, CHAT_MAX = 900;  // 参照 DeepTutor 界限
function readPanelWidth(kind, fallback){
  try {
    const v = Number(localStorage.getItem('knoact.reader.' + kind + 'Width'));
    const [min,max] = kind === 'nav' ? [NAV_MIN,NAV_MAX] : [CHAT_MIN,CHAT_MAX];
    return Number.isFinite(v) && v >= min && v <= max ? v : fallback;
  } catch(e){ return fallback; }
}
function savePanelWidth(kind, w){
  try { localStorage.setItem('knoact.reader.' + kind + 'Width', String(w)); } catch(e){}
}
let chatModel = '';     // 当前选中模型（空=用默认）
let chatMode = 'chat';  // 聊天模式：chat=对话 | visualize=可视化 | solve=解题
let chatMenu = null;    // 打开中的下拉菜单：'model' | 'mode' | null
// AI 个性化学习页：真实教材数据
let plDocs = [];        // [{id, filename, subject, lesson_count, audited_count}]
let plLessons = [];     // [{id, title, subject, start_page, end_page, texts, pages, ...}]
let activeDocId = null;
let activeLessonId = null;
let lessonSearch = '';  // 课文下拉搜索关键字
// 阅读模式：整本（全书连续懒加载） vs 分课时（单课页区间）
let readMode = 'lesson';   // 'book' | 'lesson'
let fullScreen = false;    // 全屏沉浸页开关
let bookPageMap = {};      // 整本阅读：页码 -> image_path（跨课合并）

// 沉浸式阅读：标注 + 选区 + 出处
let annotations = [];   // [{id, kind, quote, note, color, page_number, rects}]
let selectedQuote = ''; // 当前拖选的原文
let selectedPage = 1;   // 选中文字所在页（课程内相对页码，1-based）
let selectedRects = ''; // 选中文字的归一化矩形坐标（JSON [[x0,y0,x1,y1],...]，对齐 DeepTutor normalisedRects）
let citations = [];     // 最近一次 AI 回答引用的句序号
let popover = {x:0, y:0, show:false}; // 选中气泡位置

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

// 聊天模式（能力）列表 —— 对齐 DeepTutor 的 capability chip
const CHAT_MODES = [
  {id:'chat', name:'对话', icon:'sparkles', desc:'普通问答'},
  {id:'quiz', name:'测验', icon:'list', desc:'3 道理解题'},
  {id:'questions', name:'主动提问', icon:'sparkles', desc:'AI 考考你'},
  {id:'visualize', name:'可视化', icon:'grid', desc:'思维导图 / 流程图'},
  {id:'solve', name:'解题', icon:'pen', desc:'分步骤讲解'},
  {id:'more', name:'更多', icon:'menu', desc:'更多能力'},
];

// 当前 provider 下可选的模型列表（内置固定列表 + 中转站动态拉取）
function getChatModelOptions(){
  const p = aiProviders.find(x => x.id === aiConfig.provider);
  const base = p ? p.models : [];
  const set = new Set([...base, ...aiModelOptions]);
  if(aiConfig.model) set.add(aiConfig.model);
  return Array.from(set);
}

// 模型 id 太长的就截断展示
function shortModelName(model){
  return model.length > 18 ? model.slice(0,18) + '…' : model;
}

// 切换 chip 下拉（model / mode），点别处关闭由 render 时的全局监听兜底
function toggleChatMenu(kind, ev){
  ev && ev.stopPropagation();
  chatMenu = chatMenu === kind ? null : kind;
  renderImmersiveChips();
}

// 生成当前打开的下拉菜单 HTML
function chatMenuHtml(){
  if(chatMenu === 'model'){
    const opts = getChatModelOptions();
    const items = opts.map(m => `<div class="mi ${(chatModel||aiConfig.model)===m?'on':''}" onclick="selectChatModel('${escapeAttr(m)}', event)"><span class="mi-name">${escapeAttr(m)}</span>${(chatModel||aiConfig.model)===m?'✓':''}</div>`).join('');
    return `<div class="im-menu">${items || '<div class="mi" style="color:#8e9691">暂无模型</div>'}</div>`;
  }
  if(chatMenu === 'mode'){
    const items = CHAT_MODES.map(m => `<div class="mi ${chatMode===m.id?'on':''}" onclick="selectChatMode('${m.id}', event)"><span class="mi-name">${icon(m.icon,14)} ${m.name}</span><span class="mi-desc">${m.desc}</span></div>`).join('');
    return `<div class="im-menu">${items}</div>`;
  }
  return '';
}

function selectChatModel(model, ev){
  ev && ev.stopPropagation();
  chatModel = model;
  chatMenu = null;
  renderImmersiveChips();
}

function selectChatMode(mode, ev){
  ev && ev.stopPropagation();
  chatMode = mode;
  chatMenu = null;
  renderImmersiveChips();
}

// 只原地刷新 chip 行（模型/模式状态 + 下拉菜单），不重挂载阅读器
function renderImmersiveChips(){
  const host = document.getElementById('im-chips');
  if(!host) return;
  host.innerHTML = `
    <button class="im-chip ${chatModel?'on':''}" onclick="toggleChatMenu('model', event)">
      ${icon('brain',14)}<span>${chatModel ? shortModelName(chatModel) : '默认模型'}</span><span class="caret">▾</span>
    </button>
    <button class="im-chip on" onclick="toggleChatMenu('mode', event)">
      ${icon(CHAT_MODES.find(m=>m.id===chatMode)?.icon||'sparkles',14)}<span>${CHAT_MODES.find(m=>m.id===chatMode)?.name||'对话'}</span><span class="caret">▾</span>
    </button>
    ${chatMenu ? chatMenuHtml() : ''}`;
}

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

// ===== 渲染入口 =====
function renderNav(){
  document.getElementById('nav').innerHTML = NAV.map(([label,ic])=>
    `<button class="nav-item ${active===label?'active':''}" onclick="setPage('${label}')">${icon(ic,19)}${label}</button>`
  ).join('');
}
function setPage(p){ active=p; renderNav(); render(); }
async function render(){
  const main = document.getElementById('main');
  let html;
  if(isParent) html = renderParent();
  else if(active==='个性化学习') html = await renderPersonalized();
  else if(active==='错题本') html = await renderWrongBook();
  else if(active==='学习首页') html = await renderHome();
  else if(active==='听写练习') html = renderDictation();
  else if(active==='新课学习') html = renderNewLesson();
  else if(active==='学习中心') html = await renderCenter();
  else if(active==='学习报告' || active==='积分商城') html = renderPlaceholder(active);
  else html = renderHome();
  main.innerHTML = html;
  if(active==='个性化学习' && !isParent){ mountPdfReader(); bindImmersiveResize(); }
}

const PLACEHOLDER = {
  // TODO: 学习报告 / 积分商城 均未实现，仅占位展示
  '学习报告':{icon:'chart',title:'学习报告',desc:'学习时长、掌握度、错误频率统计将在这里呈现。'},
  '积分商城':{icon:'gift',title:'积分商城',desc:'积分兑换平板 / 手机使用时间，将在这里完成。'}
};
function renderPlaceholder(name){
  const p = PLACEHOLDER[name];
  return `
  <header class="page-head">
    <div><h1>${name}</h1></div>
  </header>
  <div class="placeholder-page">
    <div class="ic">${icon(p.icon,32)}</div>
    <h2>${p.title}</h2>
    <p>${p.desc}</p>
    <p style="margin-top:12px;font-size:12px;color:#a0a7a2">（TODO: 此页面尚未实现，Figma 原型中未完整设计，先以占位呈现）</p>
  </div>`;
}

// ===== 首页（与 prototype 一致，数据走后端 /api/home/snapshot）=====
function setSubject(s){
  currentSubject = s;
  render();
}
async function loadHome(){
  homeSnapshot = await api(`/api/home/snapshot?user_id=${uid}&subject=${encodeURIComponent(currentSubject)}`);
  return homeSnapshot;
}
async function loadTasks(){
  const t = new Date();
  const d = `${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,'0')}-${String(t.getDate()).padStart(2,'0')}`;
  dailyTasks = await api(`/api/tasks?user_id=${uid}&date=${d}&subject=${encodeURIComponent(currentSubject)}&role=child`);
  if(!Array.isArray(dailyTasks)) dailyTasks = [];
  // 后端 list_tasks 不按 subject 过滤，客户端再按当前科目过滤一次
  dailyTasks = dailyTasks.filter(t => !t.subject || t.subject === currentSubject);
  return dailyTasks;
}
async function renderHome(){
  await loadHome();
  await loadTasks();
  const snap = homeSnapshot || {};
  const lp = snap.lesson_progress || {current:1, total:0, mastered:0};
  const pendingReview = snap.pending_review || {};
  const dictCount = snap.dict_word_count ?? 0;
  const userName = snap.user_name || '同学';
  const totalLessons = lp.total || 0;
  const masteredPct = totalLessons > 0 ? Math.round((lp.mastered/totalLessons)*100) : 0;
  const reviewOf = (subj, fallback) => {
    const n = pendingReview[subj];
    return (n && n > 0) ? `${n} 个知识点待复习` : fallback;
  };

  const taskTypeMeta = {
    dictation:{icon:'pen',color:'blue',tag:'当前进度',tagColor:'blue',meta:'约 8 分钟'},
    knowledge:{icon:'brain',color:'green',tag:'重点巩固',tagColor:'green',meta:'约 10 分钟'},
    review:{icon:'brain',color:'green',tag:'遗忘曲线',tagColor:'green',meta:'约 10 分钟'},
    reading:{icon:'book',color:'orange',tag:'阅读理解',tagColor:'orange',meta:'约 12 分钟'},
    listening:{icon:'headphones',color:'blue',tag:'听力理解',tagColor:'blue',meta:'约 8 分钟'},
    custom:{icon:'sparkles',color:'orange',tag:'自定义',tagColor:'orange',meta:''},
  };

  const taskCards = dailyTasks.map(t=>{
    const m = taskTypeMeta[t.task_type] || taskTypeMeta.custom;
    let btn;
    if(t.submit_status==='approved'){
      btn = `<button class="task-btn done">${icon('check',17)}已完成</button>`;
    } else if(t.submit_status==='submitted'){
      btn = `<button class="task-btn done">${icon('clock',17)}等待家长确认</button>`;
    } else {
      btn = `<button class="task-btn todo" onclick="doTask(${t.id},'${t.task_type}')">开始练习</button>`;
    }
    return `<article class="task-card">
      <div class="top">
        <div class="task-ic ${m.color}">${icon(m.icon,23)}</div>
        <div style="min-width:0;flex:1">
          <div class="t-head"><span class="task-tag badge-${m.tagColor}">${m.tag}</span></div>
          <h3>${t.title}</h3>
          <div class="detail">${t.detail || ''}</div>
        </div>
      </div>
      <div class="foot">
        <span class="task-meta">${icon('clock',14)}${m.meta}</span>
        <span class="task-points">${icon('star',14)}+${t.points}</span>
      </div>
      ${btn}
    </article>`;
  }).join('');

  const taskGridHtml = dailyTasks.length
    ? taskCards
    : `<div class="task-empty" style="grid-column:1/-1;text-align:center;padding:28px 16px;color:#9aa39c;font-size:14px;background:#fafbf9;border:1px dashed #e2e6e1;border-radius:14px">${icon('book',20)}<div style="margin-top:8px">今天还没有任务，先去学习中心看看吧</div></div>`;

  // TODO: 周统计未实现——后端无数据源（week_stats=null），暂渲染为空态灰条
  const weekBars = [['一',0],['二',0],['三',0],['四',0],['五',0],['六',0],['日',0]].map((d,i)=>
    `<div class="bar ${i===4?'today':''}"><div class="track"><div class="fill" style="height:6%;background:#d9ddd9"></div></div><span>${d[0]}</span></div>`
  ).join('');

  const today = new Date();
  const week = ['日','一','二','三','四','五','六'];
  const dateStr = `${today.getMonth()+1} 月 ${today.getDate()} 日，星期${week[today.getDay()]}`;
  const hour = today.getHours();
  const greet = hour<6?'夜深了':hour<12?'早上好':hour<18?'下午好':'晚上好';

  const subjectTabs = ['语文','英语'].map(s=>
    `<button class="filter-btn ${currentSubject===s?'active':''}" style="border-radius:10px;padding:6px 16px;font-size:13px;font-weight:600;color:${currentSubject===s?'#3158e8':'#778079'};background:${currentSubject===s?'#fff':'transparent'}" onclick="setSubject('${s}')">${s}</button>`
  ).join('');

  return `
  <header class="page-head">
    <div>
      <div class="date">${dateStr}</div>
      <h1>${greet}，${userName}</h1>
      <div style="margin-top:10px;display:inline-flex;gap:6px;background:#f2f4f1;border-radius:12px;padding:4px">${subjectTabs}</div>
    </div>
    <div class="head-right">
      <div class="points-pill"><span class="star">${icon('star',18)}</span>${points.toLocaleString()}<span style="font-size:12px;font-weight:400;color:#8a928d">积分</span></div>
      <div class="avatar">晨</div>
    </div>
  </header>

  <div class="hero-grid">
    <div class="hero">
      <div class="deco-ring"></div><div class="deco-glow"></div>
      <div style="position:relative;z-index:10;max-width:520px">
        <span class="tag">${icon('sparkles',14)}今日个性化学习计划</span>
        <h2>第 ${lp.current} 课重点学习与旧课复习</h2>
        <p>根据今日${currentSubject}进度和遗忘曲线，AI 安排了新课巩固与到期复习。</p>
        <button class="start-btn" onclick="document.getElementById('tasks-anchor').scrollIntoView({behavior:'smooth'})">开始今日学习 ${icon('arrow',17)}</button>
      </div>
    </div>
    <div class="weekly-card">
      <div class="head"><h2>本周学习</h2><span>暂无记录</span></div>
      <div class="bars">${weekBars}</div>
      <div class="streak"><span style="color:#f59d20">${icon('flame',17)}</span>完成今日任务，开始积累学习记录</div>
    </div>
  </div>

  <div class="progress-strip">
    <div class="p-l">
      <div class="p-ic">${icon('book',20)}</div>
      <div style="min-width:0">
        <div class="p-title">学习进度 · ${totalLessons > 0 ? `已学到第 ${lp.current} 课` : '暂无课时'}</div>
        <div class="p-sub">${totalLessons > 0 ? '完成新课阅读与答题，推进到下一课' : '请在家长端导入教材后开始学习'}</div>
      </div>
    </div>
    <div class="p-bar"><div class="p-fill" style="width:${masteredPct}%"></div></div>
    <span class="p-txt">${totalLessons > 0 ? `${lp.mastered} / ${lp.total} 课` : '—'}</span>
    <button class="next-lesson-btn" onclick="startNewLesson()">进入下一课 ${icon('arrow',16)}</button>
  </div>

  <section class="tasks-section" id="tasks-anchor">
    <div class="section-title">
      <div><h2>今日学习任务</h2><div class="sub">完成任务可获得积分奖励</div></div>
      <button style="display:flex;align-items:center;gap:4px;font-size:14px;font-weight:600;color:#3158e8">查看全部 ${icon('arrow',15)}</button>
    </div>
    <div class="task-info">
      <div class="lead"><div class="ic">${icon('sparkles',17)}</div><div><div class="t1">AI 已根据学习进度生成</div><div class="t2">今天${currentSubject}更新至第 ${lp.current} 课</div></div></div>
      <div class="divider"></div>
      <div class="composition">
        <span class="lbl">任务组成</span>
        <div class="comp-bar"><div class="seg1"></div><div class="seg2"></div></div>
        <span class="comp-legend"><b>新课巩固</b> · <b class="g">到期复习</b></span>
      </div>
      <div class="due-pill">${icon('clock',14)}根据遗忘曲线安排复习</div>
    </div>
    <div class="task-grid">${taskGridHtml}</div>
  </section>

  <div class="review-grid">
    <div class="review-card">
      <div class="head">
        <div><h2>智能复习</h2><div class="sub">根据遗忘曲线，为你安排最佳复习时间</div></div>
        <div class="head-ic">${icon('brain',20)}</div>
      </div>
      <div class="review-items">
        <button class="review-item" onclick="setPage('学习中心')"><div class="review-ic yw serif">语</div><div style="flex:1"><div class="name">语文基础知识</div><div class="cnt">${reviewOf('语文','暂无待复习，继续保持')}</div></div>${icon('arrow',16)}</button>
        <button class="review-item" onclick="setPage('学习中心')"><div class="review-ic en serif">En</div><div style="flex:1"><div class="name">英语基础知识</div><div class="cnt">${reviewOf('英语','暂无待复习，继续保持')}</div></div>${icon('arrow',16)}</button>
      </div>
    </div>
    <div class="redeem-card">
      <div class="head">
        <div><div class="lbl">积分兑换</div><h2>劳逸结合，快乐成长</h2></div>
        <div class="pts">${icon('star',17)}${points}</div>
      </div>
      <div class="redeem-items">
        <button class="redeem-item" onclick="redeemHome(300,'tablet',30)">${icon('tablet',25)}<div class="name">平板 30 分钟</div><div class="cost">300 积分兑换</div></button>
        <button class="redeem-item" onclick="redeemHome(200,'phone',20)">${icon('phone',25)}<div class="name">手机 20 分钟</div><div class="cost">200 积分兑换</div></button>
      </div>
    </div>
  </div>`;
}

function finishTask(id, reward){
  if(completed.includes(id)) return;
  completed.push(id);
  points += reward;
  render();
  toast(`完成任务，获得 ${reward} 积分`);
}
async function doTask(id, type){
  if(type==='dictation'){ await startDictation(); return; }
  if(type==='reading'){ await loadCenter(); centerTab='阅读理解'; setPage('学习中心'); }
  else if(type==='listening'){ await loadCenter(); centerTab='听力理解'; setPage('学习中心'); }
  else if(type==='knowledge' || type==='review'){ setPage('学习中心'); }
  // 完成练习后标记已提交，等待家长完成审核（听写类在 finishDictation 提交）
  if(type!=='dictation'){
    await api(`/api/tasks/${id}/submit`, {method:'POST'});
    toast('已提交，等待家长确认');
  }
  render();
}
async function redeemHome(cost, device, minutes){
  const d = await api('/api/points/redeem', {method:'POST', body:{user_id:uid, device, minutes}});
  if(d.success){
    await loadPoints();
    render();
    toast(`已兑换${device==='tablet'?'平板':'手机'} ${minutes} 分钟，等待家长确认`);
  } else {
    toast('积分还不够，再完成几个任务吧');
  }
}

// ===== 听写练习 =====
async function startDictation(){
  dictWords = await api(`/api/dictation/words?user_id=${uid}`);
  if(!dictWords || !dictWords.length){ toast('当前词库暂无生词'); return; }
  dictState = {idx:0, phase:'listen', wrong:[], correct:0, input:''};
  setPage('听写练习');
}
function dictWord(){
  const raw = dictWords[dictState.idx];
  if(!raw) return null;
  if(raw.w) return raw;
  const parts = (raw.extra||'').split(/\s+/);
  return {w: raw.word, pinyin: parts[0]||'', meaning: parts.slice(1).join(' ')||raw.extra||'', id: raw.id};
}
function speakDict(){
  const w = dictWord();
  const text = w.w;
  playTts(text);
  const btn = document.querySelector('.dict-play');
  if(btn){ btn.classList.add('playing'); btn.innerHTML = icon('headphones',17)+'播放中…';
    setTimeout(()=>{ const b=document.querySelector('.dict-play'); if(b){ b.classList.remove('playing'); b.innerHTML = icon('headphones',17)+'再听一遍'; } },1600);
  }
}
// 播放后端 TTS：真实 provider 返回音频字节则转 blob 播放，fake 回退浏览器合成
async function playTts(text){
  try{
    const r = await fetch(`${API}/api/tts/synthesize?text=${encodeURIComponent(text)}`);
    const ct = r.headers.get('content-type')||'';
    if(ct.includes('audio')){
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = new Audio(url);
      a.onended = ()=>URL.revokeObjectURL(url);
      a.play();
    } else {
      const d = await r.json().catch(()=>({}));
      if(d && d.use_browser_tts) browserSpeak(text);
      else browserSpeak(text);
    }
  }catch(e){ browserSpeak(text); }
}
function browserSpeak(text){
  if(window.speechSynthesis){
    const u = new SpeechSynthesisUtterance(text);
    u.lang = /[a-zA-Z]/.test(text)?'en-US':'zh-CN'; u.rate = 0.9;
    speechSynthesis.cancel(); speechSynthesis.speak(u);
  }
}
function dictInput(v){ if(dictState) dictState.input = v; }
async function submitDict(){
  const s = dictState, w = dictWord();
  const right = s.input.trim() === w.w;
  s.tried = true; s.phase = 'feedback';
  await api('/api/dictation/grade', {method:'POST', body:{user_id:uid, word:w.w, word_id:w.id, answer:s.input}});
  if(right){ s.correct++; }
  else { s.wrong.push({word:w.w, pinyin:w.pinyin, meaning:w.meaning, yours:s.input.trim(), id:w.id}); }
  render();
}
function dictNext(){
  const s = dictState;
  s.idx++;
  if(s.idx >= dictWords.length){ s.phase='done'; }
  else { s.phase='listen'; s.tried=false; s.input=''; }
  render();
}
async function finishDictation(){
  const s = dictState;
  const wrongWords = s.wrong.map(x=>({word:x.word, your_answer:x.yours, word_id:x.id}));
  const d = await api('/api/dictation/complete', {method:'POST', body:{user_id:uid, correct:s.correct, wrong:s.wrong.length, wrong_words:wrongWords}});
  if(!completed.includes(1)) completed.push(1);

  // 查找今天的听写任务，标记已提交并引导拍照上传，家长核对后发放积分
  try {
    const t = new Date();
    const day = `${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,'0')}-${String(t.getDate()).padStart(2,'0')}`;
    const tasks = await api(`/api/tasks?user_id=${uid}&date=${day}&role=child`);
    const list = Array.isArray(tasks) ? tasks : (tasks && tasks.tasks) || [];
    const task = list.find(x => x && x.task_type === 'dictation' && x.submit_status !== 'approved');
    if(task && task.id){
      await api('/api/tasks/'+task.id+'/submit', {method:'POST'});
      if(confirm('请拍照上传你的听写字迹，家长核对后发放积分。现在上传？')){
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = async () => {
          if(!input.files || !input.files[0]) return;
          const fd = new FormData();
          fd.append('file', input.files[0]);
          const r = await apiForm(`/api/tasks/${task.id}/upload-photo`, fd);
          if(r && r.ok) toast('已上传，等待家长确认');
          else toast('上传失败，请重试');
        };
        input.click();
      }
    }
  } catch(e){ /* 任务查找失败不影响主流程 */ }

  await loadPoints();
  setPage('学习首页');
  toast(`完成打卡，获得 ${d.points_awarded} 积分`);
}
function renderDictation(){
  const s = dictState;
  if(!s) return '<div class="placeholder-page"><h2>听写练习</h2><p>请从首页点击任务进入。</p></div>';
  const total = dictWords.length;
  const progress = Math.round(s.idx / total * 100);

  if(s.phase==='done'){
    const wrongCount = s.wrong.length;
    return `<header class="page-head"><div><h1>第 12 课生词听写</h1></div></header>
    <div class="dict-wrap">
      <div class="dict-done">
        <div class="big">${icon('check',24)} 听写完成！</div>
        <div class="sub">本次共听写 ${total} 个生词</div>
        <div class="stat">
          <div><div class="k">正确</div><div class="v g">${s.correct}</div></div>
          <div><div class="k">错误</div><div class="v r">${wrongCount}</div></div>
        </div>
        <p style="margin-top:20px;font-size:13px;color:var(--gray2)">${wrongCount?`${wrongCount} 个错词已自动收录进错题本`:'全部正确，继续保持！'}</p>
        <button class="dict-next" onclick="finishDictation()">${icon('star',17)} 完成打卡 +积分</button>
      </div>
    </div>`;
  }

  const w = dictWord();
  const feedback = s.phase==='feedback' ? (()=>{
    const right = !s.wrong.some(x=>x.word===w.w);
    return `<div class="dict-feedback ${right?'right':'wrong'}">
      <div class="fb-head">${right?icon('check',18)+'回答正确':icon('pen',18)+'写错了，看这里'}</div>
      <div class="fb-body">${right?`「${w.w}」拼写正确，${w.meaning}`:`正确写法是「${w.w}」（${w.pinyin}）<br>${w.meaning}`}</div>
    </div>
    <button class="dict-next" onclick="dictNext()">${s.idx===total-1?'查看结果':'下一个词'} ${icon('arrow',16)}</button>`;
  })() : '';

  return `<header class="page-head">
    <div><h1>第 12 课生词听写</h1></div>
    <button class="btn-ghost" onclick="setPage('学习首页')">退出练习</button>
  </header>
  <div class="dict-wrap">
    <div class="dict-progress">
      <span class="ptxt">第 ${s.idx+1} / ${total} 个</span>
      <div class="pbar"><div class="pfill" style="width:${progress}%"></div></div>
      <span class="ptxt">${total-s.idx} 个剩余</span>
    </div>
    <div class="dict-card">
      <div class="dict-word-ic">${icon('headphones',40)}</div>
      <div class="dict-hint">点击播放，听写这个词</div>
      <button class="dict-play" onclick="speakDict()">${icon('play',17)} 播放词语</button>
      <div style="margin-top:24px">
        <input class="dict-input" placeholder="输入你听到的词语" value="${s.input||''}" oninput="dictInput(this.value)" ${s.phase==='feedback'?'disabled':''}>
      </div>
      <button class="dict-enter" onclick="submitDict()" ${s.phase==='feedback'||!s.input.trim()?'disabled':''}>确认提交</button>
      ${feedback}
    </div>
  </div>`;
}

// ===== 新课学习（与 prototype 一致 + API）=====
async function startNewLesson(){
  nlState = {phase:'read', picks:[], result:null, pass:false};
  nlChat = []; nlNotes = []; nlNoteSel = '';
  try {
    const mat = await api(`/api/reading/material?lesson_id=${currentLessonId}`);
    if(mat.text) newLesson = {...newLesson, text: mat.text};
  } catch (_) { /* 使用默认课文 */ }
  currentText = newLesson.text;
  setPage('新课学习');
}
function nlStartQuiz(){ nlState.phase='quiz'; render(); }
function nlPick(qi, oi){ nlState.picks[qi]=oi; render(); }
function nlSubmit(){
  const s=nlState; let right=0;
  newLesson.questions.forEach((q,i)=>{ if(s.picks[i]===q.ans) right++; });
  const total=newLesson.questions.length;
  const rate=right/total;
  s.pass = rate >= 0.6;
  s.result={right,total,rate};
  render();
}
async function nlAdvance(){
  const s=nlState;
  const correct = s.result ? s.result.right : newLesson.questions.length;
  const total = s.result ? s.result.total : newLesson.questions.length;
  const d = await api('/api/progress/advance', {method:'POST', body:{user_id:uid, correct, total}});
  if(d.passed){
    lessonProgress.current += 1;
    lessonProgress.mastered += 1;
    await loadPoints();
    setPage('学习首页');
    toast('进度已推进到第 '+(lessonProgress.current+1)+' 课');
  } else {
    toast('正确率未达标，请重看内容再试');
  }
}
function nlRetryRead(){ nlState.phase='read'; nlState.picks=[]; nlState.result=null; render(); }
async function nlAsk(){
  const v=(document.getElementById('nlAskInput')||{}).value||'';
  if(!v.trim()) return;
  nlChat.push({role:'q',text:v.trim()});
  const isMath = newLesson.subject==='数学';
  try {
    const d = await api('/api/ask', {method:'POST', body:{lesson_id:currentLessonId, question:v.trim(), context:currentText}});
    nlChat.push({role:'a', text: d.answer || `关于「${v.trim().slice(0,14)}」，结合这段课文的意思是……`, viz: isMath?vizDemo.math:null});
  } catch (_) {
    nlChat.push({role:'a', text: isMath?'让我用思维导图给你讲清楚这个概念：':`关于「${v.trim().slice(0,14)}」，结合这段课文的意思是……`, viz: isMath?vizDemo.math:null});
  }
  render();
  const el=document.querySelector('.nl-chat-body'); if(el) el.scrollTop=el.scrollHeight;
}
function nlQuick(q){ document.getElementById('nlAskInput').value=q; nlAsk(); }
function nlCaptureSel(){ const sel = window.getSelection ? window.getSelection().toString().trim() : ''; nlNoteSel = sel; render(); }
function nlAddNote(){
  const v=(document.getElementById('nlNoteInput')||{}).value||'';
  if(!v.trim()) return;
  api('/api/notes', {method:'POST', body:{lesson_id:currentLessonId, author_role:'child', content:v.trim(), anchor_text:nlNoteSel||''}});
  nlNotes.push({id:Date.now(), anchor:nlNoteSel||'', text:v.trim(), page:'第 38–41 页', time:'刚刚'});
  nlNoteSel=''; render();
}
function nlDelNote(id){ nlNotes = nlNotes.filter(n=>n.id!==id); render(); }
function nlNoteHint(){ toast('划词记笔记：先用鼠标选中教材里的一段文字'); }
function renderNewLesson(){
  const s=nlState;
  if(!s) return '<div class="placeholder-page"><h2>新课学习</h2><p>请从首页进入。</p></div>';

  if(s.phase==='read'){
    const isMath = newLesson.subject==='数学';
    const chatMsgs = nlChat.map(m=>`
      <div class="nl-msg ${m.role}">
        ${m.role==='q'?'<div class="bubble q">'+m.text+'</div>':'<div class="bubble a">'+m.text+(m.viz?'<div class="viz-wrap">'+m.viz+'</div>':'')+'</div>'}
      </div>`).join('');
    const noteItems = nlNotes.map(n=>`
      <div class="nl-note-item">
        ${n.anchor?`<div class="nl-note-anchor">「${n.anchor.length>18?n.anchor.slice(0,18)+'…':n.anchor}」</div>`:''}
        <div class="nl-note-text">${n.text}</div>
        <div class="nl-note-meta">${n.page} · ${n.time}<span class="nl-note-del" onclick="nlDelNote(${n.id})">删除</span></div>
      </div>`).join('');
    return `<header class="page-head"><div><h1>进入下一课</h1></div><button class="btn-ghost" onclick="setPage('学习首页')">退出</button></header>
    <div class="newlesson-wrap nl-full">
      <div class="nl-read-top">
        <span class="nl-tag read" style="display:inline-flex">${icon('book',14)} 第 1 步 · 阅读教材内容${isMath?' · 数学':''}</span>
        <span class="nl-read-hint">${icon('sparkles',14)} 边读边问 · 不懂就问</span>
      </div>
      <div class="nl-immersive">
        <div class="nl-reader">
          <div class="nl-reader-head"><span class="nl-unit">${isMath?'第 5 单元':'第十二课'}</span><span>原版教材页面</span></div>
          <div class="nl-page" onmouseup="nlCaptureSel()">
            <h2 class="serif">${newLesson.title}</h2>
            <div class="nl-content">${newLesson.text}</div>
            ${isMath?'<div class="nl-math-note">📐 数学内容以思维导图 / 动画 / 交互图讲解，选中公式或概念即可提问</div>':''}
            <div class="nl-note-tip" onclick="nlNoteHint()">${icon('pen',14)} 划词记笔记：选中文字后到这里写笔记</div>
          </div>
          <button class="nl-read-done" onclick="nlStartQuiz()">我已读完，去答题 ${icon('arrow',16)}</button>
        </div>
        <div class="nl-chat">
          <div class="nl-chat-head">${icon('sparkles',16)} 不懂就问 · AI 讲解${isMath?'（可视化）':''}</div>
          <div class="nl-chat-body">
            ${nlChat.length?chatMsgs:`<div class="nl-chat-empty">${icon('sparkles',24)}<p>看到不懂的地方，划词或输入问题，AI 结合教材为你讲解。</p></div>`}
          </div>
          <div class="nl-quick" onclick="nlQuick('${isMath?'这道题的解题思路是什么？':'这段话是什么意思？'}')">${isMath?'这道题的解题思路是什么？':'这段话是什么意思？'}｜${isMath?'这个公式怎么推导？':'帮我总结知识点'}</div>
          <div class="nl-chat-input"><input id="nlAskInput" placeholder="输入不懂的地方…" onkeydown="if(event.key==='Enter')nlAsk()"><button class="send-btn" onclick="nlAsk()">提问</button></div>
        </div>
      </div>
      <div class="nl-notes">
        <div class="nl-notes-head">${icon('pen',16)} 我的笔记（本课）<span class="nl-notes-count">${nlNotes.length} 条</span></div>
        ${nlNoteSel?`<div class="nl-note-editor">
          <div class="nl-note-anchor">${icon('check',13)} 已选中：「${nlNoteSel.length>20?nlNoteSel.slice(0,20)+'…':nlNoteSel}」</div>
          <div class="nl-note-input-row"><input id="nlNoteInput" placeholder="写下你的笔记…" onkeydown="if(event.key==='Enter')nlAddNote()"><button class="send-btn" onclick="nlAddNote()">保存</button></div>
        </div>`:`<div class="nl-note-editor"><div class="nl-note-input-row"><input id="nlNoteInput" placeholder="写一条自由笔记…" onkeydown="if(event.key==='Enter')nlAddNote()"><button class="send-btn" onclick="nlAddNote()">保存</button></div></div>`}
        <div class="nl-note-list">${nlNotes.length?noteItems:`<div class="nl-chat-empty" style="padding:16px">还没有笔记，选中教材文字或直接写一条吧。</div>`}</div>
      </div>
    </div>`;
  }

  const items = newLesson.questions.map((q,qi)=>{
    const opts = q.opts.map((o,oi)=>`<button class="nl-opt ${s.picks[qi]===oi?'sel':''}" onclick="nlPick(${qi},${oi})">${String.fromCharCode(65+oi)}. ${o}</button>`).join('');
    return `<div class="nl-quiz-item"><div class="qq">${qi+1}. ${q.q}</div><div class="nl-options">${opts}</div></div>`;
  }).join('');

  const answered = s.picks.filter(p=>p!==undefined).length;
  const allAnswered = answered === newLesson.questions.length;

  let result='';
  if(s.result){
    const retryOn = s.pass ? 'nlAdvance()' : 'nlRetryRead()';
    result = `<div class="nl-result ${s.pass?'pass':'fail'}">
      <div class="r-head">${s.pass?icon('check',18)+'答对了！通过':icon('pen',18)+'还没达标'}</div>
      <div class="r-body">${s.pass?'正确率 '+Math.round(s.result.rate*100)+'%，可以进入下一课':'正确率 '+Math.round(s.result.rate*100)+'%，需达到 60% 才能推进，重看内容再试一次'}</div>
    </div>
    <button class="nl-retry" onclick="${retryOn}">${s.pass?'进入下一课':'返回重看内容'}</button>`;
  }

  return `<header class="page-head"><div><h1>进入下一课</h1></div><button class="btn-ghost" onclick="setPage('学习首页')">退出</button></header>
  <div class="newlesson-wrap">
    <div class="nl-step">
      <span class="nl-tag quiz">${icon('pen',14)} 第 2 步 · 回答理解题</span>
      <h2>检验是否读懂</h2>
      ${items}
      ${result || `<button class="nl-submit" onclick="nlSubmit()" ${allAnswered?'':'disabled'}>提交答案</button>`}
    </div>
  </div>`;
}

async function loadCenter(){
  listenMaterial = await api(`/api/listening/material?user_id=${uid}`);
  readMaterial = await api(`/api/reading/material?lesson_id=${currentLessonId}`);
}

function centerSetTab(t){ centerTab = t; centerRevealed = {}; centerPick = {}; render(); }

function playListening(){
  const txt = (listenMaterial && listenMaterial.text) ? listenMaterial.text.replace(/\n/g, ' ') : '';
  if(txt) playTts(txt);
}

// 理解题作答：答错收录错题本，答对无操作
let centerRevealed = {};  // 已揭晓答案的题（key: src:idx）
let centerPick = {};      // 用户作答（key: src:idx）

function centerKey(src, qi){ return src + ':' + qi; }
async function centerAnswer(src, qi){
  const k = centerKey(src, qi);
  if(centerRevealed[k]) return;
  const q = (src==='listening' ? (listenMaterial?.questions||[]) : (readMaterial?.questions||[]))[qi];
  if(!q) return;
  centerRevealed[k] = true;
  const wrong = (centerPick[k] || '').trim() !== (q.answer || '').trim();
  if(wrong){
    await api('/api/review/submit', {method:'POST', body:{
      user_id:uid, question:q.question, your_answer:centerPick[k]||'',
      correct_answer:q.answer, source_type:src,
    }});
    toast('答错了，已收录进错题本');
  } else {
    toast('回答正确！');
  }
  render();
}
function centerInput(src, qi, v){ centerPick[centerKey(src, qi)] = v; }

async function renderCenter(){
  await loadCenter();
  const tabs = [['听力理解','headphones'],['阅读理解','book']].map(([name,ic])=>
    `<button class="center-tab ${centerTab===name?'active':''}" onclick="centerSetTab('${name}')">${icon(ic,16)}${name}</button>`
  ).join('');

  let body = '';
  if(centerTab==='听力理解'){
    const m = listenMaterial;
    if(!m || !m.text){
      body = `<div class="center-empty">${icon('headphones',32)}<p>暂无听力材料，AI 将根据学习进度生成对话。</p></div>`;
    } else {
      const qs = (m.questions||[]).map((q,qi)=>{
        const k = centerKey('listening', qi);
        const revealed = centerRevealed[k];
        const picked = centerPick[k]||'';
        return `<div class="center-question">
          <div class="cq-q">${qi+1}. ${q.question}</div>
          ${revealed
            ? `<div class="cq-ans ${picked.trim()===q.answer.trim()?'right':'wrong'}">${icon('check',15)} 答案：${q.answer}</div>`
            : `<div class="cq-form">
                <input class="cq-input" placeholder="输入你的答案" value="${picked}" oninput="centerInput('listening',${qi}, this.value)"/>
                <button class="cq-btn" onclick="centerAnswer('listening',${qi})">提交</button>
              </div>`}
        </div>`;
      }).join('');
      body = `
        <div class="center-panel">
          <div class="center-material">
            <div class="cm-head">${icon('volume',16)} 听力对话</div>
            <div class="cm-text">${m.text}</div>
            <button class="center-play" onclick="playListening()">${icon('play',16)} 播放对话</button>
          </div>
          <div class="center-questions">${qs}</div>
        </div>`;
    }
  } else {
    const m = readMaterial;
    if(!m || !m.text){
      body = `<div class="center-empty">${icon('book',32)}<p>暂无阅读材料，请在家长端导入教材。</p></div>`;
    } else {
      const qs = (m.questions||[]).map((q,qi)=>{
        const k = centerKey('reading', qi);
        const revealed = centerRevealed[k];
        const picked = centerPick[k]||'';
        return `<div class="center-question">
          <div class="cq-q">${qi+1}. ${q.question}</div>
          ${revealed
            ? `<div class="cq-ans ${picked.trim()===q.answer.trim()?'right':'wrong'}">${icon('check',15)} 答案：${q.answer}</div>`
            : `<div class="cq-form">
                <input class="cq-input" placeholder="输入你的答案" value="${picked}" oninput="centerInput('reading',${qi}, this.value)"/>
                <button class="cq-btn" onclick="centerAnswer('reading',${qi})">提交</button>
              </div>`}
        </div>`;
      }).join('');
      body = `
        <div class="center-panel">
          <div class="center-material">
            <div class="cm-head">${icon('book',16)} 阅读课文</div>
            <div class="cm-text">${m.text}</div>
          </div>
          <div class="center-questions">${qs}</div>
        </div>`;
    }
  }

  return `<header class="page-head"><div><h1>学习中心</h1></div></header>
  <div class="center-tabs">
    <button class="center-tab dict" onclick="startDictation()">${icon('pen',16)}听写练习</button>
    ${tabs}
  </div>
  ${body}`;
}

// ===== 错题本 =====
let mistakes = [];
async function loadMistakes(){
  mistakes = await api(`/api/mistakes?user_id=${uid}`);
}
async function renderWrongBook(){
  const [mistakeList, rep] = await Promise.all([
    api(`/api/mistakes?user_id=${uid}`),
    api(`/api/mistakes/report?user_id=${uid}`)
  ]);
  mistakes = mistakeList;
  const subjOf = s => s==='dictation'||s==='reading'?'语文':'英语';
  const srcName = {dictation:'第 12 课 · 生词听写', review:'基础知识复习', listening:'Unit 4 · 单词听写', reading:'第 10 课 · 阅读理解', goal:'目标考核'};
  const reasonOf = m => m.mistake_count > 2 ? '反复出错，需加强' : (m.source_type==='dictation'?'形近字混淆':'理解偏差');
  const visible = mistakes.filter(m => (wrongFilter==='全部'||subjOf(m.source_type)===wrongFilter) && m.consecutive_correct < 3);
  const pending = mistakes.filter(m => m.consecutive_correct < 3).length;
  const corrected = mistakes.filter(m => m.consecutive_correct > 0).length;
  const topWeak = rep.rows?.[0]?.name || '字词辨析';

  const cards = visible.map(m=>`
    <article class="wrong-card">
      <div class="top">
        <div class="meta">
          <span class="subj-tag ${subjOf(m.source_type)==='语文'?'badge-blue':'badge-orange'}">${subjOf(m.source_type)}</span>
          <span class="src">${srcName[m.source_type]||m.source_type}</span>
        </div>
        <span class="date">近期</span>
      </div>
      <div class="q">${m.question}</div>
      <div class="wrong-ans">
        <div class="wa bad"><div class="lbl">你的答案</div><div class="val">${m.your_answer||'（空）'}</div></div>
        <div class="wa good"><div class="lbl">正确答案</div><div class="val">${m.correct_answer}</div></div>
      </div>
      <div class="foot">
        <div class="reason">${icon('brain',15)}<b>错误原因：</b>${reasonOf(m)}<span style="color:#a0a7a2;margin-left:8px">已复习 ${m.consecutive_correct} 次</span></div>
        <div class="actions"><button class="btn-ghost">再练一道</button><button class="btn-primary" onclick="markMastered(${m.id})">标记已掌握</button></div>
      </div>
    </article>`).join('');

  const empty = visible.length===0 ? `<div style="text-align:center;padding:64px 0"><div style="width:48px;height:48px;border-radius:50%;background:#eaf7ef;color:#2e8b5a;display:grid;place-items:center;margin:0 auto">${icon('check',20)}</div><h3 style="margin-top:16px;font-weight:700">当前错题都掌握了</h3><p style="margin-top:4px;font-size:14px;color:#8e9691">继续保持，新的错题会自动出现在这里。</p></div>` : cards;

  return `
  <header class="page-head">
    <div>
      <div class="crumb">${icon('pen',16)}智能错题本</div>
      <h1 class="big">从错误中真正学会</h1>
      <p class="desc">练习中的错题会自动收录，并根据掌握情况安排再次复习。</p>
    </div>
    <div style="display:flex;align-items:center;gap:8px;border-radius:12px;background:#eaf7ef;padding:12px 16px;font-size:14px;font-weight:600;color:#2e8055">${icon('check',17)}已开启自动收录</div>
  </header>

  <div class="stats-grid">
    <div class="stat-card"><div class="t">待掌握错题</div><div class="row"><span class="v">${pending}</span><span class="d badge-blue">本周新增 3 题</span></div></div>
    <div class="stat-card"><div class="t">本周已订正</div><div class="row"><span class="v">${corrected}</span><span class="d badge-green">掌握后移出复习</span></div></div>
    <div class="stat-card"><div class="t">重点薄弱项</div><div class="row"><span class="v">${topWeak}</span><span class="d badge-orange">错误率 24%</span></div></div>
  </div>

  <section class="wrong-list">
    <div class="head">
      <div><h2>错题列表</h2><div class="sub">AI 会分析错误原因，并在合适的时间生成同类题</div></div>
      <div class="filter">
        ${['全部','语文','英语'].map(s=>`<button class="${wrongFilter===s?'active':''}" onclick="setFilter('${s}')">${s}</button>`).join('')}
      </div>
    </div>
    <div class="wrong-items">${empty}</div>
  </section>`;
}
function setFilter(s){ wrongFilter=s; render(); }
async function markMastered(id){
  let d;
  for(let i=0;i<3;i++) d = await api(`/api/mistakes/${id}/correct`, {method:'POST'});
  toast(d?.removed ? '已标记掌握，移出复习' : '已标记掌握，移出复习');
  render();
}

// ===== 个性化学习（接真实教材数据）=====
async function selectDoc(id){
  activeDocId = id;
  activeLessonId = null;
  lessonSearch = '';   // 切换教材时清空课文搜索
  plLessons = await api(`/api/pdf/documents/${id}/lessons`);
  render();
}
function selectLesson(id){
  activeLessonId = id;
  const l = plLessons.find(x=>x.id===id);
  currentLessonId = id;
  citations = [];
  // 选中课程后，默认把第一段文本填入「选中的教材内容」
  if(l && l.texts && l.texts.length){
    excerpt = splitSentences(l.texts[0])[0] || l.texts[0];
  }
  render();
  loadAnnotations();
}
function chooseReadMode(mode){
  readMode = mode;
  fullScreen = true;
  // 切换到整本模式时，合并整本教材所有课的页面图片映射，供懒加载使用
  if(mode === 'book'){
    bookPageMap = {};
    plLessons.forEach(l=>{
      (l.pages || []).forEach(p=>{ bookPageMap[p.page_number] = p.image_path; });
    });
    // 整本模式若尚未选中具体课文，默认落到第一课，保证标注/提问有 lesson_id 可用
    if(!activeLessonId && plLessons.length){ activeLessonId = plLessons[0].id; currentLessonId = plLessons[0].id; }
  }
  // 清空上一次的挂载标识，强制重新挂载（整本/分课页区间不同）
  _mountedKey = null;
  _pdfDoc = null;
  render();
  if(activeLessonId) loadAnnotations();
}
function lessonForPage(page){
  // 按课页区间定位某物理页属于哪一课（整本模式标注落库用）
  for(const l of plLessons){
    if(page >= l.start_page && page <= l.end_page) return l;
  }
  return null;
}
function enterImmersive(){
  fullScreen = true;
  _mountedKey = null;
  _pdfDoc = null;
  render();
  if(activeLessonId) loadAnnotations();
}
function exitImmersive(){
  fullScreen = false;
  readMode = 'lesson';
  _mountedKey = null;
  _pdfDoc = null;
  render();
  if(activeLessonId) loadAnnotations();
}

function splitSentences(text){
  if(!text) return [];
  // 按句末标点 + 换行切句
  return text.split(/(?<=[。！？!?])|\n+/).map(s=>s.trim()).filter(Boolean);
}
function renderLessonOptions(){
  // 只更新课文下拉（搜索框 + 选项），避免整体 render() 重挂载 PDF 阅读器
  const sel = document.querySelector('.lesson-select');
  if(!sel) return;
  const kw = (lessonSearch || '').trim().toLowerCase();
  const matched = kw ? plLessons.filter(l => (l.title||'').toLowerCase().includes(kw)) : plLessons;
  sel.innerHTML = `
    <div class="lesson-search">
      ${icon('search',16)}
      <input id="lesson-search-input" placeholder="搜索课文…" value="${escapeAttr(lessonSearch)}"
             oninput="lessonSearch=this.value;renderLessonOptions()" />
      ${lessonSearch?`<button class="ls-clear" onclick="lessonSearch='';renderLessonOptions()" title="清空">×</button>`:''}
    </div>
    <div class="lesson-options" id="lesson-options">
      ${matched.map(l=>`
        <button class="lesson-option ${activeLessonId===l.id?'active':''}" onclick="selectLesson(${l.id})">
          <span class="lo-title">${escapeAttr(l.title)}</span>
          <span class="lo-pages">第 ${l.start_page}–${l.end_page} 页</span>
        </button>`).join('') || `<div class="lo-empty">没有匹配的课文</div>`}
    </div>`;
  // 恢复输入框焦点到末尾，避免每次按键失焦
  const inp = sel.querySelector('#lesson-search-input');
  if(inp){ inp.focus(); const v = inp.value; inp.setSelectionRange(v.length, v.length); }
}
async function renderPersonalized(){
  if(plDocs.length===0){
    plDocs = await api('/api/pdf/documents');
  }
  const books = plDocs.map(d=>`
    <button class="book-card ${activeDocId===d.id?'active':''}" onclick="selectDoc(${d.id})">
      <div class="book-spine ${d.subject==='语文'?'blue':'orange'}">${d.subject}</div>
      <div style="min-width:0;flex:1"><div class="nm">${d.filename}</div><div class="tp">${d.lesson_count} 课 · 已审核 ${d.audited_count} 课</div></div>
      ${activeDocId===d.id?'<span style="width:20px;height:20px;border-radius:50%;background:#3158e8;color:#fff;display:grid;place-items:center">'+icon('check',12)+'</span>':''}
    </button>`).join('');

  // 课程列表：搜索下拉
  let lessonList = '';
  if(activeDocId && plLessons.length){
    const kw = (lessonSearch || '').trim().toLowerCase();
    const matched = kw ? plLessons.filter(l => (l.title||'').toLowerCase().includes(kw)) : plLessons;
    const opts = matched.map(l=>`
      <button class="lesson-option ${activeLessonId===l.id?'active':''}" onclick="selectLesson(${l.id})">
        <span class="lo-title">${escapeAttr(l.title)}</span>
        <span class="lo-pages">第 ${l.start_page}–${l.end_page} 页</span>
      </button>`).join('');
    lessonList = `
      <div class="lesson-select">
        <div class="lesson-search">
          ${icon('search',16)}
          <input id="lesson-search-input" placeholder="搜索课文…" value="${escapeAttr(lessonSearch)}"
                 oninput="lessonSearch=this.value;renderLessonOptions()" />
          ${lessonSearch?`<button class="ls-clear" onclick="lessonSearch='';renderLessonOptions()" title="清空">×</button>`:''}
        </div>
        <div class="lesson-options" id="lesson-options">
          ${opts || `<div class="lo-empty">没有匹配的课文</div>`}
        </div>
      </div>`;
  }

  // 当前课程
  const lesson = activeLessonId ? plLessons.find(x=>x.id===activeLessonId) : null;
  const activeDoc = activeDocId ? plDocs.find(d=>d.id===activeDocId) : null;

  // 阅读模式切换（选好教材后出现）：整本连续阅读 vs 分课时阅读
  let modeBar = '';
  if(activeDocId && activeDoc && activeDoc.storage_path){
    const bm = readMode==='book';
    modeBar = `
      <div class="read-mode-bar">
        <button class="rm-btn ${bm?'active':''}" onclick="chooseReadMode('book')">${icon('book',15)}整本阅读</button>
        <button class="rm-btn ${bm?'':'active'}" onclick="chooseReadMode('lesson')">${icon('grid',15)}分课时阅读</button>
      </div>`;
  }

  // 正文区：pdf.js 阅读器（可拖选文字），兜底回 PNG 图
  let readerBody = `<div style="text-align:center;padding:48px 0;color:#8e9691">${icon('book',32)}<p style="margin-top:8px;font-size:13px">选择左侧教材与课程，在正文中拖选文字追问</p></div>`;
  if(lesson && activeDoc && activeDoc.storage_path){
    readerBody = `<div id="pdf-reader" data-doc-id="${activeDocId}" data-lesson-id="${lesson.id}" data-start="${lesson.start_page}" data-end="${lesson.end_page}" data-storage="${escapeAttr(activeDoc.storage_path)}"></div>`;
  }

  // 我的标注（划线/笔记/生词），内联在正文旁 —— 由 renderAnnotationList 原地更新
  let annotationList = '';
  if(lesson){
    annotationList = `<section class="pl-sentences" id="annotation-list" style="margin-top:12px"></section>`;
  }

  // ===== 全屏沉浸页（三栏：目录 / 阅读器 / 对话）=====
  if(fullScreen && activeDoc && activeDoc.storage_path){
    const isBook = readMode === 'book';
    const title = isBook ? activeDoc.filename : (lesson ? lesson.title : '未选择课程');
    const sub = isBook ? `整本连续阅读 · 共 ${plLessons.length} 课` : (lesson ? `第 ${lesson.start_page}–${lesson.end_page} 页` : '');
    const readerId = 'pdf-reader-fs';
    // 整本：data-mode="book"（懒加载全书）；分课时：data-start/end 指定页区间
    const readerAttrs = isBook
      ? `id="${readerId}" data-mode="book" data-doc-id="${activeDocId}" data-storage="${escapeAttr(activeDoc.storage_path)}"`
      : `id="${readerId}" data-mode="lesson" data-doc-id="${activeDocId}" data-lesson-id="${lesson?lesson.id:''}" data-start="${lesson?lesson.start_page:1}" data-end="${lesson?lesson.end_page:1}" data-storage="${escapeAttr(activeDoc.storage_path)}"`;

    // 左栏目录：分课时 → 课文列表；整本 → 全部课文（按页顺序）
    const navItems = plLessons.map((l, i) => `
      <button class="im-nav-item ${activeLessonId===l.id?'active':''}" onclick="selectLesson(${l.id})">
        <span class="ni-idx">${isBook ? (l.start_page) : i+1}</span>
        <span class="ni-title">${escapeAttr(l.title)}</span>
      </button>`).join('');

    // 右栏对话记录
    const chatList = chatMessages.length
      ? chatMessages.map((m,i) => {
          const isUser = m.role === 'user';
          if(isUser){
            return `<div class="im-msg user" data-i="${i}"><div class="bubble">${escapeAttr(m.text)}</div></div>`;
          }
          return `<div class="im-msg ai" data-i="${i}">
            <div class="bubble">${renderAnswer(m.text)}</div>
            ${m.citations && m.citations.length ? `<div class="meta">出处：第 ${m.citations.join('、')} 句</div>` : ''}
          </div>`;
        }).join('')
      : `<div class="im-empty">
          <div class="mark">${welcomeMark()}</div>
          <div class="big">边读边问，随时解惑</div>
          <div class="hint">选中正文里任意一段，就能追问、解释或翻译它；AI 的回答会指明出自原文的哪一处。</div>
        </div>`;

    return `
    <div class="immersive">
      <header class="im-top">
        <button class="im-back" onclick="exitImmersive()" title="返回">${icon('arrow-left',18)}</button>
        <button class="im-tool ${navOpen?'active':''}" onclick="navOpen=!navOpen;render()" title="目录">${icon('panel-left',18)}</button>
        <div class="im-grow">
          <span class="im-title">${escapeAttr(title)}</span>
          <span class="im-sub">${sub}</span>
        </div>
        <button class="im-tool" onclick="chooseReadMode('${isBook?'lesson':'book'}')" title="${isBook?'切到分课时':'切到整本'}">${icon('grid',18)}</button>
        <span class="im-divider"></span>
        <button class="im-tool" onclick="speakLesson()" title="朗读">${icon('volume',18)}</button>
        <button class="im-tool" onclick="startQuiz()" title="测验">${icon('list',18)}</button>
        <button class="im-tool" onclick="startAskQuestions()" title="主动提问">${icon('sparkles',18)}</button>
        <button class="im-tool" onclick="exitImmersive()" title="退出全屏">${icon('expand',18)}</button>
        <button class="im-tool" onclick="toast('更多功能开发中')" title="菜单">${icon('menu',18)}</button>
        <span class="im-divider"></span>
        <button class="im-tool ${chatOpen?'active':''}" onclick="chatOpen=!chatOpen;render()" title="${chatOpen?'收起对话':'展开对话'}">${icon('panel-right',18)}</button>
      </header>
      <div class="im-body" style="grid-template-columns:${navOpen?navWidth+'px':'0'} ${navOpen?'5px':'0'} minmax(0,1fr) ${chatOpen?'5px':'0'} ${chatOpen?chatWidth+'px':'0'}">
        ${navOpen ? `<nav class="im-nav" style="width:${navWidth}px">
          <div class="nav-head">目录</div>
          ${navItems || `<div class="im-empty"><div class="hint">暂无课程</div></div>`}
        </nav>` : ''}
        ${navOpen ? `<div class="im-sep" id="im-sep-nav" data-side="nav"></div>` : ''}
        <div class="im-reader">
          <div class="reader-pad">
            <div ${readerAttrs}></div>
          </div>
        </div>
        ${chatOpen ? `<div class="im-sep" id="im-sep-chat" data-side="chat"></div>` : ''}
        ${chatOpen ? `<aside class="im-side" style="width:${chatWidth}px">
          <div class="im-chat-head">
            <span class="t">对话伴学</span>
            <span class="sub">回答会指明原文出处</span>
          </div>
          ${excerpt ? `<div class="im-ctx" title="${escapeAttr(excerpt)}"><span class="q">引用：${escapeAttr(excerpt)}</span><span class="x" onclick="excerpt='';render()">×</span></div>` : ''}
          <div class="im-chat-body" id="im-chat-body">${chatList}</div>
          <div class="im-composer">
            <div class="im-chips" id="im-chips">
              <button class="im-chip ${chatModel?'on':''}" onclick="toggleChatMenu('model', event)">
                ${icon('brain',14)}<span>${chatModel ? shortModelName(chatModel) : '默认模型'}</span><span class="caret">▾</span>
              </button>
              <button class="im-chip on" onclick="toggleChatMenu('mode', event)">
                ${icon(CHAT_MODES.find(m=>m.id===chatMode)?.icon||'sparkles',14)}<span>${CHAT_MODES.find(m=>m.id===chatMode)?.name||'对话'}</span><span class="caret">▾</span>
              </button>
              ${chatMenu ? chatMenuHtml() : ''}
            </div>
            <div class="quick">
              <button class="qa-btn" onclick="chatAsk('这段话是什么意思？')">这段话是什么意思？</button>
              <button class="qa-btn" onclick="chatAsk('帮我总结知识点')">帮我总结知识点</button>
              <button class="qa-btn" onclick="chatAsk('给我出一道练习题')">给我出一道练习题</button>
            </div>
            <div class="row">
              <textarea id="im-input" placeholder="针对这段教材提问…" oninput="question=this.value" onkeydown="imInputKey(event)"></textarea>
              <button class="send-btn" id="im-send" onclick="chatAsk()" title="发送">${icon('arrow',18)}</button>
            </div>
          </div>
        </aside>` : ''}
      </div>
    </div>`;
  }

  return `
  <header class="page-head">
    <div>
      <div class="crumb">${icon('sparkles',16)}AI 个性化学习</div>
      <h1 class="big">和教材一起深度学习</h1>
      <p class="desc">选择教材与课程，在正文里拖选任意一段，划线、记笔记、查生词，或直接追问。</p>
    </div>
    <label style="display:inline-flex;align-items:center;gap:8px;border-radius:12px;background:#3158e8;color:#fff;padding:12px 20px;font-size:14px;font-weight:700;box-shadow:0 8px 20px rgba(49,88,232,.18);cursor:pointer">${icon('book',18)}上传 PDF 教材<input type="file" accept="application/pdf" style="display:none" onchange="uploadPdfPersonal(this)"></label>
  </header>

  <section class="materials">
    <div class="head">
      <div><h2>我的教材</h2><div class="sub">选择一本教材，展开课程列表</div></div>
      <label class="add-book" style="cursor:pointer"><span style="font-size:18px;line-height:1">＋</span>添加教材<input type="file" accept="application/pdf" style="display:none" onchange="uploadPdfPersonal(this)"></label>
    </div>
    <div class="book-list">${books || `<div style="padding:24px 0;color:#8e9691;font-size:13px">暂无教材，请在家长端「教材」页上传 PDF</div>`}</div>
    ${lessonList}
    ${modeBar}
  </section>

  <div class="pl-grid">
    <section class="pl-reader">
      <div class="bar">
        <div class="t"><div class="ic">${icon('book',18)}</div><div style="min-width:0"><div class="name">${lesson?lesson.title:'请选择课程'}</div><div class="sub">${lesson?'PDF 原页面 · '+(lesson.start_page)+'–'+lesson.end_page+' 页':'配套电子教材 · 当前学习内容'}</div></div></div>
      </div>
      <div class="reader-body">${readerBody}</div>
    </section>
    <div class="pl-side">
      <section class="pl-ask">
        <h3>选中的教材内容</h3>
        <textarea class="ta" placeholder="在正文里拖选一段文字，自动填入…" oninput="excerpt=this.value">${excerpt}</textarea>
        <div class="quick-actions">
          <button class="qa-btn" onclick="ask('这段话是什么意思？')">这段话是什么意思？</button>
          <button class="qa-btn" onclick="ask('帮我总结知识点')">帮我总结知识点</button>
          <button class="qa-btn" onclick="ask('给我出一道练习题')">给我出一道练习题</button>
        </div>
      </section>
      ${annotationList}
      <section class="pl-question">
        <h3>针对这段教材提问</h3>
        <div class="qa-input"><input placeholder="针对这段教材提问…" oninput="question=this.value"><button class="send-btn" onclick="ask()">发送问题</button></div>
      </section>
      ${answer?`<section class="pl-answer"><h3>${icon('sparkles',16)}AI 讲解</h3><div class="ans">${renderAnswer(answer)}</div></section>`:''}
    </div>
  </div>`;
}
function escapeAttr(s){
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,'&#39;');
}
function selectSentence(s, lessonId){
  excerpt = s;
  currentLessonId = lessonId;
  render();
  // 直接触发一次解释
  ask('这段话是什么意思？');
}
async function uploadPdfPersonal(input){
  toast('请在家长端「教材」页上传 PDF');
  input.value = '';
}

// ===== 沉浸式阅读：pdf.js 阅读器 + 选中追问 + 标注 =====
let _pdfDoc = null;        // 当前 pdf.js 加载的文档
let _mountedKey = null;    // 已挂载的「storage|mode|range」标识，避免重复挂载刷掉渲染
const _SCALE = 1.5;        // 固定缩放：图片与文本层共用同一坐标空间，天然对齐
let _io = null;            // 整本懒加载用的 IntersectionObserver

async function mountPdfReader(){
  const host = document.getElementById('pdf-reader') || document.getElementById('pdf-reader-fs');
  if(!host) return;   // 未选课程或兜底状态
  const storage = host.dataset.storage;
  const mode = host.dataset.mode || 'lesson';
  const startPage = parseInt(host.dataset.start, 10) || 1;
  const endPage = parseInt(host.dataset.end, 10) || startPage;
  const key = `${storage}|${mode}|${mode==='book'?'all':(startPage+'-'+endPage)}`;
  if(_mountedKey === key && host.children.length){ renderAnnotationHighlights(); return; }
  _mountedKey = key;
  if(_io){ _io.disconnect(); _io = null; }
  host.innerHTML = '';

  // pdf.js 未加载（本地 module 失败）→ 兜底回 PNG 图片
  if(typeof window.pdfjsLib === 'undefined'){
    const pageMap = mode === 'book' ? bookPageMap : pageMapForLesson();
    const list = Object.keys(pageMap).map(Number).sort((a,b)=>a-b);
    if(list.length){
      host.innerHTML = list.map(p=>`<img src="${API}/${pageMap[p]}" style="width:100%;border-radius:8px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,.08)">`).join('');
    } else {
      host.innerHTML = `<div style="text-align:center;padding:48px 0;color:#8e9691">正文加载失败：请检查网络（需加载 pdf.js）</div>`;
    }
    return;
  }

  try {
    const pdfjsLib = window.pdfjsLib;
    // worker / wasm 已在 index.html 的 module 里设好同源路径（对齐 DeepTutor）。
    // 中文教材用 Type0(CID) 内嵌方正 GBK 字体，需 CMap 映射 CID→字形；
    // 6.x legacy 构建内置了常用 CMap，再显式指定本地 cMapUrl 兜底 CJK 扩展。
    _pdfDoc = await pdfjsLib.getDocument({
      url: `${API}/${storage}`,
      cMapUrl: window.pdfjsWasmUrl && (window.pdfjsWasmUrl + '../cmaps/') || undefined,
      cMapPacked: true,
      wasmUrl: window.pdfjsWasmUrl || undefined,
    }).promise;
    const pageMap = mode === 'book' ? bookPageMap : pageMapForLesson();

    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;gap:16px;align-items:center';

    if(mode === 'book'){
      // 整本连续阅读：懒加载全书页面，滚动到可视区才渲染
      const total = _pdfDoc.numPages;
      for(let p=1; p<=total; p++){
        const placeholder = document.createElement('div');
        placeholder.className = 'pdf-page-slot';
        placeholder.dataset.page = p;
        placeholder.style.cssText = 'width:100%;display:flex;justify-content:center';
        wrap.appendChild(placeholder);
      }
      host.appendChild(wrap);
      host.addEventListener('mouseup', onReaderMouseUp);
      const slots = Array.from(wrap.querySelectorAll('.pdf-page-slot'));
      // 定位当前选中课文在整本里的起始页，优先渲染它及其相邻页，并滚动过去，
      // 避免停在封面/目录等无内容的占位页上，导致「课文内容不显示」。
      const lesson = activeLessonId ? plLessons.find(x=>x.id===activeLessonId) : null;
      const anchorPage = (lesson && lesson.start_page) ? lesson.start_page : 1;
      // 首屏：渲染锚点页 + 前后各 1 页，其余交给 IntersectionObserver。
      // 锚点页单独渲染并保留其 Promise，便于渲染出高度后滚动到该页。
      const want = new Set([anchorPage - 1, anchorPage, anchorPage + 1].filter(p=>p>=1 && p<=_pdfDoc.numPages));
      const anchorSlot = slots.find(s=>parseInt(s.dataset.page,10)===anchorPage) || slots[0];
      let anchorPromise = Promise.resolve();
      slots.forEach(slot=>{
        const p = parseInt(slot.dataset.page, 10);
        if(!want.has(p)) return;
        const pr = renderPageInto(slot, p, pageMap);
        if(slot === anchorSlot) anchorPromise = pr;
      });
      _io = new IntersectionObserver((entries)=>{
        entries.forEach(e=>{
          if(e.isIntersecting){
            const slot = e.target;
            const p = parseInt(slot.dataset.page, 10);
            _io.unobserve(slot);
            renderPageInto(slot, p, pageMap);
          }
        });
      }, {rootMargin: '400px 0px'});
      slots.forEach(slot=>_io.observe(slot));
      // 滚动到当前课文起始页，让正文立刻可见。
      // 锚点页渲染是异步的（pdf.js getPage/renderTextLayer），要等它渲染出高度后再滚，
      // 否则占位符高度为 0，scrollTop 会算成 0、停在封面。
      if(anchorPage > 1){
        const scroller = anchorSlot.closest('.im-reader') || anchorSlot.closest('.pdf-reader');
        const scrollToAnchor = () => {
          if(!scroller || !anchorSlot) return;
          const scTop = scroller.getBoundingClientRect().top;
          const slotTop = anchorSlot.getBoundingClientRect().top;
          scroller.scrollTop += (slotTop - scTop) - 8;
        };
        anchorPromise.then(scrollToAnchor).catch(scrollToAnchor);
      }
    } else {
      for(let p=startPage; p<=endPage && p<=_pdfDoc.numPages; p++){
        const slot = document.createElement('div');
        slot.className = 'pdf-page-slot';
        slot.dataset.page = p;
        slot.style.cssText = 'width:100%;display:flex;justify-content:center';
        wrap.appendChild(slot);
      }
      host.appendChild(wrap);
      host.addEventListener('mouseup', onReaderMouseUp);
      const slots = wrap.querySelectorAll('.pdf-page-slot');
      slots.forEach(slot => renderPageInto(slot, parseInt(slot.dataset.page,10), pageMap));
    }

    renderAnnotationHighlights();
  } catch(err){
    host.innerHTML = `<div style="text-align:center;padding:48px 0;color:#8e9691">正文加载失败：${escapeAttr(String(err && err.message || err))}</div>`;
  }
}

function pageMapForLesson(){
  const lesson = plLessons.find(x=>x.id===activeLessonId);
  const m = {};
  (lesson && lesson.pages || []).forEach(p=>{ m[p.page_number] = p.image_path; });
  return m;
}

async function renderPageInto(slot, p, pageMap){
  if(!_pdfDoc || slot.dataset.rendered === '1') return;
  slot.dataset.rendered = '1';
  try {
    const page = await _pdfDoc.getPage(p);
    const viewport = page.getViewport({scale:_SCALE});
    const container = document.createElement('div');
    container.className = 'pdf-page';
    container.dataset.page = p;
    // 更接近 DeepTutor 的纸张质感：圆角 + 双层阴影 + 极细描边
    container.style.cssText = `position:relative;background:#fff;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.10),0 8px 24px -12px rgba(0,0,0,.18);outline:1px solid rgba(0,0,0,.06);outline-offset:0;overflow:hidden;width:${viewport.width}px;height:${viewport.height}px;max-width:100%`;

    // 视觉层：先放后端预渲染的高清 PNG（300dpi，即时可见），
    // 后台再尝试 pdf.js canvas 矢量渲染，成功则替换 PNG（对可栅格化的 PDF 获得更锐利矢量）。
    // 教材含内嵌方正 GBK Type0 字体，pdf.js 的 canvas 会死锁（DeepTutor 同样空白），
    // 故 PNG 是主视觉、canvas 是尽力增强，二者都不能阻塞文本层（可选中复制）。
    const img = document.createElement('img');
    if(pageMap[p]){
      img.src = `${API}/${pageMap[p]}`;
      img.style.cssText = `width:${viewport.width}px;max-width:100%;height:auto;display:block`;
    } else {
      img.style.cssText = `width:${viewport.width}px;height:${viewport.height}px;display:flex;align-items:center;justify-content:center;background:linear-gradient(180deg,#fbfbfa,#f2f4f1);color:#a8b0aa;font-size:13px;letter-spacing:1px`;
    }
    container.appendChild(img);
    const canvas = document.createElement('canvas');
    canvas.style.cssText = `width:${viewport.width}px;max-width:100%;height:auto;display:none`;
    container.appendChild(canvas);
    const textLayer = document.createElement('div');
    textLayer.className = 'pdf-text-layer';
    textLayer.style.cssText = 'position:absolute;top:0;left:0;overflow:hidden;line-height:1;transform-origin:0 0;';
    textLayer.style.setProperty('--total-scale-factor', String(_SCALE));
    textLayer.style.width = viewport.width + 'px';
    textLayer.style.height = viewport.height + 'px';
    container.appendChild(textLayer);
    // 标注墨迹层：绝对定位叠在文本层上方，按归一化坐标铺高亮/下划线（mix-blend-multiply）
    const annotLayer = document.createElement('div');
    annotLayer.className = 'pdf-annot-layer';
    container.appendChild(annotLayer);

    // 先把页面放进 slot，让 PNG + 文本层立即可见，canvas 增强在后台进行。
    slot.innerHTML = '';
    slot.appendChild(container);

    const paintCanvas = async () => {
      const pdfjsLib = window.pdfjsLib;
      const dpr = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
      canvas.width = Math.floor(viewport.width * dpr);
      canvas.height = Math.floor(viewport.height * dpr);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;
      const renderTask = page.render({
        canvas,
        viewport,
        transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
      });
      // 内嵌 CID 字体栅格化会死锁：2 秒赛跑，超时即放弃 canvas、保留 PNG。
      await Promise.race([
        renderTask.promise,
        new Promise((_, rej) => setTimeout(() => rej(new Error('canvas render timeout')), 2000)),
      ]);
    };
    const buildTextLayer = async () => {
      const pdfjsLib = window.pdfjsLib;
      const textContent = await page.getTextContent();
      if(typeof pdfjsLib.TextLayer === 'function'){
        const layer = new pdfjsLib.TextLayer({ textContentSource: textContent, container: textLayer, viewport });
        await layer.render();
      } else {
        await pdfjsLib.renderTextLayer({ textContent, container: textLayer, viewport, textDivs: [] }).promise;
      }
    };

    // canvas 后台增强：成功且真的画了内容（非空白）才替换 PNG，否则保持高清 PNG。
    paintCanvas().then(() => {
      const ctx = canvas.getContext('2d');
      const d = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      let nonWhite = 0;
      for(let i = 0; i < d.length; i += 4){
        if(!(d[i] > 245 && d[i+1] > 245 && d[i+2] > 245)) nonWhite++;
      }
      if(nonWhite > 500){  // 确属有效矢量内容（非白底/空白），才替换
        img.style.display = 'none';
        canvas.style.display = 'block';
      }
    }).catch(() => {
      // 超时/失败：保留 PNG，静默。
    });

    // 文本层独立渲染，不影响视觉层；失败也静默。
    buildTextLayer().catch(() => {});

    // 新页就绪后补一次高亮，但做防抖：懒加载滚动会连续渲染多页，避免每页都全量遍历
    scheduleAnnotationHighlight();
  } catch(err){
    slot.innerHTML = `<div style="text-align:center;padding:32px 0;color:#8e9691">第 ${p} 页加载失败</div>`;
  }
}

// 防抖的高亮调度：多页连续渲染时合并为一次全量扫描，消除选中/滚动的卡顿
let _highlightTimer = null;
function scheduleAnnotationHighlight(){
  if(_highlightTimer) return;
  _highlightTimer = setTimeout(()=>{ _highlightTimer = null; renderAnnotationHighlights(); }, 120);
}

function onReaderMouseUp(){
  const sel = window.getSelection();
  if(!sel || sel.isCollapsed){ hidePopover(); return; }
  const text = sel.toString().trim();
  if(!text){ hidePopover(); return; }
  // 定位到所在的 PDF 页
  const node = sel.anchorNode;
  const pageEl = node && node.parentElement ? node.parentElement.closest('.pdf-page') : null;
  const page = pageEl ? parseInt(pageEl.dataset.page, 10) : 1;
  selectedQuote = text;
  selectedPage = page;
  // 计算归一化矩形坐标（对齐 DeepTutor normaliseRects）：选区精确到页内 0~1 坐标，
  // 用于在原文上精确铺高亮/下划线（mix-blend-multiply 荧光笔，不盖文字）。
  const range = sel.getRangeAt(0);
  const rects = range.getClientRects();
  const box = pageEl ? pageEl.getBoundingClientRect() : null;
  selectedRects = (box && rects.length) ? JSON.stringify(normaliseRects(rects, box)) : '';
  excerpt = text;
  // 整本模式：按页号反推该页属于哪一课，让标注/提问落到正确的 lesson_id
  if(readMode === 'book'){
    const l = lessonForPage(page);
    if(l){ currentLessonId = l.id; activeLessonId = l.id; }
  }
  const rect = range.getBoundingClientRect();
  showPopover(rect.left + rect.width/2, rect.top, page);
}

// 归一化选区矩形（对齐 DeepTutor lib/reading-selection.ts）：按行合并 + 裁剪到 0~1
function normaliseRects(clientRects, box){
  const MIN = 2, OVERLAP = 0.5;
  const clamp = v => Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : 0;
  const usable = [];
  for(const r of clientRects){
    if(r.width >= MIN && r.height >= MIN) usable.push({left:r.left, top:r.top, width:r.width, height:r.height});
  }
  if(!usable.length) return [];
  usable.sort((a,b)=>a.top-b.top || a.left-b.left);
  const lines = [];
  for(const r of usable){
    const line = lines.find(c=>{
      const p = c[0];
      const overlap = Math.min(p.top+p.height, r.top+r.height) - Math.max(p.top, r.top);
      const shorter = Math.min(p.height, r.height);
      return shorter > 0 && overlap/shorter >= OVERLAP;
    });
    if(line) line.push(r); else lines.push([r]);
  }
  const merged = lines.map(line=>{
    const left = Math.min(...line.map(r=>r.left));
    const top = Math.min(...line.map(r=>r.top));
    const right = Math.max(...line.map(r=>r.left+r.width));
    const bottom = Math.max(...line.map(r=>r.top+r.height));
    return {left, top, width:right-left, height:bottom-top};
  });
  const out = [];
  for(const r of merged){
    const x0 = clamp((r.left - box.left)/box.width);
    const y0 = clamp((r.top - box.top)/box.height);
    const x1 = clamp((r.left + r.width - box.left)/box.width);
    const y1 = clamp((r.top + r.height - box.top)/box.height);
    if(x1-x0 > 0.001 && y1-y0 > 0.001) out.push([Math.min(x0,x1), Math.min(y0,y1), Math.max(x0,x1), Math.max(y0,y1)]);
  }
  return out;
}

let _popoverEl = null;
let _annotColor = 'yellow';   // 气泡里当前选中的标注颜色（对齐 DeepTutor 色板）
const _ANNOT_SWATCH = {yellow:'#facd5a', green:'#8cdb94', blue:'#7ac0fa', pink:'#faa1c7', purple:'#c7aefa'};

function showPopover(x, y, page){
  hidePopover();
  const el = document.createElement('div');
  el.id = 'reader-popover';
  el.style.cssText = `left:${Math.round(x)}px;top:${Math.round(y)}px;transform:translate(-50%,-110%)`;
  const quote = escapeAttr(selectedQuote || '');
  // 浅色气泡：第一行色板 + 划线/下划线/笔记/生词图标；第二行「追问」主按钮 + 快捷解释 chip。
  el.innerHTML = `
    <div class="rp-row">
      <div class="rp-swatches">${['yellow','green','blue','pink','purple'].map(c=>`<button class="rp-swatch ${_annotColor===c?'on':''}" data-c="${c}" style="background:${_ANNOT_SWATCH[c]}" onmousedown="event.preventDefault();event.stopPropagation();pickAnnotColor('${c}')" title="${c}"></button>`).join('')}</div>
      <span class="rp-sep"></span>
      <button class="rp-btn" title="划线" onmousedown="event.preventDefault();event.stopPropagation();annotate('highlight')">${icon('highlighter',16)}</button>
      <button class="rp-btn" title="下划线" onmousedown="event.preventDefault();event.stopPropagation();annotate('underline')">${icon('underline',16)}</button>
      <button class="rp-btn" title="笔记" onmousedown="event.preventDefault();event.stopPropagation();openAnnotNote()">${icon('note',16)}</button>
      <button class="rp-btn" title="生词释义" onmousedown="event.preventDefault();event.stopPropagation();annotate('glossary')">${icon('book',16)}</button>
    </div>
    <div class="rp-row">
      <button class="rp-btn ask" onmousedown="event.preventDefault();event.stopPropagation();askPopover()">${icon('chat',14)}追问</button>
      <button class="rp-chip" onmousedown="event.preventDefault();event.stopPropagation();askPopoverExplain()">解释</button>
      <button class="rp-chip" onmousedown="event.preventDefault();event.stopPropagation();askPopoverTranslate()">翻译</button>
    </div>
    <div class="rp-note-row">
      <div class="rp-quote">“${quote}”</div>
      <textarea id="rp-note-input" placeholder="给这段文字写一句笔记…"></textarea>
      <div class="rp-note-actions">
        <button class="rp-cancel" onmousedown="event.preventDefault();event.stopPropagation();closeAnnotNote()">取消</button>
        <button class="rp-save" onmousedown="event.preventDefault();event.stopPropagation();saveAnnotNote()">保存笔记</button>
      </div>
    </div>`;
  document.body.appendChild(el);
  _popoverEl = el;
  // 渲染后按窗口边界夹取，避免贴近顶部/右侧时被截断（对齐 DeepTutor 的做法）
  const box = el.getBoundingClientRect();
  const margin = 10;
  let left = Math.min(Math.max(margin, el.offsetLeft), window.innerWidth - box.width - margin);
  let top = el.offsetTop;
  if(top < margin){ top = y + 24; el.style.transform = 'translate(-50%,0)'; }
  el.style.left = left + 'px';
  el.style.top = Math.min(top, window.innerHeight - box.height - margin) + 'px';
}

function pickAnnotColor(c){ _annotColor = c; const s=document.querySelectorAll('#reader-popover .rp-swatch'); s.forEach(b=>b.classList.toggle('on', b.dataset.c===c)); }
function openAnnotNote(){ const r=document.querySelector('#reader-popover .rp-note-row'); if(r) r.style.display='flex'; }
function closeAnnotNote(){ const r=document.querySelector('#reader-popover .rp-note-row'); if(r) r.style.display='none'; }
function saveAnnotNote(){
  const t=document.getElementById('rp-note-input');
  hidePopover();
  if(!selectedQuote){ toast('请先在正文里拖选一段文字'); return; }
  addAnnotation('note', (t && t.value.trim()) || '');
}
function hidePopover(){ if(_popoverEl){ _popoverEl.remove(); _popoverEl = null; } }

function askPopover(){
  hidePopover();
  ask('这段话是什么意思？');
}
function askPopoverExplain(){
  hidePopover();
  ask('给我解释一下这段话');
}
function askPopoverTranslate(){
  hidePopover();
  ask('把这段话翻译成英文');
}

function annotate(kind){
  hidePopover();
  if(!selectedQuote){ toast('请先在正文里拖选一段文字'); return; }
  if(kind === 'glossary'){
    addAnnotation(kind, '');
  } else {
    addAnnotation(kind, '');
  }
}

async function addAnnotation(kind, note){
  const color = kind==='glossary' ? 'green' : _annotColor;
  const body = {lesson_id: currentLessonId, kind, quote: selectedQuote, note, color, page_number: selectedPage, rects: selectedRects};
  if(kind === 'glossary'){
    const d = await api('/api/annotations/glossary', {method:'POST', body:{lesson_id: currentLessonId, quote: selectedQuote, page_number: selectedPage, rects: selectedRects}});
    toast('已查生词释义');
  } else {
    await api('/api/annotations', {method:'POST', body});
    toast(kind==='note'?'已记笔记':(kind==='underline'?'已加下划线':'已划线'));
  }
  loadAnnotations();
}

async function loadAnnotations(){
  if(!activeLessonId) return;
  annotations = await api(`/api/annotations?lesson_id=${activeLessonId}`);
  // 原地更新右侧「我的标注」列表 + 正文高亮，避免整体 render() 重挂载 PDF 阅读器
  renderAnnotationList();
  renderAnnotationHighlights();
}

function renderAnnotationList(){
  const list = document.getElementById('annotation-list');
  if(!list) return;
  if(!annotations.length){ list.innerHTML = ''; list.style.display = 'none'; return; }
  list.style.display = '';
  list.innerHTML = `
    <h3>我的标注</h3>
    <div style="display:flex;flex-direction:column;gap:8px">${annotations.map(a=>`
      <div class="ann-item" data-annid="${a.id}" style="border:1px solid #eef0ed;border-radius:10px;padding:8px 12px;background:#fbfbfa">
        <div style="display:flex;align-items:center;gap:8px">
          <span class="ann-kind ${a.kind}" style="font-size:11px;font-weight:700;color:${a.kind==='glossary'?'#2e8b5a':(a.kind==='note'?'#7457d7':'#3158e8')}">${a.kind==='glossary'?'生词':(a.kind==='note'?'笔记':'划线')}</span>
          <span style="flex:1;font-size:12px;color:#4b544e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${escapeAttr(a.quote)}">${escapeAttr(a.quote)}</span>
          <button onclick="delAnnotation(${a.id})" style="color:#c05b4a;font-size:12px">删</button>
        </div>
        ${a.note?`<div style="margin-top:4px;font-size:12px;line-height:18px;color:#78817b">${escapeAttr(a.note)}</div>`:''}
      </div>`).join('')}</div>`;
}

async function delAnnotation(id){
  await api(`/api/annotations/${id}`, {method:'DELETE'});
  loadAnnotations();
}

function renderAnnotationHighlights(){
  const host = document.getElementById('pdf-reader') || document.getElementById('pdf-reader-fs');
  if(!host) return;
  // 划线墨色（对齐 DeepTutor COLOR_INK，RGB 值供 mix-blend-multiply 用，文字始终清晰）
  const INK = {yellow:'250 220 90', green:'140 219 148', blue:'122 192 250', pink:'250 161 199', purple:'199 174 250'};
  const ink = c => INK[c] || INK.yellow;
  // 先清空各页旧的墨迹层内容，避免重复叠加
  host.querySelectorAll('.pdf-annot-layer').forEach(layer => { layer.innerHTML = ''; });
  if(!annotations.length) return;
  // 每页铺一遍：优先用归一化 rects 精确铺 mark（荧光笔），缺 rects 时回退到按 quote 定位文本层 span 的坐标。
  host.querySelectorAll('.pdf-page').forEach(pageEl => {
    const p = parseInt(pageEl.dataset.page, 10);
    const layer = pageEl.querySelector('.pdf-annot-layer');
    if(!layer) return;
    const anns = annotations.filter(a => a.page_number === p || a.page_number == null);
    anns.forEach(a => {
      let rects = null;
      if(a.rects){
        try { rects = JSON.parse(a.rects); } catch(e){ rects = null; }
      }
      if(Array.isArray(rects) && rects.length){
        // 精确坐标铺 mark（对齐 DeepTutor AnnotationLayer）
        rects.forEach((r, i) => {
          if(!Array.isArray(r) || r.length < 4) return;
          const [x0,y0,x1,y1] = r;
          const mark = document.createElement('span');
          mark.className = 'ann-mark' + (a.kind === 'underline' ? ' underline' : '');
          mark.dataset.annid = a.id;
          mark.title = a.note || a.quote || (a.kind === 'underline' ? '下划线' : '划线');
          mark.style.left = (x0*100) + '%';
          mark.style.top = (y0*100) + '%';
          mark.style.width = (Math.max(0, x1-x0)*100) + '%';
          mark.style.height = (Math.max(0, y1-y0)*100) + '%';
          if(a.kind === 'underline'){
            mark.style.borderBottomColor = `rgb(${ink(a.color)})`;
          } else if(a.kind === 'glossary'){
            mark.style.background = 'rgb(140 219 148 / .6)';
          } else {
            mark.style.background = `rgb(${ink(a.color)} / .6)`;
          }
          mark.onclick = () => focusAnnotation(a);
          layer.appendChild(mark);
        });
      } else {
        // 兜底：按 quote 定位文本层 span，用 span 自身坐标精确铺 mark（而非整 span 盖色）
        const textLayer = pageEl.querySelector('.pdf-text-layer');
        if(!textLayer) return;
        const quote = (a.quote || '').trim();
        if(!quote) return;
        textLayer.querySelectorAll('span').forEach(span => {
          const node = span.firstChild;
          if(!node || node.nodeType !== 3) return;
          if(!node.nodeValue.includes(quote)) return;
          const pb = pageEl.getBoundingClientRect();
          const sb = span.getBoundingClientRect();
          const mark = document.createElement('span');
          mark.className = 'ann-mark' + (a.kind === 'underline' ? ' underline' : '');
          mark.dataset.annid = a.id;
          mark.title = a.note || a.quote;
          mark.style.left = ((sb.left-pb.left)/pb.width*100) + '%';
          mark.style.top = ((sb.top-pb.top)/pb.height*100) + '%';
          mark.style.width = (sb.width/pb.width*100) + '%';
          mark.style.height = (sb.height/pb.height*100) + '%';
          if(a.kind === 'underline'){
            mark.style.borderBottomColor = `rgb(${ink(a.color)})`;
          } else if(a.kind === 'glossary'){
            mark.style.background = 'rgb(140 219 148 / .6)';
          } else {
            mark.style.background = `rgb(${ink(a.color)} / .6)`;
          }
          mark.onclick = () => focusAnnotation(a);
          layer.appendChild(mark);
        });
      }
    });
  });
}

// 点击墨迹 → 高亮右侧「我的标注」列表对应项
function focusAnnotation(a){
  const list = document.getElementById('annotation-list');
  if(!list) return;
  list.querySelectorAll('.ann-item').forEach(el => {
    el.style.outline = el.dataset.annid == a.id ? '2px solid #3158e8' : '';
  });
  const item = list.querySelector(`.ann-item[data-annid="${a.id}"]`);
  if(item) item.scrollIntoView({behavior:'smooth', block:'nearest'});
}

let _mmdSeq = 0;
function renderAnswer(ans){
  // 把 [第N句] 渲染成可点击跳转的出处按钮
  let html = escapeAttr(ans);
  html = html.replace(/\[第\s*(\d+)\s*句\]/g, (m, n) => `<button class="citation" onclick="jumpToSentence(${n})" title="跳转到课文第${n}句">${escapeAttr(m)}</button>`);
  // 把 ```mermaid 代码块换成占位容器，稍后由 renderMermaids 异步渲染成图
  html = html.replace(/```mermaid\s*([\s\S]*?)```/g, (m, code) => {
    const id = 'mmd' + (++_mmdSeq);
    return `<div class="mmd" data-mmd="${id}"><pre style="display:none">${escapeAttr(code.trim())}</pre><div class="mmd-loading" style="color:#8e9691;font-size:12px">正在画图…</div></div>`;
  });
  return html;
}

// 把气泡里的 mermaid 占位容器渲染成 SVG 图
function renderMermaids(container){
  if(!window.mermaid || !container) return;
  container.querySelectorAll('.mmd[data-mmd]').forEach(async box=>{
    if(box._done) return; box._done = true;
    const pre = box.querySelector('pre');
    if(!pre) return;
    const code = pre.textContent;
    try{
      const {svg} = await mermaid.render(box.dataset.mmd + '-svg', code);
      box.innerHTML = svg;
    }catch(err){
      box.innerHTML = `<div style="color:#c05b4a;font-size:12px">图示渲染失败</div>`;
    }
  });
}

function jumpToSentence(n){
  const lesson = plLessons.find(x=>x.id===activeLessonId);
  const text = lesson && lesson.texts && lesson.texts[0] ? lesson.texts[0] : '';
  const sentences = splitSentences(text);
  const target = sentences[n-1];
  if(!target){ toast(`未找到第${n}句`); return; }
  const host = document.getElementById('pdf-reader') || document.getElementById('pdf-reader-fs');
  if(!host){ toast(`第${n}句：${target.slice(0,20)}…`); return; }
  // 在正文文本层定位该句，铺一个闪光层（对齐 DeepTutor dt-reader-flash），滚到可视区后淡出
  const needle = target.trim().slice(0, 12);
  for(const pageEl of host.querySelectorAll('.pdf-page')){
    const textLayer = pageEl.querySelector('.pdf-text-layer');
    if(!textLayer) continue;
    let matched = null;
    textLayer.querySelectorAll('span').forEach(span=>{
      const node = span.firstChild;
      if(matched || !node || node.nodeType !== 3) return;
      if(node.nodeValue.includes(needle)) matched = span;
    });
    if(!matched) continue;
    const pb = pageEl.getBoundingClientRect();
    const sb = matched.getBoundingClientRect();
    const flash = document.createElement('div');
    flash.className = 'pdf-annot-flash';
    flash.style.left = ((sb.left-pb.left)/pb.width*100) + '%';
    flash.style.top = ((sb.top-pb.top)/pb.height*100) + '%';
    flash.style.width = (sb.width/pb.width*100) + '%';
    flash.style.height = (sb.height/pb.height*100) + '%';
    pageEl.appendChild(flash);
    pageEl.scrollIntoView({behavior:'smooth', block:'center'});
    setTimeout(()=>{ flash.remove(); }, 1600);
    return;
  }
  toast(`第${n}句：${target.slice(0,20)}…`);
}

async function ask(preset){
  const q = preset || question;
  if(!q || !q.trim()) return;
  const ctx = excerpt && excerpt.trim() ? excerpt.trim() : currentText;
  const d = await api('/api/ask', {method:'POST', body:{lesson_id:currentLessonId, question:q.trim(), context:ctx}});
  answer = d.answer || '（暂无回答）';
  citations = d.citations || [];
  render();
}

// ===== 沉浸页对话（多轮记录）=====
function imInputKey(e){
  if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); chatAsk(); }
}
let quizState = {quiz_id:null, questions:[], answers:{}, submitted:false, results:[]};
let askState  = {questions:[], replies:{}};

async function startQuiz(){
  chatOpen = true;
  chatBusy = true; renderImmersiveChat();
  try{
    const d = await api('/api/quiz/generate', {method:'POST', body:{lesson_id:currentLessonId}});
    quizState = {quiz_id:d.quiz_id, questions:d.questions||[], answers:{}, submitted:false, results:[]};
  }catch(e){
    toast('出题失败，请确认已配置 AI');
    quizState = {quiz_id:null, questions:[], answers:{}, submitted:false, results:[]};
  }
  chatBusy = false; renderImmersiveChat();
}
function pickQuizAnswer(qid, idx){ quizState.answers[qid] = idx; renderImmersiveChat(); }
async function submitQuiz(){
  const answers = quizState.questions.map(q=>({question_id:q.id, selected_index:quizState.answers[q.id]}));
  try{
    const d = await api('/api/quiz/submit', {method:'POST', body:{quiz_id:quizState.quiz_id, answers}});
    quizState.results = d.answers; quizState.submitted = true;
  }catch(e){ toast('提交失败，测验可能已过期'); }
  renderImmersiveChat();
}
async function startAskQuestions(){
  chatOpen = true;
  const ctx = excerpt && excerpt.trim() ? excerpt.trim() : currentText;
  chatBusy = true; renderImmersiveChat();
  try{
    const d = await api('/api/ask/questions', {method:'POST', body:{lesson_id:currentLessonId, context:ctx}});
    askState = {questions:d.questions||[], replies:{}};
  }catch(e){
    toast('提问失败，请确认已配置 AI');
    askState = {questions:[], replies:{}};
  }
  chatBusy = false; renderImmersiveChat();
}
function pickAskAnswer(qid, val){ askState.replies[qid] = val; renderImmersiveChat(); }
async function submitAskReplies(){
  chatMessages.push({role:'user', text:'（回答了诊断性问题）'});
  chatBusy = true; renderImmersiveChat();
  try{
    const d = await api('/api/ask/reply', {method:'POST', body:{lesson_id:currentLessonId, context:currentText, replies:askState.replies}});
    chatMessages.push({role:'ai', text:d.answer||'（暂无回答）', citations:d.citations||[], mode:'chat'});
  }catch(e){ chatMessages.push({role:'ai', text:'抱歉，回答出错了。', citations:[]}); }
  askState = {questions:[], replies:{}};
  chatBusy = false; renderImmersiveChat();
}
async function chatAsk(preset){
  const q = (preset || question || '').trim();
  if(!q || chatBusy) return;
  const ctx = excerpt && excerpt.trim() ? excerpt.trim() : currentText;
  chatMessages.push({role:'user', text:q});
  question = '';
  chatBusy = true;
  thinkingText = '正在思考…';
  renderImmersiveChat();
  const body = {lesson_id:currentLessonId, question:q, context:ctx, mode:chatMode, sentences: splitSentences(ctx)};
  if(chatModel) body.model = chatModel;

  try{
    const resp = await fetch(API + '/api/ask/stream', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while(true){
      const {done, value} = await reader.read();
      if(done) break;
      buf += decoder.decode(value, {stream:true});
      let idx;
      while((idx = buf.indexOf('\n\n')) >= 0){
        const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2);
        const line = chunk.split('\n').find(l=>l.startsWith('data: '));
        if(!line) continue;
        try{
          const evt = JSON.parse(line.slice(6));
          handleStreamEvent(evt);
        }catch(e){ /* 跳过坏事件 */ }
      }
    }
  }catch(err){
    chatMessages.push({role:'ai', text:'抱歉，回答出错了，请稍后再试。', citations:[], mode:chatMode});
  }
  chatBusy = false;
  thinkingText = '正在思考…';
  renderImmersiveChat();
}

function updateThinking(text){
  thinkingText = text;
  renderImmersiveChat();
}

function handleStreamEvent(evt){
  if(evt.type === 'tool_call'){
    updateThinking(`正在${toolLabel(evt.data.tool)}…`);
  } else if(evt.type === 'final'){
    const d = evt.data;
    const msg = {role:'ai', text:d.answer || '（暂无回答）', citations:d.citations || [], mode:d.mode || chatMode};
    if(d.render_task_id){
      msg.renderTaskId = d.render_task_id;
      msg.renderStatus = 'rendering';
    }
    chatMessages.push(msg);
    renderImmersiveChat();
    if(d.render_task_id) pollRenderTask(d.render_task_id, chatMessages.length - 1);
  }
}

async function pollRenderTask(taskId, msgIndex){
  const renderCard = (status, url) => {
    const m = chatMessages[msgIndex];
    if(!m) return;
    m.renderStatus = status;
    if(url) m.renderVideo = url;
    renderImmersiveChat();
  };
  for(let i = 0; i < 60; i++){  // 最多 60 × 3s = 180s
    try{
      const r = await fetch(API + '/api/render/' + taskId);
      const d = await r.json();
      if(d.status === 'done' && d.video_url){
        renderCard('done', d.video_url);
        return;
      }
      if(d.status === 'error' || d.status === 'unavailable'){
        renderCard('error', null);
        return;
      }
      renderCard(d.status, null);
    }catch(e){ /* 忽略单次失败 */ }
    await new Promise(res => setTimeout(res, 3000));
  }
  renderCard('error', null);
}

function toolLabel(name){
  return {lookup_word:'查词', search_text:'检索原文', render_mermaid:'画图', render_manim:'生成动画'}[name] || '思考';
}
// 只原地刷新沉浸页对话面板（不重挂载 PDF 阅读器）
function renderImmersiveChat(){
  const body = document.getElementById('im-chat-body');
  if(!body) return;
  let list = chatMessages.length
    ? chatMessages.map((m,i) => {
        const isUser = m.role === 'user';
        if(isUser) return `<div class="im-msg user" data-i="${i}"><div class="bubble">${escapeAttr(m.text)}</div></div>`;
        const modeName = CHAT_MODES.find(x=>x.id===(m.mode||'chat'))?.name;
        const modeTag = modeName && modeName !== '对话' ? `<span class="mm-tag">${modeName}</span>` : '';
        return `<div class="im-msg ai" data-i="${i}">${modeTag}<div class="bubble">${renderAnswer(m.text)}</div>${m.renderTaskId?renderTaskCard(m):''}${m.citations&&m.citations.length?`<div class="meta">出处：第 ${m.citations.join('、')} 句</div>`:''}</div>`;
      }).join('')
    : `<div class="im-empty"><div class="mark">${welcomeMark()}</div><div class="big">边读边问，随时解惑</div><div class="hint">选中正文里任意一段，就能追问、解释或翻译它；AI 的回答会指明出自原文的哪一处。</div></div>`;
  const cards = quizCardHtml() + askCardHtml();
  if(chatBusy) list += `<div class="im-msg ai"><div class="bubble" style="color:#aab1ab">${escapeAttr(thinkingText)}</div></div>`;
  body.innerHTML = list + cards;
  body.scrollTop = body.scrollHeight;
  renderMermaids(body);
  // 同步发送按钮状态
  const send = document.getElementById('im-send');
  if(send) send.disabled = chatBusy;
  // 清空输入框
  const inp = document.getElementById('im-input');
  if(inp) inp.value = '';
}
function renderTaskCard(m){
  if(m.renderStatus === 'done' && m.renderVideo){
    return `<div class="render-card"><video src="${m.renderVideo}" controls width="100%"></video></div>`;
  }
  if(m.renderStatus === 'error'){
    return `<div class="render-card">动画生成失败，请稍后再试。</div>`;
  }
  const label = {rendering:'渲染中…', generating:'生成中…', mixing:'合成音轨…', queued:'排队中…', submitted:'已提交…'}[m.renderStatus] || '渲染中…';
  return `<div class="render-card"><span class="render-progress">${label}</span></div>`;
}
function quizCardHtml(){
  if(!quizState.questions.length) return '';
  return `<div class="quiz-card">
    ${quizState.questions.map(q=>{
      const chosen = quizState.answers[q.id];
      const r = quizState.submitted ? quizState.results.find(x=>x.question_id===q.id) : null;
      return `<div class="quiz-q">
        <div class="qq-prompt">${escapeAttr(q.prompt)}</div>
        ${q.choices.map((c,i)=>`
          <label class="qq-choice ${chosen===i?'on':''} ${r?(r.is_correct?'ok':'bad'):''}" onclick="pickQuizAnswer('${q.id}',${i})">
            ${String.fromCharCode(65+i)}. ${escapeAttr(c)}
            ${quizState.submitted && r ? (r.is_correct?' ✓':' ✗') : ''}
          </label>`).join('')}
      </div>`;
    }).join('')}
    <div class="quiz-foot">
      ${quizState.submitted
        ? `答对 ${quizState.results.filter(r=>r.is_correct).length}/${quizState.questions.length}`
        : `<button class="btn-primary" onclick="submitQuiz()">提交答案</button>`}
    </div>
  </div>`;
}
function askCardHtml(){
  if(!askState.questions.length) return '';
  return `<div class="quiz-card">
    ${askState.questions.map(q=>{
      const opts = q.options || [];
      return `<div class="quiz-q">
        <div class="qq-prompt">${escapeAttr(q.prompt||'')}</div>
        ${opts.length
          ? opts.map(o=>`<label class="qq-choice ${askState.replies[q.id]===o.label?'on':''}" onclick="pickAskAnswer('${q.id}','${escapeAttr(o.label)}')">${escapeAttr(o.label)}</label>`).join('')
          : `<input class="ms-input" placeholder="你的回答…" oninput="pickAskAnswer('${q.id}',this.value)">`}
      </div>`;
    }).join('')}
    <div class="quiz-foot"><button class="btn-primary" onclick="submitAskReplies()">继续</button></div>
  </div>`;
}
// 朗读当前课文全文
function speakLesson(){
  const lesson = plLessons.find(x => x.id === activeLessonId);
  const text = lesson && lesson.texts && lesson.texts[0] ? lesson.texts[0] : currentText;
  if(!text){ toast('当前没有可朗读的课文'); return; }
  playTts(text.slice(0, 400));
}

// 拖拽分隔条调整右栏对话宽度
function bindImmersiveResize(){
  const sep = document.getElementById('im-sep');
  const body = document.querySelector('.im-body');
  if(!sep || !body) return;
  sep.onmousedown = (e) => {
    e.preventDefault();
    sep.classList.add('dragging');
    const startX = e.clientX;
    const startW = document.querySelector('.im-side') ? document.querySelector('.im-side').getBoundingClientRect().width : 380;
    const onMove = (ev) => {
      const w = Math.max(300, Math.min(560, startW - (ev.clientX - startX)));
      body.style.gridTemplateColumns = body.style.gridTemplateColumns.replace(/[0-9.]+px\s*$/, w + 'px');
      // 更稳：重设整条 grid 模板
      const cols = getComputedStyle(body).gridTemplateColumns;
      const parts = cols.split(' ');
      parts[parts.length-1] = w + 'px';
      body.style.gridTemplateColumns = parts.join(' ');
    };
    const onUp = () => {
      sep.classList.remove('dragging');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };
}

// ===== 家长端 =====
function toggleRole(){
  isParent = !isParent;
  if(isParent){ parentTab='教材'; loadParentData(); }
  document.getElementById('userAvatar').textContent = isParent?'金':'轩';
  document.getElementById('userName').textContent = isParent?'金爸爸':'金宇轩';
  document.getElementById('userGrade').textContent = isParent?'家长':'五年级';
  document.getElementById('roleSwitch').textContent = isParent?'孩子端':'家长端';
  renderNav(); render();
  if(isParent) toast('已切换到家长端');
}
function setParentTab(t){
  parentTab=t;
  if(t==='教材'){ loadPdfDocs().then(()=>render()); return; }
  if(t==='知识点'){ loadKnowledge().then(()=>render()); return; }
  if(t==='题目'){ loadQuestionData().then(()=>render()); return; }
  if(t==='目标'){ loadGoals().then(()=>render()); return; }
  if(t==='报告'){ Promise.all([loadReport(), loadMasteryReport()]).then(()=>render()); return; }
  if(t==='任务'){ loadParentTasks().then(()=>render()); return; }
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
  goalRows = await api(`/api/goals?user_id=${uid}`);
}
async function loadReport(){
  reportRows = await api(`/api/mistakes/report?user_id=${uid}`);
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

// ---- 题目管理 ----
let questionLessons = [];   // [{id, subject, title, questions:[{id,question,answer}]}]
async function loadQuestionData(){
  // 拉取所有已提取课文的课程，再逐课拉题目
  const docs = await api('/api/pdf/documents');
  const out = [];
  for(const d of docs){
    const lessons = await api(`/api/pdf/documents/${d.id}/lessons`);
    for(const l of lessons){
      if(!(l.texts && l.texts.length)) continue;  // 无课文不列出
      const qs = await api(`/api/questions?lesson_id=${l.id}`);
      out.push({id:l.id, subject:l.subject, title:l.title, questions:qs||[]});
    }
  }
  questionLessons = out;
}
function renderQuestionTab(){
  if(questionLessons.length===0){
    return `<div class="parent-grid"><div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic blue">${icon('book',20)}</div><div><h3>题目管理</h3><div class="sub">管理每课的阅读理解题：重新生成、添加或删除</div></div></div>
      <div class="bd" style="text-align:center;padding:32px 0;color:#8e9691">暂无已提取课文的课程，请先在「教材」中上传并提取。</div>
    </div></div>`;
  }
  const rows = questionLessons.map(l=>{
    const qCards = (l.questions.length===0)
      ? `<div style="color:#a0a7a2;font-size:13px;padding:8px 0">本课暂无题目</div>`
      : l.questions.map(q=>`
        <div class="q-card" style="display:flex;gap:10px;align-items:flex-start;padding:10px 12px;background:#f7f9f7;border:1px solid var(--line3);border-radius:10px;margin-top:8px">
          <div style="flex:1;min-width:0">
            <div style="font-size:13px;font-weight:600;color:#333">${q.question}</div>
            <div style="font-size:12px;color:#778079;margin-top:2px">答案：${q.answer||'—'}</div>
          </div>
          <button class="btn-ghost" style="color:#c05b4a;flex-shrink:0" onclick="delQuestion(${q.id})">删除</button>
        </div>`).join('');
    return `<div class="parent-panel" style="grid-column:1/-1">
      <div class="head">
        <div class="ic ${l.subject==='语文'?'blue':'orange'}">${icon('book',20)}</div>
        <div><h3>${l.subject} · ${l.title}</h3><div class="sub">共 ${l.questions.length} 道阅读理解题</div></div>
        <div style="margin-left:auto;display:flex;gap:6px">
          <button class="btn-ghost" onclick="addQuestion(${l.id})">+ 添加</button>
          <button class="btn-ghost" onclick="regenerateQuestions(${l.id})">重新生成</button>
        </div>
      </div>
      <div class="bd">${qCards}</div>
    </div>`;
  }).join('');
  return `<div class="parent-grid">${rows}</div>`;
}
async function addQuestion(lessonId){
  const question = prompt('请输入题目：');
  if(!question) return;
  const answer = prompt('请输入答案（可留空）：') || '';
  const r = await api('/api/questions', {method:'POST', body:{lesson_id:lessonId, question, answer}});
  if(r && r.id!==undefined){
    toast('已添加');
    await loadQuestionData(); render();
  } else {
    toast('添加失败');
  }
}
async function regenerateQuestions(lessonId){
  if(!confirm('重新生成将覆盖本课现有题目，确定吗？')) return;
  toast('正在生成…');
  const r = await api('/api/questions/generate', {method:'POST', body:{lesson_id:lessonId, n:3}});
  if(r && r.count!==undefined){
    await loadQuestionData(); render();
    toast('已重新生成 ' + r.count + ' 题');
  } else {
    toast('生成失败');
  }
}
async function delQuestion(id){
  if(!confirm('确定删除这道题吗？')) return;
  const r = await api(`/api/questions/${id}`, {method:'DELETE'});
  if(r && r.ok){
    await loadQuestionData(); render();
    toast('已删除');
  } else {
    toast('删除失败');
  }
}

// ---- 任务审核 ----
async function loadParentTasks(){
  if(!parentTaskDate){
    const t = new Date();
    parentTaskDate = `${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,'0')}-${String(t.getDate()).padStart(2,'0')}`;
  }
  parentTasks = await api(`/api/tasks?user_id=${uid}&date=${parentTaskDate}&role=parent`);
  if(!Array.isArray(parentTasks)) parentTasks = [];
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
        (t.photo_path ? `<a href="/${t.photo_path}" target="_blank" style="font-size:12px;color:#3158e8;text-decoration:none;align-self:center">查看照片</a>` : '');
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
async function approveAllTasks(){ await api(`/api/tasks/approve-all`,{method:'POST',body:{user_id:uid,date:parentTaskDate}}); await loadParentTasks(); render(); }
async function deleteTask(id){ await api(`/api/tasks/${id}`,{method:'DELETE'}); await loadParentTasks(); render(); }
async function confirmTask(id){ await api(`/api/tasks/${id}/confirm`,{method:'POST'}); toast('已确认，积分已发放'); await loadParentTasks(); render(); }
async function showAddTask(){
  const title = prompt('任务标题');
  if(!title) return;
  const subject = prompt('科目（语文/英语）', '语文') || '语文';
  await api(`/api/tasks`,{method:'POST',body:{user_id:uid,date:parentTaskDate,task_type:'custom',subject:subject,title:title,detail:'',points:20}});
  await loadParentTasks(); render();
}

function renderParent(){
  const tabs = ['教材','知识点','题目','目标','报告','任务','规则','设置'].map(t=>
    `<button class="filter-btn ${parentTab===t?'active':''}" style="border-radius:10px;padding:8px 16px;font-size:13px;font-weight:600;color:${parentTab===t?'#3158e8':'#778079'};background:${parentTab===t?'#fff':'transparent'}" onclick="setParentTab('${t}')">${t}</button>`
  ).join('');

  let body='';
  if(parentTab==='教材') body = renderPdfTab();
  else if(parentTab==='知识点') body = renderKnowledgeTab();
  else if(parentTab==='题目') body = renderQuestionTab();
  else if(parentTab==='目标') body = renderGoalsTab();
  else if(parentTab==='报告') body = renderReportTab();
  else if(parentTab==='任务') body = renderTaskTab();
  else if(parentTab==='规则') body = renderRulesTab();
  else if(parentTab==='设置') body = renderSettingsTab();

  return `<div class="parent-banner">
    <div class="l"><div class="ic">${icon('star',20)}</div><div><div class="t">家长端 · 管理学习目标与规则</div><div class="s">在这里录入教材、设定目标、查看薄弱报告</div></div></div>
    <div style="display:flex;gap:8px;background:#f2f4f1;border-radius:12px;padding:4px">${tabs}</div>
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
            <div class="s">支持语文 / 英语教材，上传后自动识别目录并拆课</div>
          </div>
          <input type="file" id="pdfFile" accept="application/pdf" style="display:none" onchange="uploadPdf(this)">
          <div style="margin-top:12px;display:flex;gap:8px;align-items:center">
            <span style="font-size:13px;color:var(--gray2)">学科：</span>
            <select id="pdfSubject" style="border:1px solid var(--line3);border-radius:10px;padding:8px 12px;font-size:13px"><option>语文</option><option>英语</option></select>
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
  const subjColor = s => s==='语文'?'var(--blue-soft);color:var(--blue2)':'var(--orange-soft);color:var(--orange2)';
  const yw = knowledgeRows.filter(p=>p.subject==='语文');
  const en = knowledgeRows.filter(p=>p.subject==='英语');
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
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic purple">${icon('sparkles',20)}</div><div><h3>添加知识点</h3><div class="sub">手动补充教材外的基础知识，AI 据此出题</div></div></div>
      <div class="bd">
        <div style="display:flex;gap:8px">
          <select id="kpSubject" style="border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"><option>语文</option><option>英语</option></select>
          <select id="kpCategory" style="border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"><option>字词</option><option>拼音</option><option>句式</option><option>古诗文</option><option>语法</option><option>句型</option></select>
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
    const statusMap = {pending:['待开始','#eef0ed','#78817b','#d5dad5',0,'3 个知识点 · 待开始'], in_progress:['学习中','var(--orange-soft)','var(--orange2)','var(--orange)',72,'15 个生词 · 已掌握 11 个'], done:['已掌握','var(--green-soft2)','var(--green)','var(--green)',100,'20 个单词 · 全部掌握']};
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
  // 登录默认孩子
  const u = await api('/api/auth/login', {method:'POST', body:{name:'金宇轩'}});
  uid = u.id;
  document.getElementById('userName').textContent = u.name;
  await loadPoints();
  await loadCenter();
  dictWords = await api(`/api/dictation/words?user_id=${uid}`);
  // 预载 AI 配置，让模型 chip 显示真实默认模型（失败不影响其它功能）
  try{ await loadConfig(); }catch(e){}
  // 点击别处关闭模型/模式下拉
  document.addEventListener('click', (e)=>{
    if(chatMenu && !e.target.closest('.im-chips')){ chatMenu = null; renderImmersiveChips(); }
  });
  // 沉浸页面板拖拽：分隔条用 Pointer Events + setPointerCapture，拖拽中直接改
  // grid 列宽（不触发整体 render），松手后持久化到 localStorage。
  let drag = null;  // {side, pointerId, startX, startW, grid}
  document.addEventListener('pointerdown', (e)=>{
    const sep = e.target.closest && e.target.closest('.im-sep');
    if(!sep || e.button !== 0) return;
    const side = sep.dataset.side;      // 'nav' | 'chat'
    const body = sep.closest('.im-body');
    const grid = body && getComputedStyle(body).gridTemplateColumns;
    if(!grid) return;
    e.preventDefault();
    drag = {side, pointerId: e.pointerId, startX: e.clientX, startW: side==='nav'?navWidth:chatWidth};
    try { sep.setPointerCapture(e.pointerId); } catch(_){ /* 合成事件无活动指针时忽略，仍走 document 级 move/up */ }
    sep.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  });
  document.addEventListener('pointermove', (e)=>{
    if(!drag || e.pointerId !== drag.pointerId) return;
    const body = document.querySelector('.im-body');
    if(!body) return;
    const dx = e.clientX - drag.startX;
    // nav 分隔条向右拖=加宽；chat 分隔条向左拖=加宽
    const dir = drag.side === 'nav' ? 1 : -1;
    const [min,max] = drag.side === 'nav' ? [NAV_MIN,NAV_MAX] : [CHAT_MIN,CHAT_MAX];
    const w = Math.round(Math.min(max, Math.max(min, drag.startW + dir * dx)));
    if(drag.side === 'nav'){
      navWidth = w;
      body.style.gridTemplateColumns = `${navWidth}px 5px minmax(0,1fr) ${chatOpen?'5px '+chatWidth+'px':'0 0'}`;
      const nav = body.querySelector('.im-nav'); if(nav) nav.style.width = navWidth + 'px';
    } else {
      chatWidth = w;
      body.style.gridTemplateColumns = `${navOpen?navWidth+'px 5px':'0 0'} minmax(0,1fr) 5px ${chatWidth}px`;
      const side = body.querySelector('.im-side'); if(side) side.style.width = chatWidth + 'px';
    }
  });
  const endDrag = (e)=>{
    if(!drag || e.pointerId !== drag.pointerId) return;
    const side = drag.side;
    drag = null;
    document.querySelectorAll('.im-sep').forEach(s=>s.classList.remove('dragging'));
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    savePanelWidth(side, side==='nav'?navWidth:chatWidth);
  };
  document.addEventListener('pointerup', endDrag);
  document.addEventListener('pointercancel', endDrag);
  renderNav(); render();
}
async function loadPoints(){
  const d = await api(`/api/points/balance?user_id=${uid}`);
  points = d.balance || 0;
}

init();
