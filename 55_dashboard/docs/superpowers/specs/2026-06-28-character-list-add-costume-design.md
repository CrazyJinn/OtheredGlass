# 美术进度页：列表排版 + 添加节点入口（角色服装 / 场景）

> 日期：2026-06-28
> 范围：改造 55_dashboard 的「角色美术进度」页（page_overview）与「场景美术进度」页（page_scene_overview），把每个角色/地点的美术节点从 3 列网格改为每节点一行的列表；两页各加一个「添加」入口——角色的「＋添加服装」、地点的「＋添加场景」，通过 deeplink 唤起 VS Code 里的 Claude Code 按用户描述新建节点。

## 1. 背景与目标

两个进度页当前都把节点塞成 3 列按钮网格（`名字·状态`），节点名长短不一、各角色/地点节点数不同，导致网格参差、状态颜色丢失。用户要：

1. 每个角色/地点的节点改成规整的**一行一个**列表，状态有颜色区分。
2. 角色卡片加「＋添加服装」、地点卡片加「＋添加场景」：填一段自然语言描述 → 生成 deeplink → 在 VS Code 打开 Claude Code 按描述新建对应节点。

后台本身不建图节点（沿用现有约定：后台治理、Skills 生产）。deeplink 只预填 prompt，需用户在 VS Code 按回车执行（防注入，与现有「推进」按钮一致）。两页结构对称，本次一并改造。

## 2. 范围

**做**：
- page_overview `_render_char_row` 排版改造（3 列网格 → 每节点一行）
- page_scene_overview `_render_loc_row` 同法排版改造
- 新纯函数模块 `ui/components/label_text.py`（label→中文 + 角色/场景各自的排序 rank）
- 新通用组件 `ui/components/add_node_button.py`（popover，角色/场景复用）
- launch_button.py 新增 `build_add_costume_deeplink` + `build_add_scene_deeplink`
- 扩展 test_launch_button.py + 新增 test_label_text.py

**不做**：
- 「添加服装/场景」以外类型的添加入口（外貌/语言/SceneLayer 通常由生产链推导，无需手动添加）
- 后台直接写图节点（仍走 deeplink）

## 3. 共享：label→中文映射（新纯函数 `ui/components/label_text.py`）

无 streamlit 依赖，便于单测；两页复用：

```python
LABEL_CN = {
    "AppearanceStyle": "外貌风格",
    "LanguageStyle": "语言风格",
    "CostumeStyle": "着装",
    "DesignSheet": "设计图",
    "IllusDesign": "插画设计",
    "StandingIllustration": "立绘",
    "Scene": "场景",
    "SceneLayer": "图层",
}
CHAR_ORDER = ["AppearanceStyle", "LanguageStyle", "CostumeStyle",
              "DesignSheet", "IllusDesign", "StandingIllustration"]
SCENE_ORDER = ["Scene", "SceneLayer"]

def label_cn(label):
    return LABEL_CN.get(label, label)

def rank(label, order):
    return order.index(label) if label in order else 99
```

## 4. 角色美术页排版（page_overview `_render_char_row`）

```
container(border=True)
  顶部行 columns([3, 2]):
    左: **角色名**
    右: launch_button.render(char_id)
        [编辑角色]                     (现有)
        [＋添加服装] popover           (新增，见 §6)
  节点区:
    nodes = get_character_graph 的非 Character 节点
    nodes.sort(key=lambda n: (rank(n["label"], CHAR_ORDER), n.get("name") or ""))
    for n in nodes:
      row = columns([8, 3])
      左 row[0]: st.button(f"{label_cn(label)} · {name 或 id 末 6 位}",
                           key=f"prog_{id}", use_container_width=True)
                → 点击: session_state["_dialog_node"] = id; st.rerun()
      右 row[1]: st.markdown(f":{badge_color(status)}[● {badge_text(status)}]")
    无节点: st.caption("无美术节点")
  末尾(每次 render): 若 session_state["_dialog_node"] 存在 → 重开编辑弹窗（沿用现有机制）
```

状态徽章用 [status_badge.py](../../ui/components/status_badge.py) 的 `badge_color` / `badge_text`，借 Streamlit 的 `:color[text]` colored markdown 着色（颜色名 red/green/blue/orange/gray 与 `_COLOR` 一致）。左 button + 右着色徽章分列，是因为 button 内文本无法着色。

## 5. 场景美术页排版（page_scene_overview `_render_loc_row`）

与 §4 完全对称，把现有的 `_ORDER` 局部常量替换为 `label_text.rank(label, SCENE_ORDER)`：

```
container(border=True)
  顶部行 columns([3, 2]):
    左: **地点名**（有 description 则 caption）
    右: launch_button.render_scene(loc_id)
        [编辑地点]                     (现有)
        [＋添加场景] popover           (新增，见 §6)
  节点区:
    nodes = get_location_graph 的非 Location 节点
    nodes.sort(key=lambda n: (rank(n["label"], SCENE_ORDER), n.get("name") or ""))
    for n in nodes:
      row = columns([8, 3])
      左 row[0]: st.button(f"{label_cn(label)} · {name 或 id 末 6 位}",
                           key=f"sprog_{id}", use_container_width=True)
                → 点击: session_state["_dialog_node"] = id; st.rerun()
      右 row[1]: st.markdown(f":{badge_color(status)}[● {badge_text(status)}]")
    无节点: st.caption("无场景节点")
  末尾: _dialog_node 重开弹窗（与角色页共用 key，沿用现有机制）
```

## 6. 「添加」popover（新通用组件 `ui/components/add_node_button.py`）

角色「＋添加服装」与地点「＋添加场景」结构相同，抽一个参数化组件，传入标题、placeholder、deeplink 构造器：

```python
import streamlit as st

def render(entity_id, entity_name, title, placeholder, build_url, key_prefix):
    """通用添加 popover：填描述 → 「在 VS Code 创建」跳转。

    build_url: (entity_id, entity_name, description) -> deeplink str
    """
    with st.popover(title):
        desc = st.text_area("描述", key=f"{key_prefix}_desc_{entity_id}",
                            placeholder=placeholder)
        st.link_button("在 VS Code 创建",
                       build_url(entity_id, entity_name, desc),
                       use_container_width=True)
        st.caption("点击后在 VS Code 打开 Claude Code，需按回车执行（不自动提交）。")
```

调用方：
- 角色页：`add_node_button.render(char["id"], char.get("name",""), "＋ 添加服装", "如：冬季深色厚重大衣，军装风…", launch_button.build_add_costume_deeplink, "costume")`
- 场景页：`add_node_button.render(loc["id"], loc.get("name",""), "＋ 添加场景", "如：咖啡店的点餐台，午后暖光…", launch_button.build_add_scene_deeplink, "scene")`

- 描述存 `session_state[f"{key_prefix}_desc_{entity_id}"]`，每次 rerun link_button 的 URL 按当前描述重算（边输边更新）。
- 每张卡片一个独立 popover（key 带 entity_id 隔离）。
- 位置：卡片顶部行右侧列，与 [推进][编辑] 同组。

## 7. deeplink / prompt 设计（launch_button.py 新增两个函数）

### 7.1 `build_add_costume_deeplink(char_id, char_name, description)`

```python
def build_add_costume_deeplink(char_id, char_name, description):
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
```

### 7.2 `build_add_scene_deeplink(loc_id, loc_name, description)`

```python
def build_add_scene_deeplink(loc_id, loc_name, description):
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
```

### 7.3 skill gap 的处理（已确认：按描述建一个）

`char-costume-designer` 与 `scene-designer` 两个 skill 都是**事件/位置驱动**（输入仅 ID，扫未覆盖的事件/子空间自动生成），**都不吃自由文本描述**。本设计对两者统一采用「按描述建一个」：

- 用户描述不指望 skill 自动消费，而是作为 deeplink prompt 里的**自然语言需求指令**。
- VS Code 里的 Claude（主会话）收到 prompt 后理解意图，调对应 skill 或直接 MERGE 一个符合描述的节点（服装→CostumeStyle + has_costume；场景→Scene + has_scene），status=1。
- prompt 同时给出 skill 名 + 字段规范提示，引导 Claude 按规范建节点。
- 这与项目约定「编排 agent 不可靠、直调生产 skill 更稳」一致——不走 char-design / scene-design agent，直接指向对应生产 skill。

### 7.4 与现有「推进」按钮的区别

| 按钮 | prompt 目标 | 语义 |
|------|------------|------|
| 推进美术流程 | char-design agent | 按现有节点 status 推进整条链 |
| ＋添加服装 | char-costume-designer skill | 新建一套用户描述的服装 |
| 推进场景美术 | scene-design agent | 按现有节点 status 推进场景链 |
| ＋添加场景 | scene-designer skill | 新建一个用户描述的场景 |

## 8. 测试策略

| 对象 | 方式 | 用例 |
|------|------|------|
| `build_add_costume_deeplink` / `build_add_scene_deeplink` | 单测（扩 test_launch_button.py） | URL 编码正确；含中文/特殊字符（；空格引号）；空描述走 fallback；含 ID 与 name |
| label→中文 + rank | 单测（新 test_label_text.py） | 已知 label 中文正确；未知 label 原样返回；CHAR_ORDER / SCENE_ORDER 排序正确 |
| page_overview / page_scene_overview 列表渲染 | 手动验证 | 节点按序、同类多节点连续、点击进弹窗、状态颜色；两页对称 |

## 9. 验收标准

1. 角色美术进度页每个角色的美术节点以「一行一个」列表呈现，左侧「类型·名称」可点击进编辑弹窗，右侧带颜色状态徽章；节点按 外貌→语言→着装→设计图→插画→立绘 排序，多套着装连续。
2. 场景美术进度页每个地点的场景节点同样「一行一个」列表呈现；节点按 场景→图层 排序。两页结构对称。
3. 每张角色卡片顶部有「＋添加服装」、每张地点卡片顶部有「＋添加场景」按钮，点击弹出 popover；填描述后「在 VS Code 创建」的 deeplink 携带该描述。
4. 点击「在 VS Code 创建」在 VS Code 打开 Claude Code 标签页，预填 prompt 明确「为角色/地点 X 新增一套服装/一个场景：描述」，需手动按回车执行。
5. 空描述时 deeplink 仍可用（fallback 文案）。
6. 现有「推进」「编辑」按钮、编辑弹窗、审批流不受影响。
7. test_launch_button（含两个新函数）与 test_label_text 通过。
