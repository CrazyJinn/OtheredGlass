"""「推进」按钮：生成 vscode:// deeplink 唤起 char-design agent。"""
import urllib.parse

VSCODE_HANDLER = "vscode://anthropic.claude-code/open"


def build_deeplink(char_id):
    prompt = f"使用 char-design agent 推进角色 {char_id} 的美术流程"
    return f"{VSCODE_HANDLER}?prompt={urllib.parse.quote(prompt)}"


def render(char_id, label="推进美术流程"):
    import streamlit as st
    st.link_button(label, build_deeplink(char_id))


def build_scene_deeplink(loc_id):
    prompt = f"使用 scene-design agent 推进地点 {loc_id} 的场景美术流程"
    return f"{VSCODE_HANDLER}?prompt={urllib.parse.quote(prompt)}"


def render_scene(loc_id, label="推进场景美术"):
    import streamlit as st
    st.link_button(label, build_scene_deeplink(loc_id))


def build_add_costume_deeplink(char_id, char_name, description):
    """生成「为角色新增一套服装」的 deeplink，直调 char-costume-designer skill。

    description 作为给 VS Code Claude 的自然语言需求指令
    （skill 本身事件驱动、不吃自由文本）。
    """
    name = char_name or char_id
    desc = (description or "").strip()
    if desc:
        prompt = (
            f"为角色 {name}（id={char_id}）新增一套服装。着装需求：{desc}。"
            f"请调用 char-costume-designer skill 创建：新建一个 CostumeStyle 节点"
            f"（name 用\"{name}-{desc[:12]}\"），按其字段规范"
            f"（outfit_style/garment/footwear/accessory_type）填写内容，"
            f"绑定 has_costume 边到该角色，status=1。"
        )
    else:
        prompt = (
            f"为角色 {name}（id={char_id}）新增一套服装（无具体描述，"
            f"请按角色设定与世界观自行设计一套合理的着装）。"
            f"调用 char-costume-designer skill 创建 CostumeStyle 节点 + has_costume 边，status=1。"
        )
    return f"{VSCODE_HANDLER}?prompt={urllib.parse.quote(prompt)}"


def build_add_scene_deeplink(loc_id, loc_name, description):
    """生成「为地点新增一个场景」的 deeplink，直调 scene-designer skill。"""
    name = loc_name or loc_id
    desc = (description or "").strip()
    if desc:
        prompt = (
            f"为地点 {name}（id={loc_id}）新增一个场景。场景需求：{desc}。"
            f"请调用 scene-designer skill 创建：新建一个 Scene 节点"
            f"（name 用\"{name}-{desc[:12]}\"），按其字段规范"
            f"（scene_type/time_of_day/weather/atmosphere/composition/lighting/color_direction 等）填写，"
            f"绑定 has_scene 边到该地点，status=1。"
        )
    else:
        prompt = (
            f"为地点 {name}（id={loc_id}）新增一个场景（无具体描述，"
            f"请按地点设定与事件自行推导一个视觉子空间）。"
            f"调用 scene-designer skill 创建 Scene 节点 + has_scene 边，status=1。"
        )
    return f"{VSCODE_HANDLER}?prompt={urllib.parse.quote(prompt)}"


def build_chapter_deeplink(ch_id, title=None):
    """生成「推进章节剧情」的 deeplink，调 plot-design agent。"""
    name = title or ch_id
    prompt = f"使用 plot-design agent 推进章节 {name}（id={ch_id}）的剧情创作流程"
    return f"{VSCODE_HANDLER}?prompt={urllib.parse.quote(prompt)}"


def render_chapter(ch_id, title=None, label="推进剧情创作"):
    import streamlit as st
    st.link_button(label, build_chapter_deeplink(ch_id, title))


def build_section_deeplink(sec_id, sec_label=None):
    """生成「推进此节」的 deeplink，调 plot-design agent 单节聚焦模式。

    与章级入口互补：章级负责 structurer 分节 / 结构审 / 全章发布 / 全量推进；
    节级只推进单节的产物链（提纲/定稿/配音）与该节关联立绘，不碰其他节、不发布。
    """
    name = sec_label or sec_id
    prompt = (
        f"使用 plot-design agent 推进小节 {name}（section id={sec_id}）的剧情创作。"
        f"单节聚焦：按该节产物链当前进度推进提纲/定稿/拆分选绘配音，定稿已批(SecScript=11)则推进该节关联立绘"
        f"（depicts 引用；选绘 uses 边由配音判断期建立）；"
        f"不碰其他节、不发布。"
    )
    return f"{VSCODE_HANDLER}?prompt={urllib.parse.quote(prompt)}"


def render_section(sec_id, sec_label=None, label="推进此节"):
    import streamlit as st
    st.link_button(label, build_section_deeplink(sec_id, sec_label))


def build_line_regen_deeplink(sec_id, lines):
    """生成「重生成被驳回句音频」的 deeplink，调 plot-design agent 单节聚焦。

    逐句音频审驳回后，dashboard 只标行节点 status=0，重生成走对话重推（行节点 id 寻址）。
    按行类型分流重做通道：say 台词行 → section-voice-publisher TTS 重配；
    环境音行（转场音效 / 氛围声景，不走 TTS）→ ambient-sfx-designer 声景重做。

    lines 元素支持两种形态：纯行 id 字符串（一律按 say 行处理，向后兼容）或
    {"id": ..., "kind": "say"|"sfx"}；两类并存时分组列出各自的通道指令。
    """
    say_ids, sfx_ids = [], []
    for item in lines:
        if isinstance(item, dict):
            (sfx_ids if item.get("kind") == "sfx" else say_ids).append(item.get("id", ""))
        else:
            say_ids.append(item)
    parts = []
    if say_ids:
        parts.append(
            f"以下 say 台词行请调 section-voice-publisher 重配（voice_bundler tasks-from-graph "
            f"--nodes 指定行，emotion/tts_text/clone_mode/选绘 stand 重新判别，portrait_binder "
            f"apply 重建 uses 边）：{'、'.join(say_ids)}"
        )
    if sfx_ids:
        parts.append(
            f"以下环境音行（转场音效/氛围声景，不走 TTS）请调 ambient-sfx-designer 重做声景"
            f"（ambient_tasks.py 按行 kind 分流实录/生成通道，覆盖旧 wav）：{'、'.join(sfx_ids)}"
        )
    prompt = (
        f"使用 plot-design agent 推进小节（section id={sec_id}）的音频重做。"
        f"单节聚焦：该节 LineAudio 逐句音频审驳回了以下行节点。"
        + "".join(p + "。" for p in parts)
        + "其余已通过行不要重做。"
    )
    return f"{VSCODE_HANDLER}?prompt={urllib.parse.quote(prompt)}"


def render_regen_lines(sec_id, lines, label="重生成被驳回的音频"):
    import streamlit as st
    st.link_button(label, build_line_regen_deeplink(sec_id, lines))
