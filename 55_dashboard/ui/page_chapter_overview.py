"""剧情章节进度：列出 Chapter + 分节编排/立绘缺口 + 节级剧本预览 + 审批。

结构与 page_scene_overview 对称：Chapter 代替 Location，get_chapter_graph 代替
get_location_graph。dialog 复用同一 session_state["_dialog_node"] key（点 Section 行也进同
一节点编辑器——Section 已被 schema_loader 自动注册）。

节级预览（读各 Section.script_path 的 YAML 渲染逐句对话）是剧情审批的核心——review 对白质量，
区别于美术节点审批（看图片）。Chapter 审批按钮 status=10→11（结构审通过）/→0（驳回重做）；
Section 定稿审(30→31)走审批中心（page_approval）。
"""
import yaml
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


def _sections_sorted(g):
    """从章节子图取 Section 列表，按 section_no 排序，附完整节点字段（title/script_path/section_no）。

    subgraph 的 nodes 只含 id/label/status/name，不含 section_no/title，故逐个 get_node 补全。
    """
    secs = [n for n in g["nodes"] if n["label"] == "Section"]
    out = []
    for s in secs:
        full = graph_repo.get_node(s["id"]) or {}
        no = full.get("section_no")
        out.append({
            "id": s["id"],
            "status": s["status"],
            "_full": full,
            "_no": no if no is not None else 9999,
        })
    out.sort(key=lambda s: (s["_no"], s["id"]))
    return out


def _render_chapter_row(schema, ch):
    ch_id = ch["id"]
    status = ch.get("status")
    g = graph_repo.get_chapter_graph(ch_id)
    sections = _sections_sorted(g)
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

        # 审批按钮（status=10 结构审）/ 生产提示（status=11）
        if status == 10:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("通过（批准 11）", key=f"cok_{ch_id}", type="primary"):
                    graph_repo.set_status(ch_id, approval.approve(status))
                    # toast 而非 inline：紧随的 st.rerun() 会丢弃本轮 inline 输出
                    st.toast("结构已批准（status=11）", icon="✅")
                    st.rerun()
            with c2:
                if st.button("驳回（重做 0）", key=f"cno_{ch_id}"):
                    graph_repo.set_status(ch_id, approval.reject(status))
                    st.toast("已驳回（status=0），结构需重做", icon="❌")
                    st.rerun()
        elif status == 11:
            done = [s for s in sections if s["_full"].get("status") == 31]
            if sections and len(done) == len(sections):
                st.info(
                    "全章各节定稿已批（31）。下方「立绘缺口」全部就绪后，点上方「推进剧情创作」"
                    "由 plot-design 自动委派 chapter-publisher 合并发布到 `99_game/`。"
                )
            else:
                st.info(
                    f"结构已批（11），节级生产中：{len(done)}/{len(sections)} 节定稿已批。"
                    "逐节推进提纲 / 定稿（plot-design 按节委派 outliner / dialoguer）。"
                )

        # 各节剧本预览（核心：review 对白质量）——读 Section.script_path 的节级 YAML
        for s in sections:
            sp = s["_full"].get("script_path")
            if sp:
                _render_script_preview(sp, f"第{s['_no']}节 · {s['_full'].get('title') or s['id']}")

        # 编排子图：has_section→Section→contains→Scene→depicts→立绘缺口
        _render_chapter_subgraph(g, sections)


def _render_script_preview(script_path, label=""):
    """读 script_path 的节级剧本 YAML，渲染 meta + 每个 scene-block 的逐句对话，供 review。"""
    p = Path(script_path)
    if not p.is_absolute():
        p = settings.PROJECT_ROOT / script_path
    if not p.exists():
        st.caption(f"剧本文件不存在：{script_path}")
        return
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        st.error(f"剧本 YAML 解析失败：{e}")
        return
    meta = data.get("meta", {})
    req = meta.get("requires", {})
    scenes = data.get("scenes", [])
    cap = f"📜 剧本预览：{label or script_path}（{len(scenes)} 场景段"
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


def _render_chapter_subgraph(g, sections):
    """渲染 has_section→Section→contains→Scene→depicts→IllusDesign→expands_to→立绘缺口（含就绪计数）。"""
    nodes_by_id = {n["id"]: n for n in g["nodes"]}
    scenes_of = {}   # sec_id -> [scene_id]
    illus_of = {}    # scene_id -> [illus_id]   (via depicts)
    stands_of = {}   # illus_id -> [stand_id]   (via expands_to)
    for e in g["edges"]:
        if e["type"] == "contains":
            scenes_of.setdefault(e["from"], []).append(e["to"])
        elif e["type"] == "depicts":
            illus_of.setdefault(e["from"], []).append(e["to"])
        elif e["type"] == "expands_to":
            stands_of.setdefault(e["from"], []).append(e["to"])

    stands = [n for n in g["nodes"] if n["label"] == "StandingIllustration"]
    st.markdown(f"**编排子图（{len(sections)} 节）**")
    if stands:
        ready = sum(1 for n in stands if n["status"] == 11)
        st.caption(f"全章立绘就绪 {ready}/{len(stands)}")
    if not sections:
        st.caption("未分节（结构段尚未建立 Section）")
        return

    for s in sections:
        full = s["_full"]
        title = full.get("title") or s["id"]
        with st.expander(f"第{s['_no']}节 · {title}", expanded=False):
            _badge_line("节状态", s["status"])
            scene_ids = scenes_of.get(s["id"], [])
            scene_nodes = [nodes_by_id[sid] for sid in scene_ids if sid in nodes_by_id]
            scene_nodes.sort(key=lambda n: n.get("name") or "")
            if not scene_nodes:
                st.caption("无场景（contains 边未建立）")
            for sn in scene_nodes:
                _badge_line(sn.get("name") or sn["id"], sn["status"])
                illus_ids = illus_of.get(sn["id"], [])
                illus_nodes = [nodes_by_id[iid] for iid in illus_ids if iid in nodes_by_id]
                for ind in illus_nodes:
                    ifull = graph_repo.get_node(ind["id"]) or {}
                    illus_name = ifull.get("name") or ind["id"]
                    _badge_line(f"└ {illus_name}", ind["status"])
                    stand_ids = stands_of.get(ind["id"], [])
                    stand_nodes = [nodes_by_id[tid] for tid in stand_ids if tid in nodes_by_id]
                    for stn in stand_nodes:
                        sfull = graph_repo.get_node(stn["id"]) or {}
                        variant = sfull.get("variant_label", stn["id"])
                        _badge_line(f"   └ {variant}", stn["status"])


def _badge_line(label, status):
    color = status_badge.badge_color(status)
    text = status_badge.badge_text(status)
    st.markdown(f"- {label} :{color}[{text}]")
