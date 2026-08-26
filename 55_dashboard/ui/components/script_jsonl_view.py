"""台词 JSONL 渲染组件：定稿审逐句预览 + LineAudio 逐句音频审批卡。

数据源是 SecScript.script_path 指向的 `台词.jsonl`（行级状态 audio.status 就在行内）。
写回一律经 core.script_jsonl（项目唯一实现 jsonl_script），保证「单句审批只 diff 一行」。
"""
from pathlib import Path

import streamlit as st

from config import settings
from core import script_jsonl as js
from repo import graph_repo
from ui.components import launch_button

_VOICES_DIR = "99_game/assets/voices"

# 行级音频状态 → (徽章 markdown, 可执行动作集)
_STATE_BADGE = {
    "missing": ":gray[未配音]",
    "pending": ":orange[待审]",
    "approved": ":green[已通过]",
    "rejected": ":red[已驳回]",
    "stale": ":orange[台词已改·需重配]",
}


def _abs(path):
    p = Path(path)
    return p if p.is_absolute() else settings.PROJECT_ROOT / p


# ── 定稿审：只读逐句预览 ──

def render_preview(script_path, label=""):
    """读台词 JSONL，渲染 meta + 每个 scene-block 的逐句对话（含行 id / emotion / 就地试听）。"""
    p = _abs(script_path)
    if not p.exists():
        st.caption(f"台词文件不存在：{script_path}")
        return
    try:
        rows = js.load(p)
    except ValueError as e:
        st.error(f"台词 JSONL 解析失败：{e}")
        return
    if not rows or rows[0].get("op") != "meta":
        st.error("首行不是 meta 行（文件损坏）")
        return
    meta = rows[0]
    req = meta.get("requires") or {}
    n_say = sum(1 for r in rows if r.get("op") == "say")
    cap = f"📜 台词预览：{label or script_path}（{n_say} 句台词"
    if req.get("portraits"):
        cap += f"，{len(req['portraits'])} 立绘引用"
    cap += "）"
    with st.expander(cap, expanded=False):
        st.caption(f"章节 {meta.get('chapter')} · {meta.get('title')} · 行水位 `L{meta.get('line_seq', 0):04d}`")
        parts = []
        if req.get("characters"):
            parts.append("角色：" + "、".join(req["characters"]))
        if req.get("scenes"):
            parts.append("场景：" + "、".join(req["scenes"]))
        if parts:
            st.caption(" | ".join(parts))
        cur = None
        lines_area = None
        for r in rows[1:]:
            if r.get("op") == "scene":
                bits = [f"场景段 {r.get('id', '')}（{r.get('scene', '')}）"]
                if r.get("time"):
                    bits.append(f"时段 {r['time']}")
                cur = st.expander(" · ".join(bits), expanded=False)
                lines_area = cur
                continue
            if lines_area is None:
                continue
            with lines_area:
                _render_row(r)


def _render_row(r):
    """渲染一条台词行（8 行类型；say 带 audio 徽章与就地试听）。"""
    op = r.get("op")
    rid = r.get("id", "")
    if op == "say":
        head = f"**{r.get('who', '')}** `{r.get('portrait', '')}·{r.get('pos', '')}`"
        audio = r.get("audio") or {}
        if audio.get("emotion"):
            head += f" `🎭{audio['emotion']}`"
        head += f" `{rid}`"
        st.markdown(f"{head}：{r.get('text', '')}")
        key = audio.get("key")
        if key:
            wav = _abs(_VOICES_DIR) / f"{key}.wav"
            if wav.exists():
                st.audio(str(wav), format="audio/wav")
    elif op == "narrate":
        st.markdown(f"*（旁白）{r.get('text', '')}*")
    elif op == "choice":
        st.markdown("**【选择】**")
        for o in r.get("options", []):
            tails = []
            if o.get("to"): tails.append(f"→{o['to']}")
            if o.get("scene"): tails.append(f"→场景{o['scene']}")
            if o.get("file"): tails.append(f"→文件{o['file']}")
            if o.get("leads_to_ending"): tails.append("导向结局")
            tail = f"（{'，'.join(tails)}）" if tails else ""
            st.markdown(f"  - 「{o.get('label', '')}」{tail}")
    elif op == "label":
        st.caption(f"[锚点] {r.get('name', '')} `{rid}`")
    elif op == "jump":
        tails = []
        if r.get("to"): tails.append(f"→{r['to']}")
        if r.get("scene"): tails.append(f"→场景{r['scene']}")
        if r.get("file"): tails.append(f"→文件{r['file']}")
        st.caption(f"[跳转] {'，'.join(tails)} `{rid}`")
    elif op == "ending":
        st.markdown(f"**【结局 {r.get('kind', '')}】{r.get('title', '')}**")


# ── LineAudio 逐句音频审批 ──

def _mark(script_path, line_id, new_status):
    """行级审批写回（load → set_audio → save，单行 diff）。"""
    rows = js.load(script_path)
    js.set_audio(rows, line_id, status=new_status)
    js.save(script_path, rows)


def render_audio_review(script_path, vo_id):
    """逐句音频审批卡：试听 + 单句通过/驳回 + 全部通过 + 驳回行重生成 deeplink。

    行级三态写回台词 JSONL 的 audio.status；节级 LineAudio 的「通过」gate（全部行 approved）
    由调用方（page_approval）按 js.all_approved 控制。
    """
    p = _abs(script_path)
    if not p.exists():
        st.caption(f"台词文件不存在：{script_path}")
        return
    try:
        rows = js.load(p)
    except ValueError as e:
        st.error(f"台词 JSONL 解析失败：{e}")
        return

    c = js.audio_counts(rows)
    st.caption(
        f"共 {c['say']} 句：✅ {c['approved']} · ⏳ {c['pending']} · ❌ {c['rejected']} · "
        f"🔄 台词已改 {c['stale']} · ⚠️ 未配音 {c['missing']}"
    )

    sec_id = graph_repo.get_section_of_lineaudio(vo_id)
    rejected_ids = []
    voices_dir = _abs(_VOICES_DIR)

    for scene_id, r in js.iter_say_rows(rows):
        rid = r.get("id", "")
        state = js.line_state(r)
        audio = r.get("audio") or {}
        with st.container(border=True):
            head = f"**{r.get('who', '')}**"
            if audio.get("emotion"):
                head += f" `🎭{audio['emotion']}`"
            head += f" `{rid}` {_STATE_BADGE.get(state, '')}"
            st.markdown(f"{head}：{r.get('text', '')}")
            key = audio.get("key")
            if key:
                wav = voices_dir / f"{key}.wav"
                if wav.exists():
                    st.audio(str(wav), format="audio/wav")
                else:
                    st.caption(f"⚠️ 缺音频文件：{key}.wav")
            b1, b2 = st.columns(2)
            has_audio = bool(key)
            with b1:
                if has_audio and state in ("pending", "rejected", "stale") and \
                        st.button("通过", key=f"la_ok_{vo_id}_{rid}", type="primary"):
                    _mark(p, rid, "approved")
                    st.toast(f"{rid} 已通过", icon="✅")
                    st.rerun()
            with b2:
                if has_audio and state in ("pending", "approved") and \
                        st.button("驳回", key=f"la_no_{vo_id}_{rid}"):
                    _mark(p, rid, "rejected")
                    st.toast(f"{rid} 已驳回（重生成入口见下方）", icon="❌")
                    st.rerun()
            if state == "rejected":
                rejected_ids.append(rid)

    # 驳回行重生成 deeplink（对话重推：plot-design 单节聚焦只重做被驳回/已改行）
    if rejected_ids and sec_id:
        launch_button.render_regen_lines(
            sec_id, rejected_ids,
            label=f"重生成 {len(rejected_ids)} 句被驳回的音频（唤起 plot-design）",
        )

    # 全部通过快捷键：把待审行批量 approved（rejected/stale/未配音不批——需先重生成）
    if c["pending"] > 0 and c["rejected"] == 0:
        if st.button(f"全部通过（{c['pending']} 句待审）", key=f"la_all_{vo_id}"):
            rows2 = js.load(p)
            for _, r in js.iter_say_rows(rows2):
                if js.line_state(r) == "pending":
                    js.set_audio(rows2, r["id"], status="approved")
            js.save(p, rows2)
            st.toast(f"已批量通过 {c['pending']} 句", icon="✅")
            st.rerun()
