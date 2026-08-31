"""剧情章节进度：列出 Chapter + 分节编排/立绘缺口 + 节级台词预览 + 审批。

结构与 page_scene_overview 对称：Chapter 代替 Location，get_chapter_graph 代替
get_location_graph。dialog 复用同一 session_state["_dialog_node"] key（点 Section 行也进同
一节点编辑器——Section/SecOutline/SecScript/LineAudio 均被 schema_loader 自动注册）。

Section 是纯编排容器（无 status），节级进度看**产物链**：
Section→has_outline→SecOutline(提纲)→produces→SecScript(定稿)→produces→LineAudio(逐句台词行)。
节完成 = SecOutline=1 ∧ SecScript=11 ∧ 该节全部行 LineAudio=11（派生判断；行状态聚合显示瓶颈值）。

节级预览渲染各 SecScript.script_path 指向的 **台词.md**（人读定稿格式）——review 对白质量，
区别于美术节点审批（看图片）。Chapter 审批按钮 status=10→11（结构审通过，卡片内渲染
brief_path 设计简报）/→0（驳回重做）；SecScript 定稿审（审 md）与 LineAudio 逐句音频审（按节
聚合）走审批中心（page_approval）。**人工微调回路**：用户直接编辑 台词.md 单句后点「重新提交
审批」（仅 SecScript 0/1/11→10，**不动行节点**；重批后 section-voice-publisher 重拆，text_sha1
匹配的行原样保留审批结果，只有被改句重配）——不经 dialoguer，手改不丢。
"""
import streamlit as st

from config import settings
from repo import graph_repo
from core import approval
from ui.components import launch_button, status_badge, script_lines_view, markdown_viewer
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
    """从章节子图取 Section 列表，按 section_no 排序，附产物链状态与定稿路径。

    Section 无 status（纯编排容器），节级进度看产物链：
    has_outline→SecOutline.status / SecOutline-produces→SecScript.status /
    SecScript-produces→LineAudio 行（1:N）——行状态聚合为瓶颈值（min：-1 < 0 < 10 < 11），
    无行视为 None。subgraph 的 nodes 只含 id/label/status/name，节编排字段与
    script_path 逐个 get_node 补全。
    """
    nodes_by_id = {n["id"]: n for n in g["nodes"]}
    ol_of = {}     # sec_id -> ol_id（has_outline）
    lines_of = {}  # sc_id -> [line_id]（produces：SecScript→LineAudio 1:N）
    sc_of = {}     # ol_id -> sc_id（produces：SecOutline→SecScript）
    for e in g["edges"]:
        if e["type"] == "has_outline":
            ol_of[e["from"]] = e["to"]
        elif e["type"] == "produces":
            frm = e["from"]
            if frm in nodes_by_id and nodes_by_id[frm]["label"] == "SecScript":
                lines_of.setdefault(frm, []).append(e["to"])
            else:
                sc_of[frm] = e["to"]

    secs = [n for n in g["nodes"] if n["label"] == "Section"]
    out = []
    for s in secs:
        full = graph_repo.get_node(s["id"]) or {}
        no = full.get("section_no")
        ol_id = ol_of.get(s["id"])
        sc_id = sc_of.get(ol_id) if ol_id else None
        line_ids = lines_of.get(sc_id, []) if sc_id else []
        statuses = [nodes_by_id[lid]["status"] for lid in line_ids if lid in nodes_by_id
                    and nodes_by_id[lid]["status"] is not None]
        sc_full = (graph_repo.get_node(sc_id) or {}) if sc_id else {}
        out.append({
            "id": s["id"],
            "_full": full,
            "_no": no if no is not None else 9999,
            "ol_status": nodes_by_id[ol_id]["status"] if ol_id in nodes_by_id else None,
            "sc_id": sc_id,
            "sc_status": nodes_by_id[sc_id]["status"] if sc_id in nodes_by_id else None,
            "vo_count": len(statuses),
            "vo_status": min(statuses) if statuses else None,  # 瓶颈：任一行未就绪即该值
            "script_path": sc_full.get("script_path"),
        })
    out.sort(key=lambda s: (s["_no"], s["id"]))
    return out


def _section_done(s):
    """节产物链就绪 = SecOutline=1 ∧ SecScript=11 ∧ 该节全部台词行 LineAudio=11（派生判断）。"""
    return s["ol_status"] == 1 and s["sc_status"] == 11 and s["vo_count"] > 0 and s["vo_status"] == 11


def _render_product_chain(s):
    """产物链三段徽章：提纲 / 定稿 / 音频（逐句行聚合瓶颈值，附行数；无行显示 —）。"""
    parts = []
    for label, st_val in (("提纲", s["ol_status"]), ("定稿", s["sc_status"]), ("音频", s["vo_status"])):
        if st_val is None:
            parts.append(f"{label}：—")
        else:
            color = status_badge.badge_color(st_val)
            text = status_badge.badge_text(st_val)
            suffix = f"（{s.get('vo_count', 0)} 行）" if label == "音频" else ""
            parts.append(f"{label}：:{color}[{text}]{suffix}")
    st.markdown(" · ".join(parts))


def _render_section_row(s, ch_status):
    """单节状态行 + 节级推进入口（显眼展示，区别于折叠的编排子图）。

    ch_status=11 时：有待审项（SecScript/LineAudio=10）给审批指引，未全就绪给「推进此节」
    （plot-design 单节聚焦：按产物链当前段推进）；ch_status≠11 时提示待章结构审批。
    """
    full = s["_full"]
    title = full.get("title") or s["id"]
    cols = st.columns([3, 2, 2])
    cols[0].markdown(f"**第{s['_no']}节 · {title}**")
    with cols[1]:
        _render_product_chain(s)
    with cols[2]:
        if ch_status == 11:
            if s["sc_status"] == 10:
                st.caption("定稿待审 → 审批中心")
            elif s["vo_status"] == 10:
                st.caption("音频待审 → 审批中心")
            elif not _section_done(s):
                launch_button.render_section(s["id"], f"第{s['_no']}节 · {title}")
        else:
            st.caption("待章结构审批")
        # 人工微调回路：直接编辑 台词.md 后重新送审（不经 dialoguer，手改不丢）。
        # 只置 sc→10、不动行节点——重批后重拆按 text_sha1 恢复未变句审批结果，只重配被改句。
        # 显示条件含驳回后的 0——否则驳回态手改会被 plot-design 触发的 dialoguer 整篇覆盖。
        if ch_status == 11 and s.get("script_path") and s["sc_status"] in (0, 1, 11):
            if st.button("重新提交审批", key=f"resub_{s['id']}",
                         help="直接编辑 台词.md 改单句后点此重审：仅 SecScript→10（行节点不动）。"
                              "重批后「推进此节」重拆：未变句审批结果原样保留，只有被改句重配。"
                              "注意：点「推进此节」在 sc=0/1 时会让 dialoguer 整篇重写覆盖手改。"):
                graph_repo.set_status(s["sc_id"], approval.resubmit("SecScript", s["sc_status"]))
                st.toast("已重新提交定稿审（SecScript=10）；重批后重拆只重配被改句，未变句审批结果保留",
                         icon="🔁")
                st.rerun()


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

        # 审批按钮（status=10 结构审，先渲染设计简报）/ 生产提示（status=11）
        if status == 10:
            with st.expander("📑 章节设计简报（结构审对象）", expanded=True):
                markdown_viewer.render(ch.get("brief_path"))
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
            done = [s for s in sections if _section_done(s)]
            if sections and len(done) == len(sections):
                st.info(
                    "全章各节产物就绪（提纲/定稿/配音均批）。下方「立绘缺口」全部就绪后即可发布——"
                    "chapter-publisher 由你直接触发（不经 plot-design），不自动发布。"
                )
            else:
                st.info(
                    f"结构已批（11），节级生产中：{len(done)}/{len(sections)} 节产物就绪。"
                    "在各节点「推进此节」单独推进，或点上方「推进剧情创作」全量推进。"
                )

        # 各节状态 + 节级推进入口（以小节为载体：每节显眼展示状态与推进/审批入口）
        if sections:
            st.markdown("**各节进度**")
            for s in sections:
                _render_section_row(s, status)

        # 各节台词预览（核心：review 对白质量）——渲染 SecScript.script_path 指向的 台词.md
        for s in sections:
            sp = s.get("script_path")
            if sp:
                script_lines_view.render_script_md(
                    sp, f"第{s['_no']}节 · {s['_full'].get('title') or s['id']}")

        # 编排子图：has_section→Section→contains→Scene→depicts→立绘缺口
        _render_chapter_subgraph(g, sections)


def _render_chapter_subgraph(g, sections):
    """渲染 has_section→Section→contains→Scene→depicts→IllusDesign→expands_to→立绘缺口（含就绪计数）。

    节级状态与推进入口在 _render_section_row（显眼行）展示；本函数只画 Scene/立绘 子图徽章。
    """
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
        with st.expander(f"第{s['_no']}节 · {title}（场景/立绘）", expanded=False):
            for label, st_val in (("提纲", s["ol_status"]), ("定稿", s["sc_status"]), ("音频", s["vo_status"])):
                _badge_line(label, st_val)
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
    if status is None:
        st.markdown(f"- {label} :gray[未创建]")
        return
    color = status_badge.badge_color(status)
    text = status_badge.badge_text(status)
    st.markdown(f"- {label} :{color}[{text}]")
