"""Markdown 文件渲染组件：读路径 → st.markdown（章节设计简报审批预览用）。"""
from pathlib import Path

import streamlit as st

from config import settings


def render(md_path, label=None):
    """渲染 markdown 文件内容（相对路径按项目根解析）。文件缺失时提示。"""
    if not md_path:
        return
    p = Path(md_path)
    if not p.is_absolute():
        p = settings.PROJECT_ROOT / p
    if not p.exists():
        st.caption(f"文件不存在：{md_path}")
        return
    if label:
        st.caption(label)
    st.markdown(p.read_text(encoding="utf-8"))
