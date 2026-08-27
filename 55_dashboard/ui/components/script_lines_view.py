"""图行（LineAudio 逐句节点）渲染组件：定稿审台词.md 预览 + 逐句音频审批卡。

- 定稿审（SecScript=10）对象是 台词.md（人读 Markdown）——render_script_md 直接渲染全文。
- 逐句音频审（行 status=10）数据源是图行（SecScript-produces{order}->LineAudio，
  按 order 遍历遇 op=scene 行切块）；写回经 core.script_lines（行节点 status 11/0）。
"""
import base64
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from config import settings
from core import script_lines as sl
from repo import graph_repo
from ui.components import launch_button

_VOICES_DIR = "99_game/assets/voices"

# 行级音频状态 → 徽章 markdown
_STATE_BADGE = {
    "missing": ":gray[未配音]",
    "pending": ":orange[待审]",
    "approved": ":green[已通过]",
    "rejected": ":red[已驳回]",
    "void": ":orange[已作废·待重拆]",
}


def _abs(path):
    p = Path(path)
    return p if p.is_absolute() else settings.PROJECT_ROOT / p


# ── 定稿审：台词.md 只读预览（人读格式，审文字质量）──

def render_script_md(script_path, label=""):
    """渲染 台词.md 全文（定稿审对象——拆分进图发生在审批通过之后，故审的是 md）。"""
    p = _abs(script_path)
    if not p.exists():
        st.caption(f"台词文件不存在：{script_path}")
        return
    text = p.read_text(encoding="utf-8")
    with st.expander(f"📜 台词定稿：{label or script_path}", expanded=False):
        st.markdown(text)


# ── 顺序连播器（点一次播完整节；单句审批仍在各行卡）──

# st.audio 各自独立、无 ended 回调，连播需自定义组件：wav base64 内嵌 + JS ended 链自动接播。
# __ITEMS__ 占位符注入（避免 f-string 花括号转义）。
_SEQ_PLAYER_HTML = """\
<div style="font-size:14px;">
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
    <button id="sp-play" style="padding:3px 12px;cursor:pointer;">&#9654; 从头连播</button>
    <button id="sp-stop" style="padding:3px 12px;cursor:pointer;">&#9635; 停止</button>
    <span id="sp-now" style="opacity:.85;">未开始（点句可跳播）</span>
  </div>
  <div id="sp-list" style="max-height:190px;overflow:auto;margin-top:6px;
       border:1px solid rgba(128,128,128,.35);border-radius:6px;"></div>
</div>
<script>
(function () {
  const items = __ITEMS__;
  let cur = -1;
  const audio = new Audio();
  const nowEl = document.getElementById("sp-now");
  const listEl = document.getElementById("sp-list");

  function fmt(k) {
    const it = items[k];
    return "#" + it.i + " " + it.badge + " " + it.who + "\\uFF1A" + it.text;
  }
  function renderList() {
    listEl.innerHTML = "";
    items.forEach(function (it, k) {
      const d = document.createElement("div");
      d.textContent = fmt(k);
      d.style.padding = "3px 8px";
      d.style.cursor = "pointer";
      if (k === cur) d.style.background = "rgba(255,235,59,.28)";
      d.onclick = function () { play(k); };
      listEl.appendChild(d);
    });
  }
  function play(k) {
    cur = k;
    audio.src = items[k].src;
    audio.play();
    nowEl.textContent = "\\u25B6 " + fmt(k) + "\\uFF08" + (k + 1) + "/" + items.length + "\\uFF09";
    renderList();
  }
  audio.addEventListener("ended", function () {
    if (cur + 1 < items.length) play(cur + 1);
    else nowEl.textContent = "\\u2705 \\u8FDE\\u64AD\\u5B8C\\u6BD5\\uFF08" + items.length + " \\u53E5\\uFF09";
  });
  document.getElementById("sp-play").onclick = function () { play(0); };
  document.getElementById("sp-stop").onclick = function () {
    audio.pause();
    cur = -1;
    nowEl.textContent = "\\u5DF2\\u505C\\u6B62";
    renderList();
  };
  renderList();
})();
</script>
"""

_STATE_EMOJI = {
    "pending": "⏳",
    "approved": "✅",
    "rejected": "❌",
    "missing": "⚠️",
    "void": "🔄",
}


def _render_sequential_player(lines, voices_dir):
    """顺序连播器：本节全部有 wav 的 say 行串播（ended 自动接下一句，点句跳播）。

    行级通过/驳回按钮不受影响（仍在各行卡内）——本组件只是叠加的听音工具。
    wav 以 base64 内嵌组件 iframe（st.audio 无跨组件连播能力），一句数十~数百 KB。
    """
    items = []
    for i, l in enumerate(lines, 1):
        if l.get("op") != "say" or not l.get("voice_key"):
            continue
        wav = voices_dir / f"{l['voice_key']}.wav"
        if not wav.exists():
            continue
        try:
            b64 = base64.b64encode(wav.read_bytes()).decode()
        except OSError:
            continue
        items.append({
            "i": i,
            "who": l.get("who", ""),
            "text": l.get("text", ""),
            "badge": _STATE_EMOJI.get(sl.line_state(l), ""),
            "src": f"data:audio/wav;base64,{b64}",
        })
    if len(items) < 2:
        return  # 不足两句无需连播器
    st.caption(f"🎧 顺序连播（{len(items)} 句，播完自动下一句；单句通过/驳回仍在下方各行卡）")
    components.html(
        _SEQ_PLAYER_HTML.replace("__ITEMS__", json.dumps(items, ensure_ascii=False)),
        height=250,
        scrolling=False,
    )


# ── LineAudio 逐句音频审（按节一张卡）──

def render_audio_review(sec_id, sc_id, label=""):
    """逐句音频审批卡：按场景块分组渲染行 + 单句通过/驳回 + 全部通过 + 驳回行重生成 deeplink。

    行级审批写图行节点 status（11/0）；「节完成」= 全部行 11（派生判断，无节级批准按钮）。
    """
    lines = sl.get_lines(sc_id)
    if not lines:
        st.caption("图无台词行（SecScript=11 后由 section-voice-publisher 拆分进图）")
        return

    c = sl.say_counts(lines)
    st.caption(
        f"共 {c['say']} 句：✅ {c['approved']} · ⏳ {c['pending']} · ❌ {c['rejected']} · "
        f"⚠️ 未配音 {c['missing']} · 🔄 作废 {c['void']}"
    )

    # 顺序连播（听完整节再逐条定夺；行级通过/驳回按钮在下方各行卡不变）
    _render_sequential_player(lines, _abs(_VOICES_DIR))

    rejected_nodes = []
    voices_dir = _abs(_VOICES_DIR)
    block = None
    for i, l in enumerate(lines, 1):
        op = l.get("op")
        if op == "scene":
            bits = [f"场景段 {l.get('scene_block_id', '')}（{l.get('scene_name', '')}）"]
            if l.get("scene_time"):
                bits.append(f"时段 {l['scene_time']}")
            block = st.expander(" · ".join(bits), expanded=False)
            continue
        if block is None:
            continue
        with block:
            _render_line_card(l, i, sec_id, voices_dir, rejected_nodes)

    # 驳回行重生成 deeplink（plot-design 单节聚焦只重配被驳回行 --nodes）
    if rejected_nodes:
        launch_button.render_regen_lines(
            sec_id, rejected_nodes,
            label=f"重生成 {len(rejected_nodes)} 句被驳回的音频（唤起 plot-design）",
        )

    # 全部通过快捷键：批量 pending→11（rejected/missing 不批——需先重配）
    if c["pending"] > 0 and c["rejected"] == 0:
        if st.button(f"全部通过（{c['pending']} 句待审）", key=f"la_all_{sc_id}"):
            n = sl.approve_all_pending(sl.get_lines(sc_id))
            st.toast(f"已批量通过 {n} 句", icon="✅")
            st.rerun()


def _render_line_card(l, idx, sec_id, voices_dir, rejected_nodes):
    """单行卡：say 带徽章/原文变体对照/试听/通过驳回；结构行只读渲染。"""
    op = l.get("op")
    nid = l.get("id", "")
    if op != "say":
        if op == "narrate":
            st.markdown(f"*（旁白）{l.get('text', '')}*")
        elif op == "label":
            st.caption(f"[锚点] {l.get('text', '')}")
        elif op == "ending":
            st.markdown(f"**【结局 {l.get('kind', '')}】{l.get('text', '')}**")
        return

    state = sl.line_state(l)
    with st.container(border=True):
        head = f"**{l.get('who', '')}** `{l.get('portrait') or ''}·{l.get('pos') or ''}`"
        if l.get("emotion"):
            head += f" `🎭{l['emotion']}`"
        head += f" `#{idx}` {_STATE_BADGE.get(state, '')}"
        st.markdown(f"{head}：{l.get('text', '')}")
        if l.get("tts_text") and l["tts_text"] != l.get("text"):
            st.caption(f"🎙️ 配音变体：{l['tts_text']}")
        key = l.get("voice_key")
        if key:
            wav = voices_dir / f"{key}.wav"
            if wav.exists():
                st.audio(str(wav), format="audio/wav")
            else:
                st.caption(f"⚠️ 缺音频文件：{key}.wav")
        b1, b2 = st.columns(2)
        has_audio = bool(key)
        with b1:
            if has_audio and state in ("pending", "rejected") and \
                    st.button("通过", key=f"la_ok_{nid}", type="primary"):
                sl.set_line_status(nid, 11)
                st.toast(f"#{idx} 已通过", icon="✅")
                st.rerun()
        with b2:
            if has_audio and state in ("pending", "approved") and \
                    st.button("驳回", key=f"la_no_{nid}"):
                sl.set_line_status(nid, 0)
                st.toast(f"#{idx} 已驳回（重生成入口见下方）", icon="❌")
                st.rerun()
        if state == "rejected":
            rejected_nodes.append(nid)
