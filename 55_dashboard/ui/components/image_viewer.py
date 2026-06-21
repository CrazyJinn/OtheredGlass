"""图片预览：缩略图 + 点击放大（dialog）。读 image_path（相对项目根）。"""
import streamlit as st
from pathlib import Path
from config import settings


def resolve_path(image_path):
    if not image_path:
        return None
    p = Path(image_path)
    if not p.is_absolute():
        p = settings.IMAGE_ROOT / p
    return p if p.exists() else None


def render(image_path):
    """原尺寸预览（保留兼容）。"""
    p = resolve_path(image_path)
    if p is None:
        st.info("图片未生成" if image_path else "无图片")
        return
    st.image(str(p))


def render_thumbnail(image_path, width=140, key=None):
    """卡片缩略图 + 「放大」按钮（点开 dialog 看大图）。无图显示占位。"""
    p = resolve_path(image_path)
    if p is None:
        st.caption("（暂无图）")
        return
    st.image(str(p), width=width)
    if st.button("🔍 放大", key=f"zoom_{key or image_path}"):
        _zoom_dialog(str(p))


@st.dialog("图片放大预览")
def _zoom_dialog(path):
    st.image(path)
