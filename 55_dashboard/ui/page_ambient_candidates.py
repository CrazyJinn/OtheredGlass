"""环境音候选试听页：浏览 .tmp/ambient/ 的候选（ambient-sfx-designer 产出），
就地试听 + 选定 + 生成 finalize 继续指令（复制/一键唤起 Claude）。

不写图、不跑生产脚本（后台铁律）——选定只产出指令文本，执行仍在 skill 侧。
"""
import re
import urllib.parse
from pathlib import Path

import streamlit as st

from repo import graph_repo
from ui.components import launch_button

_ROOT = Path(__file__).resolve().parents[2]
_CAND_DIR = _ROOT / ".tmp" / "ambient"
_VSCODE = "vscode://anthropic.claude-code/open"
_CAND_RE = re.compile(r"^(?P<track>.+)_c(?P<n>\d+)(?:_.*)?\.wav$")


def _line_texts(node_ids: list) -> dict:
    """行 id → text（辅助显示；候选期行上还没 ambient_track，用节点 id 反查）。"""
    out = {}
    for nid in node_ids:
        try:
            node = graph_repo.get_node(nid)
            if node:
                out[nid] = node.get("text") or ""
        except Exception:
            pass
    return out


def render():
    st.subheader("环境音候选试听")
    st.caption("候选由 ambient-sfx-designer 产出到 `.tmp/ambient/`（用后清）。此处试听选定，"
               "生成 finalize 指令回 Claude 执行——页面本身不写图不跑生产。")

    if not _CAND_DIR.exists() or not list(_CAND_DIR.glob("*.wav")):
        st.info("当前无候选。触发 plot-design 单节聚焦（或直接跑 ambient-sfx-designer）"
                "产出候选后，此页自动出现内容。")
        return

    groups: dict = {}
    for w in sorted(_CAND_DIR.glob("*.wav")):
        m = _CAND_RE.match(w.name)
        if not m:
            continue
        groups.setdefault(m.group("track"), []).append((int(m.group("n")), w))

    # 行描述辅助（track 末段 = 行节点 id）
    texts = _line_texts([t.rsplit("-", 1)[-1] for t in groups])

    picks = {}
    for track, cands in groups.items():
        nid = track.rsplit("-", 1)[-1]
        desc = texts.get(nid, "（行已不在图上）")
        with st.expander(f"🔊 {desc}　`{track[-42:]}`", expanded=True):
            labels = {}
            for n, w in sorted(cands):
                label = f"c{n}"
                st.audio(str(w), format="audio/wav")
                labels[label] = w
            picks[track] = (st.radio("选定", list(labels), horizontal=True,
                                     key=f"pick_{track}"), labels, desc)

    st.divider()
    st.markdown("**选定汇总 → 生成继续指令**")
    picks_desc = "；".join(f"{desc} → {pick}" for track, (pick, _, desc) in picks.items())
    prompt = (f"执行环境音 finalize 并收尾（ambient-sfx-designer 段 3），选定结果：{picks_desc}。"
              "逐条按行语义判型（短事件=transition --cut 1.5 --fade 0.4；声景=ambience）finalize "
              "对应候选（.tmp/ambient/ 下各 track 的 _cN）到母带 15_声音/<stem>/<block>/<track>.wav，"
              "全部成功后写图（行节点 SET ambient_track + status=10，行 id=track 末段，"
              "不拷运行时副本——dashboard 试听读母带）、清理 .tmp/ambient。")
    st.code(prompt, language="text")
    if st.button("唤起 Claude 执行", type="primary"):
        st.markdown(f"[点击此链接唤起]({_VSCODE}?prompt={urllib.parse.quote(prompt)})")
        st.toast("已生成 deeplink，点击上方链接", icon="🔗")
