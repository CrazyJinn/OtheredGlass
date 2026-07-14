"""剧情章节进度：列出 Chapter + 编排/立绘缺口 + 剧本预览 + 审批。

结构与 page_scene_overview 对称：Chapter 代替 Location，get_chapter_graph 代替
get_location_graph。dialog 复用同一 session_state["_dialog_node"] key。

剧本预览（读 script_path 的 JSON 渲染逐句对话）是剧情审批的核心——review 对白质量，
区别于美术节点审批（看图片）。审批按钮 status=10→11（通过）/→0（驳回重做）。
"""
import json
from pathlib import Path

import streamlit as st

from config import settings
from repo import graph_repo
from core import approval
from ui.components import launch_button, status_badge
from ui import page_node_editor


@st.dialog("节点编辑", width="large")
def _edit_dialog(schema, node_id):
    page_node_editor.render_editor(schema, node_id)
    st.divider()
    if st.button("关闭", use_container_width=True):
        st.session_state.pop("_dialog_node", None)
        st.rerun()


def render(schema):
    st.header("剧情章节进度")
    chapters = graph_repo.get_nodes("Chapter")
    # chapter_no 可能是 0（合法 falsy），用 is not None 判断；无序号排末尾
    chapters.sort(key=lambda c: (
        c.get("chapter_no") if c.get("chapter_no") is not None else 9999,
        c.get("title") or "",
    ))
    if not chapters:
        st.caption("无章节节点。用 plot-design agent 创作第一章吧。")
        return
    for ch in chapters:
        _render_chapter_row(schema, ch)
    # 跨 rerun 保持 dialog（与其他页共用 _dialog_node）
    dn = st.session_state.get("_dialog_node")
    if dn:
        _edit_dialog(schema, dn)


def _render_chapter_row(schema, ch):
    ch_id = ch["id"]
    status = ch.get("status")
    with st.container(border=True):
        # 标题行：序号 + 标题 + status 徽章
        top = st.columns([4, 2, 2])
        no = ch.get("chapter_no")
        no_text = f"第{no}章 · " if no is not None else ""
        top[0].markdown(f"### {no_text}{ch.get('title') or ch_id}")
        top[0].caption(f"id: `{ch_id}`")
        with top[1]:
            if status is not None:
                color = status_badge.badge_color(status)
                text = status_badge.badge_text(status)
                st.markdown(f":{color}[● {text}]")
        with top[2]:
            launch_button.render_chapter(ch_id, ch.get("title"))
            if st.button("编辑章节", key=f"cedit_{ch_id}"):
                st.session_state["_dialog_node"] = ch_id
                st.rerun()

        # 概要 / 分支骨架
        if ch.get("summary"):
            st.caption(f"**概要**：{ch['summary']}")
        if ch.get("branch_summary"):
            st.caption(f"**分支骨架**：{ch['branch_summary']}")

        # 审批按钮（status=10 待审）/ 发布提示（status=11 已批）
        if status == 10:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("通过（批准 11）", key=f"cok_{ch_id}", type="primary"):
                    graph_repo.set_status(ch_id, approval.approve())
                    # toast 而非 inline：紧随的 st.rerun() 会丢弃本轮 inline 输出
                    st.toast("剧本已批准（status=11）", icon="✅")
                    st.rerun()
            with c2:
                if st.button("驳回（重做 0）", key=f"cno_{ch_id}"):
                    graph_repo.set_status(ch_id, approval.reject())
                    st.toast("已驳回（status=0），剧本需重做", icon="❌")
                    st.rerun()
        elif status == 11:
            st.info(
                "剧本已批准（11）。下方「立绘缺口」全部就绪后，点上方「推进剧情创作」"
                "由 plot-design 自动委派 chapter-publisher 发布到 `99_game/`。"
            )

        # 剧本预览（核心：review 对白质量）
        if ch.get("script_path"):
            _render_script_preview(ch["script_path"])

        # 编排子图：contains 的 Scene + depicts 的立绘缺口
        _render_chapter_subgraph(ch_id)


def _render_script_preview(script_path):
    """读 script_path 的剧本 JSON，渲染 meta + 每个 scene-block 的逐句对话，供 review。"""
    p = Path(script_path)
    if not p.is_absolute():
        p = settings.PROJECT_ROOT / script_path
    if not p.exists():
        st.caption(f"剧本文件不存在：{script_path}")
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        st.error(f"剧本 JSON 解析失败：{e}")
        return
    meta = data.get("meta", {})
    req = meta.get("requires", {})
    scenes = data.get("scenes", [])
    cap = f"📜 剧本预览：{script_path}（{len(scenes)} 场景段"
    if req.get("portraits"):
        cap += f"，{len(req['portraits'])} 立绘引用"
    cap += "）"
    with st.expander(cap, expanded=False):
        if meta:
            st.caption(f"章节 {meta.get('chapter')} · {meta.get('title')}")
            parts = []
            if req.get("characters"):
                parts.append("角色：" + "、".join(req["characters"]))
            if req.get("scenes"):
                parts.append("场景：" + "、".join(req["scenes"]))
            if req.get("portraits"):
                parts.append(f"立绘 {len(req['portraits'])} 个")
            if parts:
                st.caption(" | ".join(parts))
        for blk in scenes:
            blk_id = blk.get("id", "")
            with st.expander(f"场景段 {blk_id}（{blk.get('scene', '')}）", expanded=False):
                meta_bits = []
                if blk.get("time"):
                    meta_bits.append(f"时段：{blk['time']}")
                if blk.get("bgm"):
                    meta_bits.append(f"BGM：{blk['bgm'].get('track', '')}（{blk['bgm'].get('mode', '')}）")
                if meta_bits:
                    st.caption(" · ".join(meta_bits))
                for line in blk.get("lines", []):
                    _render_line(line)


def _render_line(line):
    """渲染单条指令为可读文本。"""
    op = line.get("op")
    if op == "say":
        who = line.get("who", "")
        portrait = line.get("portrait", "")
        pos = line.get("pos", "")
        st.markdown(f"**{who}** `{portrait}·{pos}`：{line.get('text', '')}")
    elif op == "narrate":
        st.markdown(f"*（旁白）{line.get('text', '')}*")
    elif op == "show":
        st.caption(f"[入场] {line.get('who', '')}.{line.get('portrait', '')} @ {line.get('pos', 'center')}")
    elif op == "hide":
        st.caption(f"[离场] {line.get('who', '')}")
    elif op == "bg":
        st.caption(f"[切背景] {line.get('scene', '')} {line.get('time', '')}")
    elif op == "bgm":
        st.caption(f"[BGM] {line.get('track', '')} {line.get('mode', '')}")
    elif op == "sfx":
        st.caption(f"[音效] {line.get('track', '')}")
    elif op == "choice":
        st.markdown("**【选择】**")
        for o in line.get("options", []):
            tails = []
            if o.get("to"): tails.append(f"→{o['to']}")
            if o.get("scene"): tails.append(f"→场景{o['scene']}")
            if o.get("file"): tails.append(f"→文件{o['file']}")
            if o.get("leads_to_ending"): tails.append("导向结局")
            tail = f"（{'，'.join(tails)}）" if tails else ""
            st.markdown(f"  - 「{o.get('label', '')}」{tail}")
    elif op == "label":
        st.caption(f"[锚点] {line.get('name', '')}")
    elif op == "jump":
        tails = []
        if line.get("to"): tails.append(f"→{line['to']}")
        if line.get("scene"): tails.append(f"→场景{line['scene']}")
        if line.get("file"): tails.append(f"→文件{line['file']}")
        st.caption(f"[跳转] {'，'.join(tails)}")
    elif op == "ending":
        st.markdown(f"**【结局 {line.get('kind', '')}】{line.get('title', '')}**")


def _render_chapter_subgraph(ch_id):
    """渲染 contains 的 Scene + depicts 的立绘缺口（含就绪计数）。"""
    g = graph_repo.get_chapter_graph(ch_id)
    scenes = [n for n in g["nodes"] if n["label"] == "Scene"]
    stands = [n for n in g["nodes"] if n["label"] == "StandingIllustration"]
    if not scenes and not stands:
        return
    cols = st.columns(2)
    with cols[0]:
        st.markdown("**场景编排（contains）**")
        if not scenes:
            st.caption("无（首次编排尚未建立 contains 边）")
        else:
            scenes.sort(key=lambda n: n.get("name") or "")
            for n in scenes:
                _badge_line(n.get("name") or n["id"], n["status"])
    with cols[1]:
        st.markdown("**立绘缺口（depicts）**")
        if not stands:
            st.caption("无")
        else:
            ready = sum(1 for n in stands if n["status"] == 11)
            st.caption(f"{ready}/{len(stands)} 就绪")
            for n in stands:
                full = graph_repo.get_node(n["id"]) or {}
                variant = full.get("variant_label", n["id"])
                _badge_line(variant, n["status"])


def _badge_line(label, status):
    color = status_badge.badge_color(status)
    text = status_badge.badge_text(status)
    st.markdown(f"- {label} :{color}[{text}]")
