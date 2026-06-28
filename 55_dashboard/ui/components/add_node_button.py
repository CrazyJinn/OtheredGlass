"""通用「添加节点」popover：填描述 → 生成 deeplink → 在 VS Code 创建。

角色「添加服装」与地点「添加场景」复用本组件，传入不同标题/placeholder/deeplink 构造器。
描述存 session_state，每次 rerun 按当前描述重算 link URL（边输边更新）。
"""
import streamlit as st


def render(entity_id, entity_name, title, placeholder, build_url, key_prefix):
    """渲染添加 popover。

    build_url: (entity_id, entity_name, description) -> deeplink str
    """
    with st.popover(title):
        desc = st.text_area("描述", key=f"{key_prefix}_desc_{entity_id}",
                            placeholder=placeholder)
        st.link_button("在 VS Code 创建",
                       build_url(entity_id, entity_name, desc),
                       use_container_width=True)
        st.caption("点击后在 VS Code 打开 Claude Code，需按回车执行（不自动提交）。")
