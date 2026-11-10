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
  ['教材','book'],['知识点','brain'],['题库管理','grid'],['题目审核台','list'],['目标','star'],['报告','chart'],
  ['任务','pen'],['规则','gift'],['学习配置','grid'],['屏幕时间','clock'],['设置','menu'],
  ['孩子管理','star']
];
const CHILD_TABS = ['目标','报告','任务','屏幕时间'];   // 依赖当前孩子（uid）的 Tab
const CHILD_KEY = 'knoact_parent_child_id';
const ACCESS_TOKEN_KEY = 'knoact_access_token';
const REFRESH_TOKEN_KEY = 'knoact_refresh_token';
let parentId = null;       // 当前登录家长 id（来自 /api/auth/me）
let parentName = '';
let loginAuthMode = 'login'; // 'login' | 'register'
let familyInvite = null;   // {code, expires_at}
let familyRequests = [];
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
let boundUsers = [];   // 当前打开绑定弹窗的教材已绑定的孩子 id 列表
let bindDocId = null;  // 正在绑定管理的教材 id
let archivedChildren = [];  // 已归档的孩子（include_archived 拉取后过滤）
let showArchived = false;   // 孩子管理页是否显示已归档孩子
let childDocs = null;       // {child_id, documents:[...]} 当前打开"看教材"的孩子
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
let ttsConfig = {provider:'minimax', voice:'清澈男声', key:'', baseUrl:'', model:'speech-2.8-hd', speed:1.0, repeat:2, appId:'', apiSecret:''};
const MS_TTS_VOICES = {
  xunfei: ['讯飞女声','讯飞男声','标准普通话'],
  minimax: ['male-qn-qingse','female-shaonv','presenter_male'],
  openai: ['alloy','echo','fable','onyx','nova','shimmer'],
};

// 家长端任务审核
let parentTaskDate = '';   // 家长端任务查看的日期（默认今天）
let parentTasks = [];      // 当天全部任务（含待审核）

// 屏幕时间
let screenGroups = [];     // [{id,name,kind,daily_limit_seconds}]
let screenRules = [];      // [{app_package,app_name,group_id}]
let screenUsage = [];      // [{group_id,name,kind,duration_seconds,daily_limit_seconds,overtime}]
let screenDate = '';       // 查看的日期（默认今天）

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

function getAccessToken(){
  try{ return localStorage.getItem(ACCESS_TOKEN_KEY) || ''; }catch(e){ return ''; }
}
function getRefreshToken(){
  try{ return localStorage.getItem(REFRESH_TOKEN_KEY) || ''; }catch(e){ return ''; }
}
function setTokens(access, refresh){
  try{
    localStorage.setItem(ACCESS_TOKEN_KEY, access);
    if(refresh) localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
  }catch(e){}
}
function clearAuthTokens(){
  try{
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem('knoact_parent_id');
    localStorage.removeItem('knoact_parent_name');
  }catch(e){}
}
function authHeaders(extra={}){
  const h = {'Content-Type':'application/json', ...extra};
  const t = getAccessToken();
  if(t) h.Authorization = `Bearer ${t}`;
  return h;
}
function apiErrorMsg(data, fallback='请求失败'){
  if(!data || typeof data !== 'object') return fallback;
  const d = data.detail;
  if(typeof d === 'string') return d;
  if(d && typeof d === 'object' && d.error){
    const map = {invalid_credentials:'账号或密码错误', login_name_taken:'登录名已被占用', invalid_login_name:'登录名格式无效'};
    return map[d.error] || d.error;
  }
  if(data.error) return String(data.error);
  return fallback;
}
async function api(path, opts={}){
  const init = {headers: authHeaders(), ...opts};
  if(opts.body) init.body = JSON.stringify(opts.body);
  const r = await fetch(API + path, init);
  const ct = r.headers.get('content-type')||'';
  return ct.includes('json') ? r.json() : r.text();
}
const sleep = ms => new Promise(res=>setTimeout(res,ms));
async function apiForm(path, formData){
  const h = {};
  const t = getAccessToken();
  if(t) h.Authorization = `Bearer ${t}`;
  const r = await fetch(API + path, {method:'POST', headers:h, body:formData});
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
  if(parentTab==='题库管理') updateReadingPreview();
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
  else if(parentTab==='屏幕时间') await Promise.all([loadScreenGroups(), loadScreenUsage()]);
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

// ---- 孩子管理 ----
async function loadArchivedChildren(){
  const q = parentId ? `&parent_id=${parentId}` : '';
  const list = await api(`/api/users?role=child&include_archived=1${q}`);
  archivedChildren = Array.isArray(list) ? list.filter(c => c.status === 'archived') : [];
}

function renderChildMgmt(){
  const visible = showArchived ? [...children, ...archivedChildren] : children;
  const rows = visible.map(c=>{
    const isArchived = c.status === 'archived';
    return `<div class="pdf-row">
      <div><div class="nm">${escapeAttr(c.name)}${isArchived?' <span style="color:#c05b4a">（已归档）</span>':''}</div>
        <div class="meta">${c.grade?c.grade+'年级':''}${c.edition?' · '+c.edition:''}</div></div>
      <div style="display:flex;gap:6px;margin-left:auto;align-items:center">
        <button class="btn-ghost" onclick="editChild(${c.id})">编辑</button>
        <button class="btn-ghost" onclick="openChildDocs(${c.id})">看教材</button>
        ${isArchived
          ? `<button class="btn-ghost" style="color:#2e8b5a" onclick="unarchiveChild(${c.id})">恢复</button>`
          : `<button class="btn-ghost" style="color:#c05b4a" onclick="archiveChild(${c.id})">归档</button>`}
      </div>
    </div>`;
  }).join('');
  return `<div class="parent-grid">
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic blue">${icon('star',20)}</div><div><h3>孩子管理</h3><div class="sub">新建、编辑、归档孩子；查看孩子绑定的教材</div></div>
        <button class="btn-ghost" style="margin-left:auto" onclick="showArchived=!showArchived;loadArchivedChildren().then(render)">${showArchived?'只看活跃':'显示已归档'}</button></div>
      <div class="bd">${rows || '<div style="color:#8e9691;padding:8px 0">暂无孩子</div>'}
        <button class="next-lesson-btn" style="margin-top:16px" onclick="showAddChild()">${icon('check',16)} 新建孩子</button>
      </div>
    </div>
    ${renderFamilyBindPanel()}
    ${renderChildDocs()}
  </div>`;
}

function renderChildDocs(){
  if(!childDocs) return '';
  const rows = childDocs.documents.map(d=>`
    <div class="pdf-row"><div><div class="nm">${escapeAttr(d.filename)}</div><div class="meta">${d.subject}${d.grade?(' · '+d.grade+'年级'):''}${d.edition?(' · '+d.edition):''}</div></div>
      <div style="display:flex;gap:6px;margin-left:auto;align-items:center">
        <button class="btn-ghost" style="color:#c05b4a" onclick="unbindFromChild(${childDocs.child_id}, ${d.id})">解除绑定</button>
      </div></div>`).join('');
  return `<div class="parent-panel" style="grid-column:1/-1">
    <div class="head"><div class="ic blue">${icon('book',20)}</div><div><h3>孩子绑定的教材</h3><div class="sub">该孩子当前可见的教材</div></div>
      <button class="btn-ghost" style="margin-left:auto" onclick="childDocs=null;render()">关闭</button></div>
    <div class="bd">${rows || '<div style="color:#8e9691;padding:8px 0">尚未绑定教材，请到「教材」页勾选</div>'}</div>
  </div>`;
}

async function editChild(id){
  const c = children.find(x=>x.id===id) || archivedChildren.find(x=>x.id===id);
  if(!c) return;
  const name = prompt('姓名', c.name || '');
  if(name === null) return;
  const grade = prompt('年级（1-6）', String(c.grade || '1'));
  if(grade === null) return;
  if(!grade || isNaN(Number(grade))){ toast('年级需为数字'); return; }
  const edition = prompt('教材版本（可留空）', c.edition || '') || '';
  await api(`/api/children/${id}`, {method:'PUT', body:{name:name.trim(), grade:Number(grade), edition}});
  toast('已保存');
  await loadChildren(); await loadArchivedChildren();
  render();
}

async function archiveChild(id){
  if(!confirm('归档后该孩子将无法登录，数据会保留。确定吗？')) return;
  await api(`/api/children/${id}/archive`, {method:'POST'});
  toast('已归档');
  await loadChildren(); await loadArchivedChildren();
  render();
}

async function unarchiveChild(id){
  await api(`/api/children/${id}/unarchive`, {method:'POST'});
  toast('已恢复');
  await loadChildren(); await loadArchivedChildren();
  render();
}

async function openChildDocs(id){
  const r = await api(`/api/children/${id}/documents`);
  childDocs = { child_id: id, documents: (r && r.documents) || [] };
  render();
}

async function unbindFromChild(childId, documentId){
  await api(`/api/pdf/documents/${documentId}/bind?user_id=${childId}`, {method:'DELETE'});
  toast('已解除绑定');
  const r = await api(`/api/children/${childId}/documents`);
  childDocs = { child_id: childId, documents: (r && r.documents) || [] };
  render();
}

function setParentTab(t){
  parentTab=t;
  renderNav();
  if(t==='教材'){ loadPdfDocs().then(()=>render()); return; }
  if(t==='知识点'){ loadKnowledge().then(()=>render()); return; }
  if(t==='题库管理'){ loadBankList().then(()=>render()); return; }
  if(t==='题目审核台'){ loadReviewQuestions().then(()=>render()); return; }
  if(t==='目标'){ loadGoals().then(()=>render()); return; }
  if(t==='报告'){ Promise.all([loadReport(), loadMasteryReport()]).then(()=>render()); return; }
  if(t==='任务'){ loadParentTasks().then(()=>render()); return; }
  if(t==='屏幕时间'){ Promise.all([loadScreenGroups(), loadScreenUsage()]).then(()=>render()); return; }
  if(t==='学习配置'){ loadConfig().then(()=>loadLearningPreferences()).then(()=>render()); return; }
  if(t==='设置'){ loadConfig().then(()=>render()); return; }
  if(t==='孩子管理'){ Promise.all([loadChildren(), loadArchivedChildren(), loadFamilyRequests()]).then(()=>render()); return; }
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
async function loadLearningPreferences(){
  if(!uid){ return; }
  try{
    const r = await api(`/api/learning/preferences?user_id=${uid}`);
    if(r && typeof r === 'object'){
      for(const k in r){
        configMap[k] = String(r[k]);
      }
    }
    if(!configMap.dictation_input_mode) configMap.dictation_input_mode = 'paper_photo';
  }catch(e){
    configMap.dictation_input_mode = configMap.dictation_input_mode || 'paper_photo';
  }
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
  ttsConfig.appId = configMap.tts_app_id || '';
  ttsConfig.apiSecret = configMap.tts_api_secret || '';
}

// ---- 题库管理 ----
const BANK_QTYPE_LABEL = {
  single_choice:'单选题', multi_choice:'多选题', true_false:'判断题',
  fill_blank:'填空题', cloze:'完形填空', calculation:'计算题', matching:'连线题',
  short_answer:'简答题', essay:'作文', application:'应用题', oral:'口语题',
};
const BANK_QTYPE_CATEGORY = {
  single_choice:'choice', multi_choice:'choice', true_false:'choice',
  fill_blank:'blank', cloze:'blank', calculation:'blank',
  matching:'match',
  short_answer:'subjective', essay:'subjective', application:'subjective', oral:'subjective',
};
const BANK_QTYPES = Object.keys(BANK_QTYPE_LABEL);
let bankEntryMode = 'single'; // single | reading
let readingDraft = {title:'', content:''};
function _emptyReadingSub(){
  return {qtype:'single_choice', question:'', analysis:'', difficulty:'medium',
          blanks:'', pairs:'', subjAnswer:'', rubric:'', options:['','','',''],
          correct:0, multiCorrect:[]};
}
let readingSubs = [_emptyReadingSub()];

function captureReadingForm(){
  const titleEl = document.getElementById('readingTitle');
  if(!titleEl) return;
  readingDraft.title = titleEl.value;
  readingDraft.content = document.getElementById('readingContent')?.value || '';
  readingSubs = readingSubs.map((sub,i)=>{
    const suf = '-'+i;
    const opts = [];
    for(let j=0;j<4;j++) opts[j] = document.getElementById('bankOptLabel'+j+suf)?.value || '';
    const picked = document.querySelector('input[name="bankSingleCorrect'+suf+'"]:checked');
    const multi = [...document.querySelectorAll('input[name="bankMultiCorrect'+suf+'"]:checked')].map(el=>Number(el.value));
    return {
      qtype: sub.qtype,
      question: document.getElementById('bankQText'+suf)?.value || '',
      analysis: document.getElementById('bankAnalysis'+suf)?.value || '',
      difficulty: document.getElementById('bankDifficulty'+suf)?.value || 'medium',
      blanks: document.getElementById('bankBlanks'+suf)?.value || '',
      pairs: document.getElementById('bankPairs'+suf)?.value || '',
      subjAnswer: document.getElementById('bankSubjAnswer'+suf)?.value || '',
      rubric: document.getElementById('bankRubric'+suf)?.value || '',
      options: opts,
      correct: picked ? Number(picked.value) : (sub.correct||0),
      multiCorrect: multi,
    };
  });
}
function setBankEntryMode(m){
  if(bankEntryMode==='reading') captureReadingForm();
  bankEntryMode = m;
  if(m==='reading' && (!readingSubs || !readingSubs.length)) readingSubs = [_emptyReadingSub()];
  render();
}
function setReadingSubQtype(i, v){ captureReadingForm(); readingSubs[i].qtype = v; render(); }
function addReadingSub(){ captureReadingForm(); readingSubs.push(_emptyReadingSub()); render(); }
function removeReadingSub(i){ if(readingSubs.length>1){ captureReadingForm(); readingSubs.splice(i,1); render(); } }

function escapeHtml(s){
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function renderPassageInline(escaped){
  return escaped
    .replace(/____/g, '<span class="passage-blank"></span>')
    .replace(/&lt;u&gt;([\s\S]*?)&lt;\/u&gt;/g, '<u>$1</u>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\/([^\/:\n]{1,40})\//g, '<span class="passage-ipa">/$1/</span>');
}
function renderPassageMarkup(src){
  return (src||'').split('\n').map(line=>{
    const raw = line.replace(/\s+$/,'');
    if(/^##\s+/.test(raw)){
      return '<h2>'+renderPassageInline(escapeHtml(raw.replace(/^##\s+/,'')))+'</h2>';
    }
    if(/^#\s+/.test(raw)){
      return '<h1>'+renderPassageInline(escapeHtml(raw.replace(/^#\s+/,'')))+'</h1>';
    }
    return renderPassageInline(escapeHtml(raw)) || '<br>';
  }).join('<br>');
}
let bankList = [];
let bankSelectedId = null;
let bankAddQtype = 'single_choice';
const BANK_SOURCE_LABEL = {manual:'手动录入', photo:'拍照识别', third_party:'第三方/混合'};
function bankFormDefaultGrade(){
  const c = children.find(x=>x.id===uid);
  return c && c.grade ? String(c.grade) : '';
}

async function loadBankList(){
  const rows = await api('/api/banks');
  bankList = Array.isArray(rows) ? rows : [];
  if(bankSelectedId && !bankList.find(b=>b.id===bankSelectedId)) bankSelectedId = null;
}
async function createBankFromForm(){
  const title = (document.getElementById('bankNewTitle')?.value||'').trim();
  const subject = document.getElementById('bankNewSubject')?.value||'';
  const gradeRaw = document.getElementById('bankNewGrade')?.value||'';
  const grade = gradeRaw ? Number(gradeRaw) : null;
  if(!title){ toast('请填写卷子标题'); return; }
  const includeDaily = !!document.getElementById('bankIncludeDaily')?.checked;
  const r = await api('/api/banks', {method:'POST', body:{title, subject, grade, tags:{include_daily_task:includeDaily}}});
  if(r && r.id){ toast('卷子已创建'); await loadBankList(); bankSelectedId = r.id; render(); }
  else toast(apiErrorMsg(r, '创建失败'));
}
function selectBank(id){ bankSelectedId = Number(id)||null; bankAddQtype = 'single_choice'; render(); }
function setBankAddQtype(v){ bankAddQtype = v; render(); }

function _fieldSuf(idx){ return (idx==null || idx===undefined) ? '' : '-'+idx; }
function buildBankQuestionPayload(idx){
  const suf = _fieldSuf(idx);
  const qtype = idx==null ? bankAddQtype : readingSubs[idx].qtype;
  const question = (document.getElementById('bankQText'+suf)?.value||'').trim();
  const analysis = (document.getElementById('bankAnalysis'+suf)?.value||'').trim();
  const difficulty = document.getElementById('bankDifficulty'+suf)?.value
    || document.getElementById('bankDifficulty')?.value || 'medium';
  const cat = BANK_QTYPE_CATEGORY[qtype]||'subjective';
  let options = [], answer_json = {}, answer = '';
  if(cat==='choice'){
    options = bankChoiceOptionsFromForm(idx);
    if(qtype==='multi_choice'){
      const checks = document.querySelectorAll('input[name="bankMultiCorrect'+suf+'"]:checked');
      const ix = [...checks].map(el=>Number(el.value)).filter(n=>!Number.isNaN(n));
      answer_json = {correct_index: ix.length?ix:[0]};
      answer = ix.map(i=>options[i]?.label).filter(Boolean).join('、');
    }else{
      const picked = document.querySelector('input[name="bankSingleCorrect'+suf+'"]:checked');
      const ci = picked ? Number(picked.value) : 0;
      const correct = Number.isNaN(ci)?0:ci;
      answer_json = {correct_index: correct};
      answer = options[correct]?.label || '';
    }
  }else if(cat==='blank'){
    const raw = (document.getElementById('bankBlanks'+suf)?.value||'').trim();
    const blanks = raw.split(/[,，;；\n]+/).map(s=>s.trim()).filter(Boolean);
    answer_json = {blanks};
    answer = blanks.join('；');
  }else if(cat==='match'){
    const raw = (document.getElementById('bankPairs'+suf)?.value||'').trim();
    const pairs = [];
    raw.split('\n').forEach(line=>{
      const p = line.split(/[→\-=]/).map(s=>s.trim()).filter(Boolean);
      if(p.length>=2) pairs.push([p[0], p[1]]);
    });
    answer_json = {pairs};
    answer = pairs.map(p=>p.join('→')).join('；');
  }else{
    answer = (document.getElementById('bankSubjAnswer'+suf)?.value||'').trim();
    const rubric = (document.getElementById('bankRubric'+suf)?.value||'').trim();
    answer_json = {sample: answer, rubric};
  }
  return {lesson_id:null, bank_id:bankSelectedId, qtype, question, answer, options, answer_json, analysis, difficulty, tags:{}};
}
function bankChoiceOptionsFromForm(idx){
  const suf = _fieldSuf(idx);
  const n = Math.max(2, Math.min(8, parseInt(document.getElementById('bankOptCount'+suf)?.value||'4', 10)||4));
  const opts = [];
  for(let i=0;i<n;i++){
    const label = (document.getElementById(`bankOptLabel${i}${suf}`)?.value||'').trim() || `选项${String.fromCharCode(65+i)}`;
    opts.push({label, value:i});
  }
  return opts;
}
async function submitBankQuestion(){
  if(!bankSelectedId){ toast('请先选择一张卷子'); return; }
  const body = buildBankQuestionPayload();
  if(!body.question){ toast('请填写题干'); return; }
  const r = await api('/api/questions', {method:'POST', body});
  if(r && r.id){
    toast('题目已提交审核');
    document.getElementById('bankQText').value = '';
    render();
  }else toast(apiErrorMsg(r, '提交失败'));
}

function renderBankChoiceFields(idx){
  const suf = _fieldSuf(idx);
  const qtype = idx==null ? bankAddQtype : readingSubs[idx].qtype;
  const sub = idx==null ? null : readingSubs[idx];
  const multi = qtype==='multi_choice';
  const n = 4;
  const optRows = [...Array(n)].map((_,i)=>{
    const letter = String.fromCharCode(65+i);
    const val = sub && sub.options && sub.options[i] ? escapeAttr(sub.options[i]) : '';
    const checkedSingle = !multi && ((sub ? Number(sub.correct||0) : 0) === i);
    const checkedMulti = multi && sub && Array.isArray(sub.multiCorrect) && sub.multiCorrect.includes(i);
    const mark = multi
      ? `<label class="bank-opt-mark"><input type="checkbox" name="bankMultiCorrect${suf}" value="${i}" ${checkedMulti?'checked':''}/>正确答案</label>`
      : `<label class="bank-opt-mark"><input type="radio" name="bankSingleCorrect${suf}" value="${i}" ${checkedSingle?'checked':''}/>正确答案</label>`;
    return `<div class="bank-opt-row">
      <span class="bank-opt-letter">${letter}</span>
      <input id="bankOptLabel${i}${suf}" class="inp" placeholder="选项 ${letter} 内容" value="${val}" />
      ${mark}
    </div>`;
  }).join('');
  const hint = multi ? '可多选「正确答案」' : '勾选唯一正确答案';
  return `<div class="bank-q-block">
    <span class="bank-field-label">选项 <span style="font-weight:500;color:#9aa39d">${hint}</span></span>
    <div class="bank-opt-list">${optRows}</div>
  </div>`;
}
function renderBankAnswerFields(qtype, idx){
  const suf = _fieldSuf(idx);
  const cat = BANK_QTYPE_CATEGORY[qtype]||'subjective';
  const sub = idx==null ? null : readingSubs[idx];
  if(cat==='choice') return renderBankChoiceFields(idx);
  if(cat==='blank'){
    const reading = idx!=null;
    const saved = sub ? escapeHtml(sub.blanks||'') : '';
    const label = reading ? '本空参考答案（一空一题，只填这一空）' : '参考答案（多空用逗号或换行分隔）';
    const ph = reading ? '如：游啊游' : '如：春天,播种';
    return `<div class="bank-q-block"><label class="bank-field-label">${label}</label>
      <textarea id="bankBlanks${suf}" class="inp" rows="2" placeholder="${ph}">${saved}</textarea></div>`;
  }
  if(cat==='match'){
    const saved = sub ? escapeHtml(sub.pairs||'') : '';
    return `<div class="bank-q-block"><label class="bank-field-label">连线答案（每行一对，用 → 分隔）</label>
      <textarea id="bankPairs${suf}" class="inp" rows="3" placeholder="苹果→红色">${saved}</textarea></div>`;
  }
  const subj = sub ? escapeHtml(sub.subjAnswer||'') : '';
  const rub = sub ? escapeHtml(sub.rubric||'') : '';
  return `<div class="bank-q-block">
    <label class="bank-field-label">参考答案 / 范文</label>
    <textarea id="bankSubjAnswer${suf}" class="inp" rows="2">${subj}</textarea>
    <label class="bank-field-label" style="margin-top:12px">评分要点（可选）</label>
    <textarea id="bankRubric${suf}" class="inp" rows="2">${rub}</textarea>
  </div>`;
}
function renderReadingForm(){
  const qBlocks = readingSubs.map((sub,i)=>{
    const qtypeOpts = BANK_QTYPES.map(q=>`<option value="${q}" ${q===sub.qtype?'selected':''}>${BANK_QTYPE_LABEL[q]}</option>`).join('');
    const diff = sub.difficulty || 'medium';
    return `<div class="reading-sub">
      <div class="reading-sub-head">
        <strong>子题 ${i+1}</strong>
        ${readingSubs.length>1?`<button type="button" class="btn-ghost" onclick="removeReadingSub(${i})">删除</button>`:''}
      </div>
      <div class="bank-q-meta">
        <label class="bank-field"><span class="bank-field-label">题型</span>
          <select onchange="setReadingSubQtype(${i}, this.value)">${qtypeOpts}</select></label>
        <label class="bank-field"><span class="bank-field-label">难度</span>
          <select id="bankDifficulty-${i}">
            <option value="easy" ${diff==='easy'?'selected':''}>简单</option>
            <option value="medium" ${diff==='medium'?'selected':''}>中等</option>
            <option value="hard" ${diff==='hard'?'selected':''}>困难</option>
          </select></label>
      </div>
      <div class="bank-q-block">
        <label class="bank-field-label">题干</label>
        <textarea id="bankQText-${i}" class="inp" rows="3" placeholder="围绕材料出题">${escapeHtml(sub.question||'')}</textarea>
      </div>
      ${renderBankAnswerFields(sub.qtype, i)}
      <div class="bank-q-block">
        <label class="bank-field-label">解析（可选）</label>
        <textarea id="bankAnalysis-${i}" class="inp" rows="2">${escapeHtml(sub.analysis||'')}</textarea>
      </div>
    </div>`;
  }).join('');
  return `<div class="bank-q-block">
      <label class="bank-field-label">材料标题</label>
      <input id="readingTitle" class="inp" placeholder="如：小蝌蚪找妈妈" value="${escapeAttr(readingDraft.title||'')}" />
    </div>
    <div class="bank-q-block">
      <label class="bank-field-label">材料正文（可用 # 标题、**加粗**、*斜体*、&lt;u&gt;下划线&lt;/u&gt;、/音标/、____ 挖空）</label>
      <textarea id="readingContent" class="inp" rows="6" placeholder="在这里粘贴或编写短文" oninput="updateReadingPreview()">${escapeHtml(readingDraft.content||'')}</textarea>
      <div id="readingBlankHint" class="blank-hint"></div>
      <div class="bank-field-label" style="margin-top:10px">预览</div>
      <div id="readingPreview" class="passage-preview"></div>
    </div>
    ${qBlocks}
    <div class="bank-actions-primary" style="margin-top:12px">
      <button type="button" class="btn-ghost" onclick="addReadingSub()">加一道子题</button>
      <button type="button" class="btn-primary" onclick="submitReadingPassage()">提交整篇审核</button>
    </div>`;
}
function updateReadingPreview(){
  const content = document.getElementById('readingContent')?.value || '';
  const box = document.getElementById('readingPreview');
  if(box) box.innerHTML = renderPassageMarkup(content);
  const n = (content.match(/____/g)||[]).length;
  const fillN = (readingSubs||[]).filter(s=>s.qtype==='fill_blank'||s.qtype==='cloze').length;
  const hint = document.getElementById('readingBlankHint');
  if(!hint) return;
  if(fillN===0){ hint.className='blank-hint'; hint.textContent = n?`材料挖空 ${n} 处（无填空子题，挖空仅展示）`:''; return; }
  const ok = n===fillN;
  hint.className = 'blank-hint '+(ok?'ok':'bad');
  hint.textContent = `材料挖空 ${n} 处 / 填空子题 ${fillN} 道`+(ok?'，已对齐':'，须一致才能提交');
}
async function submitReadingPassage(){
  if(!bankSelectedId){ toast('请先选择一张卷子'); return; }
  const title = (document.getElementById('readingTitle')?.value||'').trim();
  const content = (document.getElementById('readingContent')?.value||'').trim();
  if(!title){ toast('请填写材料标题'); return; }
  if(!content){ toast('请填写材料正文'); return; }
  const questions = readingSubs.map((_,i)=>{
    const body = buildBankQuestionPayload(i);
    return {qtype:body.qtype, question:body.question, answer:body.answer,
            options:body.options, answer_json:body.answer_json,
            analysis:body.analysis, difficulty:body.difficulty, tags:body.tags};
  });
  if(questions.some(q=>!q.question)){ toast('请填写每道子题的题干'); return; }
  const blankN = (content.match(/____/g)||[]).length;
  const fillN = questions.filter(q=>q.qtype==='fill_blank'||q.qtype==='cloze').length;
  if(fillN>0 && blankN!==fillN){ toast(`材料挖空 ${blankN} 处，填空子题 ${fillN} 道，须一致`); return; }
  const bank = bankList.find(b=>b.id===bankSelectedId);
  const r = await api('/api/passages', {method:'POST', body:{
    title, content, subject: bank?.subject||'语文', grade: bank?.grade??null,
    bank_id: bankSelectedId, questions
  }});
  if(r && r.id){ toast('阅读理解已提交审核'); readingSubs=[_emptyReadingSub()]; readingDraft={title:'', content:''}; render(); }
  else toast(apiErrorMsg(r, '提交失败'));
}
function renderBankQuestionForm(){
  const qtypeOpts = BANK_QTYPES.map(q=>`<option value="${q}" ${q===bankAddQtype?'selected':''}>${BANK_QTYPE_LABEL[q]}</option>`).join('');
  const bank = bankList.find(b => b.id === bankSelectedId);
  const bankHint = bank ? `当前卷子：${bank.title}` : '';
  const extra = renderBankAnswerFields(bankAddQtype);
  const modeBar = `<div class="bank-mode-toggle">
    <button type="button" class="${bankEntryMode==='single'?'on':''}" onclick="setBankEntryMode('single')">单题</button>
    <button type="button" class="${bankEntryMode==='reading'?'on':''}" onclick="setBankEntryMode('reading')">阅读理解</button>
  </div>`;
  const importBar = `<div class="bank-import-bar">
          <div class="bank-import-title">批量导入（进审核台校对）</div>
          <div class="bank-import-btns">
            <button type="button" class="btn-ghost" onclick="syncBankFromTiku()">${icon('search',16)} tiku.cn</button>
            <button type="button" class="btn-ghost" onclick="syncBankFromXuekubao()">${icon('search',16)} 学库宝选题</button>
            <label class="btn-ghost" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;cursor:pointer;margin:0">
              ${icon('camera',16)} 拍照导入
              <input type="file" accept="image/*" multiple style="display:none" onchange="uploadBankPhoto(this)">
            </label>
          </div>
          <div class="bank-import-hint">阅读理解可一次选多页（按文件名顺序拼接，如 1.png、2.png）。导入后需先审核。</div>
        </div>`;
  const body = bankEntryMode==='reading'
    ? `${modeBar}${renderReadingForm()}${importBar}`
    : `${modeBar}
      <div class="bank-q-meta">
        <label class="bank-field"><span class="bank-field-label">题型</span>
          <select id="bankQtypeSelect" onchange="setBankAddQtype(this.value)">${qtypeOpts}</select></label>
        <label class="bank-field"><span class="bank-field-label">难度</span>
          <select id="bankDifficulty"><option value="easy">简单</option><option value="medium" selected>中等</option><option value="hard">困难</option></select></label>
      </div>
      <div class="bank-q-block">
        <label class="bank-field-label">题干</label>
        <textarea id="bankQText" class="inp" rows="4" placeholder="请输入题目正文，支持换行"></textarea>
      </div>
      ${extra}
      <div class="bank-q-block">
        <label class="bank-field-label">解析（可选）</label>
        <textarea id="bankAnalysis" class="inp" rows="2" placeholder="审核与孩子练习时可查看"></textarea>
      </div>
      <div class="bank-actions">
        <div class="bank-actions-primary">
          <button type="button" class="btn-primary" onclick="submitBankQuestion()">提交审核</button>
        </div>
        ${importBar}
      </div>`;
  return `<div class="parent-panel bank-qform" style="grid-column:1/-1;margin-top:16px">
    <div class="head"><div class="ic green">${icon('pen',20)}</div>
      <div><h3>录入题目</h3><div class="sub">${escapeAttr(bankHint || '提交后进入「题目审核台」，通过后孩子可练习')}</div></div></div>
    <div class="bd">${body}</div>
  </div>`;
}
function renderBankManage(){
  const defGrade = bankFormDefaultGrade();
  const gradeOpts = `<option value="">不指定</option>${[1,2,3,4,5,6].map(g =>
    `<option value="${g}" ${defGrade === String(g) ? 'selected' : ''}>小学${g}年级</option>`
  ).join('')}`;
  const rows = bankList.map(b=>{
    const subj = b.subject || '未设学科';
    const src = BANK_SOURCE_LABEL[b.source] || b.source || '手动录入';
    const cnt = typeof b.question_count === 'number' ? `${b.question_count} 题` : '';
    const daily = b.include_daily_task ? '<span class="bank-tag">每日任务</span>' : '';
    const sel = b.id===bankSelectedId;
    return `<div class="pdf-row bank-row ${sel?'bank-row-on':''}" onclick="selectBank(${b.id})">
      <div class="ic">${icon('book',22)}</div>
      <div class="bank-row-body">
        <div class="nm">${escapeAttr(b.title)} ${daily}</div>
        <div class="meta">${escapeAttr(subj)}${b.grade?(' · '+b.grade+'年级'):''}${cnt?(' · '+cnt):''} · ${escapeAttr(src)}</div>
      </div>
      <div class="st ${sel?'done':''}">${sel?'录入中':'选择'}</div>
    </div>`;
  }).join('');
  const form = bankSelectedId ? renderBankQuestionForm() : `<div class="parent-panel" style="grid-column:1/-1;margin-top:16px"><div class="bd" style="color:#8e9691;padding:24px">在下方列表点选一张卷子，即可录入、同步或拍照导入题目</div></div>`;
  return `<div class="parent-grid" style="display:block">
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic blue">${icon('grid',20)}</div>
        <div><h3>题库管理</h3><div class="sub">新建卷子并录入题目，经审核后进入学生端练习</div></div></div>
      <div class="bd">
        <form class="bank-create" onsubmit="event.preventDefault();createBankFromForm();">
          <div class="bank-create-grid">
            <label class="bank-field">
              <span class="bank-field-label">卷子标题</span>
              <input id="bankNewTitle" class="inp" type="text" placeholder="如：五年级数学单元测" autocomplete="off"/>
            </label>
            <label class="bank-field">
              <span class="bank-field-label">学科</span>
              <select id="bankNewSubject" class="inp">
                <option value="">请选择</option>
                <option>语文</option><option>数学</option><option>英语</option>
              </select>
            </label>
            <label class="bank-field">
              <span class="bank-field-label">年级</span>
              <select id="bankNewGrade" class="inp">${gradeOpts}</select>
            </label>
          </div>
          <div class="bank-create-foot">
            <label class="bank-daily">
              <input type="checkbox" id="bankIncludeDaily"/>
              <span>纳入每日任务</span>
              <span class="bank-daily-hint">勾选后，审核通过的题可进入孩子首页练习任务</span>
            </label>
            <button type="submit" class="btn-primary">新建卷子</button>
          </div>
        </form>
        <div class="bank-list-head">我的卷子 ${bankList.length ? `（${bankList.length}）` : ''}</div>
        <div class="bank-list">${rows || '<div class="bank-empty">还没有卷子，填写上方信息并点击「新建卷子」</div>'}</div>
      </div>
    </div>
    ${form}
  </div>`;
}

// ---- 题目审核台 ----
const QTYPE_LABEL = {
  knowledge:'基础知识', listening:'听力', reading:'阅读理解', math:'数学练习',
  ...BANK_QTYPE_LABEL,
};
let reviewGroups = [];          // [{subject, lesson_id, questions:[{id, qtype, question, answer, extra, task_type}]}]
let expandedLessons = new Set(); // 展开的分组 key（课程 id 或 bank-{id}）

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
async function approveByBank(bankId){
  await api(`/api/questions/approve-by-bank?bank_id=${bankId}&d=${todayStr()}`, {method:'POST'});
  await loadReviewQuestions(); render();
}
async function approveByPassage(passageId){
  await api(`/api/questions/approve-by-passage?passage_id=${passageId}&d=${todayStr()}`, {method:'POST'});
  await loadReviewQuestions(); render();
}
async function syncBankFromTiku(){
  if(!bankSelectedId){ toast('请先选择卷子'); return; }
  const keyword = (prompt('tiku.cn 搜索关键词（可空）','')||'').trim();
  const pageSize = Number(prompt('每页拉取条数（1-20）','10')||'10');
  const r = await api(`/api/banks/${bankSelectedId}/sync-tiku`, {
    method:'POST',
    body:{keyword, page:1, page_size:Math.max(1,Math.min(20,pageSize||10)), max_import:20},
  });
  if(r && r.count>0){ toast(`已导入 ${r.count} 道题，请到审核台确认`); await loadBankList(); }
  else toast((r && r.message) || apiErrorMsg(r, '同步失败或未配置 TIKU_CN_API'));
}
// 与学库宝 subjectEditionApi 一致：学段 → 年级(上下册) → 学科 → 教材版本（code 传给 chapterApi）
const XKB_LEVEL_LABELS = ['学段','年级','学科','教材版本'];
let xkbPicker = {
  open: false, loading: false, error: '', tree: [], sel: ['','','',''],
  chapters: null, knowledge: [], filter: '', picked: null, page: 1,
};

function xkbLevelOptions(depth){
  let nodes = xkbPicker.tree;
  if(!Array.isArray(nodes)) return [];
  for(let i = 0; i < depth; i++){
    const code = xkbPicker.sel[i];
    if(!code) return [];
    const hit = nodes.find(n => String(n.code ?? n.id) === String(code));
    nodes = hit && hit.child ? hit.child : [];
  }
  return nodes;
}
function xkbSetLevel(depth, code){
  xkbPicker.sel[depth] = code || '';
  for(let i = depth + 1; i < XKB_LEVEL_LABELS.length; i++) xkbPicker.sel[i] = '';
  xkbPicker.chapters = null;
  xkbPicker.knowledge = [];
  xkbPicker.picked = null;
  if(xkbPicker.sel[0]) loadXkbChapters();
  else paintXkbModal();
}
function xkbWalkChapters(nodes, path, out){
  for(const n of nodes || []){
    if(!n || typeof n !== 'object') continue;
    const name = (n.name || n.title || '').trim();
    const kids = n.child || n.children || [];
    const oldId = (n.oldId != null ? n.oldId : n.oldid != null ? n.oldid : n.knowledgeId);
    const kid = oldId != null ? String(oldId).trim() : '';
    const nextPath = name ? [...path, name] : path;
    if(kid && kid !== '0'){
      out.push({id: kid, name: name || kid, path: nextPath.join(' › ')});
    }
    if(kids.length) xkbWalkChapters(kids, nextPath, out);
  }
}
function xkbFilteredKnowledge(){
  const q = (xkbPicker.filter || '').trim().toLowerCase();
  if(!q) return xkbPicker.knowledge;
  return xkbPicker.knowledge.filter(k =>
    k.name.toLowerCase().includes(q) || k.path.toLowerCase().includes(q) || k.id.toLowerCase().includes(q));
}
function closeXuekubaoPicker(){
  xkbPicker.open = false;
  paintXkbModal();
}
function guessXkbDefaults(){
  const bank = bankList.find(b => b.id === bankSelectedId);
  const subj = (bank && bank.subject) || '';
  const grade = bank && bank.grade ? String(bank.grade) : bankFormDefaultGrade();
  const pick = (nodes, pred) => {
    if(!nodes || !nodes.length) return '';
    const hit = nodes.find(pred);
    return hit ? String(hit.code ?? hit.id) : '';
  };
  let nodes = xkbPicker.tree;
  const g = Number(grade);
  const phaseHint = g >= 7 ? '初' : g >= 10 ? '高' : '小';
  xkbPicker.sel[0] = pick(nodes, n => (n.name || '').includes(phaseHint)) || pick(nodes, () => true);
  nodes = (nodes.find(n => String(n.code ?? n.id) === xkbPicker.sel[0]) || {}).child || [];
  xkbPicker.sel[1] = pick(nodes, n => grade && (
    (n.name || '').includes(`${grade}年级`) || (n.name || '').includes(`年级${grade}`) ||
    (n.name || '').includes(`${['一','二','三','四','五','六','七','八','九'][grade-1] || grade}年级`)
  )) || pick(nodes, () => true);
  nodes = (nodes.find(n => String(n.code ?? n.id) === xkbPicker.sel[1]) || {}).child || [];
  xkbPicker.sel[2] = pick(nodes, n => subj && (n.name || '').includes(subj)) || pick(nodes, () => true);
  nodes = (nodes.find(n => String(n.code ?? n.id) === xkbPicker.sel[2]) || {}).child || [];
  xkbPicker.sel[3] = nodes.length === 1 ? String(nodes[0].code ?? nodes[0].id) : pick(nodes, () => true);
}
function xkbPickKnowledge(id){
  xkbPicker.picked = id;
  paintXkbModal();
}
async function openXuekubaoPicker(){
  if(!bankSelectedId){ toast('请先选择卷子'); return; }
  xkbPicker = {open:true, loading:true, error:'', tree:[], sel:['','','',''], chapters:null, knowledge:[], filter:'', picked:null, page:1};
  paintXkbModal();
  try{
    const r = await api('/api/xuekubao/subject-edition', {method:'POST', body:{}});
    if(r && r.detail){ throw new Error(r.detail); }
    xkbPicker.tree = Array.isArray(r && r.data) ? r.data : [];
    if(!xkbPicker.tree.length){ xkbPicker.error = '未获取到教材目录，请检查学库宝密钥'; }
    else { guessXkbDefaults(); if(xkbPicker.sel[0]) await loadXkbChapters(true); }
  }catch(e){
    xkbPicker.error = (e && e.message) || '加载失败：请在「设置 → 题库来源」配置学库宝 Access Key';
  }
  xkbPicker.loading = false;
  paintXkbModal();
}
async function loadXkbChapters(silent){
  if(!xkbPicker.sel[0]) return;
  if(!silent){ xkbPicker.loading = true; paintXkbModal(); }
  try{
    const [pharse_id, grade_id, subject_id, edition_id] = xkbPicker.sel;
    const r = await api('/api/xuekubao/chapters', {method:'POST', body:{
      pharse_id, subject_id, grade_id, edition_id,
    }});
    if(r && r.detail) throw new Error(r.detail);
    const data = (r && r.data) || [];
    const roots = Array.isArray(data) ? data : (data.child || data.children || [data]);
    const out = [];
    xkbWalkChapters(roots, [], out);
    const seen = new Set();
    xkbPicker.knowledge = out.filter(k => { if(seen.has(k.id)) return false; seen.add(k.id); return true; });
    xkbPicker.chapters = true;
    if(xkbPicker.knowledge.length && !xkbPicker.picked) xkbPicker.picked = xkbPicker.knowledge[0].id;
  }catch(e){
    xkbPicker.error = (e && e.message) || '章节加载失败';
    xkbPicker.knowledge = [];
  }
  xkbPicker.loading = false;
  paintXkbModal();
}
function paintXkbModal(){
  const el = document.getElementById('xkbModal');
  if(!el) return;
  if(!xkbPicker.open){ el.style.display = 'none'; el.innerHTML = ''; return; }
  el.style.display = 'flex';
  const cascade = XKB_LEVEL_LABELS.map((label, depth) => {
    const opts = xkbLevelOptions(depth);
    const disabled = depth > 0 && !xkbPicker.sel[depth - 1];
    const options = `<option value="">${disabled ? '请先选上一级' : '请选择'}</option>` +
      opts.map(n => {
        const code = String(n.code ?? n.id);
        const sel = xkbPicker.sel[depth] === code ? ' selected' : '';
        return `<option value="${escapeAttr(code)}"${sel}>${escapeAttr(n.name || code)}</option>`;
      }).join('');
    return `<label><span>${label}</span><select ${disabled?'disabled':''} onchange="xkbSetLevel(${depth}, this.value)">${options}</select></label>`;
  }).join('');
  const list = xkbFilteredKnowledge();
  const kps = list.length ? list.map(k => `
    <button type="button" class="xkb-kp-item ${xkbPicker.picked===k.id?'on':''}" onclick='xkbPickKnowledge(${JSON.stringify(k.id)})'>
      <span>${escapeAttr(k.name)}</span>
      <span class="xkb-kp-path">${escapeAttr(k.path)}</span>
    </button>`).join('') : `<div style="padding:16px;color:#8e9691;font-size:13px">${xkbPicker.chapters ? '该教材下未解析到知识点' : '选好教材后自动加载章节'}</div>`;
  const picked = xkbPicker.knowledge.find(k => k.id === xkbPicker.picked);
  el.innerHTML = `<div class="xkb-panel" role="dialog">
    <div class="hd">
      <h4>从学库宝按知识点拉题</h4>
      <p>先选学段与教材，再点选知识点（无需手工填 ID）</p>
    </div>
    <div class="bd">
      ${xkbPicker.error ? `<div style="color:#c05b4a;font-size:13px;margin-bottom:10px">${escapeAttr(xkbPicker.error)}</div>` : ''}
      ${xkbPicker.loading ? '<div style="color:#8e9691;font-size:13px">加载中…</div>' : ''}
      <div class="xkb-cascade">${cascade}</div>
      ${xkbPicker.knowledge.length ? `<input class="xkb-search" placeholder="搜索知识点名称或路径…" value="${escapeAttr(xkbPicker.filter)}" oninput="xkbPicker.filter=this.value;paintXkbModal()">` : ''}
      <div class="xkb-kp-list">${kps}</div>
      ${picked ? `<div style="margin-top:10px;font-size:12px;color:#6b746e">已选：<b>${escapeAttr(picked.name)}</b>（ID: ${escapeAttr(picked.id)}）</div>` : ''}
      <label style="display:flex;align-items:center;gap:8px;margin-top:12px;font-size:13px">
        页码 <input type="number" min="1" max="50" value="${xkbPicker.page||1}" style="width:72px;padding:6px 8px;border-radius:8px;border:1px solid var(--line3)"
          onchange="xkbPicker.page=Math.max(1, parseInt(this.value,10)||1)">
      </label>
    </div>
    <div class="xkb-foot">
      <button type="button" class="btn-ghost" onclick="closeXuekubaoPicker()">取消</button>
      <button type="button" class="btn-primary" ${!xkbPicker.picked || xkbPicker.loading ? 'disabled' : ''} onclick="confirmXuekubaoSync()">导入题目</button>
    </div>
  </div>`;
}
async function confirmXuekubaoSync(){
  if(!bankSelectedId || !xkbPicker.picked) return;
  closeXuekubaoPicker();
  toast('正在从学库宝拉题…');
  const r = await api(`/api/banks/${bankSelectedId}/sync-xuekubao`, {
    method:'POST',
    body:{knowledge_id: xkbPicker.picked, page: Math.max(1, xkbPicker.page || 1), max_import: 20, fetch_answers: true},
  });
  if(r && r.count > 0){ toast(`已导入 ${r.count} 道题，请到审核台确认`); await loadBankList(); render(); }
  else toast((r && r.message) || apiErrorMsg(r, '同步失败或未配置学库宝密钥'));
}
async function syncBankFromXuekubao(){
  openXuekubaoPicker();
}
async function uploadBankPhoto(input){
  if(!bankSelectedId || !input.files || !input.files[0]) return;
  const list = [...input.files].sort((a,b)=>a.name.localeCompare(b.name, 'zh', {numeric:true}));
  const fd = new FormData();
  list.forEach(f=>fd.append('files', f));
  const h = {};
  const t = getAccessToken();
  if(t) h.Authorization = `Bearer ${t}`;
  toast(`正在识别 ${list.length} 张图片…`);
  try{
    const r = await fetch(API + `/api/banks/${bankSelectedId}/photo-import`, {method:'POST', headers:h, body:fd});
    const data = await r.json();
    if(data && data.count>0){ toast(`已识别 ${data.count} 道题，请到审核台确认`); await loadBankList(); }
    else toast((data && data.message) || '未识别到题目');
  }catch(e){ toast('上传失败'); }
  input.value = '';
  render();
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
function reviewGroupKey(g){
  if(g.passage_id) return `passage-${g.passage_id}`;
  if(g.bank_id) return `bank-${g.bank_id}`;
  if(g.lesson_id != null && g.lesson_id !== '') return String(g.lesson_id);
  return `solo-${(g.questions && g.questions[0] && g.questions[0].id) || 0}`;
}
function toggleLesson(id){
  const key = String(id);
  if(expandedLessons.has(key)) expandedLessons.delete(key);
  else expandedLessons.add(key);
  render();
}

function formatQuestionRichDetail(q){
  const cat = q.qtype_category || BANK_QTYPE_CATEGORY[q.qtype] || '';
  const parts = [];
  const opts = Array.isArray(q.options) ? q.options : [];
  if(cat==='choice' && opts.length){
    parts.push(`<div style="font-size:12px;color:#5c6761;margin-top:6px"><b>选项：</b>${opts.map(o=>escapeAttr(o.label||'')).join(' · ')}</div>`);
  }
  const aj = (q.answer_json && typeof q.answer_json==='object') ? q.answer_json : {};
  if(cat==='blank' && aj.blanks){
    parts.push(`<div style="font-size:12px;color:#5c6761;margin-top:4px"><b>填空答案：</b>${aj.blanks.map(escapeAttr).join('；')}</div>`);
  }
  if(cat==='match' && aj.pairs){
    const pairs = aj.pairs.map(p=>`${escapeAttr(p[0])}→${escapeAttr(p[1])}`).join('；');
    parts.push(`<div style="font-size:12px;color:#5c6761;margin-top:4px"><b>连线：</b>${pairs}</div>`);
  }
  if(cat==='subjective' && (aj.sample || q.answer)){
    parts.push(`<div style="font-size:12px;color:#5c6761;margin-top:4px"><b>参考：</b>${escapeAttr(aj.sample || q.answer)}</div>`);
    if(aj.rubric) parts.push(`<div style="font-size:12px;color:#78817b;margin-top:2px"><b>要点：</b>${escapeAttr(aj.rubric)}</div>`);
  }
  if(q.analysis) parts.push(`<div style="font-size:12px;color:#78817b;margin-top:4px"><b>解析：</b>${escapeAttr(q.analysis)}</div>`);
  return parts.join('');
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
      const gkey = reviewGroupKey(g);
      const open = expandedLessons.has(gkey);
      const chev = open ? '▾' : '▸';
      const qItems = qs.map(q=>{
        const label = QTYPE_LABEL[q.qtype] || q.task_type || '题目';
        const ansText = (q.answer!=null && q.answer!=='') ? `答案：${escapeAttr(q.answer)}` : '';
        const richText = formatQuestionRichDetail(q);
        const extraText = formatQuestionExtra(q.extra);
        return `<div class="q-item" style="display:flex;align-items:flex-start;gap:10px;padding:12px 14px;background:#fafbf9;border:1px solid var(--line3);border-radius:10px;margin-bottom:8px">
          <div style="flex:1;min-width:0">
            <div style="font-size:13px;font-weight:600;color:#333;line-height:1.5"><span class="q-type" style="font-size:10px;font-weight:700;border-radius:5px;padding:1px 6px;margin-right:6px;background:#edf1ff;color:#4566e8">${label}</span>${escapeAttr(q.question||'')}</div>
            ${ansText?`<div style="font-size:12px;color:#8e9691;margin-top:3px">${ansText}</div>`:''}
            ${richText}
            ${extraText}
          </div>
          <div style="display:flex;gap:6px;flex-shrink:0">
            <button class="btn-ghost" style="color:#2e8b5a;padding:4px 10px" onclick="approveQuestion(${q.id})">通过</button>
            <button class="btn-ghost" style="color:#c05b4a;padding:4px 10px" onclick="rejectQuestion(${q.id})">驳回</button>
          </div>
        </div>`;
      }).join('');
      const passageHtml = (g.passage && g.passage.content)
        ? `<div class="passage-preview" style="margin:8px 0 12px">${renderPassageMarkup(g.passage.content)}</div>`
        : '';

      return `<div class="lesson-group" style="border-top:1px solid var(--line2);padding:12px 20px">
        <div style="display:flex;align-items:center;gap:8px;cursor:pointer" onclick="toggleLesson('${gkey}')">
          <span style="color:#8e9691;font-size:12px">${chev}</span>
          <span style="font-size:14px;font-weight:600">${g.subject||''} · ${escapeAttr(g.lesson_title||('课程 '+g.lesson_id))}</span>
          <span style="font-size:12px;color:#8e9691">${qs.length} 题待审</span>
          <div style="margin-left:auto;display:flex;align-items:center;gap:8px" onclick="event.stopPropagation()">
            ${g.lesson_id?`<button class="btn-ghost" style="padding:4px 10px" onclick="approveByLesson('${g.lesson_id}')">通过本课</button>`:''}
            ${g.bank_id && !g.passage_id?`<button class="btn-ghost" style="padding:4px 10px" onclick="approveByBank('${g.bank_id}')">通过本卷</button>`:''}
            ${g.passage_id?`<button class="btn-ghost" style="padding:4px 10px" onclick="approveByPassage('${g.passage_id}')">通过本篇</button>`:''}
          </div>
        </div>
        <div style="margin-top:10px;padding-left:20px;${open?'':'display:none'}">${passageHtml}${qItems}</div>
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
  reading:'阅读理解', listening:'听力理解', custom:'自由任务', math:'数学练习',
  practice:'题库练习',
};
function parseMathTaskContent(raw){
  const s = (raw || '').trim();
  if(!s) return {calc:[], word:[]};
  try{
    const data = JSON.parse(s);
    if(Array.isArray(data)) return {calc:data, word:[]};
    if(data && typeof data === 'object'){
      return {calc:[...(data.calc||[])], word:[...(data.word||[])]};
    }
  }catch(e){ /* legacy / corrupt */ }
  return {calc:[], word:[]};
}
const MATH_AI_STATUS_LABEL = {
  ok:'AI 已通过',
  pending_review:'待家长确认',
  failed:'批改失败'
};
function mathAiStatusLabel(st){
  const k = (st || '').trim();
  return MATH_AI_STATUS_LABEL[k] || (k ? k : '未批改');
}
function mathCalcSummaryHtml(calc){
  if(!calc.length) return '<span style="font-size:12px;color:#5c6761">计算题：无</span>';
  let ok = 0;
  calc.forEach(c => {
    const v = c.is_correct !== undefined ? c.is_correct : c.user_correct;
    if(v === true) ok++;
  });
  return `<span style="font-size:12px;color:#5c6761">计算题：${ok}/${calc.length} 对</span>`;
}
function mathWordThumbsHtml(word){
  if(!word.length) return '';
  const items = word.map((w, i) => {
    const p = (w.photo_path || '').replace(/^\/+/, '');
    const lab = mathAiStatusLabel(w.ai_status);
    const thumb = p
      ? `<a href="${API}/${p}" target="_blank" rel="noopener" title="应用题 ${i + 1}">
           <img src="${API}/${p}" alt="应用题 ${i + 1}" style="width:56px;height:56px;object-fit:cover;border-radius:8px;border:1px solid var(--line3);display:block"/>
         </a>`
      : `<span style="width:56px;height:56px;display:flex;align-items:center;justify-content:center;border-radius:8px;border:1px dashed #c5cbc7;font-size:10px;color:#8e9691;background:#f7f8f7">无图</span>`;
    return `<div style="display:flex;flex-direction:column;align-items:center;gap:4px;max-width:72px">
      ${thumb}
      <span style="font-size:10px;color:#78817b;text-align:center;line-height:1.2">题${i + 1}<br/>${lab}</span>
    </div>`;
  }).join('');
  return `<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:8px">${items}</div>`;
}
function renderMathSubmittedDetail(t){
  const {calc, word} = parseMathTaskContent(t.content);
  return `<div class="math-task-review" style="margin-top:6px">
    ${mathCalcSummaryHtml(calc)}
    ${word.length ? `<div style="font-size:12px;color:#5c6761;margin-top:6px">应用题照片</div>${mathWordThumbsHtml(word)}` : ''}
  </div>`;
}
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
      const photoHint = (t.task_type==='dictation' && !t.photo_path)
        ? `<span style="font-size:11px;color:#c05b4a">未上传打卡照</span>` : '';
      actions = `<button class="btn-primary" style="padding:6px 14px;font-size:12px" onclick="confirmTask(${t.id})">确认完成</button>` +
        (t.task_type==='math'
          ? `<button class="btn-ghost" style="color:#c05b4a;padding:6px 14px;font-size:12px" onclick="rejectTask(${t.id})">打回重做</button>`
          : '') +
        (t.photo_path ? `<a href="${API}/${t.photo_path}" target="_blank" style="font-size:12px;color:#3158e8;text-decoration:none;align-self:center">查看照片</a>` : '') +
        photoHint;
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
    const mathDetail = (t.task_type==='math' && t.submit_status==='submitted')
      ? renderMathSubmittedDetail(t) : '';
    return `<div class="goal-item" style="display:flex;align-items:center;gap:12px">
      <div style="flex:1;min-width:0">
        <div class="g-top"><span class="g-name">${t.title||'(无标题)'}</span>${status}</div>
        ${meta?`<div class="g-meta">${meta}</div>`:''}
        ${mathDetail}
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
async function rejectTask(id){
  await api(`/api/tasks/${id}/reject`, {method:'POST', body:{scope:'task'}});
  toast('已打回，孩子可重新提交');
  await loadParentTasks(); render();
}
async function showAddTask(){
  if(!uid) return;
  const title = prompt('任务标题');
  if(!title) return;
  const subject = prompt('科目（语文/英语）', '语文') || '语文';
  await api(`/api/tasks`,{method:'POST',body:{user_id:uid,date:parentTaskDate,task_type:'custom',subject:subject,title:title,detail:'',points:20}});
  await loadParentTasks(); render();
}

// ---- 家长登录 ----
function updateParentSidebar(){
  const nm = parentName || '家长';
  document.getElementById('userName').textContent = nm;
  document.getElementById('userAvatar').textContent = (nm||'家').slice(0,1);
}
function applyParentSession(me){
  if(!me || me.role !== 'parent') return false;
  parentId = me.id;
  parentName = me.display_name || me.name || me.login_name || '';
  updateParentSidebar();
  return true;
}
function renderLogin(){
  const isReg = loginAuthMode === 'register';
  const title = isReg ? '注册家长账号' : '家长登录';
  const sub = isReg ? '创建账号后管理孩子与学习配置' : '使用登录名和密码进入家长端（不再支持只填姓名）';
  const legacyHint = isReg ? '' : `<p style="font-size:12px;color:#8e9691;line-height:1.5;margin:0 0 4px">老账号：登录名一般为原「姓名」（如 金爸爸），初始密码 <code style="font-size:11px">ChangeMe123</code>。新用户请点下方「注册」。</p>`;
  const toggle = isReg
    ? `<button type="button" class="btn-ghost" style="padding:0;font-size:13px;color:var(--blue)" onclick="loginAuthMode='login';render()">已有账号？去登录</button>`
    : `<button type="button" class="btn-ghost" style="padding:0;font-size:13px;color:var(--blue)" onclick="loginAuthMode='register';render()">没有账号？注册</button>`;
  return `<div class="parent-grid" style="display:block;max-width:420px;margin:60px auto 0">
    <div class="parent-panel">
      <div class="head"><div class="ic orange">${icon('star',20)}</div>
        <div><h3>${title}</h3><div class="sub">${sub}</div></div></div>
      <div class="bd" style="display:flex;flex-direction:column;gap:10px">
        ${legacyHint}
        <input id="authLoginName" placeholder="登录名（新注册：字母数字；老账号可为原姓名）" autocomplete="username"
          style="border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"
          onkeydown="if(event.key==='Enter')${isReg?'doParentRegister()':'doParentLogin()'}">
        <input id="authPassword" type="password" placeholder="密码（至少 8 位）" autocomplete="${isReg?'new-password':'current-password'}"
          style="border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"
          onkeydown="if(event.key==='Enter')${isReg?'doParentRegister()':'doParentLogin()'}">
        <button class="btn-primary" style="padding:10px 20px" onclick="${isReg?'doParentRegister()':'doParentLogin()'}">${isReg?'注册并登录':'登录'}</button>
        <div style="text-align:center;margin-top:4px">${toggle}</div>
      </div>
    </div>
  </div>`;
}
async function finishAuthResponse(r, fallbackMsg){
  if(!r || !r.access_token){
    toast(apiErrorMsg(r, fallbackMsg));
    return false;
  }
  setTokens(r.access_token, r.refresh_token);
  const me = r.user || await api('/api/auth/me');
  if(!applyParentSession(me)){
    clearAuthTokens();
    parentId = null;
    toast('请使用家长账号登录');
    return false;
  }
  await loadChildren();
  try{ await loadConfig(); await loadParentData(); await reloadChildData(); }catch(e){}
  render();
  return true;
}
async function doParentLogin(){
  const login_name = (document.getElementById('authLoginName')?.value || '').trim();
  const password = document.getElementById('authPassword')?.value ?? '';
  if(!login_name || !password){ toast('请输入登录名和密码'); return; }
  const r = await api('/api/auth/login', {method:'POST', body:{login_name, password}});
  await finishAuthResponse(r, '登录失败');
}
async function doParentRegister(){
  const login_name = (document.getElementById('authLoginName')?.value || '').trim();
  const password = document.getElementById('authPassword')?.value ?? '';
  if(!login_name || !password){ toast('请输入登录名和密码'); return; }
  const r = await api('/api/auth/register', {method:'POST', body:{login_name, password, role:'parent'}});
  if(await finishAuthResponse(r, '注册失败')) toast('注册成功');
}
async function logoutParent(){
  const rt = getRefreshToken();
  clearAuthTokens();
  parentId = null; parentName = '';
  uid = null; children = []; buckets = []; bucketId = null;
  familyInvite = null; familyRequests = [];
  updateParentSidebar();
  if(rt){
    try{ await api('/api/auth/logout', {method:'POST', body:{refresh_token: rt}}); }catch(e){}
  }
  renderNav();
  render();
}

// ---- 家庭绑定（邀请码 + 孩子申请）----
async function loadFamilyRequests(){
  if(!parentId) return;
  const list = await api('/api/family/requests');
  familyRequests = Array.isArray(list) ? list : [];
}
async function generateFamilyInvite(){
  if(!parentId){ toast('请先登录'); return; }
  const r = await api('/api/family/invite', {method:'POST'});
  if(!r || !r.code){ toast(apiErrorMsg(r, '生成邀请码失败')); return; }
  familyInvite = {code: r.code, expires_at: r.expires_at};
  toast('邀请码已生成（24 小时内有效）');
  render();
}
async function approveFamilyRequest(id){
  await api(`/api/family/requests/${id}/approve`, {method:'POST'});
  toast('已通过绑定');
  await loadFamilyRequests();
  await loadChildren();
  render();
}
async function rejectFamilyRequest(id){
  await api(`/api/family/requests/${id}/reject`, {method:'POST'});
  toast('已拒绝');
  await loadFamilyRequests();
  render();
}
function renderFamilyBindPanel(){
  const reqRows = familyRequests.map(r=>`
    <div class="pdf-row">
      <div><div class="nm">${escapeAttr(r.child_name || r.child_login_name || '孩子')}</div>
        <div class="meta">登录名：${escapeAttr(r.child_login_name || '—')}</div></div>
      <div style="display:flex;gap:6px;margin-left:auto">
        <button class="btn-primary" style="padding:8px 14px" onclick="approveFamilyRequest(${r.id})">通过</button>
        <button class="btn-ghost" style="color:#c05b4a" onclick="rejectFamilyRequest(${r.id})">拒绝</button>
      </div>
    </div>`).join('');
  const inviteBlock = familyInvite
    ? `<div style="margin-top:12px;padding:12px 14px;border-radius:12px;background:var(--blue-soft2);font-size:13px">
        <div>邀请码：<strong style="font-size:18px;letter-spacing:.12em">${escapeAttr(familyInvite.code)}</strong></div>
        <div style="color:var(--gray2);margin-top:6px">有效期至 ${escapeAttr(familyInvite.expires_at || '')} · 请让孩子在学生端输入此码绑定</div>
      </div>` : '';
  return `<div class="parent-panel" style="grid-column:1/-1;margin-top:20px">
    <div class="head"><div class="ic green">${icon('gift',20)}</div>
      <div><h3>家庭绑定</h3><div class="sub">生成邀请码供孩子绑定，或审批孩子的绑定申请</div></div>
      <button class="btn-ghost" style="margin-left:auto" onclick="generateFamilyInvite()">生成邀请码</button></div>
    <div class="bd">
      ${inviteBlock}
      <div style="margin-top:${familyInvite?16:0}px;font-size:13px;font-weight:600;color:var(--ink2)">待审批申请</div>
      ${reqRows || '<div style="color:#8e9691;padding:8px 0;margin-top:8px">暂无待处理申请</div>'}
    </div>
  </div>`;
}

function renderParent(){
  if(!parentId) return renderLogin();
  const tabs = PARENT_TABS.map(([t])=>
    `<button class="filter-btn ${parentTab===t?'active':''}" style="border-radius:10px;padding:8px 16px;font-size:13px;font-weight:600;color:${parentTab===t?'#3158e8':'#778079'};background:${parentTab===t?'#fff':'transparent'}" onclick="setParentTab('${t}')">${t}</button>`
  ).join('');

  let body='';
  if(parentTab==='教材') body = renderPdfTab();
  else if(parentTab==='知识点') body = renderKnowledgeTab();
  else if(parentTab==='题库管理') body = renderBankManage();
  else if(parentTab==='题目审核台') body = renderQuestionTab();
  else if(parentTab==='目标') body = renderGoalsTab();
  else if(parentTab==='报告') body = renderReportTab();
  else if(parentTab==='任务') body = renderTaskTab();
  else if(parentTab==='规则') body = renderRulesTab();
  else if(parentTab==='学习配置') body = renderLearningConfigTab();
  else if(parentTab==='屏幕时间') body = renderScreenTab();
  else if(parentTab==='设置') body = renderSettingsTab();
  else if(parentTab==='孩子管理') body = renderChildMgmt();

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
          <div style="margin-top:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <span style="font-size:13px;color:var(--gray2)">年级：</span>
            <select id="pdfGrade" style="border:1px solid var(--line3);border-radius:10px;padding:8px 12px;font-size:13px"><option value="">不限</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option><option value="6">6</option></select>
            <span style="font-size:13px;color:var(--gray2)">版本：</span>
            <input id="pdfEdition" placeholder="如 人教/北师大（可空）" style="border:1px solid var(--line3);border-radius:10px;padding:8px 12px;font-size:13px;width:200px">
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
      <div><div class="nm">${d.filename}</div><div class="meta">${d.subject}${d.grade?(' · '+d.grade+'年级'):''}${d.edition?(' · '+d.edition):''} · ${d.lesson_count} 课 · 已审核 ${d.audited_count} 课</div></div>
      <div style="display:flex;gap:6px;margin-left:auto">
        <button class="btn-ghost" onclick="openDocBind(${d.id})">绑定孩子</button>
        <button class="btn-ghost" onclick="openDoc(${d.id})">查看/审核</button>
        <button class="btn-ghost" onclick="resplitDoc(${d.id})">重新拆分</button>
        <button class="btn-ghost" style="color:#c05b4a" onclick="removeDoc(${d.id})">移除</button>
      </div>
    </div>`).join('');
  const empty = pdfDocs.length===0 ? `<div style="text-align:center;padding:32px 0;color:#8e9691">还没有上传教材，点击下方按钮开始</div>` : rows;
  return `<div class="parent-grid">
    ${renderDocBind()}
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
  const grade = document.getElementById('pdfGrade').value;
  const edition = document.getElementById('pdfEdition').value.trim();
  const fd = new FormData();
  fd.append('subject', subject);
  if(grade) fd.append('grade', grade);
  if(edition) fd.append('edition', edition);
  fd.append('file', f);
  toast('上传中，正在自动拆课…');
  await apiForm('/api/pdf/upload', fd);
  await loadPdfDocs();
  pdfTab=null; render(); toast('上传完成，已自动拆课');
}

async function openDocBind(documentId){
  bindDocId = documentId;
  const r = await api(`/api/pdf/documents/${documentId}/bound-users`);
  if(bindDocId !== documentId) return; // 过期响应，忽略
  boundUsers = (r && r.user_ids) || [];
  render();
}

async function toggleDocBind(documentId, userId, checked){
  bindDocId = documentId;
  if(checked){
    await api(`/api/pdf/documents/${documentId}/bind`, {method:'POST', body:{user_id:userId}});
  } else {
    await api(`/api/pdf/documents/${documentId}/bind?user_id=${userId}`, {method:'DELETE'});
  }
  const r = await api(`/api/pdf/documents/${documentId}/bound-users`);
  boundUsers = (r && r.user_ids) || [];
  render();
}

function renderDocBind(){
  if(bindDocId === null) return '';
  const rows = children.map(c=>`
    <label style="display:flex;align-items:center;gap:8px;padding:6px 0">
      <input type="checkbox" ${boundUsers.includes(c.id)?'checked':''} onchange="toggleDocBind(${bindDocId}, ${c.id}, this.checked)">
      <span>${escapeAttr(c.name)}${c.grade?('（'+c.grade+'年级）'):''}</span>
    </label>`).join('');
  return `<div class="parent-panel" style="grid-column:1/-1">
    <div class="head"><div class="ic blue">${icon('star',20)}</div><div><h3>绑定孩子</h3><div class="sub">勾选能看到这本教材的孩子</div></div>
      <button class="btn-ghost" style="margin-left:auto" onclick="bindDocId=null;render()">关闭</button></div>
    <div class="bd">${rows || '<div style="color:#8e9691;padding:8px 0">还没有孩子，请先在孩子管理里添加</div>'}</div>
  </div>`;
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

// ---- 屏幕时间 ----
function fmtDuration(seconds){
  seconds = Math.max(0, Math.round(seconds||0));
  const m = Math.floor(seconds/60);
  if(m < 60) return `${m}分钟`;
  const h = Math.floor(m/60), rest = m%60;
  return rest ? `${h}小时${rest}分` : `${h}小时`;
}
async function loadScreenGroups(){
  if(!uid){ screenGroups = []; screenRules = []; return; }
  const u = uid;
  const d = await api(`/api/screen-time/groups?user_id=${u}`);
  if(u !== uid) return;
  screenGroups = (d && d.groups) || [];
  screenRules = (d && d.rules) || [];
}
async function loadScreenUsage(){
  if(!uid){ screenUsage = []; return; }
  if(!screenDate){
    const t = new Date();
    screenDate = `${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,'0')}-${String(t.getDate()).padStart(2,'0')}`;
  }
  const u = uid, d = screenDate;
  const res = await api(`/api/screen-time/usage?child_id=${u}&date=${d}`);
  if(u === uid && d === screenDate) screenUsage = (res && res.groups) || [];
}
function changeScreenDate(){
  screenDate = document.getElementById('screenDate').value;
  loadScreenUsage().then(()=>render()).catch(()=>toast('加载使用情况失败，请稍后重试'));
}
async function saveScreenGroups(){
  if(!uid) return;
  // 收集每个分组的每日上限（分钟）；规则保持现状不变
  const groups = screenGroups.map(g=>{
    const el = document.getElementById(`screen-limit-${g.id}`);
    const raw = el ? el.value.trim() : '';
    // 空白 = 不限（后端 daily_limit_seconds 为 null）；填了数字才换算成秒
    let limitSeconds = null;
    if(raw !== ''){
      const mins = parseFloat(raw);
      if(mins===mins && mins>=0) limitSeconds = Math.round(mins*60);
      else limitSeconds = (g.daily_limit_seconds||0);
    }
    return {name:g.name, kind:g.kind, daily_limit_seconds:limitSeconds};
  });
  // 注意：后端按 name 幂等 upsert 分组（忽略 id），规则也按 app_package + group_name 关联；
  // 将来若做「分组改名」，需同步改规则里的 group_name，否则会新建/错挂分组。
  const rules = screenRules.map(r=>{
    const g = screenGroups.find(x=>x.id===r.group_id);
    return {app_package:r.app_package, app_name:r.app_name, group_name:(g&&g.name)||''};
  }).filter(r=>r.group_name);
  const res = await api('/api/screen-time/groups', {method:'PUT', body:{user_id:uid, groups, rules}});
  if(res && res.ok){ toast('屏幕时间设置已保存'); await loadScreenGroups(); }
  else { toast('保存失败，请稍后重试'); }
}
function renderScreenTab(){
  const head = `<div class="parent-panel" style="grid-column:1/-1">
    <div class="head">
      <div class="ic blue">${icon('clock',20)}</div>
      <div><h3>屏幕时间</h3><div class="sub">${screenDate} · 各分组每日使用时长与超时情况</div></div>
      <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
        <input type="date" id="screenDate" value="${screenDate}" onchange="changeScreenDate()"
          style="border:1px solid var(--line3);border-radius:10px;padding:8px 12px;font-size:13px">
        <button class="btn-primary" style="padding:8px 16px" onclick="saveScreenGroups()">保存</button>
      </div>
    </div>
  </div>`;

  if(!screenUsage.length){
    return `<div class="parent-grid">
      ${head}
      <div class="parent-panel" style="grid-column:1/-1">
        <div class="bd" style="text-align:center;padding:40px 0;color:#8e9691">
          <div style="font-size:15px;font-weight:600;color:#5c6761;margin-bottom:6px">暂无屏幕时间数据</div>
          <div style="font-size:13px">孩子端使用时长上报后，这里会按分组汇总展示。</div>
        </div>
      </div>
    </div>`;
  }

  const rows = screenUsage.map(g=>{
    const limitMins = g.daily_limit_seconds ? Math.round(g.daily_limit_seconds/60) : 0;
    const limitText = g.daily_limit_seconds ? `${limitMins}分钟` : '未设';
    const status = g.overtime
      ? `<span class="g-status" style="background:#fff3f0;color:#c05b4a">超时</span>`
      : `<span class="g-status" style="background:var(--green-soft2);color:var(--green)">正常</span>`;
    return `<tr ${g.overtime?'style="color:red"':''}>
      <td>${escapeAttr(g.name)}</td>
      <td>${fmtDuration(g.duration_seconds)}</td>
      <td>${limitText}</td>
      <td>${status}</td>
    </tr>`;
  }).join('');

  // 分组每日上限编辑（简单输入框），规则只读展示
  const groupEditRows = screenGroups.map(g=>{
    const limitMins = g.daily_limit_seconds ? Math.round(g.daily_limit_seconds/60) : '';
    const grpRules = screenRules.filter(r=>r.group_id===g.id);
    return `<div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--line2)">
      <span style="font-size:13px;font-weight:600;min-width:90px">${escapeAttr(g.name)}</span>
      <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--gray2)">每日上限
        <input type="number" id="screen-limit-${g.id}" min="0" step="5" value="${limitMins}"
          style="width:70px;border:1px solid var(--line3);border-radius:8px;padding:5px 8px;font-size:13px">分钟</label>
      <span style="font-size:12px;color:#8e9691">${grpRules.length?('含应用：'+grpRules.map(r=>escapeAttr(r.app_name||r.app_package)).join('、')):''}</span>
    </div>`;
  }).join('');

  return `<div class="parent-grid" style="display:block">
    ${head}
    <div class="parent-panel" style="margin-bottom:20px">
      <div class="bd">
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead><tr style="color:var(--gray2);text-align:left;border-bottom:1px solid var(--line)">
            <th style="padding:8px 10px">分组</th>
            <th style="padding:8px 10px">今日时长</th>
            <th style="padding:8px 10px">上限</th>
            <th style="padding:8px 10px">状态</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
    <div class="parent-panel">
      <div class="head"><div class="ic purple">${icon('grid',20)}</div><div><h3>分组与每日上限</h3><div class="sub">调整各分组每日限额（分钟），点击右上角「保存」生效</div></div></div>
      <div class="bd">${groupEditRows || '<p style="font-size:13px;color:var(--gray2)">暂无分组</p>'}</div>
    </div>
  </div>`;
}


let msCatalog = null;
let msRoleTab = 'llm';
let msSources = null;
let msSourcesDraft = {xuekubao_api_base:'', xuekubao_access_key:'', tiku_cn_api_base:'', tiku_cn_app_key:''};
let msSourcesProbe = '';
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
  (msCatalog.connections||[]).forEach(c=>{
    if(c.provider === 'xunfei') c._xunfei = msParseConnExtra(c);
  });
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
function msConnProviderForRole(role){
  const svc = msSvc(role);
  const idx = svc.connection_index;
  if(idx === null || idx === undefined || idx === '') return (svc.effective||{}).provider || '';
  const c = msConns()[idx];
  return (c && c.provider) || '';
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
    <div class="ms-wrap">${msNavHtml()}${msRoleTab==='connections' ? msConnectionsHtml() : msRoleTab==='sources' ? msSourcesHtml() : msRoleHtml()}</div>`;
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
    <button class="ms-item ${msRoleTab==='sources'?'on':''}" onclick="msSelectRole('sources')">
      ${icon('grid',16)}<span>题库来源</span>
    </button>
  </aside>`;
}

function msSourcesHtml(){
  const s = msSources || {};
  const xkbOn = !!s.xuekubao_configured;
  const tikuOn = !!s.tiku_cn_configured;
  return `<section class="ms-main">
    <div class="head"><div class="ic green">${icon('grid',20)}</div>
      <div><h3>题库来源</h3><div class="sub">学库宝 / tiku.cn 拉题凭证；服务器环境变量仍可作为兜底</div></div>
      <span class="ms-badge ${xkbOn?'ok':(tikuOn?'warn':'off')}">${xkbOn?'学库宝已配':tikuOn?'仅 tiku':'未配置'}</span>
    </div>
  <div class="ms-field" style="margin-top:18px">
    <div class="ms-label">学库宝 API 地址</div>
    <input class="ms-input" value="${escapeAttr(msSourcesDraft.xuekubao_api_base||s.xuekubao_api_base||'https://api.xuekubao.com')}"
      placeholder="https://api.xuekubao.com" oninput="msSourcesDraft.xuekubao_api_base=this.value">
    <div class="ms-hint">控制台申请的 x-api-key 填在下方；用于「题库管理 → 学库宝选题」。</div>
  </div>
  <div class="ms-field">
    <div class="ms-label">学库宝 Access Key</div>
    <input class="ms-input" type="password" value="" placeholder="${xkbOn?'已保存，留空则不修改':'粘贴 Access Key'}"
      oninput="msSourcesDraft.xuekubao_access_key=this.value">
  </div>
  <div style="margin:22px 0 8px;padding-top:16px;border-top:1px solid #eef1ec;font-size:12px;font-weight:700;color:var(--gray2)">tiku.cn（可选）</div>
  <div class="ms-field">
    <div class="ms-label">tiku.cn API 地址</div>
    <input class="ms-input" value="${escapeAttr(msSourcesDraft.tiku_cn_api_base!==''?msSourcesDraft.tiku_cn_api_base:(s.tiku_cn_api_base||''))}"
      placeholder="https://…" oninput="msSourcesDraft.tiku_cn_api_base=this.value">
  </div>
  <div class="ms-field">
    <div class="ms-label">tiku.cn App Key</div>
    <input class="ms-input" type="password" value="" placeholder="${tikuOn?'已保存，留空则不修改':'App Key'}"
      oninput="msSourcesDraft.tiku_cn_app_key=this.value">
  </div>
  <div class="ms-hint" style="margin-top:4px">${escapeAttr(msSourcesProbe||'')}</div>
  <div class="ms-actions">
    <button type="button" class="btn-ghost" style="padding:10px 20px" onclick="msTestXuekubao()">测试学库宝连接</button>
    <button type="button" class="btn-primary" style="padding:10px 24px" onclick="msSaveSources()" ${msSaving?'disabled':''}>保存配置</button>
  </div>
  </section>`;
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
          <div class="ms-field"><div class="ms-label">厂商</div>
            <select class="ms-select" onchange="msSetConnProvider(${i}, this.value)">
              ${['openai','deepseek','glm','minimax','xunfei'].map(p=>
                `<option value="${p}" ${(c.provider||'openai')===p?'selected':''}>${p}</option>`).join('')}
            </select>
            <div class="ms-hint">语音选 <b>xunfei</b> 时需填写开放平台「语音合成」的 APPID / APIKey / APISecret。</div>
          </div>
          ${(c.provider||'openai') === 'xunfei' ? `
          <div class="ms-field"><div class="ms-label">APPID</div>
            <input class="ms-input" value="${escapeAttr((c._xunfei||msParseConnExtra(c)).app_id||'')}" placeholder="讯飞控制台 APPID"
              oninput="msConnField(${i},'xunfei_app_id',this.value)"></div>
          <div class="ms-field"><div class="ms-label">APIKey（32 位）</div>
            <input class="ms-input" type="password" value="" placeholder="${c.api_key?'已保存，留空则不修改':'APIKey'}"
              oninput="msConnField(${i},'_newKey',this.value)">
            <div class="ms-hint">密钥只在提供方录一次，所有角色共用。</div></div>
          <div class="ms-field"><div class="ms-label">APISecret</div>
            <input class="ms-input" type="password" value="" placeholder="${msParseConnExtra(c).api_secret?'已保存，留空则不修改':'APISecret'}"
              oninput="msConnField(${i},'_newSecret',this.value)"></div>` : `
          <div class="ms-field"><div class="ms-label">Base URL</div>
            <input class="ms-input" value="${escapeAttr(c.base_url||'')}" placeholder="留空使用默认端点" oninput="msConnField(${i},'base_url',this.value)"></div>
          <div class="ms-field"><div class="ms-label">API Key</div>
            <input class="ms-input" type="password" value="" placeholder="${c.api_key?'已保存，留空则不修改':'sk-...'}" oninput="msConnField(${i},'_newKey',this.value)">
            <div class="ms-hint">密钥只在提供方录一次，所有角色共用。</div></div>`}
        ` : ''}
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
      ${r.id==='tts' ? (()=>{
        const prov = msConnProviderForRole('tts') || 'openai';
        const voices = MS_TTS_VOICES[prov] || MS_TTS_VOICES.openai;
        const cur = opts.voice || voices[0] || '';
        return `<div class="ms-field"><div class="ms-label">音色</div>
        <select class="ms-select" onchange="msSetOption('voice',this.value)">
          ${voices.map(v=>`<option value="${escapeAttr(v)}" ${cur===v?'selected':''}>${escapeAttr(v)}</option>`).join('')}
        </select>
        ${prov==='xunfei'?'<div class="ms-hint">需在「提供方」选用厂商 xunfei 并填写开放平台语音合成凭证。</div>':''}</div>`;
      })() : ''}
      ${r.id==='tts' ? `
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
          <div class="lc-row">
            <div class="lc-label">听写作答方式</div>
            <select class="lc-input" data-key="dictation_input_mode">
              <option value="paper_photo" ${(configMap.dictation_input_mode||'paper_photo')==='paper_photo'?'selected':''}>纸上听写 + 拍照</option>
              <option value="on_screen" ${configMap.dictation_input_mode==='on_screen'?'selected':''}>屏上手写</option>
            </select>
            <div class="lc-hint">仅对当前孩子生效；孩子端不可自行修改</div>
          </div>
          ${num('task_dictation_count_语文','7','语文每日听写量','每天听写几个语文生词')}
          ${num('task_dictation_count_英语','7','英语每日听写量','每天听写几个英语单词')}
          ${num('task_math_calc_count','2','数学每日计算题数','每天几道屏上计算题（0–10）','0','10')}
          ${num('task_math_word_count','2','数学每日应用题数','每天几道纸上应用题，一题一照（0–10）','0','10')}
          ${num('task_dictation_due_cap','0.5','到期/错词复习上限比例','每天到期+错词复习最多占多少（0~1）','0','1','0.1')}
          ${num('task_dictation_new_floor','0.3','新课生词下限比例','每天至少留多少比例给未听写过的生词（0~1）','0','1','0.1')}
          ${num('assignment_question_count','4','作业题数','个性化学习每次作业几道题')}
          ${num('assignment_pass_threshold','0.6','通过正确率','0~1，例如 0.6 表示 60%','0','1','0.1')}
          ${sel('difficulty_语文','中等','语文出题难度',['简单','中等','困难'])}
          ${sel('difficulty_英语','中等','英语出题难度',['简单','中等','困难'])}
          ${sel('difficulty_数学','中等','数学出题难度',['简单','中等','困难'])}
          ${chk('personalized_disable_chat','禁用个性化学习 AI 对话','勾选 = 禁用，不勾选 = 开放（默认）；孩子做作业期间始终暂停对话')}
          ${!uid ? `<div class="lc-hint" style="color:#c05b4a;margin-top:8px">请先选择当前孩子</div>` : ''}
          <div style="margin-top:16px">
            <button class="btn-primary" ${uid ? 'onclick="saveLearningConfig()"' : 'disabled'} style="${uid ? '' : 'opacity:0.5;cursor:not-allowed;'}">保存配置</button>
          </div>
        </div>
      </div>
    </div>`;
}

async function saveLearningConfig(){
  if(!uid){ toast('请先选择当前孩子'); return; }
  const inputs = document.querySelectorAll('[data-key]');
  const childKeys = new Set([
    'dictation_input_mode',
    'task_dictation_count_语文',
    'task_dictation_count_英语',
    'task_dictation_due_cap',
    'task_dictation_new_floor',
  ]);
  const childBody = { user_id: uid };
  let dictMode = null;
  for(const el of inputs){
    const key = el.dataset.key;
    if(key === 'dictation_input_mode'){
      dictMode = el.value;
      continue;
    }
    let value;
    if(el.type === 'checkbox'){ value = el.checked ? 'true' : 'false'; }
    else { value = el.value; }
    if(childKeys.has(key)){
      const isRatio = (key === 'task_dictation_due_cap' || key === 'task_dictation_new_floor');
      const isCount = (key === 'task_dictation_count_语文' || key === 'task_dictation_count_英语');
      if(isRatio){ childBody[key] = parseFloat(value); }
      else if(isCount){ childBody[key] = parseInt(value, 10); }
      else { childBody[key] = value; }
    } else {
      await api('/api/config', {method:'POST', body:{key, value}});
    }
  }
  if(uid){
    if(dictMode) childBody.dictation_input_mode = dictMode;
    await api('/api/learning/preferences', {method:'PUT', body: childBody});
    if(dictMode) configMap.dictation_input_mode = dictMode;
  }
  toast('学习配置已保存');
  await loadConfig();
  await loadLearningPreferences();
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
          ${ttsConfig.provider==='xunfei'?`
          <div><div style="font-size:13px;color:var(--gray2);margin-bottom:8px">APPID</div><input type="text" value="${ttsConfig.appId||''}" oninput="ttsConfig.appId=this.value" style="width:100%;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"></div>
          <div><div style="font-size:13px;color:var(--gray2);margin-bottom:8px">APIKey</div><input type="password" placeholder="讯飞 APIKey" value="${ttsConfig.key}" oninput="ttsConfig.key=this.value" style="width:100%;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"></div>
          <div><div style="font-size:13px;color:var(--gray2);margin-bottom:8px">APISecret</div><input type="password" placeholder="讯飞 APISecret" value="${ttsConfig.apiSecret||''}" oninput="ttsConfig.apiSecret=this.value" style="width:100%;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"></div>
          `:`<div><div style="font-size:13px;color:var(--gray2);margin-bottom:8px">API Key</div><input type="password" placeholder="语音服务 Key" value="${ttsConfig.key}" oninput="ttsConfig.key=this.value" style="width:100%;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"></div>`}
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
function msSelectRole(id){
  msRoleTab = id;
  msConnEdit = null;
  if(id === 'sources'){
    loadSourcesConfig().then(()=>render()).catch(()=>render());
    return;
  }
  render();
}
async function loadSourcesConfig(){
  msSources = await api('/api/config/sources');
  if(!msSourcesDraft.xuekubao_api_base && msSources){
    msSourcesDraft.xuekubao_api_base = msSources.xuekubao_api_base || 'https://api.xuekubao.com';
  }
  return msSources;
}
async function msSaveSources(){
  if(msSaving) return;
  msSaving = true;
  render();
  const base = (msSourcesDraft.xuekubao_api_base || msSources?.xuekubao_api_base || 'https://api.xuekubao.com').trim();
  const body = {
    xuekubao_api_base: base,
    xuekubao_access_key: msSourcesDraft.xuekubao_access_key || '',
    tiku_cn_api_base: (msSourcesDraft.tiku_cn_api_base ?? msSources?.tiku_cn_api_base ?? '').trim(),
    tiku_cn_app_key: msSourcesDraft.tiku_cn_app_key || '',
  };
  try{
    const r = await api('/api/config/sources', {method:'PUT', body});
    if(r && r.ok){
      msSourcesDraft.xuekubao_access_key = '';
      msSourcesDraft.tiku_cn_app_key = '';
      await loadSourcesConfig();
      toast('题库来源已保存');
    } else toast('保存失败');
  }catch(e){ toast('保存失败：' + (e.message||e)); }
  msSaving = false;
  render();
}
async function msTestXuekubao(){
  msSourcesProbe = '正在测试…';
  render();
  try{
    const r = await api('/api/config/sources/test-xuekubao', {method:'POST', body:{}});
    msSourcesProbe = r.ok ? (r.message || '连接成功') : ('失败：' + (r.error || '未知'));
  }catch(e){ msSourcesProbe = '失败：' + (e.message||e); }
  render();
}
function msToggleConnEdit(i){ msConnEdit = msConnEdit === i ? null : i; render(); }
function msParseConnExtra(c){
  if(!c || !c.extra_headers) return {};
  if(typeof c.extra_headers === 'object') return c.extra_headers;
  try { return JSON.parse(c.extra_headers) || {}; } catch(e){ return {}; }
}
function msSetConnProvider(i, val){
  const c = msConns()[i];
  if(!c) return;
  c.provider = val;
  if(val === 'xunfei'){
    c._xunfei = c._xunfei || msParseConnExtra(c);
    c.base_url = '';
  }
  render();
}
function msConnField(i, field, val){
  const c = msConns()[i]; if(!c) return;
  if(field === '_newKey'){ c._newKey = val; return; }
  if(field === '_newSecret'){ c._newSecret = val; return; }
  if(field === 'xunfei_app_id'){
    c._xunfei = c._xunfei || msParseConnExtra(c);
    c._xunfei.app_id = val;
    return;
  }
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
    connections: msConns().map(c=>{
      let extra = c.extra_headers || '';
      if(c.provider === 'xunfei'){
        const ex = c._xunfei || msParseConnExtra(c);
        const secret = c._newSecret || ex.api_secret || '';
        extra = JSON.stringify({app_id: ex.app_id || '', api_secret: secret});
      } else if(typeof extra !== 'string'){
        extra = JSON.stringify(extra || {});
      }
      return {
        id: c.id || null, provider: c.provider, name: c.name,
        base_url: c.base_url, api_key: c._newKey || c.api_key || '',
        extra_headers: extra
      };
    }),
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
    ['tts_app_id', ttsConfig.appId || ''], ['tts_api_secret', ttsConfig.apiSecret || ''],
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
  const sample = '你好，这是语音合成测试';
  try{
    const r = await fetch(
      `${API}/api/tts/synthesize?text=${encodeURIComponent(sample)}`,
      {headers: authHeaders()}
    );
  if(r.status === 401){
      toast('请先登录家长账号后再试听');
      return;
    }
    const ct = r.headers.get('content-type')||'';
    if(ct.includes('audio')){
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = new Audio(url); a.onended=()=>URL.revokeObjectURL(url); a.play();
      toast('已播放中转站合成语音');
    } else {
      const d = await r.json().catch(()=>({}));
      if(d && d.use_browser_tts){ browserSpeak(sample); toast('当前为浏览器合成（未配置真实 TTS）'); }
      else { toast('语音合成失败：' + (d.detail || d.error || r.statusText || '未知错误')); }
    }
  }catch(e){ toast('语音合成失败：' + e.message); }
}

// ===== 初始化 =====
async function init(){
  renderNav();
  if(getAccessToken()){
    try{
      const me = await api('/api/auth/me');
      if(!applyParentSession(me)){
        clearAuthTokens();
        parentId = null;
        toast('登录已失效，请重新登录');
      }else{
        await loadChildren();
      }
    }catch(e){
      clearAuthTokens();
      parentId = null;
      toast('登录已失效，请重新登录');
    }
  }
  if(!parentId){ render(); return; }
  try{ await loadConfig(); }catch(e){}
  try{ await loadParentData(); }catch(e){}
  if(!Array.isArray(pdfDocs)) pdfDocs = [];
  try{ await reloadChildData(); }catch(e){}
  render();
}

init();
