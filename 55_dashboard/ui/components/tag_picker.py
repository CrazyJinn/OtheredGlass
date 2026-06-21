"""标签字段编辑：HTML tag-input 风格 + 组合选择器（复合维度）。

值按分号拆成 chip 展示，每个可删除；可自由输入添加，也可点选标签库。
复合维度（如 garment = 材质+颜色+类型）提供组合选择器：各维度选/填后一键组合成一个 chip。
"""


def merge_options(tagdef, gender):
    """合并公共 options 与对应性别的追加候选。"""
    opts = list(tagdef.get("options", []))
    key = "female" if gender == "女" else "male" if gender == "男" else None
    if key and key in tagdef:
        opts.extend(tagdef[key])
    return opts


def _grp_options(group, gender):
    opts = list(group.get("options", []))
    key = "female" if gender == "女" else "male" if gender == "男" else None
    if key and key in group:
        opts.extend(group[key])
    return opts


def _render_chips(tags, state_key):
    import streamlit as st
    if not tags:
        st.caption("（空）")
        return
    ncol = 4
    for r in range(0, len(tags), ncol):
        cols = st.columns(ncol)
        for c in range(ncol):
            idx = r + c
            if idx >= len(tags):
                break
            with cols[c]:
                t1, t2 = st.columns([5, 1])
                t1.write(tags[idx])
                if t2.button("×", key=f"del_{state_key}_{idx}", help="删除此项"):
                    tags.pop(idx)
                    st.rerun()


def _render_add(state_key, tags):
    """自由输入添加（整串，含标签库外的值）。"""
    import streamlit as st
    c1, c2 = st.columns([5, 1])
    new = c1.text_input("添加", key=f"new_{state_key}", label_visibility="collapsed",
                        placeholder="输入新项后点 ＋")
    if c2.button("＋", key=f"add_{state_key}", help="添加"):
        if new.strip():
            tags.append(new.strip())
            st.session_state.setdefault(f"_clear_{state_key}", []).append(f"new_{state_key}")
            st.rerun()


def _render_suggestions(opts, state_key, tags, multi):
    import streamlit as st
    ncol = min(len(opts), 5)
    for r in range(0, len(opts), ncol):
        cols = st.columns(ncol)
        for c in range(ncol):
            idx = r + c
            if idx >= len(opts):
                break
            with cols[c]:
                if st.button(opts[idx], key=f"sug_{state_key}_{idx}", use_container_width=True):
                    if multi:
                        tags.append(opts[idx])     # 多值：追加
                    else:
                        tags[:] = [opts[idx]]       # 单值：替换
                    st.rerun()


def _render_combine_picker(tagdef, state_key, tags, gender):
    """复合维度：各 group 维度选（标签库或自定义）→ 组合按钮拼接成一个 chip。"""
    import streamlit as st
    st.caption("组合添加（各维度选择或自定义，然后组合）：")
    chosen = {}
    cols = st.columns(len(tagdef["groups"]))
    for col, g in zip(cols, tagdef["groups"]):
        with col:
            opts = _grp_options(g, gender)
            sel = col.selectbox(g["label"], [""] + opts, key=f"csel_{state_key}_{g['key']}")
            cust = col.text_input(f"自定义{g['label']}", key=f"ccus_{state_key}_{g['key']}",
                                  label_visibility="collapsed", placeholder=f"自定义{g['label']}")
            chosen[g["key"]] = cust.strip() if cust.strip() else (sel if sel else "")
    if st.button("＋ 组合添加", key=f"combo_{state_key}", use_container_width=True):
        parts = [v for v in chosen.values() if v]
        if parts:
            tags.append("".join(parts))
            # 标记清空组合选择（render 开头处理），方便连续添加
            clear = st.session_state.setdefault(f"_clear_{state_key}", [])
            for g in tagdef["groups"]:
                clear.extend([f"csel_{state_key}_{g['key']}", f"ccus_{state_key}_{g['key']}"])
            st.rerun()


def render(field_name, tagdef, current_value, gender, node_id=""):
    """渲染 tag-input：chip 列表 + 添加 + 组合选择器/标签库建议，返回分号串。"""
    import streamlit as st
    label = tagdef.get("label", field_name)
    state_key = f"tags_{node_id}_{field_name}" if node_id else f"tags_{field_name}"
    if state_key not in st.session_state:
        st.session_state[state_key] = [t for t in str(current_value or "").split(";") if t]
    tags = st.session_state[state_key]

    # 处理待清空的 widget key（必须在 text_input/selectbox 实例化前执行，
    # 否则触发 "cannot be modified after widget instantiated"）
    for k in st.session_state.pop(f"_clear_{state_key}", []):
        st.session_state.pop(k, None)

    st.markdown(f"**{label}**")
    _render_chips(tags, state_key)
    _render_add(state_key, tags)

    if "combine" in tagdef:
        _render_combine_picker(tagdef, state_key, tags, gender)
    else:
        opts = merge_options(tagdef, gender)
        if opts:
            multi = tagdef.get("multi", False)
            st.caption("标签库（点击%s）：" % ("添加" if multi else "选择"))
            _render_suggestions(opts, state_key, tags, multi)

    return ";".join(tags)
