"""审批中心：列出待审节点（status=10 通用/结构审 或 30 定稿审），通过/驳回。"""
import streamlit as st

from repo import graph_repo
from core import approval
from ui.components import image_viewer, status_badge


def render():
    st.header("审批中心")
    pendings = graph_repo.get_pending_approvals()
    if not pendings:
        st.success("暂无待审节点")
        return
    labels = sorted({n["label"] for n in pendings})
    sel = st.selectbox("按类型筛选", ["全部"] + labels)
    items = [n for n in pendings if sel == "全部" or n["label"] == sel]
    for n in items:
        full = graph_repo.get_node(n["id"]) or {}
        with st.container(border=True):
            # 显式标注审批类型：Chapter 结构审(10) / Section 定稿审(30)
            review_tag = ""
            if n["label"] == "Chapter" and n["status"] == 10:
                review_tag = "（结构审）"
            elif n["label"] == "Section" and n["status"] == 30:
                review_tag = "（定稿审）"
            label_text = full.get("title") or full.get("name") or n["id"]
            st.write(f"**{n['label']}** · {label_text}{review_tag}")
            status_badge.render(n["status"])
            if full.get("image_path"):
                image_viewer.render(full["image_path"])
            c1, c2 = st.columns(2)
            with c1:
                if st.button("通过", key=f"ok_{n['id']}"):
                    new_status = approval.approve(n["status"])
                    graph_repo.set_status(n["id"], new_status)
                    # toast 而非 inline st.success/st.warning：紧随的 st.rerun() 会丢弃本轮输出。
                    st.toast(f"已批准（status={new_status}）", icon="✅")
                    st.rerun()
            with c2:
                reason = st.text_input("驳回理由", key=f"r_{n['id']}")
                if st.button("驳回", key=f"no_{n['id']}"):
                    new_status = approval.reject(n["status"])
                    graph_repo.set_status(n["id"], new_status)
                    st.toast(f"已驳回（status={new_status}）" + (f"：{reason}" if reason else ""), icon="❌")
                    st.rerun()
