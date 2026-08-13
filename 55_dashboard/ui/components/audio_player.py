"""声音审听组件：逐句播放节定稿 YAML 的 voice wav + 显示 emotion/文本。

供审批中心 Section 声音审（status=32）使用。节级配音阶段 manifest.voices 尚未写
（章未合并），故直接按 say.voice 键拼 assets/voices/<key>.wav 路径播放，不依赖 manifest。
"""
from pathlib import Path
import streamlit as st
import yaml

from config import settings


def render(script_path):
    """逐句渲染节 YAML 的 say 行：who · emotion · text + 音频播放控件。缺音频标警告。"""
    p = Path(script_path)
    if not p.is_absolute():
        p = settings.PROJECT_ROOT / script_path
    if not p.exists():
        st.caption(f"剧本文件不存在：{script_path}")
        return
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        st.error(f"剧本 YAML 解析失败：{e}")
        return

    voices_dir = settings.PROJECT_ROOT / "99_game" / "assets" / "voices"
    total, missing = 0, 0
    for blk in data.get("scenes", []):
        scene_id = blk.get("id", "")
        with st.expander(f"场景段 {scene_id}（{blk.get('scene', '')}）", expanded=True):
            for line in blk.get("lines", []):
                if line.get("op") != "say":
                    continue
                total += 1
                who = line.get("who", "")
                emotion = line.get("emotion", "")
                text = line.get("text", "")
                voice = line.get("voice")
                head = f"**{who}**"
                if emotion:
                    head += f" `🎭{emotion}`"
                st.markdown(f"{head}：{text}")
                if voice:
                    wav = voices_dir / f"{voice}.wav"
                    if wav.exists():
                        st.audio(str(wav), format="audio/wav")
                    else:
                        st.caption(f"⚠️ 缺音频：{voice}.wav")
                        missing += 1
                else:
                    st.caption("⚠️ 该句未配音（无 voice 字段）")
                    missing += 1
    if total:
        st.caption(f"共 {total} 句台词，{missing} 句缺音频")
