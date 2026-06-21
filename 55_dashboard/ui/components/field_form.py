"""按 FieldDef.type 动态渲染表单，标签字段交 tag_picker。

所有可编辑字段都正确预填当前值；widget key 含 node_id，切换节点时刷新。
"""
from core.schema_loader import FieldDef
from ui.components import tag_picker
from core import status


def _render_field(field: FieldDef, current, tag_fields, gender, node_id):
    import streamlit as st
    from datetime import date
    name, ftype = field.name, field.type
    cur = current if current is not None else ""

    # 标签字段优先（在标签库里）：text_input 为主 + 标签库辅助
    tagdef = tag_fields.get(name) if tag_fields else None
    if tagdef is not None:
        return tag_picker.render(name, tagdef, cur, gender, node_id=node_id)

    # 只读字段
    if name in ("id", "prompt_path"):
        st.text_input(field.label_cn, value=str(cur), disabled=True)
        return cur

    if name in ("image_path", "image"):
        from ui.components import image_viewer  # lazy import
        image_viewer.render(cur)
        return cur

    # enum 词表：预填当前值
    if ftype == "enum" and name in status.ENUM_OPTIONS:
        opts = status.ENUM_OPTIONS[name]
        idx = opts.index(cur) if cur in opts else 0
        return st.selectbox(field.label_cn, options=opts, index=idx, key=f"en_{node_id}_{name}")

    if ftype == "int":
        return st.number_input(field.label_cn, value=int(cur) if str(cur).strip() else 0, step=1,
                               key=f"int_{node_id}_{name}")
    if ftype == "Date":
        try:
            d = date.fromisoformat(str(cur)) if cur else date.today()
        except (ValueError, TypeError):
            d = date.today()
        return st.date_input(field.label_cn, value=d, key=f"dt_{node_id}_{name}").isoformat()
    # 默认 string
    return st.text_area(field.label_cn, value=str(cur), key=f"str_{node_id}_{name}")


def render(node_def, tag_fields, node_data, gender=None):
    """渲染节点全部字段，返回 props dict。"""
    node_id = node_data.get("id", "")
    props = {}
    for f in node_def.fields:
        props[f.name] = _render_field(f, node_data.get(f.name), tag_fields, gender, node_id)
    return props
