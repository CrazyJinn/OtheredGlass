# 角色美术治理后台（55_dashboard）设计文档

> 日期：2026-06-17
> 范围：为「他者之镜」Neo4j 图数据库搭建一个管理后台，V1 聚焦角色美术生产链的治理——浏览、属性编辑、审批、sync 级联。

---

## 1. 背景与目标

项目「他者之镜」用 Neo4j 存储叙事与美术数据，目前完全由文档 + Claude Skills 驱动生产，缺少人工治理界面。本后台提供：

- **浏览**：角色及其美术生产链的进度总览与 DAG 详情。
- **编辑**：修改每个节点的属性（含受控标签）。
- **审批**：对美术生产节点走 10 待审 → 11 批准 / → 0 重做。
- **级联**：保存属性后，沿 `sync=true` 边顺序重置下游节点 status。

后台是**独立 Python 应用直连 Neo4j**，与现有 Claude Skills 共享同一数据库——Skills 继续负责自动化生产（组装 prompt、调 OfoxAI 出图、推进 status 0→1→2），后台负责人工治理（编辑/审批/级联/预览）。两者通过 `status` 字段协作。

---

## 2. 已确认的核心约束

| 维度 | 决策 |
|------|------|
| 技术形态 | Streamlit 直连 Neo4j（`neo4j` python driver） |
| V1 范围 | `Character` + 美术生产链 6 节点；叙事其他（Event/Location/Info）与剧情、场景美术**预留 + TODO**，不实现 |
| 保存后级联 | 仅沿 `sync=true` 边 BFS 重置下游 `status=-1`（作废重做）；**不自动重新出图**，重出图仍由 Skills 按 status 推进 |
| 编辑已批准节点 | 编辑 `status=11` 的节点 → 自身回退到 **0（重做）**；下游由 cascade 标 **-1** |
| 审批职责切分 | 节点编辑器管「改属性 + submit」；审批中心管「approve / reject」 |
| DAG 展示 | `st.graphviz_chart`；保留树形展开（expander）作备选 |
| Schema 来源 | 字段定义解析自 `Schema/*.md`；标签词表读 `标签库.json`；status 流转与 enum 词表在 `status.py` 显式定义 |
| 操作入口 | 节点/角色提供「推进」按钮，经 `vscode://anthropic.claude-code/open` deeplink 预填 prompt 唤起 **char-design agent**（角色级编排，自动从图恢复状态、按依赖调度 skill）；后台本身不出图 |

---

## 3. 架构总览

### 3.1 项目落位

`55_dashboard/`。标签库 `标签库.json` 从 `55_manage/` 迁入 `55_dashboard/config/`（后台自包含），并同步更新 [Schema/角色美术.md](../../00_init/Schema/角色美术.md) 中两处引用链接。

### 3.2 目录结构

```
55_dashboard/
├── app.py                  # Streamlit 入口：侧边栏导航 + 页面路由
├── config/
│   ├── settings.py         # Neo4j 连接配置、Schema/标签库/图片根路径
│   └── 标签库.json          # 迁自 55_manage/
├── repo/
│   ├── neo4j_conn.py       # driver 单例（env 读 URI/账号）
│   └── graph_repo.py       # 节点/边读写 Cypher（唯一碰数据库的地方）
├── core/
│   ├── schema_loader.py    # 解析 Schema/*.md + 标签库.json → SchemaDef
│   ├── status.py           # 各节点 status 枚举、流转规则、enum 词表
│   ├── cascade.py          # sync BFS 级联（重置下游 status=-1 作废重做）
│   └── approval.py         # 审批状态机 + 下游推进前置校验
├── ui/
│   ├── page_overview.py        # 进度看板
│   ├── page_character.py       # 角色详情（美术链 DAG）
│   ├── page_node_editor.py     # 节点编辑器
│   ├── page_approval.py        # 审批中心
│   └── components/
│       ├── tag_picker.py       # 标签选择（读标签库.json）
│       ├── field_form.py       # 按字段类型动态渲染表单
│       ├── image_viewer.py     # 图片预览（读 image_path）
│       ├── status_badge.py     # status 徽章
│       └── launch_button.py    # 「推进」deeplink 按钮（唤起 char-design agent）
└── requirements.txt
```

### 3.3 分层职责（单向依赖：ui → core → repo）

| 层 | 职责 | 不做什么 |
|----|------|---------|
| `repo` | 封装 neo4j-driver，所有 Cypher 读写、连接管理 | 不含业务逻辑 |
| `core` | 级联引擎、审批状态机、Schema 加载、status 规则 | 不渲染 UI，不耦合 Streamlit |
| `ui` | 页面与组件，把用户操作翻译成 core 调用 | 不写 Cypher，不直接碰 driver |

### 3.4 数据流

`UI 操作 → core（级联/审批/校验）→ repo（Cypher）→ Neo4j`。
`SchemaDef` 由 `schema_loader` 启动时加载并缓存，供 UI 动态生成表单、供 core 校验字段与 status 合法值。

### 3.5 技术依赖与运行

依赖：`streamlit`、`neo4j`（driver）、`pydantic`（SchemaDef/节点模型校验）、`pillow`（图片预览）、`pandas`（表格）。
配置：`.env`（`NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`）。
运行：`streamlit run 55_dashboard/app.py`。

---

## 4. 数据访问层 + Schema 加载

### 4.1 数据访问（repo 层）

`neo4j_conn.py`：driver 单例，从环境变量读连接信息，复用 Skills 连的同一 Neo4j 实例。

`graph_repo.py`——**唯一写 Cypher 的地方**：

| 方法 | 用途 |
|------|------|
| `get_node(label, id)` / `get_nodes(label)` | 取单节点 / 列表 |
| `get_character_graph(char_id)` | 取角色 + 全部美术链节点与边（角色详情页用） |
| `get_sync_downstream(id)` | 取该节点**一跳内** `sync=true` 出边指向的直接下游（级联 BFS 在 `cascade.py` 中迭代展开，遇 `sync=false` 自然不再返回） |
| `update_node(id, props)` | 更新节点属性 |
| `set_status(id, status)` / `set_status_batch(ids, status)` | 改 status（单个 / 批量） |
| `get_pending_approvals()` | 取 `status=10` 的待审节点 |

### 4.2 Schema 动态加载（schema_loader）

"Schema 驱动"核心：**节点字段定义不硬编码，启动时从现有文档解析**。三类来源分工：

| 数据 | 来源 | 加载方式 |
|------|------|---------|
| 字段定义（字段名/中文/类型/必填） | `00_init/Schema/*.md` 节点表格 | 解析 markdown 表格 → `FieldDef` |
| 标签词表（受控选项、复合维度、性别差异） | `55_dashboard/config/标签库.json` | 直接读 JSON |
| status 流转规则 + enum 选项 | 不解析，`core/status.py` 显式定义 | 业务规则，非数据 |

合并产物：`SchemaDef = {label: NodeDef{fields[], tag_fields{}}}`。

加载时做**启动校验**：`.md` 表格列不符合预期格式（字段/中文/类型/必填）即报错，避免格式漂移导致静默解析错误。

> status/enum 不解析 .md 的理由：它们在 .md 中是散文式说明，格式不稳定且属业务规则。显式定义更可靠，改动时也明确。

### 4.3 字段类型 → UI 渲染映射

`field_form.py` 按 `FieldDef.type` + 是否在 `tag_fields` 中选择组件：

| 判定 | UI 组件 |
|------|---------|
| 在标签库.json 中 | `tag_picker` |
| `string` | `text_area` |
| `int` | `number_input` |
| `enum`（gender / Event.type / knowledge_level） | `selectbox`（选项来自 `status.py` 显式词表） |
| `Date` | `date_input` |
| `image_path` / `image` | `image_viewer`（只读预览） |
| `prompt_path` | 只读文件链接 |
| `id` | 只读 |

---

## 5. 级联引擎 + 审批状态机

### 5.1 级联引擎 `cascade.py`

保存属性后触发。沿 `sync=true` 出边做 BFS，把可达下游 `status` 重置为 `-1`（作废重做），遇 `sync=false` 阻断：

```python
def cascade_reset(changed_id) -> list[CascadedNode]:
    queue, visited, result = [changed_id], set(), []
    while queue:
        cur = queue.pop(0)
        if cur in visited:
            continue
        visited.add(cur)
        for d in repo.get_sync_downstream(cur):   # 仅 sync=true 出边的下游
            if d.id not in visited:
                result.append(d)                    # 记录受影响节点 + BFS 层级
                queue.append(d.id)
    repo.set_status_batch([n.id for n in result], -1)
    return result        # 返回给 UI 展示级联路径
```

- **被编辑节点自身不改 status**（只改属性），仅重置下游；例外见 5.3。
- `Character` 无 status 字段，作为触发源只传播、不重置。
- 返回结果带 BFS 层级，UI 按层级展示级联路径（即「顺序更新」的视觉体现）。
- 用 `visited` 防环（DAG 本身无环，保险起见）。

**sync 边清单**（角色美术链）：

| 边 | 方向 | sync | 级联 |
|----|------|------|------|
| has_appearance | Character → AppearanceStyle | true | 传播 |
| has_voice_style | Character → LanguageStyle | true | 传播 |
| has_costume | Character → CostumeStyle | true | 传播 |
| produces | AppearanceStyle → DesignSheet | true | 传播 |
| produces | DesignSheet → IllusDesign | true | 传播 |
| outfit_for | CostumeStyle → IllusDesign | true | 传播 |
| expands_to | IllusDesign → StandingIllustration | true | 传播 |
| ref_style | LanguageStyle → StandingIllustration | true | 传播 |
| wears | Event → CostumeStyle | false | 阻断（叙事边） |

> 美术生产链的 sync 边全部传播（唯一阻断的是 `wears` 叙事边）。任一上游节点编辑保存后，沿这些边 BFS 把可达下游 status 重置为 -1（作废重做）。

**级联场景示例**：

| 编辑节点 | 级联重置的下游（status → -1） |
|---------|---------------|
| Character | AppearanceStyle、LanguageStyle、CostumeStyle；其中 AppearanceStyle 再级联到 DesignSheet → IllusDesign → StandingIllustration，CostumeStyle 再级联到 IllusDesign → StandingIllustration，LanguageStyle 再级联到 ref_style 指向的 StandingIllustration |
| AppearanceStyle | DesignSheet → IllusDesign → StandingIllustration（全链） |
| LanguageStyle | ref_style 指向的 StandingIllustration |
| CostumeStyle | IllusDesign → StandingIllustration |
| DesignSheet | IllusDesign → StandingIllustration |
| IllusDesign | expands_to 指向的 StandingIllustration |

### 5.2 审批状态机 `approval.py` + `status.py`

`status.py` 显式定义每个 label 的合法 status 值、含义、完成态、enum 词表。

**status 值**：

| label | 合法 status | 完成态（可 submit） |
|-------|------------|------------------|
| AppearanceStyle / LanguageStyle | -1 作废 → 0 待设计 → 1 已完成 | 无审批 |
| CostumeStyle | -1 作废 → 0 待设计 → 1 已完成 | 1 |
| DesignSheet / IllusDesign / StandingIllustration | -1 作废 → 0 待生成 → 1 提示词完成 → 2 图片完成 → 10 待审 → 11 批准 | 2 |

**审批操作**：

```
完成态 ──submit──▶ 10 待审 ──approve──▶ 11 批准
                       └──reject──▶ 0 重做
```

- `submit`：完成态 → 10（在节点编辑器）。
- `approve`：10 → 11（在审批中心）。
- `reject`：10 → 0（在审批中心，可填理由）。

**下游推进前置校验**（来自项目治理手册）：IllusDesign 推进需 `DesignSheet=11` 且 `CostumeStyle=1`；StandingIllustration 推进需 `IllusDesign=11`；StandingIllustration 的 10 仅作质量确认（无下游）。后台**不阻塞**推进（那是 Skills 的职责），只在节点详情展示「上游就绪状态」提示。

### 5.3 编辑保存的完整后置流程

```
用户改属性 → 点【保存】
  ① repo.update_node(id, props)               写属性
  ② 若 node.status == 11 → set_status(id, 0)   审批失效，回退 0 重做
  ③ cascade_reset(id)                          sync BFS 重置下游 status=-1
  ④ UI 弹级联路径：已影响 N 个下游节点
```

> 规则 ②：编辑 `status=11` 的节点 → 自身回退到 0。内容实质变更 = 审批完全作废，自身回 0 重走流程、下游由 cascade 标 -1 作废重做，而非停在 10 拿新内容直接送审。这是对「修改后审批态不一致」隐患的制度化防线。

---

## 6. UI 模块

侧边栏导航 4 个页面 + Neo4j 连接状态指示。

### 6.1 页面职责

| 页面 | 职责 | 核心元素 |
|------|------|---------|
| 进度看板 `page_overview` | 全局进度总览 | 统计卡（角色数 / 待审数 / 需重做数）+ 角色列表表（每行显示该角色美术链各节点 status 缩略）→ 点角色跳详情 |
| 角色详情 `page_character` | 单角色美术生产链 | DAG 图（`st.graphviz_chart`）展示 Character→外貌/语言/着装→DesignSheet→IllusDesign→Standing，节点带 status 徽章；上游就绪提示；点节点进编辑器。备选：expander 树形展开 |
| 节点编辑器 `page_node_editor` | 改属性、提交审批（核心操作页） | 动态属性表单 + 标签组件 + 图片预览 + status 徽章 + `submit` 按钮 + `保存` 按钮；显示上下游节点链接 |
| 审批中心 `page_approval` | 集中审批 status=10 的节点 | 待审列表（按类型/角色筛选）+ 卡片（图片预览）+ `通过→11` / `驳回→0`（驳回可填理由） |

**职责切分**：编辑器管「改属性 + submit」；审批中心管「approve / reject」——因为审批要看图、可能批量。

### 6.2 节点编辑器交互流

```
选节点 → field_form 渲染属性（SchemaDef 驱动）
       → 标签字段交 tag_picker；图片字段交 image_viewer 预览
       → 改完点【保存】→ update + (11→0 回退) + cascade_reset
       → 顶部弹「已级联重置 N 个下游：DesignSheet→Standing…」路径
       → 或点【提交审批】→ submit（完成态→10），跳审批中心
```

### 6.3 tag_picker 组件

标签库有三类结构，组件统一处理，输出**分号分隔的值串**写回节点：

| 标签结构 | 渲染 | 示例 |
|---------|------|------|
| 简单单选 `multi:false` | `selectbox` | shape_language: 圆形 |
| 简单多选 `multi:true` | `multiselect` | marks: 疤痕;泪痣 |
| 复合维度 `combine` | 分组渲染，每组各自单/多选，按规则合成 | hair: [发色深棕]+[发型大波浪]+[发长长发] → "深棕色大波浪长发" |

- **性别差异**：合并 `options`（公共，男女都见）+ 对应 `gender` 的追加候选（如女性 body_type 多出「曼妙/娇小」）。
- **自定义输入**：每个 selectbox/multiselect 允许 free text（标签库允许自定义）。
- 性别从该节点的上游 Character 读取。

### 6.4 操作按钮 + deeplink 唤起 char-design

后台不直接出图，但提供一键唤起 **char-design agent** 的入口。char-design 是角色级编排层：传入角色 ID 即自动查询图状态、判断下一步、按依赖调度对应 skill、处理审批与 sync 级联。因此**所有「推进」按钮统一指向 char-design，不按节点类型区分唤起目标**——点哪个节点都行，agent 自己从图恢复。

**deeplink 格式**（VS Code 扩展注册的 handler，打开 Claude Code 编辑器标签页而非终端）：
```
vscode://anthropic.claude-code/open?prompt=<URL-encoded prompt>
```
prompt 推荐文本：`使用 char-design agent 推进角色 <char_id> 的美术流程`（明确指定 agent + 角色 snowflake ID；char-design 接受 ID 直接使用）。

**组件** `launch_button.py`：输入 `char_id`，组装上述 deeplink，用 `st.link_button` 渲染「推进美术流程」按钮。纯 UI（生成 URL），不触及 core/repo。

**按钮位置**（三处，都传 `char_id`）：
- 进度看板：角色列表每行一个「推进」按钮。
- 角色详情页：顶部一个「推进美术流程」按钮。
- 节点编辑器：一个「推进此角色流程」按钮，传该节点所属角色的 `char_id`（从节点经边回溯到 Character）。

**限制**：
- URL scheme **只预填、不自动提交**（防 prompt 注入的故意设计）——用户点击后需在 Claude Code 里按回车执行。
- 需 VS Code 扩展已注册 `vscode://anthropic.claude-code` handler（当前开发环境已满足）。

> 触发 char-design agent 的确切 prompt 写法在实现时验证：自然语言明确指定 agent 名 + 角色 ID，Claude 即按其 description 自动调度 char-design。

---

## 7. 预留边界 + 测试策略 + 工程细节

### 7.1 预留策略：架构通用化 + 入口 TODO

原则：`schema_loader` 和 UI 按 label 通用化，未来加节点类型近乎零成本；只在导航/看板层用禁用入口 + `TODO` 标注未实现模块。

- `schema_loader` 解析**所有** `Schema/*.md` 节点表格——叙事层（Event/Location/Info）字段定义 V1 就能解析，只是 UI 不暴露管理入口。
- `field_form` / `tag_picker` / 节点编辑器 / 审批中心 全部 SchemaDef 驱动，加新 label 自动支持。
- `status.py` 里叙事节点 status 规则留空（它们本就无审批）。

**TODO 清单**（代码内 `# TODO` + 本文档）：

| 模块 | 现状 | 预留方式 |
|------|------|---------|
| 剧情管理 | Schema 空 | 侧边栏禁用入口 + TODO，待 Schema 定义 |
| 场景美术 | 无独立节点 | 同上 |
| 叙事节点（Event/Location/Info）管理 | schema 层就绪 | UI 入口未暴露 + TODO；叙事层审批字段需 Schema 决策 |
| 叙事层 sync 级联 | 全 sync=false | 若启用需 Schema 决策 + TODO |
| 多用户 / 权限 / 审批历史 | V1 单用户无 auth | TODO |

### 7.2 测试策略

`core/` 不依赖 Streamlit、通过 repo 接口访问数据 → 可纯 Python 单测，是测试重点：

| 层 | 测试方式 | 重点用例 |
|----|---------|---------|
| `core` 单元测试 | mock graph_repo（内存构造图结构），不连真实库 | cascade：sync 阻断、BFS 层级、环防护；approval：非法转换拒绝、完成态判定、编辑 11→0 回退；schema_loader：表格解析、启动校验、标签库合并 |
| `repo` 集成测试 | 连真实 Neo4j（只读为主）或 docker 测试库 | `get_sync_downstream` 边过滤、`set_status_batch`、`update_node` |
| `ui` | 手动验证为主 | 标签组件交互、级联路径提示、DAG 渲染 |

可测性设计要点：`cascade` 接收图结构（节点 + sync 边）作为输入，是纯函数；`schema_loader` 输入文件路径输出 `SchemaDef`，纯解析——两者都易单测。

### 7.3 工程细节

- **配置**：`.env`（`NEO4J_URI/USER/PASSWORD`）+ `config/settings.py`（Schema/标签库/图片根路径）。
- **错误处理**：Neo4j 连接失败、status 非法转换、图片文件缺失 → 明确中文提示，不静默。
- **.gitignore**：`.env`、`__pycache__/`。

---

## 8. 验收标准（V1）

1. 启动后台，能看到所有角色及其美术链进度。
2. 进入任一节点编辑器，可修改属性（含标签字段），保存后：
   - 属性写入 Neo4j；
   - 若该节点原 status=11，自身回退到 0；
   - 沿 sync=true 边的下游被重置为 0，并展示级联路径。
3. 在审批中心能看到所有 status=10 的节点，可逐个通过（→11）或驳回（→0，可填理由）。
4. 节点编辑器能提交审批（完成态 → 10）。
5. 图片节点的 `image_path` 能预览。
6. 剧情、场景美术入口为禁用 + TODO 标注。
7. 任一角色/节点的「推进」按钮点击后，能在 VS Code 打开预填 char-design 的 Claude Code 标签页（携带 char_id）。
