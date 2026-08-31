"""审批中心：列出待审节点（status=10：通用/结构审/定稿审/逐句音频审），通过/驳回。

全图统一待审 10 → 批准 11 / 驳回 0。剧情产物：SecScript(10)=定稿审（渲染 台词.md 全文）、
LineAudio(10)=**逐句行节点**（按节聚合为一张「逐句音频审」卡：逐句试听 + 单句通过=11/驳回=0，
「节完成」= 全部行 11 的派生判断，无节级批准按钮）、Chapter(10)=结构审（渲染 brief_path 设计简报）。

VoiceDesign status=10 两态（由 candidates_path 区分）：
- 非空 = 候选待选——渲染 3 候选卡（ref + 3 情绪试听），「采用」固化候选（status 仍 10），
  隐藏「通过」（防未选先批）、保留「驳回」（三候选皆不理想→0 重做）。
- 空/缺 = 单 ref 待审——原单文件试听 + 通过/驳回（存量节点零迁移）。
"""
import streamlit as st

from config import settings
from repo import graph_repo
from core import approval, voice_candidates, script_lines as sl
from ui.components import image_viewer, status_badge, audio_player, script_lines_view, markdown_viewer


def _render_voice_candidates(node_id, manifest):
    """VoiceDesign 候选待选态：3 候选 ×（基线 ref + 3 情绪试听）+ 采用按钮。

    采用事务顺序：promote move（幂等，先行）→ update_node（写 ref_audio_path +
    candidates_path=None 删属性）→ cleanup 整删临时文件夹 → toast + rerun。
    """
    st.caption(f"instruct：{manifest.get('instruct', '')}")
    st.caption(f"ref_text：{manifest.get('ref_text', '')}")
    texts = manifest.get("audition_texts", {})
    cols = st.columns(len(manifest["candidates"]))
    for col, cand in zip(cols, manifest["candidates"]):
        with col:
            st.markdown(f"**候选 {cand.get('key')}**")
            st.caption("基线 ref")
            audio_player.render_wav(cand.get("ref"))
            for emo, wav in (cand.get("auditions") or {}).items():
                st.caption(f"🎭 {emo}：{texts.get(emo, '')}")
                audio_player.render_wav(wav)
            if st.button("采用", key=f"adopt_{node_id}_{cand.get('key')}"):
                props = voice_candidates.promote_candidate(
                    manifest, cand["key"], settings.PROJECT_ROOT
                )
                graph_repo.update_node(node_id, props)
                voice_candidates.cleanup_candidates_dir(manifest, settings.PROJECT_ROOT)
                # toast 而非 inline st.success：紧随的 st.rerun() 会丢弃本轮输出
                st.toast(f"已采用候选 {cand['key']}（status 仍 10，请二审）", icon="✅")
                st.rerun()
    st.caption("三个候选都不理想？驳回 → 0 重跑 char-voice-design 重新采样。")


def _render_lineaudio_groups(items):
    """LineAudio 逐句行节点按节聚合：每节一张「逐句音频审」卡（行级 11/0）。

    「节完成」= 全部行 status=11（派生判断）——全部通过后待审行消失，组卡随之消失，
    无节级批准按钮；整节驳回 = 该节 say 行全置 0（重配语义，台词不变）。
    """
    groups = {}  # sc_id -> {"sec_id", "name", "lines": [行]}
    for n in items:
        info = graph_repo.get_script_of_line(n["id"])
        if not info:
            continue
        g = groups.setdefault(info["sc_id"], {"sec_id": info["sec_id"], "name": info["sc_name"], "n": 0})
        g["n"] += 1
    for sc_id, g in groups.items():
        with st.container(border=True):
            st.write(f"**LineAudio · {g['name']}（逐句音频审）** · 待审行 {g['n']} 句")
            script_lines_view.render_audio_review(g["sec_id"], sc_id)
            if st.button("整节驳回（全部 say 行重配）", key=f"la_rej_sec_{sc_id}"):
                n = sl.reject_section(sl.get_lines(sc_id))
                # toast 而非 inline：紧随的 st.rerun() 会丢弃本轮输出
                st.toast(f"已整节驳回：{n} 行置 0（重配，台词与已产 wav 不变）", icon="❌")
                st.rerun()


def render():
    st.header("审批中心")
    pendings = graph_repo.get_pending_approvals()
    if not pendings:
        st.success("暂无待审节点")
        return
    labels = sorted({n["label"] for n in pendings})
    sel = st.selectbox("按类型筛选", ["全部"] + labels)
    items = [n for n in pendings if sel == "全部" or n["label"] == sel]
    # LineAudio 逐句行按节聚合渲染（不逐行出现）
    line_items = [n for n in items if n["label"] == "LineAudio"]
    if line_items:
        _render_lineaudio_groups(line_items)
    for n in items:
        if n["label"] == "LineAudio":
            continue
        full = graph_repo.get_node(n["id"]) or {}
        with st.container(border=True):
            # 显式标注审批类型：Chapter 结构审 / SecScript 定稿审 / VoiceDesign 声音审
            review_tag = ""
            if n["label"] == "Chapter" and n["status"] == 10:
                review_tag = "（结构审）"
            elif n["label"] == "SecScript" and n["status"] == 10:
                review_tag = "（定稿审）"
            elif n["label"] == "VoiceDesign" and n["status"] == 10:
                review_tag = "（声音审）"
            label_text = full.get("title") or full.get("name") or n["id"]
            st.write(f"**{n['label']}** · {label_text}{review_tag}")
            status_badge.render(n["status"])
            show_approve = True  # 候选待选态置 False（防未选先批）
            if n["label"] == "SecScript" and n["status"] == 10:
                # 定稿审：渲染 台词.md 全文（人读格式，review 对白质量；拆分进图在批准后）
                script_lines_view.render_script_md(full.get("script_path"), label_text)
            elif n["label"] == "Chapter" and n["status"] == 10:
                # 结构审：渲染设计简报（brief_path）
                markdown_viewer.render(full.get("brief_path"), "📑 章节设计简报")
            elif n["label"] == "VoiceDesign" and n["status"] == 10:
                if full.get("candidates_path"):
                    manifest = voice_candidates.load_manifest(
                        full["candidates_path"], settings.PROJECT_ROOT
                    )
                    if manifest:
                        _render_voice_candidates(n["id"], manifest)
                        show_approve = False
                    else:
                        st.warning(
                            "candidates_path 指向的 manifest 缺失/损坏——"
                            "请驳回后重跑 char-voice-design 重新生成候选"
                        )
                        show_approve = False
                else:
                    # 单 ref 待审（采用后/存量节点）：试听角色基线音色
                    audio_player.render_wav(full.get("ref_audio_path"))
            elif full.get("image_path"):
                image_viewer.render(full["image_path"])
            c1, c2 = st.columns(2)
            with c1:
                if show_approve and st.button("通过", key=f"ok_{n['id']}"):
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
