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
from ui import page_overview, page_approval

st.set_page_config(page_title="他者之镜 · 美术治理后台", layout="wide")

# 启动加载 Schema（带启动校验）
try:
    SCHEMA = load_schema(settings.SCHEMA_DIR, settings.TAG_LIB_PATH)
except Exception as e:
    st.error(f"Schema 加载失败：{e}")
    st.stop()

# 顶层模块导航（隔离远的管理域才用页面级切换）
_MODULES = ["角色美术", "场景美术（TODO）"]
if st.session_state.get("module") not in _MODULES:
    st.session_state["module"] = "角色美术"
module = st.sidebar.radio("模块", _MODULES, index=_MODULES.index(st.session_state["module"]))
st.session_state["module"] = module

if module == "场景美术（TODO）":
    st.info(f"{module}：Schema 待定义，V1 暂未实现。")
elif module == "角色美术":
    view = st.sidebar.radio("查看", ["角色进度", "审批中心"], horizontal=True)
    if view == "审批中心":
        page_approval.render()
    else:
        page_overview.render(SCHEMA)
