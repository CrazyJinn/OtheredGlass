"""「推进」按钮：生成 vscode:// deeplink 唤起 char-design agent。"""
import urllib.parse

VSCODE_HANDLER = "vscode://anthropic.claude-code/open"


def build_deeplink(char_id):
    prompt = f"使用 char-design agent 推进角色 {char_id} 的美术流程"
    return f"{VSCODE_HANDLER}?prompt={urllib.parse.quote(prompt)}"


def render(char_id, label="推进美术流程"):
    import streamlit as st
    st.link_button(label, build_deeplink(char_id))
