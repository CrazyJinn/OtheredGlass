"""叙事审批：逐条审阅 nrt-narrative-grower 的剧情建议，通过即把 cypher 写入 Neo4j。

建议来自 02_剧情数据/<日期>_建议.json，每条含 check/priority/reason/content/cypher。
通过 → 单事务执行该条 cypher（多语句）→ 记 _reviewed.json；驳回 → 仅记录。
"""
import streamlit as st

from repo import graph_repo
from core import narrative_review

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_PRIORITY_BADGE = {"high": "🔴 high", "medium": "🟡 medium", "low": "🟢 low"}


def render():
    st.header("叙事审批")
    st.caption(
        "数据来自 nrt-narrative-grower（02_剧情数据）。"
        "通过即把该条 Cypher 写入 Neo4j，驳回则记录为不采纳；结果跨会话保留。"
    )

    suggestions = narrative_review.load_suggestions()
    if not suggestions:
        st.success("暂无待审叙事建议")
        return
    reviewed = narrative_review.load_reviewed()

    files = sorted({s["source_file"] for s in suggestions})
    fcol, pcol, hcol = st.columns([2, 1, 1])
    with fcol:
        sel_file = st.selectbox("来源文件", ["全部"] + files)
    with pcol:
        sel_prio = st.selectbox("优先级", ["全部", "high", "medium", "low"])
    with hcol:
        hide_reviewed = st.checkbox("隐藏已审")

    items = [
        s for s in suggestions
        if (sel_file == "全部" or s["source_file"] == sel_file)
        and (sel_prio == "全部" or s.get("priority") == sel_prio)
    ]
    if hide_reviewed:
        items = [s for s in items if s["key"] not in reviewed]
    items.sort(key=lambda s: (
        _PRIORITY_ORDER.get(s.get("priority"), 99), s["source_file"], s["index"],
    ))

    for s in items:
        _render_item(s, reviewed.get(s["key"]))


def _render_item(item, rec):
    prio = item.get("priority")
    badge = _PRIORITY_BADGE.get(prio, prio or "—")
    with st.container(border=True):
        st.write(f"**{badge}** · `{item.get('check', '')}`")
        st.caption(f"来源：{item['source_file']}  #{item['index']}")
        st.markdown(f"**建议**：{item.get('content', '')}")
        st.markdown(f"**依据**：{item.get('reason', '')}")
        with st.expander("查看 Cypher"):
            st.code(item.get("cypher", ""), language="cypher")

        status = rec.get("status") if rec else None
        if status == "approved":
            st.success("✅ 已写入数据库")
            return
        if status == "rejected":
            st.info("已驳回")
            return

        c1, c2 = st.columns(2)
        with c1:
            if st.button("通过（写入数据库）", key=f"ok_{item['key']}", type="primary"):
                try:
                    n = graph_repo.run_write_script(item.get("cypher", ""))
                except Exception as e:  # cypher 语法/约束错误：不标记，展示详情
                    st.toast(f"写入失败：{e}", icon="❌")
                    st.error(f"Cypher 执行失败：\n\n{e}")
                    return
                narrative_review.mark_reviewed(item["key"], "approved")
                # toast 而非 inline st.success：紧随的 st.rerun() 会丢弃本轮输出
                st.toast(f"已写入（{n} 条语句）", icon="✅")
                st.rerun()
        with c2:
            if st.button("驳回", key=f"no_{item['key']}"):
                narrative_review.mark_reviewed(item["key"], "rejected")
                st.toast("已驳回", icon="❌")
                st.rerun()
