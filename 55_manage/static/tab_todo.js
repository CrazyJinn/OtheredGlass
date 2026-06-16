/* ═══════════════════════════════════════════════════════════════
   tab_todo.js — Tab 3 地点美术（只读 Location 列表）+ Tab 4 剧情占位
   ═══════════════════════════════════════════════════════════════ */

async function loadLocationList() {
  const tbody = $('scene-tbody');
  const emptyEl = $('scene-empty');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="3" class="text-center text-gray-500 py-4">加载中...</td></tr>';

  try {
    const data = await api('/api/narrative/list?label=Location');
    const nodes = data.nodes || [];
    if (!nodes.length) {
      tbody.innerHTML = '';
      emptyEl.classList.remove('hidden');
      return;
    }
    emptyEl.classList.add('hidden');
    tbody.innerHTML = nodes.map(n => {
      const trunc = (s, len) => (!s ? '--' : s.length > len ? esc(s.substring(0, len)) + '...' : esc(s));
      return `<tr class="border-b border-gray-700/50 hover:bg-gray-700/30 fade-in">
        <td class="px-3 py-2"><span class="text-xs text-gray-500">${esc(n.id)}</span></td>
        <td class="px-3 py-2 font-medium">${esc(n.name) || '--'}</td>
        <td class="px-3 py-2 text-sm text-gray-300" style="max-width:400px">${trunc(n.description, 80)}</td>
      </tr>`;
    }).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="3" class="text-center text-red-400 py-4">加载失败: ${esc(e.message)}</td></tr>`;
  }
}
