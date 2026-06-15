/* ═══════════════════════════════════════════════════════════════
   tab_narrative.js — 叙事节点 Tab
   ═══════════════════════════════════════════════════════════════ */

/* ═══ 叙事节点 Schema ═══ */
const NAR_NF = {
  Character: {
    l: '角色', i: '👤',
    thead: '<th class="px-3 py-2 text-left">ID</th><th class="px-3 py-2 text-left">姓名</th><th class="px-3 py-2 text-center w-12">性别</th><th class="px-3 py-2 text-left">简介</th><th class="px-3 py-2 text-left">标签</th>',
    f: [
      { k: 'name', l: '姓名' },
      { k: 'gender', l: '性别' },
      { k: 'description', l: '简介', t: 'textarea' },
      { k: 'birth_year', l: '出生年份' },
      { k: 'character_tags', l: '人设标签' },
      { k: 'color_direction', l: '配色逻辑', t: 'textarea' },
    ],
  },
  Event: {
    l: '事件', i: '📅',
    thead: '<th class="px-3 py-2 text-left">ID</th><th class="px-3 py-2 text-left">标题</th><th class="px-3 py-2 text-center w-24">时间</th><th class="px-3 py-2 text-center w-16">类型</th><th class="px-3 py-2 text-left">描述</th>',
    f: [
      { k: 'title', l: '标题' },
      { k: 'time', l: '时间' },
      { k: 'description', l: '描述', t: 'textarea' },
      { k: 'type', l: '类型' },
    ],
  },
  Scene: {
    l: '场景', i: '🏠',
    thead: '<th class="px-3 py-2 text-left">ID</th><th class="px-3 py-2 text-left">名称</th><th class="px-3 py-2 text-left">描述</th>',
    f: [
      { k: 'name', l: '名称' },
      { k: 'description', l: '描述', t: 'textarea' },
    ],
  },
  Info: {
    l: '信息', i: '💡',
    thead: '<th class="px-3 py-2 text-left">ID</th><th class="px-3 py-2 text-left">标题</th><th class="px-3 py-2 text-center w-16">层级</th><th class="px-3 py-2 text-left">内容</th>',
    f: [
      { k: 'title', l: '标题' },
      { k: 'content', l: '内容', t: 'textarea' },
      { k: 'knowledge_level', l: '知识层级' },
    ],
  },
};

/* 边类型中文名 */
const EDGE_CN = {
  relation: '人物关系', involved: '参与事件', occurred_at: '发生地点',
  at: '人物-场景', link: '信息关联', evt_relation: '事件关联',
  has_appearance: '外貌', has_costume: '着装', has_voice_style: '语言风格',
  produces: '产出', outfit_for: '着装服务', wears: '穿着',
  expands_to: '拓展变体', ref_style: '风格参考',
};

let _narLabel = 'Character';

/* ═══ Init ═══ */
async function initNarrative() {
  try {
    // 统计
    const stats = await api('/api/narrative/stats');
    $('ns-chars').textContent = stats.chars || 0;
    $('ns-events').textContent = stats.events || 0;
    $('ns-scenes').textContent = stats.scenes || 0;
    $('ns-infos').textContent = stats.infos || 0;
    const edges = stats.edges || [];
    const totalEdges = edges.reduce((s, e) => s + (e.cnt || 0), 0);
    $('ns-edges').textContent = totalEdges;
    $('err').classList.add('hidden');
  } catch (e) {
    showErr('加载叙事统计失败: ' + e.message);
  }
  // 节点列表
  await loadNarList(_narLabel);
  // 草案
  loadDrafts();
}

/* ═══ Sub-tab switch ═══ */
function switchNarLabel(label) {
  _narLabel = label;
  document.querySelectorAll('.nar-sub-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.label === label);
  });
  loadNarList(label);
}

/* ═══ Node List ═══ */
async function loadNarList(label) {
  const schema = NAR_NF[label];
  $('nar-thead').innerHTML = '<tr class="border-b border-gray-600 text-gray-300">' + schema.thead + '</tr>';
  $('nar-tbody').innerHTML = '<tr><td colspan="10" class="text-center text-gray-500 py-4">加载中...</td></tr>';

  try {
    const data = await api('/api/narrative/list?label=' + label);
    const nodes = data.nodes || [];
    if (!nodes.length) {
      $('nar-tbody').innerHTML = '';
      $('nar-empty').classList.remove('hidden');
      return;
    }
    $('nar-empty').classList.add('hidden');
    $('nar-tbody').innerHTML = nodes.map(n => renderNarRow(n, label)).join('');
  } catch (e) {
    $('nar-tbody').innerHTML = '<tr><td colspan="10" class="text-center text-red-400 py-4">加载失败: ' + esc(e.message) + '</td></tr>';
  }
}

function renderNarRow(n, label) {
  const id = n.id || '';
  const trunc = (s, len) => (!s ? '--' : s.length > len ? esc(s.substring(0, len)) + '...' : esc(s));
  const click = `onclick="openNarrativeNode('${id}','${label}')"`;
  const cls = 'class="px-3 py-2"';
  const tdClick = `class="px-3 py-2 cursor-pointer hover:text-cyan-300" ${click}`;

  if (label === 'Character') {
    return `<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 fade-in">
      <td ${tdClick} style="max-width:120px"><span class="text-xs text-gray-500">${esc(id)}</span></td>
      <td ${tdClick} class="font-medium">${esc(n.name) || '--'}</td>
      <td ${cls} style="text-align:center">${esc(n.gender) || '--'}</td>
      <td ${cls} style="max-width:300px">${trunc(n.description, 60)}</td>
      <td ${cls} style="max-width:150px">${trunc(n.tags, 40)}</td>
    </tr>`;
  }
  if (label === 'Event') {
    return `<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 fade-in">
      <td ${tdClick} style="max-width:120px"><span class="text-xs text-gray-500">${esc(id)}</span></td>
      <td ${tdClick} class="font-medium">${esc(n.title) || '--'}</td>
      <td ${cls} style="text-align:center">${esc(n.time) || '--'}</td>
      <td ${cls} style="text-align:center">${esc(n.type) || '--'}</td>
      <td ${cls} style="max-width:300px">${trunc(n.description, 60)}</td>
    </tr>`;
  }
  if (label === 'Scene') {
    return `<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 fade-in">
      <td ${tdClick} style="max-width:120px"><span class="text-xs text-gray-500">${esc(id)}</span></td>
      <td ${tdClick} class="font-medium">${esc(n.name) || '--'}</td>
      <td ${cls} style="max-width:400px">${trunc(n.description, 80)}</td>
    </tr>`;
  }
  if (label === 'Info') {
    return `<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 fade-in">
      <td ${tdClick} style="max-width:120px"><span class="text-xs text-gray-500">${esc(id)}</span></td>
      <td ${tdClick} class="font-medium">${esc(n.title) || '--'}</td>
      <td ${cls} style="text-align:center">${n.level || '--'}</td>
      <td ${cls} style="max-width:400px">${trunc(n.content, 80)}</td>
    </tr>`;
  }
  return '';
}

/* ═══ Open Narrative Node Detail ═══ */
async function openNarrativeNode(nodeId, label) {
  const schema = NAR_NF[label] || { l: label, i: '📋', f: [] };
  openP(schema.i + ' ' + schema.l + ' · ' + nodeId);

  try {
    // 并行加载节点详情和关系
    const [detail, relData] = await Promise.all([
      api('/api/node/' + nodeId),
      api('/api/narrative/relations?node_id=' + nodeId),
    ]);

    if (detail.error) throw new Error(detail.error);
    renderNarPanel(detail, relData.relations || [], label);
  } catch (e) {
    $('pn-b').innerHTML = '<div class="text-red-400 py-8 text-center">' + esc(e.message) + '</div>';
  }
}

function renderNarPanel(detail, relations, label) {
  const schema = NAR_NF[label] || { l: label, i: '📋', f: [] };
  const props = detail.props || {};
  let h = '<div class="space-y-4">';

  // 节点属性
  h += '<div class="bg-gray-800 rounded-lg border border-gray-700 p-4">';
  h += '<h3 class="text-sm font-semibold text-gray-300 mb-3">' + schema.i + ' ' + esc(schema.l) + ' 属性</h3>';
  for (const f of schema.f) {
    const val = props[f.k] || '';
    if (f.t === 'textarea') {
      h += `<div class="mb-2"><label class="text-xs text-gray-400 block mb-0.5">${esc(f.l)}</label>`;
      h += `<div class="w-full bg-gray-900 border border-gray-600 rounded px-2.5 py-1.5 text-sm text-gray-200 whitespace-pre-wrap">${esc(val) || '<span class="text-gray-600">--</span>'}</div></div>`;
    } else {
      h += `<div class="mb-2"><label class="text-xs text-gray-400 block mb-0.5">${esc(f.l)}</label>`;
      h += `<div class="w-full bg-gray-900 border border-gray-600 rounded px-2.5 py-1.5 text-sm text-gray-200">${esc(val) || '<span class="text-gray-600">--</span>'}</div></div>`;
    }
  }
  h += '</div>';

  // 关系列表
  h += '<div class="bg-gray-800 rounded-lg border border-gray-700 p-4">';
  h += '<h3 class="text-sm font-semibold text-gray-300 mb-3">🔗 关系 (' + relations.length + ')</h3>';
  if (!relations.length) {
    h += '<div class="text-gray-500 text-sm text-center py-3">无关联关系</div>';
  } else {
    h += '<div class="space-y-2">';
    for (const r of relations) {
      const dirIcon = r.direction === 'out' ? '→' : '←';
      const dirColor = r.direction === 'out' ? 'text-cyan-400' : 'text-amber-400';
      const edgeName = EDGE_CN[r.rel_type] || r.rel_type;
      const labelColor = nodeLabelColor(r.target_label);
      h += `<div class="flex items-center gap-2 text-sm py-1 px-2 rounded hover:bg-gray-700/30">`;
      h += `<span class="${dirColor} font-bold">${dirIcon}</span>`;
      h += `<span class="px-1.5 py-0.5 rounded text-xs bg-gray-700 text-gray-300">${esc(edgeName)}</span>`;
      h += `<span class="px-1.5 py-0.5 rounded text-xs ${labelColor}">${esc(r.target_label)}</span>`;
      h += `<span class="text-gray-200 cursor-pointer hover:text-cyan-300" onclick="closeP();setTimeout(()=>openNarrativeNode('${r.target_id}','${r.target_label}'),100)">${esc(r.target_name)}</span>`;
      // 显示边的 detail 属性
      const rp = r.rel_props || {};
      if (rp.detail) h += `<span class="text-xs text-gray-500 ml-auto">${esc(rp.detail).substring(0, 30)}</span>`;
      if (rp.sync !== undefined && rp.sync !== null) h += `<span class="text-xs ${rp.sync ? 'text-green-400' : 'text-red-400'} ml-1">sync=${rp.sync}</span>`;
      h += '</div>';
    }
    h += '</div>';
  }
  h += '</div>';
  h += '</div>';

  $('pn-b').innerHTML = h;
}

function nodeLabelColor(label) {
  const colors = {
    Character: 'bg-cyan-900 text-cyan-200',
    Event: 'bg-amber-900 text-amber-200',
    Scene: 'bg-emerald-900 text-emerald-200',
    Info: 'bg-purple-900 text-purple-200',
    AppearanceStyle: 'bg-pink-900 text-pink-200',
    CostumeStyle: 'bg-violet-900 text-violet-200',
    LanguageStyle: 'bg-blue-900 text-blue-200',
    DesignSheet: 'bg-teal-900 text-teal-200',
    IllusDesign: 'bg-orange-900 text-orange-200',
    StandingIllustration: 'bg-rose-900 text-rose-200',
  };
  return colors[label] || 'bg-gray-700 text-gray-300';
}

/* ═══ Draft Management ═══ */
async function loadDrafts() {
  try {
    const d = await api('/api/drafts');
    if (d.error) throw new Error(d.error);
    const drafts = d.drafts || [];
    const pending = drafts.filter(x => x.status === 'pending').length;
    $('ns-drafts').textContent = pending;
    rDrafts(drafts);
  } catch (e) {
    if ($('ns-drafts')) $('ns-drafts').textContent = '?';
  }
}

function rDrafts(drafts) {
  const el = $('draft-list');
  const e = $('draft-e');
  if (!el) return;
  if (!drafts.length) { el.innerHTML = ''; e.classList.remove('hidden'); return; }
  e.classList.add('hidden');
  el.innerHTML = drafts.map(d => {
    const pCls = d.priority === 'high' ? 'bg-red-900 text-red-200' : d.priority === 'medium' ? 'bg-amber-900 text-amber-200' : 'bg-green-900 text-green-200';
    const pTxt = d.priority === 'high' ? '🔴 高' : d.priority === 'medium' ? '🟡 中' : '🟢 低';
    const sCls = d.status === 'pending' ? 'bg-cyan-800 text-cyan-200' : d.status === 'approved' ? 'bg-green-700 text-green-100' : d.status === 'rejected' ? 'bg-red-800 text-red-200' : d.status === 'applied' ? 'bg-gray-600 text-gray-300' : 'bg-gray-700 text-gray-400';
    const sTxt = d.status === 'pending' ? '⏳ 待审批' : d.status === 'approved' ? '✓ 已批准' : d.status === 'rejected' ? '✗ 已驳回' : d.status === 'applied' ? '✓✓✓ 已导入' : d.status;
    let actH = '';
    if (d.status === 'pending') {
      actH = `<button onclick="doDraftAction('${d.filename}','approve',this)" class="px-3 py-1 bg-green-800 hover:bg-green-700 rounded text-white text-xs">✓ 批准</button>`;
      actH += `<button onclick="doDraftAction('${d.filename}','reject',this)" class="px-3 py-1 bg-red-800 hover:bg-red-700 rounded text-white text-xs ml-1">✗ 驳回</button>`;
    } else if (d.status === 'approved') {
      const applyCmd = `/nrt-narrative-grower apply --draft ${d.path.replace(/\\\\/g, '/')}`;
      actH = `<span class="text-xs text-gray-400 mr-2">待导入：</span>`;
      actH += `<code class="text-xs bg-gray-900 px-2 py-1 rounded border border-gray-600 select-all cursor-pointer" title="点击复制" onclick="navigator.clipboard.writeText(this.textContent)">${esc(applyCmd)}</code>`;
    }
    const typeTag = d.opportunity_type ? `<span class="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-400 ml-2">${esc(d.opportunity_type)}</span>` : '';
    return `<div class="bg-gray-750 rounded-lg border border-gray-700 p-4 mb-3 flex items-start gap-4 fade-in" style="background:#252a3a">
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <span class="font-semibold text-gray-200">${esc(d.title)}</span>
          <span class="px-1.5 py-0.5 rounded text-xs ${pCls}">${pTxt}</span>
          <span class="px-1.5 py-0.5 rounded text-xs ${sCls}">${sTxt}</span>
          ${typeTag}
        </div>
        <div class="text-xs text-gray-500">${d.draft_id} · ${d.created_at || ''}</div>
      </div>
      <div class="flex items-center gap-2 flex-shrink-0">
        <button onclick="openDraft('${d.filename}')" class="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-gray-200 text-xs">📖 阅读</button>
        ${actH}
      </div>
    </div>`;
  }).join('');
}

async function openDraft(filename) {
  openP('📖 叙事草案 · ' + filename);
  try {
    const d = await api('/api/drafts/' + encodeURIComponent(filename.replace('.md', '')));
    if (d.error) throw new Error(d.error);
    let body = d.content || '';
    if (body.startsWith('---')) { const end = body.indexOf('---', 3); if (end !== -1) body = body.substring(end + 3); }
    body = body.trim();
    // Simple markdown → HTML
    body = body.replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold text-amber-200 mt-4 mb-1">$1</h3>');
    body = body.replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold text-amber-300 mt-5 mb-2 pb-1 border-b border-gray-700">$1</h2>');
    body = body.replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-cyan-300 mb-3">$1</h1>');
    body = body.replace(/^> (.+)$/gm, '<blockquote class="border-l-2 border-cyan-600 pl-3 my-2 text-gray-300 text-sm">$1</blockquote>');
    body = body.replace(/^\|(.+)\|$/gm, (m) => '<tr>' + m.split('|').slice(1, -1).map(c => '<td class="px-2 py-1 border border-gray-700 text-sm">' + c.trim() + '</td>').join('') + '</tr>');
    body = body.replace(/(<tr>.*<\/tr>\n?)+/g, (m) => '<table class="w-full text-sm my-2 border-collapse">' + m + '</table>');
    const lines = body.split('\n');
    let out = '';
    for (const line of lines) {
      if (line.startsWith('<h') || line.startsWith('<blockquote') || line.startsWith('<table') || line.startsWith('<tr') || line.trim() === '') { out += line + '\n'; continue; }
      out += `<p class="text-sm text-gray-300 my-1">${line}</p>\n`;
    }
    let html = '<div class="prose prose-invert max-w-none">' + out + '</div>';
    const fm = d.frontmatter || {};
    if (fm.status === 'pending') {
      html += `<div class="mt-4 pt-3 border-t border-gray-700 flex gap-2">`;
      html += `<button onclick="doDraftAction('${d.filename}','approve',this);closeP();setTimeout(()=>{loadDrafts()},500)" class="px-4 py-1.5 bg-green-800 hover:bg-green-700 rounded text-white text-sm font-medium">✓ 批准</button>`;
      html += `<button onclick="doDraftAction('${d.filename}','reject',this);closeP();setTimeout(()=>{loadDrafts()},500)" class="px-4 py-1.5 bg-red-800 hover:bg-red-700 rounded text-white text-sm font-medium">✗ 驳回</button>`;
      html += '</div>';
    } else if (fm.status === 'approved') {
      const applyCmd = `/nrt-narrative-grower apply --draft ${d.path.replace(/\\\\/g, '/')}`;
      html += `<div class="mt-4 pt-3 border-t border-gray-700">`;
      html += `<div class="text-xs text-gray-400 mb-2">导入命令（在 Claude Code 中执行）：</div>`;
      html += `<code class="block text-xs bg-gray-900 px-3 py-2 rounded border border-gray-600 select-all cursor-pointer" onclick="navigator.clipboard.writeText(this.textContent)">${esc(applyCmd)}</code>`;
      html += '</div>';
    }
    $('pn-b').innerHTML = html;
  } catch (e) {
    $('pn-b').innerHTML = '<div class="text-red-400 py-8 text-center">' + esc(e.message) + '</div>';
  }
}

async function doDraftAction(filename, action, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '处理中...'; }
  try {
    const r = await api('/api/drafts/' + encodeURIComponent(filename.replace('.md', '')) + '/' + action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    if (r.error) throw new Error(r.error);
    if (btn) {
      btn.textContent = action === 'approve' ? '✓ 已批准' : '✗ 已驳回';
      btn.className = 'px-3 py-1 rounded text-white text-xs ' + (action === 'approve' ? 'bg-green-700' : 'bg-red-700');
    }
    setTimeout(() => { loadDrafts(); initNarrative(); }, 500);
  } catch (e) {
    if (btn) { btn.textContent = '✗ 失败'; btn.className = 'px-3 py-1 rounded text-white text-xs bg-red-700'; }
  }
}
