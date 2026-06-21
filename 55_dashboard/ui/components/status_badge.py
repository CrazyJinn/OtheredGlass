"""status 徽章：文本与颜色映射 + 渲染。"""
from core.status import STATUS_LABEL

_COLOR = {-1: "red", 0: "gray", 1: "blue", 2: "blue", 10: "orange", 11: "green"}


def badge_text(status):
    return STATUS_LABEL.get(status, str(status))


def badge_color(status):
    return _COLOR.get(status, "gray")


def render(status):
    import streamlit as st
    text = badge_text(status)
    st.markdown(f"**状态**：{text}")
