/* ═══════════════════════════════════════════════════════════════
   tab_art.js — 角色美术 Tab
   ═══════════════════════════════════════════════════════════════ */

/* ═══ Node Schemas ═══ */
const NF = {
  AppearanceStyle: { l: '外貌特征', i: '👤', f: [
    { k: 'appearance', l: '外貌描述(综合气质)', t: 'textarea' },
    { k: 'shape_language', l: '形状语言', t: 'tags' },
    { k: 'age_impression', l: '年龄感', t: 'tags' },
    { k: 'body_type', l: '体态', t: 'tags' },
    { k: 'skin_tone', l: '肤色', t: 'tags' },
    { k: 'ethnicity', l: '面孔/人种', t: 'tags' },
    { k: 'hair', l: '头发', t: 'tags' },
    { k: 'eye', l: '眼睛', t: 'tags' },
    { k: 'lip_shape', l: '唇形', t: 'tags' },
    { k: 'marks', l: '特殊标记', t: 'tags' },
    { k: 'visual_tone', l: '视觉气质' },
    { k: 'first_impression', l: '第一印象' },
  ]},
  CostumeStyle: { l: '着装特征', i: '👔', f: [
    { k: 'name', l: '名称' },
    { k: 'outfit_style', l: '着装风格', t: 'tags' },
    { k: 'garment', l: '服装', t: 'tags' },
    { k: 'footwear', l: '鞋类', t: 'tags' },
    { k: 'accessory_type', l: '配饰类型', t: 'tags' },
  ]},
  LanguageStyle: { l: '语言风格', i: '🗣️', f: [
    { k: 'description', l: '语言风格描述', t: 'textarea' },
  ]},
  DesignSheet: { l: '设计图', i: '📐', f: [
    { k: 'prompt_path', l: '提示词文件' },
    { k: 'image_path', l: '图片路径', t: 'image' },
  ]},
  IllusDesign: { l: '立绘设计图', i: '🎨', f: [
    { k: 'adaptation_notes', l: '着装补充说明', t: 'textarea' },
    { k: 'prompt_path', l: '提示词文件' },
    { k: 'image_path', l: '图片路径', t: 'image' },
  ]},
  StandingIllustration: { l: '立绘', i: '🖼️', f: [
    { k: 'variant_label', l: '变体', t: 'tags' },
    { k: 'eye', l: '眼部', t: 'tags' },
    { k: 'brow', l: '眉毛', t: 'tags' },
    { k: 'mouth', l: '嘴部', t: 'tags' },
    { k: 'head_angle', l: '头部角度', t: 'tags' },
    { k: 'hand', l: '手部动作', t: 'tags' },
    { k: 'foot', l: '脚部动作', t: 'tags' },
    { k: 'prompt_path', l: '提示词文件' },
    { k: 'image_path', l: '图片路径', t: 'image' },
  ]},
};

/* status config */
const SM = { AppearanceStyle: 1, CostumeStyle: 1, LanguageStyle: 1, DesignSheet: 2, IllusDesign: 2, StandingIllustration: 2 };
const SL = { 0: '待处理', 1: '属性已填', 2: '图片已生成' };
const SC = { 0: 'bg-yellow-800 text-yellow-200', 1: 'bg-blue-800 text-blue-200', 2: 'bg-green-800 text-green-200' };

/* ═══ Tag Selector (设计元素标签选择组件) ═══ */
let _COMBO = {};  // 复合字段子维度选中 {fieldKey: {groupKey: [values]}}
let NODE_GENDER = {};  // nodeId → "男"/"女"，编辑节点时取性别化候选用
let CUR_GENDER = '';   // 当前打开节点所属角色性别
function _dim(nodeType, k) { return (TAGLIB[nodeType] || {})[k] || {}; }
// 按 gender 合并候选：公共 options + 对应性别追加（简单维度顶层 / 复合维度 group 结构一致）
function _gOpts(dimOrGroup, gender) {
  const o = dimOrGroup.options || [];
  const extra = gender === '女' ? (dimOrGroup.female || [])
             : gender === '男' ? (dimOrGroup.male   || [])
             : [];
  return o.concat(extra);
}
function _isCombo(nodeType, k) { return !!_dim(nodeType, k).groups; }

// 从已有组合值反推子维度选中（打开节点时高亮子维度）
function _comboFromVal(nodeType, k, combos) {
  const groups = _dim(nodeType, k).groups;
  const res = {};
  for (const g of groups) res[g.key] = [];
  for (const g of groups) {
    for (const opt of _gOpts(g, CUR_GENDER)) {
      if (combos.some(c => c.includes(opt)) && !res[g.key].includes(opt)) res[g.key].push(opt);
    }
  }
  return res;
}
// 根据子维度选中合成组合 tag（单个字符串）；不可合成返回 null
function _combine(nodeType, k) {
  const dim = _dim(nodeType, k);
  const groups = dim.groups;
  const sel = _COMBO[k] || {};
  if ((dim.combine || 'stack') === 'pair') {
    for (const g of groups) if ((sel[g.key] || []).length > 1) return null; // 配对型：每组≤1
  }
  const parts = []; let used = 0;
  for (const g of groups) {
    const vals = sel[g.key] || [];
    if (!vals.length) continue;
    used++;
    parts.push(vals.map(v => v + (g.suffix || '')).join(''));
  }
  return used >= 2 ? parts.join('') : null;
}

function renderTagField(nodeType, f, val) {
  return _isCombo(nodeType, f.k) ? _renderComboField(nodeType, f, val) : _renderSimpleField(nodeType, f, val);
}

// 简单字段（单/多维度，扁平分号存）
function _renderSimpleField(nodeType, f, val) {
  const dim = _dim(nodeType, f.k);
  const groups = dim.groups || [{ key: f.k, label: dim.label || f.l, multi: dim.multi, options: _gOpts(dim, CUR_GENDER) }];
  const sel = val ? String(val).split(';').map(s => s.trim()).filter(Boolean) : [];
  const multiGroup = groups.length > 1;
  let h = `<div><label class="text-xs text-gray-400 block mb-1">${esc(f.l)}</label>`;
  h += `<input id="f-${f.k}" type="hidden" value="${escA(sel.join(';'))}" />`;
  h += `<div id="tags-${f.k}" class="space-y-1.5">`;
  const known = new Set();
  for (const g of groups) {
    if (multiGroup) h += `<div class="text-xs text-gray-500">${esc(g.label)}${g.multi ? ' (可多选)' : ' (单选)'}</div>`;
    h += `<div class="flex flex-wrap gap-1.5">`;
    for (const opt of _gOpts(g, CUR_GENDER)) {
      known.add(opt);
      const on = sel.includes(opt);
      h += `<button type="button" data-tag="${escA(opt)}" data-group="${escA(g.key)}" data-multi="${g.multi ? 1 : 0}" onclick="toggleTag('${f.k}',this)" class="tag-chip px-2 py-0.5 rounded text-xs border ${on ? 'bg-amber-700 border-amber-500 text-white' : 'bg-gray-800 border-gray-600 text-gray-300 hover:border-amber-500'}">${esc(opt)}</button>`;
    }
    h += `</div>`;
  }
  h += `</div>`;
  h += `<div class="text-xs text-gray-500 mt-2">已选标签 <span class="text-gray-600">(点击候选加入此处，存入字段)</span></div>`;
  h += `<div id="sel-out-${f.k}" class="flex flex-wrap gap-1.5">${_selOutHTML(f.k, sel)}</div>`;
  h += `<div class="flex gap-1 mt-1.5"><input id="tagin-${f.k}" type="text" placeholder="+ 自定义标签" class="flex-1 bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-amber-500 focus:outline-none" onkeydown="if(event.key==='Enter'){event.preventDefault();addCustomTag('${f.k}',this.value);this.value='';}" /><button type="button" onclick="addCustomTag('${f.k}',document.getElementById('tagin-${f.k}').value);document.getElementById('tagin-${f.k}').value='';" class="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-200">添加</button></div>`;
  h += `</div>`;
  return h;
}

// 复合字段（子维度选择 → 合成组合存入字段，子维度不散存）
function _renderComboField(nodeType, f, val) {
  const groups = _dim(nodeType, f.k).groups;
  const combos = val ? String(val).split(';').map(s => s.trim()).filter(Boolean) : [];
  _COMBO[f.k] = _comboFromVal(nodeType, f.k, combos);
  let h = `<div><label class="text-xs text-gray-400 block mb-1">${esc(f.l)} <span class="text-gray-600">(选子维度自动合成组合)</span></label>`;
  h += `<input id="f-${f.k}" type="hidden" value="${escA(combos.join(';'))}" />`;
  h += `<div id="tags-${f.k}" class="space-y-1.5">`;
  for (const g of groups) {
    h += `<div class="text-xs text-gray-500">${esc(g.label)}${g.multi ? ' (可多选)' : ' (单选)'}</div>`;
    h += `<div class="flex flex-wrap gap-1.5">`;
    const picked = _COMBO[f.k][g.key] || [];
    for (const opt of _gOpts(g, CUR_GENDER)) {
      const on = picked.includes(opt);
      h += `<button type="button" data-tag="${escA(opt)}" data-group="${escA(g.key)}" data-multi="${g.multi ? 1 : 0}" onclick="toggleCombo('${f.k}','${nodeType}',this)" class="tag-chip px-2 py-0.5 rounded text-xs border ${on ? 'bg-amber-700 border-amber-500 text-white' : 'bg-gray-800 border-gray-600 text-gray-300 hover:border-amber-500'}">${esc(opt)}</button>`;
    }
    h += `</div>`;
  }
  h += `</div>`;
  h += `<div class="text-xs text-gray-500 mt-2">合成组合 <span class="text-gray-600">(存入字段)</span> <span id="combo-hint-${f.k}" class="text-gray-600"></span></div>`;
  h += `<div id="combo-out-${f.k}" class="flex flex-wrap gap-1.5">${_comboOutHTML(f.k, combos)}</div>`;
  h += `<div class="flex gap-1 mt-1.5"><input id="tagin-${f.k}" type="text" placeholder="+ 手动添加组合(如 棉衬衫)" class="flex-1 bg-gray-900 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:border-amber-500 focus:outline-none" onkeydown="if(event.key==='Enter'){event.preventDefault();addCustomCombo('${f.k}',this.value);this.value='';}" /><button type="button" onclick="addCustomCombo('${f.k}',document.getElementById('tagin-${f.k}').value);document.getElementById('tagin-${f.k}').value='';" class="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-200">添加</button></div>`;
  h += `</div>`;
  return h;
}
function _comboOutHTML(k, combos) {
  return combos.map(c => `<button type="button" onclick="removeCombo('${k}',this)" data-combo="${escA(c)}" class="tag-chip px-2 py-0.5 rounded text-xs border bg-green-800 border-green-600 text-white">${esc(c)} ✕</button>`).join('');
}

function _tagSel(k) { const el = $('f-' + k); return el && el.value ? el.value.split(';').map(s => s.trim()).filter(Boolean) : []; }
function _tagSet(k, arr) { const el = $('f-' + k); if (el) el.value = arr.join(';'); }
function _chipOn(b) { b.classList.remove('bg-gray-800','border-gray-600','text-gray-300'); b.classList.add('bg-amber-700','border-amber-500','text-white'); }
function _chipOff(b) { b.classList.add('bg-gray-800','border-gray-600','text-gray-300'); b.classList.remove('bg-amber-700','border-amber-500','text-white'); }
function _selOutHTML(k, sel) {
  return sel.map(s => `<button type="button" onclick="removeSel('${k}',this)" data-v="${escA(s)}" class="tag-chip px-2 py-0.5 rounded text-xs border bg-green-800 border-green-600 text-white">${esc(s)} ✕</button>`).join('');
}
function _renderSelOut(k) { const el = $('sel-out-' + k); if (el) el.innerHTML = _selOutHTML(k, _tagSel(k)); }
function removeSel(k, btn) {
  const v = btn.dataset.v;
  _tagSet(k, _tagSel(k).filter(x => x !== v));
  _renderSelOut(k);
  const sel = _tagSel(k);
  document.querySelectorAll('#tags-' + k + ' .tag-chip').forEach(c => { if (sel.includes(c.dataset.tag)) _chipOn(c); else _chipOff(c); });
}

// 简单字段 toggle
function toggleTag(k, btn) {
  const group = btn.dataset.group;
  const multi = btn.dataset.multi !== '0';
  const tag = btn.dataset.tag;
  let sel = _tagSel(k);
  if (sel.includes(tag)) { sel = sel.filter(t => t !== tag); _chipOff(btn); }
  else {
    if (!multi) {
      document.querySelectorAll('#tags-' + k + ' .tag-chip[data-group="' + group + '"]').forEach(c => {
        const ct = c.dataset.tag;
        if (ct !== tag && sel.includes(ct)) { sel = sel.filter(t => t !== ct); _chipOff(c); }
      });
    }
    sel.push(tag);
    _chipOn(btn);
  }
  _tagSet(k, sel);
  _renderSelOut(k);
}
function addCustomTag(k, val) {
  val = (val || '').trim();
  if (!val) return;
  let sel = _tagSel(k);
  if (sel.includes(val)) return;
  sel.push(val);
  _tagSet(k, sel);
  _renderSelOut(k);
}

// 复合字段 toggle：更新子维度选中 → 重算组合 → 更新字段值与组合区
function toggleCombo(k, nodeType, btn) {
  const group = btn.dataset.group;
  const multi = btn.dataset.multi !== '0';
  const tag = btn.dataset.tag;
  let arr = ((_COMBO[k] || {})[group] || []).slice();
  if (arr.includes(tag)) {
    arr = arr.filter(t => t !== tag);
    _chipOff(btn);
  } else {
    if (!multi) {
      document.querySelectorAll('#tags-' + k + ' .tag-chip[data-group="' + group + '"]').forEach(c => _chipOff(c));
      arr = [tag];
    } else {
      arr.push(tag);
    }
    _chipOn(btn);
  }
  _COMBO[k][group] = arr;
  _recomputeCombo(k, nodeType);
}
function _recomputeCombo(k, nodeType) {
  const combo = _combine(nodeType, k);
  const out = $('combo-out-' + k);
  const hint = $('combo-hint-' + k);
  if (combo) {
    _tagSet(k, [combo]);
    if (out) out.innerHTML = _comboOutHTML(k, [combo]);
    if (hint) hint.textContent = '';
  } else if (hint) {
    hint.textContent = '— 子维度未形成有效组合（配对型需每组≤1个），可手动添加';
  }
}
function removeCombo(k, btn) {
  const c = btn.dataset.combo;
  _tagSet(k, _tagSel(k).filter(x => x !== c));
  btn.remove();
}
function addCustomCombo(k, val) {
  val = (val || '').trim();
  if (!val) return;
  let sel = _tagSel(k);
  if (sel.includes(val)) return;
  sel.push(val);
  _tagSet(k, sel);
  const out = $('combo-out-' + k);
  if (out) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.setAttribute('data-combo', val);
    btn.setAttribute('onclick', "removeCombo('" + k + "',this)");
    btn.className = 'tag-chip px-2 py-0.5 rounded text-xs border bg-green-800 border-green-600 text-white';
    btn.textContent = val + ' ✕';
    out.appendChild(btn);
  }
}

/* ═══ Load ═══ */
// 建立 nodeId → gender 映射（appearance/language/design/costume/illus/stand 全覆盖）
function _buildNodeGender(chars) {
  NODE_GENDER = {};
  for (const c of chars) {
    const g = c.char_gender;
    if (!g) continue;
    for (const id of [c.appearance_id, c.language_id, c.design_id]) if (id) NODE_GENDER[id] = g;
    for (const co of (c.costumes || [])) if (co.id) NODE_GENDER[co.id] = g;
    for (const il of (c.illus || [])) if (il.id) NODE_GENDER[il.id] = g;
    for (const s of (c.stands || [])) if (s.id) NODE_GENDER[s.id] = g;
  }
}

async function loadArtStatus() {
  try {
    const d = await api('/api/status');
    if (d.error) throw new Error(d.error);
    $('s-t').textContent = d.total;
    $('s-d').textContent = d.completed;
    $('s-todo').textContent = d.todos.length;
    $('s-ia').textContent = d.image_approvals.length;
    $('s-sa').textContent = d.sync_approvals.length;
    $('s-ca').textContent = (d.costume_approvals || []).length;
    _buildNodeGender(d.characters);
    rOv(d.characters);
    rTodo(d.todos);
    rCA(d.costume_approvals || []);
    rIA(d.image_approvals);
    rSA(d.sync_approvals);
    $('ts').textContent = d.timestamp;
    $('err').classList.add('hidden');
  } catch (e) {
    showErr('加载角色美术状态失败: ' + e.message);
  }
}

/* ═══ Overview ═══ */
function rOv(chars) {
  $('art-ov').innerHTML = chars.map(c => {
    const imgH = c.design_image
      ? `<img src="/file/${enc(c.design_image)}" class="h-20 rounded border border-gray-600 object-contain bg-gray-900 cursor-pointer" onclick="event.stopPropagation();openArtNode('${c.design_id}','DesignSheet')" onerror="this.style.display='none';this.nextElementSibling.style.display=''" /><div style="display:none" class="text-xs text-gray-600 italic">${esc(c.design_image)}</div>`
      : '<span class="text-gray-600 text-xs">--</span>';
    return `<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 fade-in">
      <td class="px-3 py-2"><div class="font-medium">${esc(c.char_name)}</div><div class="text-xs text-gray-500">${c.char_id}</div></td>
      <td class="px-3 py-2 text-center">${dataBadge(c.appearance_status, 1, c.appearance_id, 'AppearanceStyle')}</td>
      <td class="px-3 py-2 text-center"><div class="flex flex-wrap gap-1 justify-center items-center">${rCostumes(c.costumes)}<button type="button" onclick="addCostume('${c.char_id}','${escA(c.char_name)}')" class="text-xs text-gray-500 hover:text-amber-400 hover:ring-1 hover:ring-amber-400 px-1.5 py-0.5 rounded border border-gray-700" title="为该角色添加一套着装">＋</button></div></td>
      <td class="px-3 py-2 text-center">${dataBadge(c.language_status, 1, c.language_id, 'LanguageStyle')}</td>
      <td class="px-3 py-2 text-center">${imgBadge(c.design_status, 2, c.design_id, 'DesignSheet')}</td>
      <td class="px-3 py-2 text-center">${imgH}</td>
      <td class="px-3 py-2 text-center">${rIllus(c.illus || [])}</td>
      <td class="px-3 py-2 text-center">${rStands(c.stands || [])}</td>
    </tr>`;
  }).join('');
}

function dataBadge(s, max, id, type) {
  if (!id) return '<span class="text-gray-600 text-xs">--</span>';
  const cls = s === null || s === undefined ? 'bg-gray-600 text-gray-300' : s >= max ? 'bg-green-800 text-green-200' : 'bg-yellow-800 text-yellow-200';
  const txt = s === null || s === undefined ? '--' : s >= max ? '✓' : s;
  return `<span class="cursor-pointer px-1.5 py-0.5 rounded text-xs ${cls} hover:ring-1 hover:ring-amber-400" onclick="event.stopPropagation();openArtNode('${id}','${type}')">${txt}</span>`;
}

function imgBadge(s, max, id, type) {
  if (!id) return '<span class="text-gray-600 text-xs">--</span>';
  let cls, txt;
  if (s === null || s === undefined) { cls = 'bg-gray-600 text-gray-300'; txt = '--'; }
  else if (s === 11) { cls = 'bg-green-700 text-green-100'; txt = '✓✓✓'; }
  else if (s === 10) { cls = 'bg-amber-800 text-amber-200'; txt = '⏳'; }
  else if (s === max) { cls = 'bg-green-800 text-green-200'; txt = '✓'; }
  else { cls = SC[s] || 'bg-gray-600 text-gray-300'; txt = String(s); }
  return `<span class="cursor-pointer px-1.5 py-0.5 rounded text-xs ${cls} hover:ring-1 hover:ring-amber-400" onclick="event.stopPropagation();openArtNode('${id}','${type}')">${txt}</span>`;
}

function rIllus(a) { return a.length ? a.map(i => imgBadge(i.status, 2, i.id, 'IllusDesign')).join(' ') : '<span class="text-gray-600 text-xs">--</span>'; }
function rStands(a) { return a.length ? a.map(s => imgBadge(s.status, 2, s.id, 'StandingIllustration')).join(' ') : '<span class="text-gray-600 text-xs">--</span>'; }

/* 着装：每套独立徽章，可分别点击编辑 */
function rCostumes(a) {
  if (!a || !a.length) return dataBadge(null, 1);
  const multi = a.length > 1;
  return a.map((co, idx) => {
    const s = co.status, tag = multi ? String(idx + 1) : '';
    let cls, txt;
    if (s === 10) { cls = 'bg-amber-800 text-amber-200'; txt = tag + '⏳'; }
    else if (s === 11) { cls = 'bg-green-700 text-green-100'; txt = '✓' + tag; }
    else if (s !== null && s !== undefined && s >= 1) { cls = 'bg-green-800 text-green-200'; txt = '✓' + tag; }
    else { cls = 'bg-yellow-800 text-yellow-200'; txt = tag || '0'; }
    const hint = co.name ? ` title="${escA(co.name)}"` : '';
    return `<span${hint} class="cursor-pointer inline-block px-1.5 py-0.5 rounded text-xs ${cls} hover:ring-1 hover:ring-amber-400" onclick="event.stopPropagation();openArtNode('${co.id}','CostumeStyle')">${txt}</span>`;
  }).join(' ');
}

/* 添加着装：输入思路 → deeplink 触发 char-costume-designer */
function addCostume(charId, charName) {
  showInputIdea('添加着装 · ' + charName, '描述这套着装的基本思路，确认后启动 char-costume-designer skill（Ctrl+Enter 提交）', (idea) => {
    if (!idea) return;
    const p = `使用 char-costume-designer 为角色 ${charId} 新增一套着装。着装思路：${idea}`;
    const uri = 'vscode://anthropic.claude-code/open?prompt=' + encodeURIComponent(p);
    const a = document.createElement('a'); a.href = uri; a.click();
  });
}

/* ═══ TODOs ═══ */
function rTodo(todos) {
  const tb = $('art-todo'), e = $('art-todo-e');
  if (!todos.length) { tb.innerHTML = ''; e.classList.remove('hidden'); return; }
  e.classList.add('hidden');
  tb.innerHTML = todos.map(t => {
    const stH = t.status === 'missing'
      ? '<span class="px-2 py-0.5 rounded text-xs bg-gray-600 text-gray-300">未创建</span>'
      : `<span class="px-2 py-0.5 rounded text-xs ${SC[t.status] || ''}">${t.status}</span>`;
    let actH;
    if (t.action === 'approve') {
      actH = '<span class="text-amber-300">待审批</span>';
    } else {
      const uri = 'vscode://anthropic.claude-code/open?prompt=' + encodeURIComponent(t.prompt);
      actH = `<a href="${uri}" class="inline-block px-3 py-1 bg-blue-700 hover:bg-blue-600 rounded text-white text-xs whitespace-nowrap">▶ 启动</a>`;
    }
    return `<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 fade-in">
      <td class="px-3 py-2"><div class="font-medium">${esc(t.char_name)}</div><div class="text-xs text-gray-500">${t.char_id}</div></td>
      <td class="px-3 py-2">${esc(t.node_type_cn)}</td>
      <td class="px-3 py-2 text-center">${stH}</td>
      <td class="px-3 py-2">${esc(t.action_cn)}</td>
      <td class="px-3 py-2 text-center">${actH}</td>
    </tr>`;
  }).join('');
}

/* ═══ Costume Approvals ═══ */
function rCA(list) {
  const el = $('art-ca-list'), e = $('art-ca-e');
  if (!list.length) { el.innerHTML = ''; e.classList.remove('hidden'); return; }
  e.classList.add('hidden');
  el.innerHTML = list.map(a => `<div class="bg-gray-750 rounded-lg border border-purple-900/50 p-4 mb-3" style="background:#252a3a">
    <div class="flex items-start justify-between">
      <div>
        <div class="font-medium text-purple-200">${esc(a.costume_name)}</div>
        <div class="text-xs text-gray-400 mt-1">${esc(a.char_name)} (${a.char_id})</div>
        ${a.outfit ? `<div class="text-sm text-gray-300 mt-2">${esc(a.outfit)}</div>` : ''}
        ${a.accessories ? `<div class="text-xs text-gray-400 mt-1">配饰: ${esc(a.accessories)}</div>` : ''}
      </div>
      <div class="flex gap-2 ml-4 shrink-0">
        <button onclick="doApproveNode('${a.costume_id}',this)" class="px-3 py-1.5 bg-green-800 hover:bg-green-700 rounded text-white text-xs font-medium">✓ 通过</button>
        <button onclick="doRejectNode('${a.costume_id}',this)" class="px-3 py-1.5 bg-red-800 hover:bg-red-700 rounded text-white text-xs font-medium">✗ 驳回</button>
      </div>
    </div>
  </div>`).join('');
}

/* ═══ Image Approvals ═══ */
function rIA(list) {
  const el = $('art-ia-list'), e = $('art-ia-e');
  if (!list.length) { el.innerHTML = ''; e.classList.remove('hidden'); return; }
  e.classList.add('hidden');
  el.innerHTML = '<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">' + list.map(a => {
    const imgH = a.image_path ? `<img src="/file/${enc(a.image_path)}" class="w-full rounded border border-gray-600 object-contain bg-gray-900 max-h-48" onerror="this.style.display='none'"/>` : '';
    return `<div class="bg-gray-750 rounded-lg border border-gray-700 p-3" style="background:#252a3a">
      <div class="text-xs text-gray-400 mb-2">${a.type}: ${a.id}</div>
      ${imgH}
      <div class="flex gap-2 mt-3">
        <button onclick="doApproveNode('${a.id}',this)" class="flex-1 px-2 py-1.5 bg-green-800 hover:bg-green-700 rounded text-white text-xs font-medium">✓ 通过</button>
        <button onclick="doRejectNode('${a.id}',this)" class="flex-1 px-2 py-1.5 bg-red-800 hover:bg-red-700 rounded text-white text-xs font-medium">✗ 驳回</button>
      </div>
    </div>`;
  }).join('') + '</div>';
}

/* ═══ Sync Approvals ═══ */
function rSA(list) {
  const tb = $('art-sa'), e = $('art-sa-e');
  if (!list.length) { tb.innerHTML = ''; e.classList.remove('hidden'); return; }
  e.classList.add('hidden');
  tb.innerHTML = list.map(a => `<tr class="border-b border-gray-700/50">
    <td class="px-3 py-2"><div class="font-medium">${esc(a.from_name)}</div><div class="text-xs text-gray-500">${a.from_label}: ${a.from_id}</div></td>
    <td class="px-3 py-2 text-center"><span class="px-2 py-0.5 rounded text-xs bg-amber-900 text-amber-200">${a.edge_type}</span></td>
    <td class="px-3 py-2 text-xs text-gray-400">${a.to_id}</td>
    <td class="px-3 py-2 text-center"><button onclick="doSyncApprove('${a.from_id}','${a.to_id}','${a.edge_type}',this)" class="px-3 py-1 bg-amber-700 hover:bg-amber-600 rounded text-white text-xs">✓ 批准</button></td>
  </tr>`).join('');
}

/* ═══ Open Art Node Detail ═══ */
async function openArtNode(nodeId, nodeType) {
  CUR_GENDER = NODE_GENDER[nodeId] || '';
  const schema = NF[nodeType] || { l: nodeType, i: '📋', f: [] };
  openP(schema.i + ' ' + schema.l + ' · ' + nodeId);

  try {
    const d = await api('/api/node/' + nodeId);
    if (d.error) throw new Error(d.error);
    rArtPanel(d, nodeType);
  } catch (e) {
    $('pn-b').innerHTML = '<div class="text-red-400 py-8 text-center">' + esc(e.message) + '</div>';
  }
}

function rArtPanel(detail, type) {
  const schema = NF[type] || { l: type, i: '📋', f: [] };
  const props = detail.props || {};
  const st = props.status;
  const doneMax = SM[type] || 2;
  let h = '<div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">';

  // Header
  h += `<div class="flex items-center justify-between px-4 py-2.5 border-b border-gray-700" style="background:#252a3a">`;
  h += `<div class="flex items-center gap-2"><span>${schema.i}</span><span class="font-semibold text-gray-200">${schema.l}</span><span class="text-xs text-gray-500">${props.id || ''}</span></div>`;
  h += '<div class="flex items-center gap-2">';
  if (st !== undefined && st !== null) {
    let sCls = SC[st] || 'bg-gray-600 text-gray-300';
    let sTxt = SL[st] || ('status=' + st);
    if (st === 10) { sCls = 'bg-amber-800 text-amber-200'; sTxt = '待审批'; }
    else if (st === 11) { sCls = 'bg-green-700 text-green-100'; sTxt = '已批准'; }
    else if (st === doneMax) { sCls = 'bg-green-800 text-green-200'; sTxt = (SL[st] || '已完成') + '·未审'; }
    h += `<span class="px-2 py-0.5 rounded text-xs ${sCls}">${sTxt}</span>`;
  }
  h += '</div></div>';
  h += '<div class="px-4 py-3 space-y-2">';

  // Image preview
  for (const f of schema.f) {
    if (f.t === 'image' && props[f.k]) {
      h += `<div class="mb-3"><div class="text-xs text-gray-400 mb-1">${esc(f.l)}</div>`;
      h += `<img src="/file/${enc(props[f.k])}" class="max-w-full rounded border border-gray-600 max-h-64 object-contain bg-gray-900" onerror="this.style.display='none';this.nextElementSibling.style.display=''" />`;
      h += `<div style="display:none" class="text-xs text-gray-500 italic">未找到: ${esc(props[f.k])}</div></div>`;
    }
  }

  // Editable fields
  for (const f of schema.f) {
    if (f.t === 'image') continue;
    const val = props[f.k] || '';
    if (f.t === 'tags') {
      h += renderTagField(type, f, val);
    } else if (f.t === 'textarea') {
      h += `<div><label class="text-xs text-gray-400 block mb-0.5">${esc(f.l)}</label>`;
      h += `<textarea id="f-${f.k}" class="fi w-full bg-gray-900 border border-gray-600 rounded px-2.5 py-1.5 text-sm text-gray-200 focus:border-amber-500 focus:outline-none">${esc(val)}</textarea></div>`;
    } else {
      h += `<div><label class="text-xs text-gray-400 block mb-0.5">${esc(f.l)}</label>`;
      h += `<input id="f-${f.k}" type="text" value="${escA(val)}" class="w-full bg-gray-900 border border-gray-600 rounded px-2.5 py-1.5 text-sm text-gray-200 focus:border-amber-500 focus:outline-none" /></div>`;
    }
  }

  // Action buttons
  const nodeId = props.id || '';
  h += '<div class="pt-3 flex gap-2 flex-wrap">';
  h += `<button onclick="saveNode('${nodeId}','${type}')" class="px-4 py-1.5 bg-amber-700 hover:bg-amber-600 rounded text-white text-sm font-medium">💾 保存</button>`;
  if (st === 10) {
    h += `<button onclick="doApproveNode('${nodeId}');closeP();setTimeout(loadArtStatus,500)" class="px-4 py-1.5 bg-green-800 hover:bg-green-700 rounded text-white text-sm font-medium">✓ 通过</button>`;
    h += `<button onclick="doRejectNode('${nodeId}');closeP();setTimeout(loadArtStatus,500)" class="px-4 py-1.5 bg-red-800 hover:bg-red-700 rounded text-white text-sm font-medium">✗ 驳回</button>`;
  }
  h += '<span id="save-msg" class="text-xs text-gray-500 self-center ml-2"></span>';
  h += '</div>';

  h += '</div></div>';
  $('pn-b').innerHTML = h;
}
