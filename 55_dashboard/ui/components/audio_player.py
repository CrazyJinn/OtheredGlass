"""声音审听组件：单 wav 试听（VoiceDesign 审批用）。

逐句音频审（LineAudio）已迁移到 script_jsonl_view.render_audio_review（读台词 JSONL 行级
audio 三态）；本组件只剩 render_wav 供 VoiceDesign 声音审（status=10）单文件试听 ref_audio。
"""
from pathlib import Path
import streamlit as st

from config import settings


def render_wav(audio_path):
    """单 wav 试听（VoiceDesign 审批用）：播放 ref_audio_path 指向的参考音频。"""
    if not audio_path:
        st.caption("⚠️ 该节点未填 ref_audio_path")
        return
    p = Path(audio_path)
    if not p.is_absolute():
        p = settings.PROJECT_ROOT / p
    if not p.exists():
        st.caption(f"参考音频不存在：{audio_path}")
        return
    st.audio(str(p), format="audio/wav")
