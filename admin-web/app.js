// ===== 知学伴 · 运营后台 MVP =====
const API = window.KNOACT_API_BASE ?? 'http://127.0.0.1:8010';
const TOKEN_KEY = 'knoact_admin_access_token';
const ADMIN_USER_KEY = 'knoact_admin_user';

let accessToken = localStorage.getItem(TOKEN_KEY) || '';
let adminUser = null;
try {
  adminUser = JSON.parse(localStorage.getItem(ADMIN_USER_KEY) || 'null');
} catch {
  adminUser = null;
}

let roleFilter = '';
let searchQ = '';
let users = [];
let loading = false;
let adminPage = 'users';
let checkinDate = '';
let checkinQ = '';
let checkinStatus = '';
let checkinSubject = '';
let checkins = [];
let checkinsTotal = 0;
let checkinsLoading = false;

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.style.display = 'none'; }, 2600);
}

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function jsEsc(s) {
  return String(s ?? '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function errMsg(data, fallback) {
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  const d = data.detail;
  if (typeof d === 'string') return d;
  if (d && typeof d === 'object' && d.error) {
    const map = { invalid_credentials: '登录名或密码错误' };
    return map[d.error] || String(d.error);
  }
  return fallback;
}

async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const init = { ...opts, headers };
  if (opts.body && typeof opts.body !== 'string') init.body = JSON.stringify(opts.body);
  const r = await fetch(API + path, init);
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json() : await r.text();
  if (r.status === 401) {
    logout(false);
    throw new Error('登录已过期，请重新登录');
  }
  if (!r.ok) throw new Error(errMsg(data, `请求失败 (${r.status})`));
  return data;
}

function saveSession(tokens) {
  accessToken = tokens.access_token;
  adminUser = tokens.user;
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(ADMIN_USER_KEY, JSON.stringify(adminUser));
}

function logout(notify = true) {
  accessToken = '';
  adminUser = null;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ADMIN_USER_KEY);
  users = [];
  render();
  if (notify) toast('已退出登录');
}

async function doLogin(loginName, password) {
  const r = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login_name: loginName, password }),
  });
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json() : {};
  if (!r.ok) throw new Error(errMsg(data, '登录失败'));
  if (data.user?.role !== 'admin') throw new Error('该账号不是管理员');
  saveSession(data);
  toast('登录成功');
  await loadUsers();
  render();
}

async function loadUsers() {
  loading = true;
  render();
  try {
    const qs = new URLSearchParams();
    if (roleFilter) qs.set('role', roleFilter);
    if (searchQ.trim()) qs.set('q', searchQ.trim());
    const q = qs.toString();
    users = await api(`/api/admin/users${q ? `?${q}` : ''}`);
  } finally {
    loading = false;
    render();
  }
}

async function createUser(ev) {
  ev.preventDefault();
  const fd = new FormData(ev.target);
  const body = {
    login_name: String(fd.get('login_name') || '').trim(),
    password: String(fd.get('password') || ''),
    role: String(fd.get('role') || 'child'),
    display_name: String(fd.get('display_name') || '').trim(),
    edition: String(fd.get('edition') || '').trim(),
    phone: String(fd.get('phone') || '').trim(),
  };
  const gradeRaw = String(fd.get('grade') || '').trim();
  if (gradeRaw) body.grade = Number(gradeRaw);
  const parentRaw = String(fd.get('parent_id') || '').trim();
  if (parentRaw) body.parent_id = Number(parentRaw);
  try {
    await api('/api/admin/users', { method: 'POST', body });
    toast('用户已创建');
    ev.target.reset();
    await loadUsers();
  } catch (e) {
    toast(e.message || '创建失败');
  }
}

async function resetPassword(userId, loginName) {
  const pwd = window.prompt(`为「${loginName}」设置新密码（至少 8 位）：`);
  if (pwd === null) return;
  if (!pwd.trim()) {
    toast('密码不能为空');
    return;
  }
  try {
    await api(`/api/admin/users/${userId}/reset-password`, {
      method: 'POST',
      body: { password: pwd },
    });
    toast('密码已重置');
  } catch (e) {
    toast(e.message || '重置失败');
  }
}

async function archiveUser(userId, loginName) {
  if (!window.confirm(`确定归档用户「${loginName}」？归档后该账号将无法登录。`)) return;
  try {
    await api(`/api/admin/users/${userId}/archive`, { method: 'POST' });
    toast('已归档');
    await loadUsers();
  } catch (e) {
    toast(e.message || '归档失败');
  }
}

function roleTag(role) {
  const labels = { child: '孩子', parent: '家长', admin: '管理员' };
  return `<span class="tag ${esc(role)}">${esc(labels[role] || role)}</span>`;
}

function renderLogin() {
  return `
    <div class="login-wrap">
      <form class="login-card" onsubmit="loginSubmit(event)">
        <h1>知学伴运营后台</h1>
        <p>使用管理员账号登录，管理家长与孩子账户。</p>
        <p class="hint">默认开发账号：<strong>admin</strong> / <strong>ChangeMe123</strong>（与 <code>ADMIN_INITIAL_PASSWORD</code> 一致）</p>
        <div class="field">
          <label for="login_name">登录名</label>
          <input id="login_name" name="login_name" required autocomplete="username" placeholder="admin">
        </div>
        <div class="field">
          <label for="password">密码</label>
          <input id="password" name="password" type="password" required autocomplete="current-password">
        </div>
        <button type="submit" class="btn-primary">登录</button>
        <p class="login-hint">默认种子账号：<code>admin</code> / <code>ChangeMe123</code>（可通过环境变量 <code>ADMIN_INITIAL_PASSWORD</code> 覆盖）</p>
      </form>
    </div>`;
}

function renderShell(mainHtml, active = 'users') {
  const name = adminUser?.display_name || adminUser?.name || adminUser?.login_name || '管理员';
  return `
    <div class="layout">
      <aside class="sidebar">
        <div>
          <div class="logo">知学伴</div>
          <div class="logo-sub">运营后台</div>
        </div>
        <nav class="nav">
          <button type="button" class="nav-item ${active === 'users' ? 'on' : ''}" onclick="setAdminPage('users')">用户管理</button>
          <button type="button" class="nav-item ${active === 'checkins' ? 'on' : ''}" onclick="setAdminPage('checkins')">听写打卡</button>
        </nav>
        <div class="sidebar-foot">
          <div class="who">${esc(name)}</div>
          <button type="button" class="btn-ghost" onclick="logout()">退出登录</button>
        </div>
      </aside>
      <main class="main">${mainHtml}</main>
    </div>`;
}

function renderUsersPage() {
  const rows = users.map((u) => {
    const status = u.status === 'archived'
      ? '<span class="tag archived">已归档</span>'
      : '<span class="tag active">正常</span>';
    const actions = u.status === 'archived'
      ? '<span style="color:#9aa39c;font-size:12px">—</span>'
      : `<div class="row-actions">
          <button type="button" class="btn-ghost" onclick="resetPassword(${u.id}, '${jsEsc(u.login_name)}')">重置密码</button>
          <button type="button" class="btn-ghost btn-danger" onclick="archiveUser(${u.id}, '${jsEsc(u.login_name)}')">归档</button>
        </div>`;
    return `<tr>
      <td>${u.id}</td>
      <td>${esc(u.login_name)}</td>
      <td>${esc(u.display_name || u.name || '—')}</td>
      <td>${roleTag(u.role)}</td>
      <td>${u.parent_id ?? '—'}</td>
      <td>${u.grade ?? '—'}</td>
      <td>${esc(u.phone || '—')}</td>
      <td>${status}</td>
      <td>${actions}</td>
    </tr>`;
  }).join('');

  const tableBody = loading
    ? '<tr><td colspan="9" class="empty">加载中…</td></tr>'
    : (rows || '<tr><td colspan="9" class="empty">暂无用户</td></tr>');

  return renderShell(`
    <div class="page-head">
      <h1>用户管理</h1>
      <p>查询、创建家长/孩子账号，重置密码或归档账号。</p>
    </div>
    <div class="toolbar">
      <select id="roleFilter" onchange="onRoleFilterChange(this.value)">
        <option value="" ${roleFilter === '' ? 'selected' : ''}>全部角色</option>
        <option value="child" ${roleFilter === 'child' ? 'selected' : ''}>孩子</option>
        <option value="parent" ${roleFilter === 'parent' ? 'selected' : ''}>家长</option>
        <option value="admin" ${roleFilter === 'admin' ? 'selected' : ''}>管理员</option>
      </select>
      <input type="search" id="searchQ" placeholder="搜索登录名 / 昵称 / 手机" value="${esc(searchQ)}"
        onkeydown="if(event.key==='Enter'){onSearchChange(this.value)}">
      <button type="button" class="btn-ghost" onclick="onSearchChange(document.getElementById('searchQ').value)">搜索</button>
      <button type="button" class="btn-primary" onclick="loadUsers()">刷新</button>
    </div>
    <section class="panel">
      <h2>创建用户</h2>
      <form onsubmit="createUser(event)">
        <div class="form-grid">
          <div class="field"><label>登录名 *</label><input name="login_name" required minlength="3"></div>
          <div class="field"><label>密码 *</label><input name="password" type="password" required minlength="8"></div>
          <div class="field"><label>角色 *</label>
            <select name="role"><option value="child">孩子</option><option value="parent">家长</option></select>
          </div>
          <div class="field"><label>显示名</label><input name="display_name"></div>
          <div class="field"><label>家长 ID（孩子可选）</label><input name="parent_id" type="number" min="1" placeholder="家长 user id"></div>
          <div class="field"><label>年级（孩子）</label><input name="grade" type="number" min="1" max="6"></div>
          <div class="field"><label>教材版本</label><input name="edition" placeholder="人教版"></div>
          <div class="field"><label>手机</label><input name="phone"></div>
        </div>
        <div class="form-actions">
          <button type="submit" class="btn-primary">创建用户</button>
        </div>
      </form>
    </section>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th><th>登录名</th><th>显示名</th><th>角色</th><th>家长 ID</th>
            <th>年级</th><th>手机</th><th>状态</th><th>操作</th>
          </tr>
        </thead>
        <tbody>${tableBody}</tbody>
      </table>
    </div>
  `, 'users');
}

async function loadDictationCheckins() {
  checkinsLoading = true;
  render();
  try {
    if (!checkinDate) {
      const t = new Date();
      checkinDate = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`;
    }
    const qs = new URLSearchParams({ date: checkinDate, limit: '50' });
    if (checkinQ.trim()) qs.set('q', checkinQ.trim());
    if (checkinStatus) qs.set('submit_status', checkinStatus);
    if (checkinSubject) qs.set('subject', checkinSubject);
    const data = await api(`/api/admin/dictation-checkins?${qs}`);
    checkins = data.items || [];
    checkinsTotal = data.total ?? checkins.length;
  } finally {
    checkinsLoading = false;
    render();
  }
}

function renderCheckinsPage() {
  const rows = checkins.map((t) => {
    const photo = t.photo_path
      ? `<a href="${API}/${esc(t.photo_path)}" target="_blank" rel="noopener">查看照片</a>`
      : '<span style="color:#9aa39c">无</span>';
    return `<tr>
      <td>${esc(t.child_display_name || t.child_login_name || t.user_id)}</td>
      <td>${esc(t.parent_display_name || '—')}</td>
      <td>${esc(t.date)}</td>
      <td>${esc(t.subject)}</td>
      <td>${esc(t.title)}</td>
      <td>${esc(t.submit_status)}</td>
      <td>${t.points ?? '—'}</td>
      <td>${photo}</td>
    </tr>`;
  }).join('');
  const body = checkinsLoading
    ? '<tr><td colspan="8" class="empty">加载中…</td></tr>'
    : (rows || '<tr><td colspan="8" class="empty">暂无听写打卡记录</td></tr>');
  return renderShell(`
    <div class="page-head">
      <h1>听写打卡</h1>
      <p>只读查看各孩子听写任务提交与打卡照片（共 ${checkinsTotal} 条）。</p>
    </div>
    <div class="toolbar">
      <input type="date" value="${esc(checkinDate)}" onchange="onCheckinDateChange(this.value)">
      <input type="search" placeholder="孩子登录名/昵称" value="${esc(checkinQ)}"
        onkeydown="if(event.key==='Enter'){onCheckinSearch(this.value)}">
      <select onchange="checkinStatus=this.value;loadDictationCheckins().catch(e=>toast(e.message))">
        <option value="" ${!checkinStatus ? 'selected' : ''}>全部状态</option>
        <option value="not_started" ${checkinStatus === 'not_started' ? 'selected' : ''}>未开始</option>
        <option value="submitted" ${checkinStatus === 'submitted' ? 'selected' : ''}>待审核</option>
        <option value="approved" ${checkinStatus === 'approved' ? 'selected' : ''}>已通过</option>
      </select>
      <select onchange="checkinSubject=this.value;loadDictationCheckins().catch(e=>toast(e.message))">
        <option value="" ${!checkinSubject ? 'selected' : ''}>全部学科</option>
        <option value="语文" ${checkinSubject === '语文' ? 'selected' : ''}>语文</option>
        <option value="英语" ${checkinSubject === '英语' ? 'selected' : ''}>英语</option>
      </select>
      <button type="button" class="btn-primary" onclick="loadDictationCheckins().catch(e=>toast(e.message))">刷新</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>孩子</th><th>家长</th><th>日期</th><th>学科</th><th>任务</th><th>状态</th><th>积分</th><th>照片</th>
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `, 'checkins');
}

function render() {
  const root = document.getElementById('app');
  if (!accessToken || !adminUser || adminUser.role !== 'admin') {
    root.innerHTML = renderLogin();
    return;
  }
  root.innerHTML = adminPage === 'checkins' ? renderCheckinsPage() : renderUsersPage();
}

function setAdminPage(page) {
  adminPage = page;
  if (page === 'checkins') loadDictationCheckins().catch((e) => toast(e.message));
  else render();
}

window.loginSubmit = async (ev) => {
  ev.preventDefault();
  const fd = new FormData(ev.target);
  const login_name = String(fd.get('login_name') || '').trim();
  const password = String(fd.get('password') || '');
  try {
    await doLogin(login_name, password);
  } catch (e) {
    toast(e.message || '登录失败');
  }
};

window.onRoleFilterChange = (val) => {
  roleFilter = val;
  loadUsers().catch((e) => toast(e.message));
};

window.onSearchChange = (val) => {
  searchQ = val;
  loadUsers().catch((e) => toast(e.message));
};

window.createUser = createUser;
window.resetPassword = resetPassword;
window.archiveUser = archiveUser;
window.loadUsers = () => loadUsers().catch((e) => toast(e.message));
window.logout = logout;
window.setAdminPage = setAdminPage;
window.loadDictationCheckins = () => loadDictationCheckins().catch((e) => toast(e.message));
window.onCheckinDateChange = (v) => { checkinDate = v; loadDictationCheckins().catch((e) => toast(e.message)); };
window.onCheckinSearch = (v) => { checkinQ = v; loadDictationCheckins().catch((e) => toast(e.message)); };

render();
if (accessToken && adminUser?.role === 'admin') {
  loadUsers().catch(() => logout(false));
}
