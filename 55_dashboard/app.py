"""55_dashboard 入口：侧边栏模块导航 + 角色选择；主区域就地编辑。

导航层级：顶层模块（角色美术 / 场景美术）才跳转；
节点级操作（编辑、审批）都在角色美术模块内就地完成，不跳转。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 让 config/repo/... 可导入

import streamlit as st

from config import settings
from core.schema_loader import load_schema
from repo import graph_repo
from ui import page_overview, page_scene_overview, page_chapter_overview, page_approval, \
    page_narrative_approval, page_ambient_candidates

st.set_page_config(page_title="代恋 · 美术治理后台", layout="wide")

# 启动加载 Schema（带启动校验）
try:
    SCHEMA = load_schema(settings.SCHEMA_DIR, settings.TAG_LIB_PATH)
except Exception as e:
    st.error(f"Schema 加载失败：{e}")
    st.stop()

# 顶层模块导航（隔离远的管理域才用页面级切换）
_MODULES = ["角色美术", "场景美术", "剧情"]
if st.session_state.get("module") not in _MODULES:
    st.session_state["module"] = "角色美术"
module = st.sidebar.radio("模块", _MODULES, index=_MODULES.index(st.session_state["module"]))
st.session_state["module"] = module

# 当前模块的查看视图（节点编辑弹窗只在「角色进度/场景进度」里有意义）
if module == "场景美术":
    _views = ["场景进度", "审批中心"]
elif module == "剧情":
    _views = ["章节进度", "审批中心", "环境音候选"]
else:
    _views = ["角色进度", "审批中心", "叙事审批"]
view = st.sidebar.radio("查看", _views, horizontal=True)

# 切换模块/视图 = 离开节点编辑上下文 → 关闭节点编辑弹窗，避免无关 rerun 又把它重开
if st.session_state.get("_last_nav") != (module, view):
    st.session_state.pop("_dialog_node", None)
st.session_state["_last_nav"] = (module, view)

if module == "剧情":
    if view == "审批中心":
        page_approval.render()
    elif view == "环境音候选":
        page_ambient_candidates.render()
    else:
        page_chapter_overview.render(SCHEMA)
elif module == "场景美术":
    if view == "审批中心":
        page_approval.render()
    else:
        page_scene_overview.render(SCHEMA)
else:  # 角色美术
    if view == "审批中心":
        page_approval.render()
    elif view == "叙事审批":
        page_narrative_approval.render()
    else:
        page_overview.render(SCHEMA)

# 数据备份（侧边栏底部，全库 CSV）。两步法：点「生成备份」触发一次扫描存 session_state，
# 再用 download_button 下载——避免 download_button 的 data 在每次 rerun 都全库扫描。
with st.sidebar:
    st.divider()
    st.caption("数据备份")
    if st.button("生成备份", use_container_width=True):
        st.session_state.pop("_dialog_node", None)  # 侧边栏全局操作：关掉节点编辑弹窗
        try:
            csv_text, stats = graph_repo.export_csv_all()
            st.session_state["_backup_csv"] = csv_text
            st.session_state["_backup_stats"] = stats
            st.toast(f"备份已生成：{stats['nodes']} 节点 / {stats['relationships']} 边", icon="✅")
        except Exception:
            try:
                csv_text, stats = graph_repo.export_csv_all_pure()
                st.session_state["_backup_csv"] = csv_text
                st.session_state["_backup_stats"] = stats
                st.toast(f"APOC 不可用，已用兜底导出：{stats['nodes']} 节点 / {stats['relationships']} 边", icon="⚠️")
            except Exception as e2:
                st.error(f"备份失败：{e2}")
    backup = st.session_state.get("_backup_csv")
    if backup:
        from datetime import datetime
        fname = f"ProxyLove_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        st.download_button("下载 CSV", data=backup, file_name=fname,
                           mime="text/csv", use_container_width=True)
        st.caption(f"已就绪：{st.session_state.get('_backup_stats', {})}")
