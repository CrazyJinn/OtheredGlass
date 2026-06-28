"""角色美术进度：按 priority 分组的角色列表 + 点节点弹窗（dialog）编辑。

dialog 用 session_state["_dialog_node"] 保持打开：弹窗内的删除/添加/保存触发 rerun
不会关闭弹窗，只有「关闭」按钮或切换节点才清状态。
"""
import streamlit as st

from repo import graph_repo
from ui.components import launch_button, status_badge, label_text, add_node_button
from ui import page_node_editor

_PRIORITY_ORDER = ["P0", "P1", "P2"]


@st.dialog("节点编辑", width="large")
def _edit_dialog(schema, node_id):
    page_node_editor.render_editor(schema, node_id)
    st.divider()
    if st.button("关闭", use_container_width=True):
        st.session_state.pop("_dialog_node", None)
        st.rerun()


def render(schema):
    st.header("角色美术进度")
    chars = graph_repo.get_nodes("Character")

    groups = {}
    for c in chars:
        p = c.get("priority") or "未分类"
        groups.setdefault(p, []).append(c)

    ordered = [p for p in _PRIORITY_ORDER if groups.get(p)] + \
              [p for p in groups if p not in _PRIORITY_ORDER]
    for prio in ordered:
        st.subheader(prio)
        for c in groups[prio]:
            _render_char_row(schema, c)

    # 跨 rerun 保持 dialog：每次 render 检查 _dialog_node，在则重新打开弹窗
    dn = st.session_state.get("_dialog_node")
    if dn:
        _edit_dialog(schema, dn)


def _render_char_row(schema, char):
    with st.container(border=True):
        top = st.columns([3, 2])
        top[0].write(f"**{char.get('name', char['id'])}**")
        with top[1]:
            launch_button.render(char["id"])
            if st.button("编辑角色", key=f"edit_{char['id']}"):
                st.session_state["_dialog_node"] = char["id"]
                st.rerun()
            add_node_button.render(
                char["id"], char.get("name", ""),
                "＋ 添加服装", "如：冬季深色厚重大衣，军装风…",
                launch_button.build_add_costume_deeplink, "costume",
            )
        g = graph_repo.get_character_graph(char["id"])
        nodes = [n for n in g["nodes"] if n["label"] != "Character"]
        if not nodes:
            st.caption("无美术节点")
            return
        nodes.sort(key=lambda n: (label_text.rank(n["label"], label_text.CHAR_ORDER),
                                  n.get("name") or ""))
        for n in nodes:
            row = st.columns([8, 3])
            with row[0]:
                shown = n.get("name") or f"{n['id'][-6:]}"
                if st.button(f"{label_text.label_cn(n['label'])} · {shown}",
                             key=f"prog_{n['id']}", use_container_width=True):
                    st.session_state["_dialog_node"] = n["id"]
                    st.rerun()
            with row[1]:
                color = status_badge.badge_color(n["status"])
                text = status_badge.badge_text(n["status"])
                st.markdown(f":{color}[● {text}]")
