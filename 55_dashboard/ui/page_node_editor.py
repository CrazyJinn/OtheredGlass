"""节点编辑组件：就地渲染属性表单 + 保存（级联）+ 提交审批。

不独立成页——由角色详情页的右列调用，就地编辑、不跳转。
"""
import streamlit as st

from repo import graph_repo
from core import approval, cascade, status as status_mod
from ui.components import field_form, image_viewer, status_badge


def render_editor(schema, node_id):
    """在当前容器（右列）内渲染节点编辑面板。"""
    node = graph_repo.get_node(node_id)
    if not node:
        st.error("节点不存在")
        return
    label = node["label"]
    st.subheader(f"编辑：{label}")
    st.caption(f"id: {node_id}")
    # 场景节点显示所属地点（回溯 Location 名用于上下文）
    if label in ("Scene", "SceneLayer"):
        loc_id = graph_repo.get_upstream_location_id(node_id)
        if loc_id:
            loc = graph_repo.get_node(loc_id)
            if loc:
                st.caption(f"地点：{loc.get('name', loc_id)}")
    # 无 status 字段的节点（如 Character）不渲染状态徽章。用 is not None 而非真值判断：
    # status=0（待处理）是合法 falsy，真值判断会误隐藏美术节点的待处理状态。
    if node.get("status") is not None:
        status_badge.render(node["status"])

    if node.get("image_path"):
        image_viewer.render_thumbnail(node["image_path"], width=200, key=f"editor_{node_id}")

    node_def = schema.nodes.get(label)
    if node_def is None:
        st.warning(f"Schema 未定义 {label}（可能是预留节点）")
        return
    tag_fields = schema.tag_fields.get(label, {})
    gender = _lookup_gender(node_id)
    props = field_form.render(node_def, tag_fields, node, gender)

    if st.button("保存", type="primary", key=f"save_{node_id}"):
        graph_repo.update_node(node_id, props)
        revert = approval.on_edit(node.get("status", 0))
        if revert is not None:
            graph_repo.set_status(node_id, revert)
        affected = cascade.cascade_reset(node_id, graph_repo)
        # 用 toast 而非 inline st.info/st.success：紧随的 st.rerun() 会丢弃本轮
        # inline 输出，导致「保存后无反馈」。toast 由前端管理，跨 rerun 显示。
        for msg, icon in _save_toasts(revert, affected):
            st.toast(msg, icon=icon)
        st.rerun()

    if status_mod.can_submit(label, node.get("status", 0)):
        if st.button("提交审批", key=f"submit_{node_id}"):
            graph_repo.set_status(node_id, approval.submit(label, node["status"]))
            st.toast("已提交审批（status=10）", icon="📤")
            st.rerun()


def _save_toasts(revert, affected):
    """保存后应弹出的 toast 列表：(message, icon)。

    提取为纯函数以便单测：保证保存后总有即时反馈，避免重蹈「success+rerun 被吞」。
    """
    toasts = []
    if revert is not None:
        toasts.append((f"原已批准，已回退到 {revert}（待重做）", "ℹ️"))
    if affected:
        names = "、".join(n.label for n in affected)
        toasts.append((f"已保存，级联重置 {len(affected)} 个下游：{names}", "✅"))
    else:
        toasts.append(("已保存（无 sync 下游受影响）", "✅"))
    return toasts


def _lookup_gender(node_id):
    char_id = graph_repo.get_upstream_character_id(node_id)
    if not char_id:
        return None
    c = graph_repo.get_node(char_id)
    return c.get("gender") if c else None
