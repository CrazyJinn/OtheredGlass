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
