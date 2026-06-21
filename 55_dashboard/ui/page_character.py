"""角色详情：美术链 DAG + 节点卡片（缩略图）+ 右列就地编辑。"""
import streamlit as st

from repo import graph_repo
from ui.components import status_badge, launch_button, image_viewer
from ui import page_node_editor


def render(schema, char_id):
    char = graph_repo.get_node(char_id)
    if not char:
        st.error("角色不存在")
        return
    st.header(f"角色：{char.get('name', char_id)}")
    launch_button.render(char_id)

    g = graph_repo.get_character_graph(char_id)
    _draw_dag(g)
    st.divider()

    left, right = st.columns([2, 1])
    with left:
        st.subheader("美术链节点")
        for n in g["nodes"]:
            if n["label"] == "Character":
                continue
            full = graph_repo.get_node(n["id"])
            with st.container(border=True):
                if full.get("image_path"):
                    image_viewer.render_thumbnail(full["image_path"], width=140, key=n["id"])
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{n['label']}** · {full.get('name', n['id'])}")
                status_badge.render(n["status"])
                if st.button("编辑", key=f"ed_{n['id']}"):
                    st.session_state["selected_node"] = n["id"]
                    st.rerun()
    with right:
        selected = st.session_state.get("selected_node")
        if selected:
            page_node_editor.render_editor(schema, selected)
        else:
            st.info("点左侧节点的「编辑」按钮，在此修改属性。")


def _draw_dag(g):
    """生成 dot 字符串交 st.graphviz_chart（前端 viz.js 渲染，无需 graphviz 包）；失败回退树形。"""
    lines = ["digraph G {"]
    for n in g["nodes"]:
        lines.append(f'  "{n["id"]}" [label="{n["label"]}\\n{status_badge.badge_text(n["status"])}"];')
    for e in g["edges"]:
        lines.append(f'  "{e["from"]}" -> "{e["to"]}" [label="{e["type"]}"];')
    lines.append("}")
    try:
        st.graphviz_chart("\n".join(lines))
    except Exception:
        st.warning("DAG 图渲染失败，回退树形列表")
        for n in g["nodes"]:
            st.write(f"- {n['label']}（{status_badge.badge_text(n['status'])}）")
