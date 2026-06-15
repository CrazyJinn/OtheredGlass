/* ═══════════════════════════════════════════════════════════════
   app.js — 全局工具 + Tab 切换 + Side Panel + Confirm Dialog
   ═══════════════════════════════════════════════════════════════ */

const RMS = 30000; // 自动刷新间隔 30s
let _cr = null;    // confirm dialog 回调

/* ═══ Helpers ═══ */
function $(id) { return document.getElementById(id); }
function enc(s) { return encodeURIComponent(s || ''); }
function esc(s) {
  if (!s) return '';
  const d = document.createElement('span');
  d.textContent = String(s);
  return d.innerHTML;
}
function escA(s) {
  if (!s) return '';
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

/* ═══ Tag Library (设计元素标签库) ═══ */
let TAGLIB = {};
async function loadTaglib() {
  try { TAGLIB = await api('/api/taglib'); }
  catch (e) { console.warn('标签库加载失败', e); }
}

/* ═══ Tab Switching ═══ */
const TAB_INIT = { narrative: false, art: false, scene: false, story: false };

function switchTab(name) {
  // 更新按钮样式
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === name);
  });
  // 显示/隐藏内容
  document.querySelectorAll('.tab-content').forEach(el => {
    el.classList.toggle('hidden', el.id !== 'tab-' + name);
  });
  // 首次切换到该 Tab 时初始化
  if (!TAB_INIT[name]) {
    TAB_INIT[name] = true;
    if (name === 'narrative') initNarrative();
    else if (name === 'art') loadArtStatus();
    else if (name === 'scene') loadSceneList();
    // story 不需要初始化
  }
  localStorage.setItem('activeTab', name);
}

/* ═══ Side Panel ═══ */
function openP(title) {
  $('pn-t').textContent = title;
  $('pn-b').innerHTML = '<div class="text-gray-400 text-center py-8">加载中...</div>';
  $('po').classList.remove('hidden');
  $('pn').classList.remove('hidden');
}

function closeP() {
  $('po').classList.add('hidden');
  $('pn').classList.add('hidden');
}

/* ═══ Confirm Dialog ═══ */
function cfShow(msg) {
  return new Promise(resolve => {
    _cr = resolve;
    $('cf-m').innerHTML = msg;
    $('cf').classList.remove('hidden');
  });
}
function cfY() {
  $('cf').classList.add('hidden');
  if (_cr) { _cr(true); _cr = null; }
}
function cfN() {
  $('cf').classList.add('hidden');
  if (_cr) { _cr(false); _cr = null; }
}

/* ═══ Input Modal（文本输入，如添加着装思路） ═══ */
let _im_cb = null;
function showInputIdea(title, hint, onConfirm) {
  $('im-t').textContent = title;
  $('im-h').textContent = hint;
  $('im-v').value = '';
  $('im').classList.remove('hidden');
  _im_cb = onConfirm;
  setTimeout(() => $('im-v').focus(), 50);
}
function imOK() {
  const v = $('im-v').value.trim();
  $('im').classList.add('hidden');
  if (_im_cb) { const cb = _im_cb; _im_cb = null; cb(v); }
}
function imCancel() {
  $('im').classList.add('hidden');
  _im_cb = null;
}

/* ═══ Error Bar ═══ */
function showErr(msg) {
  $('err-m').textContent = '⚠ ' + msg;
  $('err').classList.remove('hidden');
}

/* ═══ Save Node (通用，用于角色美术节点编辑) ═══ */
async function saveNode(nodeId, type) {
  const msgEl = $('save-msg');
  if (!msgEl) return;
  msgEl.textContent = '检查级联...';
  msgEl.className = 'text-xs text-gray-400';

  const schema = (NF[type] || { f: [] });
  const props = {};
  for (const f of schema.f) {
    if (f.t === 'image') continue;
    const el = $('f-' + f.k);
    if (el) props[f.k] = el.value;
  }

  let cascade = [];
  try { cascade = await api('/api/node/' + nodeId + '/cascade'); } catch (e) {}

  let msgH = '确认保存修改？';
  const isImgNode = (SM[type] === 2);
  if (isImgNode) msgH += '<br/><br/>🔄 本节点状态将重置为 1（提示词已就绪，图片将重新生成）';
  if (cascade.length) {
    msgH += '<br/><br/>⚠️ 级联重置: ' + cascade.map(c =>
      `<span class="px-1.5 py-0.5 rounded bg-red-900 text-red-200 text-xs m-0.5">${esc(c.type)}:${esc(c.id)}</span>`
    ).join('');
  }

  if (!await cfShow(msgH)) {
    msgEl.textContent = '已取消';
    msgEl.className = 'text-xs text-gray-500';
    return;
  }

  msgEl.textContent = '保存中...';
  msgEl.className = 'text-xs text-amber-400';

  try {
    const r = await api('/api/node/' + nodeId, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ props }),
    });
    const sr = (r.self_reset || []).length;
    const n = (r.cascade_reset || []).length;
    const parts = [];
    if (sr) parts.push('本节点已重置为待生成');
    if (n) parts.push('重置 ' + n + ' 个下游');
    msgEl.textContent = '✓ 已保存' + (parts.length ? ' (' + parts.join('，') + ')' : '');
    msgEl.className = 'text-xs text-green-400';
    setTimeout(() => {
      loadArtStatus();
    }, 800);
  } catch (e) {
    msgEl.textContent = '✗ ' + e.message;
    msgEl.className = 'text-xs text-red-400';
  }
}

/* ═══ Approve / Reject ═══ */
async function doApproveNode(id, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '处理中...'; }
  try {
    await api('/api/approve/node', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: id }),
    });
    if (btn) { btn.textContent = '✓ 已通过'; btn.className = 'flex-1 px-2 py-1.5 rounded text-white text-xs font-medium bg-green-700'; }
    setTimeout(() => { loadArtStatus(); }, 600);
  } catch (e) { if (btn) btn.textContent = '✗ 失败'; }
}

async function doRejectNode(id, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '处理中...'; }
  try {
    await api('/api/reject/node', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: id }),
    });
    if (btn) { btn.textContent = '✗ 已驳回'; btn.className = 'flex-1 px-2 py-1.5 rounded text-white text-xs font-medium bg-red-700'; }
    setTimeout(() => { loadArtStatus(); }, 600);
  } catch (e) { if (btn) btn.textContent = '✗ 失败'; }
}

async function doSyncApprove(fromId, toId, edgeType, btn) {
  btn.disabled = true; btn.textContent = '审批中...'; btn.classList.add('pulse');
  try {
    await api('/api/approve/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_id: fromId, to_id: toId, edge_type: edgeType }),
    });
    btn.classList.remove('pulse');
    btn.textContent = '✓ 已批准';
    btn.className = 'px-3 py-1 rounded text-white text-xs bg-green-700';
    setTimeout(() => { loadArtStatus(); }, 800);
  } catch (e) {
    btn.classList.remove('pulse');
    btn.textContent = '✗ 失败';
    btn.className = 'px-3 py-1 rounded text-white text-xs bg-red-700';
  }
}

/* ═══ Refresh All ═══ */
function refreshAll() {
  const active = localStorage.getItem('activeTab') || 'narrative';
  if (active === 'narrative') initNarrative();
  else if (active === 'art') loadArtStatus();
  else if (active === 'scene') loadSceneList();
}

/* ═══ Boot ═══ */
(async function boot() {
  await loadTaglib();
  await loadArtStatus();   // 启动即预加载美术数据（无论当前 tab）
  const saved = localStorage.getItem('activeTab') || 'narrative';
  switchTab(saved);
})();
