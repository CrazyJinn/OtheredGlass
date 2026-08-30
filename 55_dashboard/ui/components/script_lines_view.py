"""图行（LineAudio 逐句节点）渲染组件：定稿审台词.md 预览 + 逐句音频审批卡。

- 定稿审（SecScript=10）对象是 台词.md（人读 Markdown）——render_script_md 直接渲染全文。
- 逐句音频审（行 status=10）数据源是图行（SecScript-produces{order}->LineAudio，
  按 order 遍历遇 op=scene 行切块）；写回经 core.script_lines（行节点 status 11/0）。
"""
import base64
import json
from pathlib import Path

import streamlit as st

from config import settings
from core import script_lines as sl
from repo import graph_repo
from ui.components import launch_button

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


def _rel(p: Path) -> str:
    """绝对路径 → 项目根相对（缺文件提示用，兜底返回原串）。"""
    try:
        return str(p.relative_to(settings.PROJECT_ROOT))
    except ValueError:
        return str(p)


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


def _render_sequential_player(lines):
    """顺序连播器：本节全部有母带的音频行（say 配音 + ambient 环境音）按行序串播
    （ended 自动接下一句，点句跳播）。

    行级通过/驳回按钮不受影响（仍在各行卡内）——本组件只是叠加的听音工具。
    试听读母带 15_声音/（sl.master_wav_path）——运行时副本归 chapter-publisher
    发布时按 status=11 拷贝，未批音频不进 99_game/assets。
    wav 以 base64 内嵌组件 iframe（st.audio 无跨组件连播能力），一句数十~数百 KB。
    """
    items = []
    for i, l in enumerate(lines, 1):
        op = l.get("op")
        if op == "transition" or (op == "narrate" and l.get("ambient_track")):
            wav = sl.master_wav_path(l)
            who = "🔊 转场音效" if op == "transition" else "🔊 氛围声景"
        elif op == "say":
            wav = sl.master_wav_path(l)
            who = l.get("who", "")
        else:
            continue
        if wav is None or not wav.exists():
            continue
        try:
            b64 = base64.b64encode(wav.read_bytes()).decode()
        except OSError:
            continue
        items.append({
            "i": i,
            "who": who,
            "text": l.get("text", ""),
            "badge": _STATE_EMOJI.get(sl.line_state(l), ""),
            "src": f"data:audio/wav;base64,{b64}",
        })
    if len(items) < 2:
        return  # 不足两句无需连播器
    st.caption(f"🎧 顺序连播（{len(items)} 条，含环境音，播完自动下一句；单句通过/驳回仍在下方各行卡）")
    st.iframe(
        _SEQ_PLAYER_HTML.replace("__ITEMS__", json.dumps(items, ensure_ascii=False)),
        height=250,
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

    # 顺序连播（听完整节再逐条定夺；say + ambient 按行序；行级通过/驳回按钮在下方各行卡不变）
    _render_sequential_player(lines)

    rejected_nodes = []
    block = None
    prev_block = None
    for i, l in enumerate(lines, 1):
        if l.get("scene_block_id") != prev_block:  # 行上块归属变化 → 开块分组（scene 行已去图化）
            prev_block = l.get("scene_block_id")
            block = st.expander(f"场景段 {prev_block or '（未分块）'}", expanded=False)
        with block:
            _render_line_card(l, i, sec_id, rejected_nodes)

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


def _render_line_card(l, idx, sec_id, rejected_nodes):
    """单行卡：音频行（say / 转场 ambient / 带氛围标注 narrate）带徽章/对照/试听/通过驳回；
    其余结构行只读渲染。

    试听读母带 15_声音/（sl.master_wav_path）。驳回行收进 rejected_nodes 为
    {"id": 行id, "kind": "say"|"sfx"}——重生成 deeplink 按类型分流
    （say 走 TTS 重配、sfx 走声景重做）。
    """
    op = l.get("op")
    nid = l.get("id", "")
    if op == "transition" or (op == "narrate" and l.get("ambient_track")):
        state = sl.line_state(l)
        kind_label = "🔊 转场音效" if op == "transition" else "🔊 氛围声景"
        with st.container(border=True):
            st.markdown(f"**{kind_label}** `#{idx}` {_STATE_BADGE.get(state, '')}：{l.get('text', '')}")
            track = l.get("ambient_track")  # 已产音频才有通过/驳回按钮
            wav = sl.master_wav_path(l)
            if wav:
                if wav.exists():
                    st.caption(f"🎧 母带试听：{_rel(wav)}")
                    st.audio(str(wav), format="audio/wav")
                else:
                    st.caption(f"⚠️ 缺母带音频：{_rel(wav)}")
            b1, b2 = st.columns(2)
            with b1:
                if track and state in ("pending", "rejected") and \
                        st.button("通过", key=f"la_ok_{nid}", type="primary"):
                    sl.set_line_status(nid, 11)
                    gone = sl.cleanup_after_approval(l)
                    note = f"（已清素材 {','.join(gone)}）" if gone else ""
                    st.toast(f"#{idx} 环境音已通过{note}", icon="✅")
                    st.rerun()
            with b2:
                if track and state in ("pending", "approved") and \
                        st.button("驳回", key=f"la_no_{nid}"):
                    sl.set_line_status(nid, 0)
                    st.toast(f"#{idx} 环境音已驳回（重做入口见下方）", icon="❌")
                    st.rerun()
            if state == "rejected":
                rejected_nodes.append({"id": nid, "kind": "sfx"})
        return
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
        if l.get("clone_mode") == "xvec":
            head += " `⚡xvec`"  # 非缺省演绎通道才显示（icl=缺省不占视觉噪音）
        head += f" `#{idx}` {_STATE_BADGE.get(state, '')}"
        st.markdown(f"{head}：{l.get('text', '')}")
        if l.get("tts_text") and l["tts_text"] != l.get("text"):
            st.caption(f"🎙️ 配音变体：{l['tts_text']}")
        key = l.get("voice_key")
        if key:
            wav = sl.master_wav_path(l)
            if wav and wav.exists():
                st.caption(f"🎧 母带试听：{_rel(wav)}")
                st.audio(str(wav), format="audio/wav")
            else:
                st.caption(f"⚠️ 缺母带音频：{_rel(wav) if wav else key + '.wav'}")
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
            rejected_nodes.append({"id": nid, "kind": "say"})
