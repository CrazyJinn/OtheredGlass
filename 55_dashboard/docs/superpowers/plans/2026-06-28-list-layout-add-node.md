# 美术进度页列表排版 + 添加节点入口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把角色/场景两个美术进度页的节点从 3 列网格改成每节点一行列表，并各加一个「添加服装/添加场景」popover，通过 deeplink 唤起 VS Code 里的 Claude Code 按用户描述新建节点。

**Architecture:** 新增纯函数 `label_text.py`（label→中文 + 排序 rank）和两个 deeplink 构造器（直调 `char-costume-designer` / `scene-designer` 生产 skill，把用户描述作为需求指令）；新增通用 `add_node_button.py` popover 组件供两页复用；改造 `page_overview._render_char_row` 与 `page_scene_overview._render_loc_row` 为逐行列表（左可点 button + 右着色状态徽章）。纯函数走 TDD 单测，UI 组件/页面走手动验证。

**Tech Stack:** Streamlit（>=1.40，popover 需 >=1.30）、Python 3.14、pytest。

## Global Constraints

- 测试在 `55_dashboard` 目录运行：`cd 55_dashboard && python -m pytest`（测试用 `from ui.components import ...`，依赖 cwd 在 sys.path）。
- 状态徽章着色用 Streamlit `:color[text]` colored markdown，颜色名取自 `ui/components/status_badge.py` 的 `_COLOR`（`red`/`gray`/`blue`/`orange`/`green`）。
- 后台不写图节点；deeplink 格式 `vscode://anthropic.claude-code/open?prompt=<URL-encoded prompt>`。
- Streamlit widget key 必须带 entity/node id 隔离；popover 描述存 `session_state`，每次 rerun 按当前描述重算 link URL。
- 纯函数（label_text、deeplink 构造器）走 TDD 单测；UI 组件与页面渲染走手动验证（spec §8 约定，streamlit 组件单测成本过高）。

---

### Task 1: label_text 纯函数（label→中文 + 排序 rank）

**Files:**
- Create: `55_dashboard/ui/components/label_text.py`
- Test: `55_dashboard/tests/test_label_text.py`

**Interfaces:**
- Produces: `LABEL_CN: dict[str,str]`、`CHAR_ORDER: list[str]`、`SCENE_ORDER: list[str]`、`label_cn(label:str)->str`、`rank(label:str, order:list[str])->int`

- [ ] **Step 1: Write the failing test**

Create `55_dashboard/tests/test_label_text.py`:

```python
from ui.components.label_text import (
    LABEL_CN, CHAR_ORDER, SCENE_ORDER, label_cn, rank,
)


def test_label_cn_known_labels():
    assert label_cn("AppearanceStyle") == "外貌风格"
    assert label_cn("LanguageStyle") == "语言风格"
    assert label_cn("CostumeStyle") == "着装"
    assert label_cn("DesignSheet") == "设计图"
    assert label_cn("IllusDesign") == "插画设计"
    assert label_cn("StandingIllustration") == "立绘"
    assert label_cn("Scene") == "场景"
    assert label_cn("SceneLayer") == "图层"


def test_label_cn_unknown_returns_raw():
    assert label_cn("SomethingElse") == "SomethingElse"


def test_rank_char_order():
    assert rank("AppearanceStyle", CHAR_ORDER) == 0
    assert rank("LanguageStyle", CHAR_ORDER) == 1
    assert rank("CostumeStyle", CHAR_ORDER) == 2
    assert rank("StandingIllustration", CHAR_ORDER) == 5


def test_rank_scene_order():
    assert rank("Scene", SCENE_ORDER) == 0
    assert rank("SceneLayer", SCENE_ORDER) == 1


def test_rank_unknown_is_high():
    assert rank("Unknown", CHAR_ORDER) == 99
    assert rank("Scene", CHAR_ORDER) == 99  # 场景 label 不在角色 order 里
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 55_dashboard && python -m pytest tests/test_label_text.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ui.components.label_text'`

- [ ] **Step 3: Write minimal implementation**

Create `55_dashboard/ui/components/label_text.py`:

```python
"""label → 中文显示名 + 排序 rank（纯函数，无 streamlit 依赖，便于单测）。

page_overview 用 CHAR_ORDER，page_scene_overview 用 SCENE_ORDER。
"""
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
CHAR_ORDER = [
    "AppearanceStyle", "LanguageStyle", "CostumeStyle",
    "DesignSheet", "IllusDesign", "StandingIllustration",
]
SCENE_ORDER = ["Scene", "SceneLayer"]


def label_cn(label):
    return LABEL_CN.get(label, label)


def rank(label, order):
    return order.index(label) if label in order else 99
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd 55_dashboard && python -m pytest tests/test_label_text.py -v`
Expected: PASS（5 项全过）

- [ ] **Step 5: Commit**

```bash
git add 55_dashboard/ui/components/label_text.py 55_dashboard/tests/test_label_text.py
git commit -m "feat(dashboard): add label_text pure helpers for node list rendering"
```

---

### Task 2: launch_button 新增两个 deeplink 构造器

**Files:**
- Modify: `55_dashboard/ui/components/launch_button.py`
- Test: `55_dashboard/tests/test_launch_button.py`

**Interfaces:**
- Consumes: `VSCODE_HANDLER`（已存在于 launch_button.py）
- Produces: `build_add_costume_deeplink(char_id:str, char_name:str, description:str)->str`、`build_add_scene_deeplink(loc_id:str, loc_name:str, description:str)->str`

- [ ] **Step 1: Write the failing tests**

Append to `55_dashboard/tests/test_launch_button.py`（保留现有测试，文件末尾追加）:

```python
import urllib.parse
from ui.components.launch_button import (
    VSCODE_HANDLER,
    build_add_costume_deeplink,
    build_add_scene_deeplink,
)


def _prompt_of(url):
    assert url.startswith(f"{VSCODE_HANDLER}?prompt=")
    return urllib.parse.unquote(url.split("prompt=", 1)[1])


def test_add_costume_deeplink_encodes_desc_and_targets_skill():
    url = build_add_costume_deeplink("abc123", "陆择", "冬季深色大衣；军装风")
    prompt = _prompt_of(url)
    assert "陆择" in prompt
    assert "abc123" in prompt
    assert "冬季深色大衣；军装风" in prompt
    assert "char-costume-designer" in prompt
    assert "has_costume" in prompt
    assert "status=1" in prompt


def test_add_costume_deeplink_empty_desc_uses_fallback():
    url = build_add_costume_deeplink("abc123", "陆择", "")
    prompt = _prompt_of(url)
    assert "无具体描述" in prompt
    assert "char-costume-designer" in prompt


def test_add_costume_deeplink_name_falls_back_to_id():
    url = build_add_costume_deeplink("abc123", "", "x")
    prompt = _prompt_of(url)
    assert "abc123" in prompt


def test_add_scene_deeplink_encodes_desc_and_targets_skill():
    url = build_add_scene_deeplink("loc1", "咖啡店", "点餐台，午后暖光")
    prompt = _prompt_of(url)
    assert "咖啡店" in prompt
    assert "loc1" in prompt
    assert "点餐台，午后暖光" in prompt
    assert "scene-designer" in prompt
    assert "has_scene" in prompt
    assert "status=1" in prompt


def test_add_scene_deeplink_whitespace_desc_uses_fallback():
    url = build_add_scene_deeplink("loc1", "咖啡店", "   ")
    prompt = _prompt_of(url)
    assert "无具体描述" in prompt
    assert "scene-designer" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd 55_dashboard && python -m pytest tests/test_launch_button.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_add_costume_deeplink'`

- [ ] **Step 3: Write minimal implementation**

Append to `55_dashboard/ui/components/launch_button.py`（在文件末尾追加；`urllib.parse` 已在文件顶部 import）:

```python
def build_add_costume_deeplink(char_id, char_name, description):
    """生成「为角色新增一套服装」的 deeplink，直调 char-costume-designer skill。

    description 作为给 VS Code Claude 的自然语言需求指令（skill 本身事件驱动、不吃自由文本）。
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd 55_dashboard && python -m pytest tests/test_launch_button.py -v`
Expected: PASS（现有 + 新增 5 项全过）

- [ ] **Step 5: Commit**

```bash
git add 55_dashboard/ui/components/launch_button.py 55_dashboard/tests/test_launch_button.py
git commit -m "feat(dashboard): add deeplink builders for adding costume/scene node"
```

---

### Task 3: add_node_button 通用 popover 组件

**Files:**
- Create: `55_dashboard/ui/components/add_node_button.py`

**Interfaces:**
- Consumes: 调用方传入 `build_url: (entity_id, entity_name, description)->str`（即 Task 2 的 deeplink 构造器）
- Produces: `render(entity_id:str, entity_name:str, title:str, placeholder:str, build_url:callable, key_prefix:str)->None`

> UI 组件（streamlit popover），按 spec §8 走手动验证，不写单测。

- [ ] **Step 1: Write implementation**

Create `55_dashboard/ui/components/add_node_button.py`:

```python
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
```

- [ ] **Step 2: Verify import works**

Run: `cd 55_dashboard && python -c "from ui.components import add_node_button; print(add_node_button.render)"`
Expected: 打印函数对象，无 ImportError

- [ ] **Step 3: Commit**

```bash
git add 55_dashboard/ui/components/add_node_button.py
git commit -m "feat(dashboard): add reusable add_node_button popover component"
```

---

### Task 4: page_overview 角色页改列表排版 + 添加服装入口

**Files:**
- Modify: `55_dashboard/ui/page_overview.py`（import 行 + `_render_char_row`）

**Interfaces:**
- Consumes: `label_text.{label_cn, rank, CHAR_ORDER}`、`status_badge.{badge_color, badge_text}`、`add_node_button.render`、`launch_button.build_add_costume_deeplink`

> UI 页面改造，手动验证。

- [ ] **Step 1: Update imports**

In `55_dashboard/ui/page_overview.py`, replace:

```python
from ui.components import launch_button, status_badge
```

with:

```python
from ui.components import launch_button, status_badge, label_text, add_node_button
```

- [ ] **Step 2: Replace `_render_char_row` with list layout**

In `55_dashboard/ui/page_overview.py`, replace the whole `_render_char_row` function with:

```python
def _render_char_row(schema, char):
    with st.container(border=True):
        top = st.columns([3, 2])
        top[0].write(f"**{char.get('name', char['id'])}**")
        with top[1]:
            launch_button.render(char["id"])
            if st.button("编辑角色", key=f"edit_{char['id']}"):
                st.session_state["_dialog_node"] = char["id"]
                st.rerun()
            add_node_button.render(
                char["id"], char.get("name", ""),
                "＋ 添加服装", "如：冬季深色厚重大衣，军装风…",
                launch_button.build_add_costume_deeplink, "costume",
            )
        g = graph_repo.get_character_graph(char["id"])
        nodes = [n for n in g["nodes"] if n["label"] != "Character"]
        if not nodes:
            st.caption("无美术节点")
            return
        nodes.sort(key=lambda n: (label_text.rank(n["label"], label_text.CHAR_ORDER),
                                  n.get("name") or ""))
        for n in nodes:
            row = st.columns([8, 3])
            with row[0]:
                shown = n.get("name") or f"{n['id'][-6:]}"
                if st.button(f"{label_text.label_cn(n['label'])} · {shown}",
                             key=f"prog_{n['id']}", use_container_width=True):
                    st.session_state["_dialog_node"] = n["id"]
                    st.rerun()
            with row[1]:
                color = status_badge.badge_color(n["status"])
                text = status_badge.badge_text(n["status"])
                st.markdown(f":{color}[● {text}]")
```

- [ ] **Step 3: Smoke-test the page imports**

Run: `cd 55_dashboard && python -c "from ui import page_overview; print(page_overview._render_char_row)"`
Expected: 打印函数对象，无 ImportError / 无语法错误

- [ ] **Step 4: Manual verification**

Run: `cd 55_dashboard && python -m streamlit run app.py`，打开 http://localhost:8501 → 角色美术 → 角色进度。逐项核对：
- 每个角色的节点一行一个，左列「类型·名称」按钮、右列 `● 状态`（着色：已完成=蓝、待处理=灰、待审=橙、批准=绿、需重做=红）
- 节点按 外貌→语言→着装→设计图→插画→立绘 排序，多套着装连续
- 点左列按钮进编辑弹窗（沿用旧弹窗）
- 顶部「＋ 添加服装」点击弹出 popover；填描述后「在 VS Code 创建」按钮 URL 含描述（浏览器底部状态栏看链接，或复制链接）
- 现有「推进」「编辑角色」仍可用

Expected: 全部符合

- [ ] **Step 5: Commit**

```bash
git add 55_dashboard/ui/page_overview.py
git commit -m "feat(dashboard): character page list layout + add-costume popover"
```

---

### Task 5: page_scene_overview 场景页改列表排版 + 添加场景入口

**Files:**
- Modify: `55_dashboard/ui/page_scene_overview.py`（import 行 + 删 `_ORDER` + `_render_loc_row`）

**Interfaces:**
- Consumes: `label_text.{label_cn, rank, SCENE_ORDER}`、`status_badge.{badge_color, badge_text}`、`add_node_button.render`、`launch_button.build_add_scene_deeplink`

> UI 页面改造，手动验证。

- [ ] **Step 1: Update imports**

In `55_dashboard/ui/page_scene_overview.py`, replace:

```python
from ui.components import launch_button, status_badge
```

with:

```python
from ui.components import launch_button, status_badge, label_text, add_node_button
```

- [ ] **Step 2: Remove the now-unused `_ORDER` constant**

In `55_dashboard/ui/page_scene_overview.py`, delete these two lines:

```python
# 节点网格排序：Scene 排在 SceneLayer 前
_ORDER = {"Scene": 0, "SceneLayer": 1}
```

- [ ] **Step 3: Replace `_render_loc_row` with list layout**

In `55_dashboard/ui/page_scene_overview.py`, replace the whole `_render_loc_row` function with:

```python
def _render_loc_row(schema, loc):
    with st.container(border=True):
        top = st.columns([3, 2])
        top[0].write(f"**{loc.get('name', loc['id'])}**")
        if loc.get("description"):
            top[0].caption(loc["description"])
        with top[1]:
            launch_button.render_scene(loc["id"])
            if st.button("编辑地点", key=f"sedit_{loc['id']}"):
                st.session_state["_dialog_node"] = loc["id"]
                st.rerun()
            add_node_button.render(
                loc["id"], loc.get("name", ""),
                "＋ 添加场景", "如：咖啡店的点餐台，午后暖光…",
                launch_button.build_add_scene_deeplink, "scene",
            )
        g = graph_repo.get_location_graph(loc["id"])
        nodes = [n for n in g["nodes"] if n["label"] != "Location"]
        if not nodes:
            st.caption("无场景节点")
            return
        nodes.sort(key=lambda n: (label_text.rank(n["label"], label_text.SCENE_ORDER),
                                  n.get("name") or ""))
        for n in nodes:
            row = st.columns([8, 3])
            with row[0]:
                shown = n.get("name") or f"{n['id'][-6:]}"
                if st.button(f"{label_text.label_cn(n['label'])} · {shown}",
                             key=f"sprog_{n['id']}", use_container_width=True):
                    st.session_state["_dialog_node"] = n["id"]
                    st.rerun()
            with row[1]:
                color = status_badge.badge_color(n["status"])
                text = status_badge.badge_text(n["status"])
                st.markdown(f":{color}[● {text}]")
```

- [ ] **Step 4: Smoke-test the page imports**

Run: `cd 55_dashboard && python -c "from ui import page_scene_overview; print(page_scene_overview._render_loc_row)"`
Expected: 打印函数对象，无 ImportError / 无语法错误

- [ ] **Step 5: Manual verification**

Run: `cd 55_dashboard && python -m streamlit run app.py` → 场景美术 → 场景进度。逐项核对：
- 每个地点的节点一行一个，左列「类型·名称」按钮、右列着色 `● 状态`
- 节点按 场景→图层 排序
- 点左列按钮进编辑弹窗
- 顶部「＋ 添加场景」popover 填描述后 URL 含描述
- 与角色页结构对称；现有「推进场景美术」「编辑地点」仍可用

Expected: 全部符合

- [ ] **Step 6: Commit**

```bash
git add 55_dashboard/ui/page_scene_overview.py
git commit -m "feat(dashboard): scene page list layout + add-scene popover"
```

---

### Task 6: 全量测试 + 回归验证

**Files:** 无（验证任务）

- [ ] **Step 1: Run full test suite**

Run: `cd 55_dashboard && python -m pytest -q`
Expected: 全部 PASS（原有 62 + Task 1 的 5 + Task 2 的 5 = 72）

- [ ] **Step 2: Full manual regression**

Run: `cd 55_dashboard && python -m streamlit run app.py`，过一遍两个模块：
- 角色美术：进度看板列表 + 添加服装 popover；审批中心；叙事审批不受影响
- 场景美术：场景进度列表 + 添加场景 popover；审批中心不受影响
- 编辑弹窗、保存级联、提交审批等既有流程正常

Expected: 既有功能无回归

- [ ] **Step 3: Final commit (if any stray changes)**

```bash
git status
# 若有未提交的零星改动：
git add -A && git commit -m "chore(dashboard): finalize list layout + add-node entry"
```

---

## Self-Review 记录

- **Spec coverage**：§3 label_text → Task 1；§4 角色页 → Task 4；§5 场景页 → Task 5；§6 通用 popover → Task 3；§7 两个 deeplink → Task 2；§8 测试 → Task 1/2 单测 + Task 4/5/6 手动验证；§9 验收 → Task 4/5/6 步骤覆盖。无遗漏。
- **Placeholder scan**：无 TBD/TODO；所有代码步骤含完整代码；UI 任务用手动验证步骤（非空泛"测试 UI"）。
- **Type consistency**：`rank(label, order)` 在 Task 1 定义、Task 4/5 调用一致；`build_add_costume_deeplink(char_id, char_name, description)` / `build_add_scene_deeplink(loc_id, loc_name, description)` 在 Task 2 定义、Task 3/4/5 调用签名一致；`add_node_button.render(entity_id, entity_name, title, placeholder, build_url, key_prefix)` 在 Task 3 定义、Task 4/5 调用参数顺序一致。
