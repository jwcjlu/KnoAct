// ===== 知学伴 前端逻辑（对接真实后端 API）=====
const API = 'http://127.0.0.1:8000';

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
  arrow:'<path d="M5 12h14M14 7l5 5-5 5"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  sparkles:'<path d="m12 3 1.3 3.7L17 8l-3.7 1.3L12 13l-1.3-3.7L7 8l3.7-1.3ZM5 15l.8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8ZM19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8Z"/>',
  tablet:'<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M11 18h2"/>',
  phone:'<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
  flame:'<path d="M12 22c4 0 7-2.7 7-6.5 0-2.6-1.4-4.8-3.8-7.5-.2 2-1.3 3.1-2.4 3.7.3-3.7-1.7-7-5-9.7.2 4-2.8 6.4-2.8 10.4C5 18 8 22 12 22Z"/>',
  headphones:'<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><path d="M4 14h3v6H5a1 1 0 0 1-1-1ZM20 14h-3v6h2a1 1 0 0 0 1-1Z"/>',
  play:'<circle cx="12" cy="12" r="9"/><path d="m10 8 6 4-6 4Z"/>'
};
function icon(name, size=18){
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]||''}</svg>`;
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

// 家长端数据缓存
let pdfDocs = [];
let pdfTab = null; // null | 'upload' | 'confirm'
let confirmDocId = null;
let knowledgeRows = [];
let goalRows = [];
let reportRows = [];
let configMap = {};
let aiConfig = {provider:'deepseek', model:'deepseek-chat', key:''};
let ttsConfig = {provider:'minimax', voice:'清澈男声', key:'', speed:1.0, repeat:2};

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
let centerTab = '听力';

const aiProviders = [
  {id:'deepseek',name:'DeepSeek',models:['deepseek-chat','deepseek-reasoner']},
  {id:'glm',name:'GLM（智谱）',models:['glm-4-plus','glm-4-flash']}
];
const ttsProviders = [
  {id:'minimax',name:'MiniMax',voices:['清澈男声','温柔女声','标准童声']},
  {id:'xunfei',name:'科大讯飞',voices:['讯飞女声','讯飞男声','标准普通话']}
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
  else if(active==='学习中心') html = renderCenter();
  else if(active==='学习报告') html = await renderReport();
  else if(active==='积分商城') html = await renderMall();
  else if(active==='学习首页') html = renderHome();
  else if(active==='听写练习') html = renderDictation();
  else if(active==='新课学习') html = renderNewLesson();
  else html = renderHome();
  main.innerHTML = html;
}

// ===== 首页 =====
function renderHome(){
  const today = new Date();
  const week = ['日','一','二','三','四','五','六'];
  const dateStr = `${today.getMonth()+1} 月 ${today.getDate()} 日，星期${week[today.getDay()]}`;
  const hour = today.getHours();
  const greet = hour<6?'夜深了':hour<12?'早上好':hour<18?'下午好':'晚上好';
  const mastered = dictWords.length; // 词库总数（近似进度）

  return `
  <header class="page-head">
    <div>
      <div class="date">${dateStr}</div>
      <h1>${greet}，林晨</h1>
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
        <h2>第 12 课重点学习与旧课复习</h2>
        <p>根据今日语文进度和遗忘曲线，AI 安排了 70% 新课巩固与 30% 到期复习。</p>
        <button class="start-btn" onclick="document.getElementById('tasks-anchor').scrollIntoView({behavior:'smooth'})">开始今日学习 ${icon('arrow',17)}</button>
      </div>
    </div>
    <div class="weekly-card">
      <div class="head"><h2>本周学习</h2><span>坚持打卡</span></div>
      <div class="bars">
        ${['一','二','三','四','五','六','日'].map((d,i)=>{
          const v=[42,65,50,82,70,25,12][i];
          return `<div class="bar ${i===4?'today':''}"><div class="track"><div class="fill" style="height:${v}%;background:${i<5?'#5b77eb':'#d9ddd9'}"></div></div><span>${d}</span></div>`;
        }).join('')}
      </div>
      <div class="streak"><span style="color:#f59d20">${icon('flame',17)}</span>每天坚持 30 分钟，学习效果更好</div>
    </div>
  </div>

  <div class="progress-strip">
    <div class="p-l">
      <div class="p-ic">${icon('book',20)}</div>
      <div style="min-width:0">
        <div class="p-title">学习进度 · 词库 ${mastered} 个生词</div>
        <div class="p-sub">完成听写与新课阅读，积累掌握度</div>
      </div>
    </div>
    <div class="p-bar"><div class="p-fill" style="width:${Math.min(100, mastered*10)}%"></div></div>
    <span class="p-txt">${mastered} 词</span>
    <button class="next-lesson-btn" onclick="startNewLesson()">进入下一课 ${icon('arrow',16)}</button>
  </div>

  <section class="tasks-section" id="tasks-anchor">
    <div class="section-title">
      <div><h2>今日学习任务</h2><div class="sub">完成任务可获得积分奖励</div></div>
    </div>
    <div class="task-info">
      <div class="lead"><div class="ic">${icon('sparkles',17)}</div><div><div class="t1">AI 已根据学习进度生成</div><div class="t2">今天语文更新至第 12 课</div></div></div>
      <div class="divider"></div>
      <div class="composition">
        <span class="lbl">任务组成</span>
        <div class="comp-bar"><div class="seg1"></div><div class="seg2"></div></div>
        <span class="comp-legend"><b>70%</b> 新课 · <b class="g">30%</b> 复习</span>
      </div>
    </div>
    <div class="task-grid">
      <article class="task-card">
        <div class="top"><div class="task-ic blue">${icon('pen',23)}</div><div style="min-width:0;flex:1"><div class="t-head"><span class="task-tag badge-blue">当前进度</span></div><h3>第 12 课生词听写</h3><div class="detail">今日新学 · ${dictWords.length} 个重点生词</div></div></div>
        <div class="foot"><span class="task-meta">${icon('clock',14)}约 8 分钟</span><span class="task-points">${icon('star',14)}+20</span></div>
        <button class="task-btn todo" onclick="startDictation()">开始练习</button>
      </article>
      <article class="task-card">
        <div class="top"><div class="task-ic orange">${icon('book',23)}</div><div style="min-width:0;flex:1"><div class="t-head"><span class="task-tag badge-orange">重点巩固</span></div><h3>阅读理解</h3><div class="detail">重点段落 · 理解题</div></div></div>
        <div class="foot"><span class="task-meta">${icon('clock',14)}约 12 分钟</span><span class="task-points">${icon('star',14)}+30</span></div>
        <button class="task-btn todo" onclick="setPage('学习中心')">开始练习</button>
      </article>
      <article class="task-card">
        <div class="top"><div class="task-ic green">${icon('brain',23)}</div><div style="min-width:0;flex:1"><div class="t-head"><span class="task-tag badge-green">遗忘曲线</span></div><h3>基础知识复习</h3><div class="detail">易错知识点 · 智能排期</div></div></div>
        <div class="foot"><span class="task-meta">${icon('clock',14)}约 10 分钟</span><span class="task-points">${icon('star',14)}+25</span></div>
        <button class="task-btn todo" onclick="setPage('学习中心')">开始练习</button>
      </article>
    </div>
  </section>

  <div class="review-grid">
    <div class="review-card">
      <div class="head">
        <div><h2>智能复习</h2><div class="sub">根据遗忘曲线，为你安排最佳复习时间</div></div>
        <div class="head-ic">${icon('brain',20)}</div>
      </div>
      <div class="review-items">
        <button class="review-item" onclick="setPage('学习中心')"><div class="review-ic yw serif">语</div><div style="flex:1"><div class="name">语文基础知识</div><div class="cnt">知识点复习</div></div>${icon('arrow',16)}</button>
        <button class="review-item" onclick="setPage('学习中心')"><div class="review-ic en serif">En</div><div style="flex:1"><div class="name">英语基础知识</div><div class="cnt">听力练习</div></div>${icon('arrow',16)}</button>
      </div>
    </div>
    <div class="redeem-card">
      <div class="head">
        <div><div class="lbl">积分兑换</div><h2>劳逸结合，快乐成长</h2></div>
        <div class="pts">${icon('star',17)}${points}</div>
      </div>
      <div class="redeem-items">
        <button class="redeem-item" onclick="redeem('tablet',30,300)">${icon('tablet',25)}<div class="name">平板 30 分钟</div><div class="cost">300 积分兑换</div></button>
        <button class="redeem-item" onclick="redeem('phone',20,200)">${icon('phone',25)}<div class="name">手机 20 分钟</div><div class="cost">200 积分兑换</div></button>
      </div>
    </div>
  </div>`;
}

async function redeem(device, minutes, cost){
  const d = await api('/api/points/redeem', {method:'POST', body:{user_id:uid, device, minutes}});
  if(d.success){ await loadPoints(); render(); toast(`已兑换 ${device==='tablet'?'平板':'手机'} ${minutes} 分钟`); }
  else toast('积分不足，再完成几个任务吧');
}

// ===== 听写练习 =====
async function startDictation(){
  dictWords = await api(`/api/dictation/words?user_id=${uid}`);
  if(!dictWords || !dictWords.length){ toast('当前词库暂无生词'); return; }
  dictState = {idx:0, phase:'listen', wrong:[], correct:0, input:''};
  setPage('听写练习');
}
function dictWord(){ return dictWords[dictState.idx]; }
function speakDict(){
  const w = dictWord();
  const text = w.word;
  // 优先用后端 TTS，失败回退浏览器 speechSynthesis
  api(`/api/tts/synthesize?text=${encodeURIComponent(text)}`).then(d=>{
    if(d && d.use_browser_tts) browserSpeak(text);
    // 真实 provider 返回音频字节时无法直接播放（需 blob），简化：仍用浏览器合成
    else browserSpeak(text);
  }).catch(()=>browserSpeak(text));
  const btn = document.querySelector('.dict-play');
  if(btn){ btn.classList.add('playing'); btn.innerHTML = icon('headphones',17)+'播放中…';
    setTimeout(()=>{ const b=document.querySelector('.dict-play'); if(b){ b.classList.remove('playing'); b.innerHTML = icon('headphones',17)+'再听一遍'; } },1600);
  }
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
  const right = s.input.trim() === w.word;
  s.tried = true; s.phase = 'feedback';
  await api('/api/dictation/grade', {method:'POST', body:{user_id:uid, word:w.word, word_id:w.id, answer:s.input}});
  if(right){ s.correct++; }
  else { s.wrong.push({word:w.word, extra:w.extra, yours:s.input.trim()}); }
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
  const wrongWords = s.wrong.map(x=>({word:x.word, your_answer:x.yours}));
  const d = await api('/api/dictation/complete', {method:'POST', body:{user_id:uid, correct:s.correct, wrong:s.wrong.length, wrong_words:wrongWords}});
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
    const right = !s.wrong.some(x=>x.word===w.word);
    const [pinyin, meaning] = (w.extra||'').split(' ');
    return `<div class="dict-feedback ${right?'right':'wrong'}">
      <div class="fb-head">${right?icon('check',18)+'回答正确':icon('pen',18)+'写错了，看这里'}</div>
      <div class="fb-body">${right?`「${w.word}」拼写正确${meaning?('，'+meaning):''}`:`正确写法是「${w.word}」${pinyin?('（'+pinyin+'）'):''}${meaning?('<br>'+meaning):''}`}</div>
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

// ===== 新课学习 =====
async function startNewLesson(){
  nlState = {phase:'read', questions:[], picks:[], result:null};
  nlChat = []; nlNotes = []; nlNoteSel = '';
  // 取课文与出题（阅读材料）
  const mat = await api(`/api/reading/material?lesson_id=${currentLessonId}`);
  currentText = mat.text || '白鹭是一首精巧的诗。色素的配合，身段的大小，一切都很适宜。';
  nlState.questions = mat.questions && mat.questions.length ? mat.questions : [
    {question:'作者把白鹭比作什么？', answer:'一首精巧的诗'},
    {question:'文中表达了怎样的感情？', answer:'对白鹭的喜爱'}
  ];
  // 主观题简化：只做“会/不会”自评
  setPage('新课学习');
}
function nlStartQuiz(){ nlState.phase='quiz'; render(); }
function nlPick(qi, oi){ nlState.picks[qi]=oi; render(); }
function nlSubmit(){
  const s=nlState;
  // 阅读理解主观题：以“我答对了”自评通过
  s.result = {pass:true, rate:1.0};
  render();
}
async function nlAdvance(){
  await api('/api/progress/advance', {method:'POST', body:{user_id:uid, correct:1, total:1}});
  await loadPoints();
  setPage('学习首页'); toast('进度已推进到下一课');
}
function nlRetryRead(){ nlState.phase='read'; nlState.picks=[]; nlState.result=null; render(); }
async function nlAsk(){
  const v=(document.getElementById('nlAskInput')||{}).value||'';
  if(!v.trim()) return;
  nlChat.push({role:'q',text:v.trim()});
  const d = await api('/api/ask', {method:'POST', body:{lesson_id:currentLessonId, question:v.trim(), context:currentText}});
  nlChat.push({role:'a', text: d.answer || '（暂无回答）'});
  render();
  const el=document.querySelector('.nl-chat-body'); if(el) el.scrollTop=el.scrollHeight;
}
function nlQuick(q){ document.getElementById('nlAskInput').value=q; nlAsk(); }
function nlCaptureSel(){ const sel = window.getSelection ? window.getSelection().toString().trim() : ''; nlNoteSel = sel; if(sel) render(); }
function nlAddNote(){
  const v=(document.getElementById('nlNoteInput')||{}).value||'';
  if(!v.trim()) return;
  api('/api/notes', {method:'POST', body:{lesson_id:currentLessonId, author_role:'child', content:v.trim(), anchor_text:nlNoteSel||''}});
  nlNotes.push({id:Date.now(), anchor:nlNoteSel||'', text:v.trim(), time:'刚刚'});
  nlNoteSel=''; render();
}
function nlDelNote(id){ nlNotes = nlNotes.filter(n=>n.id!==id); render(); }
function nlNoteHint(){ toast('划词记笔记：先用鼠标选中教材里的一段文字'); }
function renderNewLesson(){
  const s=nlState;
  if(!s) return '<div class="placeholder-page"><h2>新课学习</h2><p>请从首页进入。</p></div>';

  if(s.phase==='read'){
    const chatMsgs = nlChat.map(m=>`
      <div class="nl-msg ${m.role}">
        ${m.role==='q'?'<div class="bubble q">'+m.text+'</div>':'<div class="bubble a">'+m.text+'</div>'}
      </div>`).join('');
    const noteItems = nlNotes.map(n=>`
      <div class="nl-note-item">
        ${n.anchor?`<div class="nl-note-anchor">「${n.anchor.length>18?n.anchor.slice(0,18)+'…':n.anchor}」</div>`:''}
        <div class="nl-note-text">${n.text}</div>
        <div class="nl-note-meta">${n.time}<span class="nl-note-del" onclick="nlDelNote(${n.id})">删除</span></div>
      </div>`).join('');
    return `<header class="page-head"><div><h1>进入下一课</h1></div><button class="btn-ghost" onclick="setPage('学习首页')">退出</button></header>
    <div class="newlesson-wrap nl-full">
      <div class="nl-read-top">
        <span class="nl-tag read" style="display:inline-flex">${icon('book',14)} 第 1 步 · 阅读教材内容</span>
        <span class="nl-read-hint">${icon('sparkles',14)} 边读边问 · 不懂就问</span>
      </div>
      <div class="nl-immersive">
        <div class="nl-reader">
          <div class="nl-reader-head"><span class="nl-unit">第十二课</span><span>课文内容</span></div>
          <div class="nl-page" onmouseup="nlCaptureSel()">
            <h2 class="serif">第 12 课 · 精读课文</h2>
            <div class="nl-content">${currentText}</div>
            <div class="nl-note-tip" onclick="nlNoteHint()">${icon('pen',14)} 划词记笔记：选中文字后到这里写笔记</div>
          </div>
          <button class="nl-read-done" onclick="nlStartQuiz()">我已读完，去答题 ${icon('arrow',16)}</button>
        </div>
        <div class="nl-chat">
          <div class="nl-chat-head">${icon('sparkles',16)} 不懂就问 · AI 讲解</div>
          <div class="nl-chat-body">
            ${nlChat.length?chatMsgs:`<div class="nl-chat-empty">${icon('sparkles',24)}<p>看到不懂的地方，划词或输入问题，AI 结合教材为你讲解。</p></div>`}
          </div>
          <div class="nl-quick">这段话是什么意思？｜帮我总结知识点</div>
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

  // quiz 阶段：阅读理解主观题自评
  const items = nlState.questions.map((q,qi)=>`
    <div class="nl-quiz-item"><div class="qq">${qi+1}. ${q.question}</div><div style="margin-top:8px;font-size:12px;color:var(--gray2)">参考答案：${q.answer}</div></div>`).join('');
  return `<header class="page-head"><div><h1>进入下一课</h1></div><button class="btn-ghost" onclick="setPage('学习首页')">退出</button></header>
  <div class="newlesson-wrap">
    <div class="nl-step">
      <span class="nl-tag quiz">${icon('pen',14)} 第 2 步 · 阅读理解</span>
      <h2>检验是否读懂</h2>
      ${items}
      <p style="margin-top:16px;font-size:13px;color:var(--gray2)">先在心里作答，再点「我答对了」确认掌握。</p>
      <button class="nl-submit" onclick="nlAdvance()">我答对了，进入下一课 ${icon('arrow',16)}</button>
    </div>
  </div>`;
}

// ===== 学习中心（听力 + 阅读）=====
async function loadCenter(){
  listenMaterial = await api(`/api/listening/material?user_id=${uid}`);
  readMaterial = await api(`/api/reading/material?lesson_id=${currentLessonId}`);
}
function renderCenter(){
  const l = listenMaterial || {text:'（点击下方加载听力材料）', questions:[]};
  const r = readMaterial || {text:'（点击下方加载阅读材料）', questions:[]};
  if(centerTab==='听力'){
    return `<header class="page-head"><div><h1>学习中心</h1></div></header>
    <div class="filter" style="margin-bottom:20px;width:fit-content">
      <button class="${centerTab==='听力'?'active':''}" onclick="centerTab='听力';render()">英语听力</button>
      <button class="${centerTab==='阅读'?'active':''}" onclick="centerTab='阅读';render()">语文阅读</button>
    </div>
    <div class="dict-wrap">
      <div class="dict-card" style="text-align:left">
        <h2 style="text-align:center">英语听力练习</h2>
        <div style="margin-top:16px;display:flex;justify-content:center"><button class="dict-play" onclick="browserSpeak((listenMaterial&&listenMaterial.text)||'')">${icon('play',17)} 播放对话</button></div>
        <p style="margin-top:20px;font-size:15px;line-height:28px">${l.text}</p>
        ${l.questions && l.questions.length ? `<div style="margin-top:16px;border-top:1px solid var(--line);padding-top:16px"><b>理解题：</b>${l.questions[0].question}</div>`:''}
        <button class="next-lesson-btn" style="margin-top:20px" onclick="loadCenter().then(()=>render())">换一段 ${icon('arrow',16)}</button>
      </div>
    </div>`;
  }
  return `<header class="page-head"><div><h1>学习中心</h1></div></header>
  <div class="filter" style="margin-bottom:20px;width:fit-content">
    <button class="${centerTab==='听力'?'active':''}" onclick="centerTab='听力';render()">英语听力</button>
    <button class="${centerTab==='阅读'?'active':''}" onclick="centerTab='阅读';render()">语文阅读</button>
  </div>
  <div class="dict-wrap">
    <div class="dict-card" style="text-align:left">
      <h2 style="text-align:center">语文阅读理解</h2>
      <p style="margin-top:20px;font-size:15px;line-height:30px">${r.text}</p>
      ${r.questions && r.questions.length ? `<div style="margin-top:16px;border-top:1px solid var(--line);padding-top:16px"><b>思考题：</b>${r.questions[0].question}<div style="margin-top:8px;font-size:12px;color:var(--gray2)">参考答案：${r.questions[0].answer}</div></div>`:''}
    </div>
  </div>`;
}

// ===== 错题本 =====
let mistakes = [];
async function loadMistakes(){
  mistakes = await api(`/api/mistakes?user_id=${uid}`);
}
async function renderWrongBook(){
  // 同步加载错题
  mistakes = await api(`/api/mistakes?user_id=${uid}`);
  const subjOf = s => s==='dictation'||s==='reading'?'语文':'英语';
  const srcName = {dictation:'生词听写', review:'复习', listening:'听力', reading:'阅读', goal:'考核'};
  const visible = mistakes.filter(m => wrongFilter==='全部' || subjOf(m.source_type)===wrongFilter);
  const cards = visible.map(m=>`
    <article class="wrong-card">
      <div class="top">
        <div class="meta">
          <span class="subj-tag ${subjOf(m.source_type)==='语文'?'badge-blue':'badge-orange'}">${subjOf(m.source_type)}</span>
          <span class="src">${srcName[m.source_type]||m.source_type}</span>
        </div>
      </div>
      <div class="q">${m.question}</div>
      <div class="wrong-ans">
        <div class="wa bad"><div class="lbl">你的答案</div><div class="val">${m.your_answer||'（空）'}</div></div>
        <div class="wa good"><div class="lbl">正确答案</div><div class="val">${m.correct_answer}</div></div>
      </div>
      <div class="foot">
        <div class="reason">${icon('brain',15)}<b>已连续答对</b> ${m.consecutive_correct} 次（3 次移出）</div>
        <div class="actions">
          <button class="btn-ghost" onclick="mistakeWrong(${m.id})">又错了</button>
          <button class="btn-primary" onclick="mistakeCorrect(${m.id})">我答对了</button>
        </div>
      </div>
    </article>`).join('');

  const empty = visible.length===0 ? `<div style="text-align:center;padding:64px 0"><div style="width:48px;height:48px;border-radius:50%;background:#eaf7ef;color:#2e8b5a;display:grid;place-items:center;margin:0 auto">${icon('check',20)}</div><h3 style="margin-top:16px;font-weight:700">当前错题都掌握了</h3><p style="margin-top:4px;font-size:14px;color:#8e9691">继续保持，新的错题会自动出现在这里。</p></div>` : cards;

  return `
  <header class="page-head">
    <div>
      <div class="crumb">${icon('pen',16)}智能错题本</div>
      <h1 class="big">从错误中真正学会</h1>
      <p class="desc">练习中的错题会自动收录，连续答对 3 次移出错题本。</p>
    </div>
    <div style="display:flex;align-items:center;gap:8px;border-radius:12px;background:#eaf7ef;padding:12px 16px;font-size:14px;font-weight:600;color:#2e8055">${icon('check',17)}已开启自动收录</div>
  </header>

  <div class="stats-grid">
    <div class="stat-card"><div class="t">待掌握错题</div><div class="row"><span class="v">${mistakes.length}</span><span class="d badge-blue">自动收录</span></div></div>
    <div class="stat-card"><div class="t">连续答对后移除</div><div class="row"><span class="v">3 次</span><span class="d badge-green">掌握后移出</span></div></div>
    <div class="stat-card"><div class="t">错题来源</div><div class="row"><span class="v">${new Set(mistakes.map(m=>m.source_type)).size}</span><span class="d badge-orange">类题型</span></div></div>
  </div>

  <section class="wrong-list">
    <div class="head">
      <div><h2>错题列表</h2><div class="sub">答对一次累计，连续 3 次自动移出复习</div></div>
      <div class="filter">
        ${['全部','语文','英语'].map(s=>`<button class="${wrongFilter===s?'active':''}" onclick="setFilter('${s}')">${s}</button>`).join('')}
      </div>
    </div>
    <div class="wrong-items">${empty}</div>
  </section>`;
}
function setFilter(s){ wrongFilter=s; render(); }
async function mistakeCorrect(id){
  const d = await api(`/api/mistakes/${id}/correct`, {method:'POST'});
  toast(d.removed ? '已连续答对 3 次，移出错题本' : `累计答对 ${d.consecutive_correct} 次`);
  render();
}
async function mistakeWrong(id){
  await api(`/api/mistakes/${id}/wrong`, {method:'POST'});
  toast('已重置连续答对计数');
  render();
}

// ===== 学习报告（孩子端）=====
async function renderReport(){
  const rep = await api(`/api/mistakes/report?user_id=${uid}`);
  const rows = (rep.rows||[]).map(r=>{
    const pct = rep.total? Math.round(r.count/rep.total*100):0;
    return `<div class="weak-row"><span class="w-name">${r.name}</span><div class="w-bar"><div class="w-fill" style="width:${Math.max(pct,4)}%"></div></div><span class="w-val">${r.count} 次</span></div>`;
  }).join('');
  const bal = points;
  return `<header class="page-head"><div><h1>学习报告</h1><p class="desc">学习积分与错题分布</p></div></header>
  <div class="stats-grid">
    <div class="stat-card"><div class="t">当前积分</div><div class="row"><span class="v" style="color:var(--orange)">${bal}</span></div></div>
    <div class="stat-card"><div class="t">错题总数</div><div class="row"><span class="v">${rep.total||0}</span></div></div>
    <div class="stat-card"><div class="t">词库生词</div><div class="row"><span class="v">${dictWords.length}</span></div></div>
  </div>
  <div class="parent-grid" style="margin-top:24px">
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic green">${icon('chart',20)}</div><div><h3>错题分布</h3><div class="sub">按题型汇总错误频率</div></div></div>
      <div class="bd">${rows || '<p style="font-size:13px;color:var(--gray2)">暂无错题记录</p>'}</div>
    </div>
  </div>`;
}

// ===== 积分商城 =====
async function renderMall(){
  const bal = points;
  return `<header class="page-head"><div><h1>积分商城</h1><p class="desc">用学习积分兑换设备使用时间</p></div></header>
  <div class="review-grid">
    <div class="redeem-card">
      <div class="head">
        <div><div class="lbl">我的积分</div><h2>劳逸结合，快乐成长</h2></div>
        <div class="pts">${icon('star',17)}${bal}</div>
      </div>
      <div class="redeem-items">
        <button class="redeem-item" onclick="redeem('tablet',30,300)">${icon('tablet',25)}<div class="name">平板 30 分钟</div><div class="cost">300 积分兑换</div></button>
        <button class="redeem-item" onclick="redeem('phone',20,200)">${icon('phone',25)}<div class="name">手机 20 分钟</div><div class="cost">200 积分兑换</div></button>
      </div>
    </div>
    <div class="review-card">
      <div class="head"><div><h2>兑换规则</h2><div class="sub">兑换后由家长确认</div></div></div>
      <div class="redeem-rule" style="margin-top:16px">
        <div class="rule-row"><div class="r-l">${icon('tablet',22)}<div><div class="r-name">平板 30 分钟</div><div class="r-cost">300 积分</div></div></div></div>
        <div class="rule-row"><div class="r-l">${icon('phone',22)}<div><div class="r-name">手机 20 分钟</div><div class="r-cost">200 积分</div></div></div></div>
      </div>
      <p style="margin-top:16px;font-size:12px;color:#8e9691">兑换后请配合系统家长控制设置对应限额。</p>
    </div>
  </div>`;
}

// ===== 个性化学习 =====
let excerpt='', answer='', question='';
async function renderPersonalized(){
  return `
  <header class="page-head">
    <div>
      <div class="crumb">${icon('sparkles',16)}AI 个性化学习</div>
      <h1 class="big">和教材一起深度学习</h1>
      <p class="desc">上传 PDF 教材（家长端），边读边问，AI 会结合内容耐心讲解。</p>
    </div>
  </header>

  <div class="pl-grid">
    <section class="pl-reader">
      <div class="bar">
        <div class="t"><div class="ic">${icon('book',18)}</div><div style="min-width:0"><div class="name">语文 五年级下册</div><div class="sub">配套电子教材 · 当前学习内容</div></div></div>
      </div>
      <div class="reader-body">
        <article class="reader-page">
          <div class="unit">第十二课</div>
          <h2 class="serif">古诗三首</h2>
          <div class="body">
            <p style="margin-bottom:16px">四时田园杂兴（其三十一）</p>
            <p style="margin-bottom:16px">昼出耘田夜绩麻，村庄儿女各当家。</p>
            <p style="margin-bottom:16px">童孙未解供耕织，也傍桑阴学种瓜。</p>
            <p style="margin-top:24px;color:#78817b">注释：耘田，在田间除草。绩麻，把麻搓成线。供，从事。傍，靠近。</p>
          </div>
        </article>
      </div>
    </section>
    <div class="pl-side">
      <section class="pl-ask">
        <h3>选中的教材内容</h3>
        <textarea class="ta" placeholder="从左侧教材复制一段内容，粘贴到这里…" oninput="excerpt=this.value">${excerpt}</textarea>
        <div class="quick-actions">
          <button class="qa-btn" onclick="ask('这段话是什么意思？')">这段话是什么意思？</button>
          <button class="qa-btn" onclick="ask('帮我总结知识点')">帮我总结知识点</button>
          <button class="qa-btn" onclick="ask('给我出一道练习题')">给我出一道练习题</button>
        </div>
      </section>
      <section class="pl-question">
        <h3>针对这段教材提问</h3>
        <div class="qa-input"><input placeholder="针对这段教材提问…" oninput="question=this.value"><button class="send-btn" onclick="ask()">发送问题</button></div>
      </section>
      ${answer?`<section class="pl-answer"><h3>${icon('sparkles',16)}AI 讲解</h3><div class="ans">${answer}</div></section>`:''}
    </div>
  </div>`;
}
async function ask(preset){
  const q = preset || question;
  if(!q || !q.trim()) return;
  const ctx = excerpt && excerpt.trim() ? excerpt.trim() : currentText;
  const d = await api('/api/ask', {method:'POST', body:{lesson_id:currentLessonId, question:q.trim(), context:ctx}});
  answer = d.answer || '（暂无回答）';
  render();
}

// ===== 家长端 =====
function toggleRole(){
  isParent = !isParent;
  if(isParent){ parentTab='教材'; loadParentData(); }
  document.getElementById('userAvatar').textContent = isParent?'林':'晨';
  document.getElementById('userName').textContent = isParent?'林爸爸':'林晨';
  document.getElementById('userGrade').textContent = isParent?'家长':'五年级';
  document.getElementById('roleSwitch').textContent = isParent?'孩子端':'家长端';
  renderNav(); render();
  if(isParent) toast('已切换到家长端');
}
function setParentTab(t){ parentTab=t; if(t==='教材') loadPdfDocs(); if(t==='知识点') loadKnowledge(); if(t==='目标') loadGoals(); if(t==='报告') loadReport(); if(t==='设置') loadConfig(); render(); }
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
  ttsConfig.provider = configMap.tts_provider || 'minimax';
  ttsConfig.voice = configMap.tts_voice || '清澈男声';
  ttsConfig.key = configMap.tts_key || '';
  ttsConfig.speed = parseFloat(configMap.tts_speed || '1.0');
  ttsConfig.repeat = parseInt(configMap.tts_repeat || '2');
}

function renderParent(){
  const tabs = ['教材','知识点','目标','报告','规则','设置'].map(t=>
    `<button style="border-radius:10px;padding:8px 16px;font-size:13px;font-weight:600;color:${parentTab===t?'#3158e8':'#778079'};background:${parentTab===t?'#fff':'transparent'}" onclick="setParentTab('${t}')">${t}</button>`
  ).join('');

  let body='';
  if(parentTab==='教材') body = renderPdfTab();
  else if(parentTab==='知识点') body = renderKnowledgeTab();
  else if(parentTab==='目标') body = renderGoalsTab();
  else if(parentTab==='报告') body = renderReportTab();
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
      <button class="btn-ghost" onclick="openDoc(${d.id})">查看/审核</button>
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
async function doExtract(){
  await api(`/api/pdf/documents/${confirmDocId}/extract`, {method:'POST'});
  docLessons = await api(`/api/pdf/documents/${confirmDocId}/lessons`);
  toast('生词与知识点提取完成');
  render();
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
        ${l.extract_status!=='done'?`<button class="btn-primary" onclick="doExtract()">提取生词/知识点</button>`:''}
        <button class="btn-ghost" style="color:#c05b4a" onclick="auditLesson(${l.id},'驳回')">驳回</button>
        <button class="btn-primary" onclick="auditLesson(${l.id},'通过')">审核通过</button>
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
    const statusMap = {pending:['待开始','#eef0ed','#78817b'], in_progress:['学习中','var(--orange-soft)','var(--orange2)'], done:['已掌握','var(--green-soft2)','var(--green)']};
    const [label,bg,fg] = statusMap[g.status]||statusMap.pending;
    return `<div class="goal-item">
      <div class="g-top"><span class="g-name">${g.content}</span><span class="g-status" style="background:${bg};color:${fg}">${label}</span></div>
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
        <div style="font-size:13px;color:var(--gray2);margin-bottom:16px">错误频率（题型级）</div>
        <div class="weak-list">${rows || '<p style="font-size:13px;color:var(--gray2)">暂无错误记录</p>'}</div>
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
          <div class="rule-row"><div class="r-l">${icon('tablet',22)}<div><div class="r-name">平板 30 分钟</div><div class="r-cost">300 积分</div></div></div></div>
          <div class="rule-row"><div class="r-l">${icon('phone',22)}<div><div class="r-name">手机 20 分钟</div><div class="r-cost">200 积分</div></div></div></div>
        </div>
        <p style="margin-top:16px;font-size:12px;color:#8e9691">兑换后，请配合系统家长控制（iOS 屏幕使用时间 / Android Family Link）设置对应限额。</p>
      </div>
    </div>
  </div>`;
}

// ---- 设置 ----
function renderSettingsTab(){
  const aiOpts = aiProviders.map(p=>{
    const models = p.models.map(m=>`<option value="${m}" ${aiConfig.provider===p.id&&aiConfig.model===m?'selected':''}>${m}</option>`).join('');
    return `<div class="rule-row" style="flex-direction:column;align-items:stretch;gap:10px">
      <label style="display:flex;align-items:center;gap:10px;font-size:14px;font-weight:700;cursor:pointer"><input type="radio" name="aiProvider" value="${p.id}" ${aiConfig.provider===p.id?'checked':''} onchange="setAiProvider('${p.id}')">${p.name}</label>
      ${aiConfig.provider===p.id?`<div style="display:flex;gap:10px;align-items:center"><span style="font-size:13px;color:var(--gray2)">模型</span><select style="flex:1;border:1px solid var(--line3);border-radius:10px;padding:8px 10px;font-size:13px" onchange="aiConfig.model=this.value">${models}</select></div>`:''}
    </div>`;
  }).join('');
  const ttsOpts = ttsProviders.map(p=>{
    const voices = p.voices.map(v=>`<option value="${v}" ${ttsConfig.provider===p.id&&ttsConfig.voice===v?'selected':''}>${v}</option>`).join('');
    return `<div class="rule-row" style="flex-direction:column;align-items:stretch;gap:10px">
      <label style="display:flex;align-items:center;gap:10px;font-size:14px;font-weight:700;cursor:pointer"><input type="radio" name="ttsProvider" value="${p.id}" ${ttsConfig.provider===p.id?'checked':''} onchange="setTtsProvider('${p.id}')">${p.name}</label>
      ${ttsConfig.provider===p.id?`<div style="display:flex;gap:10px;align-items:center"><span style="font-size:13px;color:var(--gray2)">音色</span><select style="flex:1;border:1px solid var(--line3);border-radius:10px;padding:8px 10px;font-size:13px" onchange="ttsConfig.voice=this.value">${voices}</select></div>`:''}
    </div>`;
  }).join('');
  return `<div class="parent-grid">
    <div class="parent-panel">
      <div class="head"><div class="ic purple">${icon('brain',20)}</div><div><h3>AI 大模型配置</h3><div class="sub">选择出题 / 批改 / 对话用的默认模型</div></div></div>
      <div class="bd">
        <div class="redeem-rule">${aiOpts}</div>
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
        <div style="margin-top:16px;display:flex;flex-direction:column;gap:12px">
          <div><div style="font-size:13px;color:var(--gray2);margin-bottom:8px">API Key</div><input type="password" placeholder="语音服务 Key" value="${ttsConfig.key}" oninput="ttsConfig.key=this.value" style="width:100%;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px"></div>
          <div style="display:flex;gap:10px;align-items:center"><span style="font-size:13px;color:var(--gray2);white-space:nowrap">语速</span><input type="range" min="0.5" max="2" step="0.1" value="${ttsConfig.speed}" oninput="ttsConfig.speed=this.value;this.nextElementSibling.textContent=this.value" style="flex:1"><span style="font-size:13px;width:32px;text-align:right">${ttsConfig.speed}</span></div>
          <div style="display:flex;gap:10px;align-items:center"><span style="font-size:13px;color:var(--gray2);white-space:nowrap">重复次数</span><input type="range" min="1" max="3" step="1" value="${ttsConfig.repeat}" oninput="ttsConfig.repeat=this.value;this.nextElementSibling.textContent=this.value+' 次'" style="flex:1"><span style="font-size:13px;width:44px;text-align:right">${ttsConfig.repeat} 次</span></div>
        </div>
      </div>
    </div>
    <div style="grid-column:1/-1;display:flex;justify-content:flex-end;gap:10px">
      <button class="btn-ghost" style="padding:10px 20px" onclick="testVoice()">试听语音</button>
      <button class="btn-primary" style="padding:10px 24px" onclick="saveConfig()">保存配置</button>
    </div>
  </div>`;
}
function setAiProvider(id){ aiConfig.provider=id; aiConfig.model=aiProviders.find(p=>p.id===id).models[0]; render(); }
function setTtsProvider(id){ ttsConfig.provider=id; ttsConfig.voice=ttsProviders.find(p=>p.id===id).voices[0]; render(); }
async function saveConfig(){
  const kv = [
    ['ai_provider', aiConfig.provider], ['ai_model', aiConfig.model], ['ai_key', aiConfig.key],
    ['tts_provider', ttsConfig.provider], ['tts_voice', ttsConfig.voice], ['tts_key', ttsConfig.key],
    ['tts_speed', String(ttsConfig.speed)], ['tts_repeat', String(ttsConfig.repeat)]
  ];
  for(const [key,value] of kv){ await api('/api/config', {method:'POST', body:{key, value}}); }
  toast('配置已保存');
}
function testVoice(){ browserSpeak('你好，这是语音合成测试'); toast('已播放试听语音'); }

// ===== 初始化 =====
async function init(){
  // 登录默认孩子
  const u = await api('/api/auth/login', {method:'POST', body:{name:'林晨'}});
  uid = u.id;
  document.getElementById('userName').textContent = u.name;
  await loadPoints();
  await loadCenter();
  dictWords = await api(`/api/dictation/words?user_id=${uid}`);
  renderNav(); render();
}
async function loadPoints(){
  const d = await api(`/api/points/balance?user_id=${uid}`);
  points = d.balance || 0;
}

init();
