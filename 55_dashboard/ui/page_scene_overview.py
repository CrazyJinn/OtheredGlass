"""场景美术进度：按地点列出 + 点节点弹窗（dialog）编辑。

结构与 page_overview 对称：Location 代替 Character，get_location_graph 代替
get_character_graph。dialog 复用同一 session_state["_dialog_node"] key。
"""
import streamlit as st

from repo import graph_repo
from ui.components import launch_button, status_badge, label_text, add_node_button
from ui import page_node_editor


@st.dialog("节点编辑", width="large")
def _edit_dialog(schema, node_id):
    page_node_editor.render_editor(schema, node_id)
    st.divider()
    if st.button("关闭", use_container_width=True):
        st.session_state.pop("_dialog_node", None)
        st.rerun()


def render(schema):
    st.header("场景美术进度")
    locs = graph_repo.get_nodes("Location")
    # Location 无 priority，按名称排序
    locs = sorted(locs, key=lambda x: x.get("name") or x["id"])
    if not locs:
        st.caption("无地点节点")
        return
    for loc in locs:
        _render_loc_row(schema, loc)
    # 跨 rerun 保持 dialog（与角色美术页共用 _dialog_node）
    dn = st.session_state.get("_dialog_node")
    if dn:
        _edit_dialog(schema, dn)


def _render_loc_row(schema, loc):
    with st.container(border=True):
        top = st.columns([3, 2])
        top[0].write(f"**{loc.get('name', loc['id'])}**")
        if loc.get("description"):
            top[0].caption(loc["description"])
        with top[1]:
            launch_button.render_scene(loc["id"])
            if st.button("编辑地点", key=f"sedit_{loc['id']}"):
                st.session_state["_dialog_node"] = loc["id"]
                st.rerun()
            add_node_button.render(
                loc["id"], loc.get("name", ""),
                "＋ 添加场景", "如：咖啡店的点餐台，午后暖光…",
                launch_button.build_add_scene_deeplink, "scene",
            )
        g = graph_repo.get_location_graph(loc["id"])
        nodes = [n for n in g["nodes"] if n["label"] != "Location"]
        if not nodes:
            st.caption("无场景节点")
            return
        nodes.sort(key=lambda n: (label_text.rank(n["label"], label_text.SCENE_ORDER),
                                  n.get("name") or ""))
        for n in nodes:
            row = st.columns([8, 3])
            with row[0]:
                shown = n.get("name") or f"{n['id'][-6:]}"
                if st.button(f"{label_text.label_cn(n['label'])} · {shown}",
                             key=f"sprog_{n['id']}", use_container_width=True):
                    st.session_state["_dialog_node"] = n["id"]
                    st.rerun()
            with row[1]:
                color = status_badge.badge_color(n["status"])
                text = status_badge.badge_text(n["status"])
                st.markdown(f":{color}[● {text}]")
