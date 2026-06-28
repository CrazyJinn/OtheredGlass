# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这个项目是什么

`55_dashboard` 是「他者之镜」项目的人工治理后台——一个直连 Neo4j 的 Streamlit 应用，与项目里的 Claude Skills 共享**同一个 Neo4j 实例**。职责分工：

- **Skills**（项目根的 `.claude/`、`06_角色美术/` 等驱动）：自动化生产——组装 prompt、调 OfoxAI 出图、推进节点 `status` 0→1→2。
- **本后台**：人工治理——浏览进度、编辑节点属性、审批（10→11/→0）、属性变更后沿 `sync` 边级联重置下游、审批叙事建议（把 Cypher 写库）、全库 CSV 备份。

后台**不直接出图**。需要推进生产时，页面上的「推进」按钮生成 `vscode://anthropic.claude-code/open` deeplink 唤起 `char-design` / `scene-design` agent。

## 常用命令

```bash
# 运行后台（http://localhost:8501）。脚本会自动检测 .venv、缺 streamlit 时自动装依赖
bash run.sh          # Git Bash / Linux
run.bat              # Windows 双击
# 等价直跑：
python -m streamlit run app.py --server.port 8501

# 测试（必须在 55_dashboard 目录下，测试用 from core import ... 依赖 cwd 在 sys.path）
python -m pytest                         # 全部（core 层纯单测，不连真实 Neo4j）
python -m pytest tests/test_cascade.py   # 单个文件
python -m pytest tests/test_cascade.py::test_xxx -v   # 单个用例
```

无 lint / formatter 配置；无 `.venv`，用系统 Python（开发环境为 3.14）。

## Neo4j 凭证（非显而易见的优先级）

凭证来源与项目其他工具（`${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py`）保持一致，优先级：**环境变量 `NEO4J_PASSWORD` > 项目根 `settings.json` 的 `neo4j_password` 字段**。`URI`/`USER` 默认 `bolt://localhost:7687` / `neo4j`。本地可用 `55_dashboard/.env`（见 `.env.example`）覆盖。改凭证来源时要同步 `config/settings.py`。

## 架构：三层单向依赖 `ui → core → repo`

| 层 | 职责 | 边界 |
|----|------|------|
| [repo/](repo/) | 封装 neo4j-driver，**全项目唯一写 Cypher 的地方** | 不含业务逻辑 |
| [core/](core/) | 级联引擎、审批状态机、Schema 加载、status 规则 | 不渲染 UI、不耦合 Streamlit |
| [ui/](ui/) | 页面与组件，把用户操作翻译成 core/repo 调用 | 不写 Cypher、不直接碰 driver |

- [graph_repo.py](repo/graph_repo.py) 所有方法**接收/返回普通 dict**（不用 node 对象），便于 core 用内存 mock 测试。
- core 通过 repo 接口（`get_sync_downstream` / `set_status_batch` 等）访问数据，所以 [tests/conftest.py](tests/conftest.py) 的 `MockRepo` 能让 [cascade.py](core/cascade.py)、[approval.py](core/approval.py)、[schema_loader.py](core/schema_loader.py) 完全脱库单测——这是测试重点。UI 层只做手动验证。

## Schema 驱动：字段定义不硬编码

[core/schema_loader.py](core/schema_loader.py) 在 `app.py` 启动时加载一次并缓存：

- **字段定义**：解析 `00_init/Schema/*.md` 里 `### 名称（Label）` 标题下的 markdown 表格（`|字段|中文|类型|必填|...|`）→ `FieldDef`/`NodeDef`/`SchemaDef`。表格列格式不符会抛 `SchemaError`（启动校验，防格式漂移静默出错）。
- **标签词表**：直接读 [config/标签库.json](config/标签库.json)。
- **status 流转规则 + enum 词表**：**刻意不解析 .md**（.md 中是散文式说明，格式不稳定），在 [core/status.py](core/status.py) 显式定义。改业务规则改这里。

[ui/components/field_form.py](ui/components/field_form.py) 按 `FieldDef.type` + 是否命中 `tag_fields` 动态选组件（标签库→tag_picker、enum→selectbox、int→number_input、image_path→只读预览…）。**这是"加新节点类型近乎零成本"的预留策略**：schema_loader 已解析全部 Schema，加 label 通常只需在 `status.py` 补 status 规则 + 暴露 UI 入口。

## status 系统（治理的核心）

`status` 值统一语义：`-1` 作废重做 / `0` 待处理 / `1` 已完成 / `2` 图片完成 / `10` 待审 / `11` 批准。每个 label 的合法值、完成态、是否走审批，在 [status.py](core/status.py) 的 `NODE_STATUS` 显式定义：

- 有审批（completion=2，可 submit→10→11）：`DesignSheet`/`IllusDesign`/`StandingIllustration`/`SceneLayer`
- 无审批（completion=1）：`AppearanceStyle`/`LanguageStyle`/`CostumeStyle`/`Scene`
- `Character`/`Location` **无 status 字段**，只作级联触发源。

> 判断节点"有无 status"必须用 `is not None`——`status=0`（待处理）是合法 falsy，真值判断会误隐藏。

## sync 级联（属性变更的连锁反应）

保存节点属性后，[cascade.py](core/cascade.py) 沿 `sync=true` 出边做 BFS，把可达下游 `status` **重置为 `-1`（作废重做）**，遇 `sync=false` 阻断（如叙事边 `wears`）。`get_sync_downstream` 只返回**一跳** sync 出边，多跳展开由 cascade 迭代完成。

[page_node_editor.py](ui/page_node_editor.py) 的保存后置流程是固定四步，改动顺序要谨慎：
1. `update_node` 写属性；
2. `approval.on_edit`：若该节点原 `status==11` → 自身回退到 `0`（审批失效）；
3. `cascade_reset` 重置下游为 `-1`；
4. 弹 toast 反馈。

> 注意：以代码为准，级联下游重置为 **`-1`**（设计文档 `docs/superpowers/specs/2026-06-17-dashboard-design.md` 验收标准里写成 `0` 是笔误）。

## 叙事审批（写 Cypher 进库）

[page_narrative_approval.py](ui/page_narrative_approval.py) + [core/narrative_review.py](core/narrative_review.py)：扫描 `02_剧情数据/<日期>_建议.json`（`nrt-narrative-grower` 产出，每条含 `check/priority/reason/content/cypher`），逐条审阅。**通过 = 把该条 Cypher 写入 Neo4j**（[graph_repo.run_write_script](repo/graph_repo.py) 用 `split_cypher_script` 拆多语句、单事务执行、任一失败整体回滚）；驳回 = 仅记录。审批留痕写 `02_剧情数据/_reviewed.json`（键=`文件名#index`），跨会话保留，避免重复执行与重复展示。

## 场景美术 = 角色美术的对称镜像

[page_scene_overview.py](ui/page_scene_overview.py) 与 [page_overview.py](ui/page_overview.py) 结构对称：`Location` 替代 `Character`、`get_location_graph` 替代 `get_character_graph`、`_SCENE_EDGES`(`has_scene|has_layer`) 替代 `_ART_EDGES`(`has_appearance|has_voice_style|has_costume|produces|outfit_for|expands_to|ref_style`)，且**共用同一个 `_dialog_node` session_state key 和 [page_node_editor.py](ui/page_node_editor.py)**。这些边类型正则在 [graph_repo.py](repo/graph_repo.py) 里限定子图遍历范围，避免把叙事 `Event`/`Info` 或其他角色/地点混进来——加新链路类型时记得补这里的正则。

## Streamlit rerun 陷阱（项目里反复踩过的坑）

写新交互时务必注意，否则会出现"操作成功却无反馈"或"弹窗异常关闭"：

- **保存/审批后用 `st.toast`，不要用 inline `st.success`/`st.info`**——紧跟其后的 `st.rerun()` 会丢弃本轮所有 inline 输出。代码注释里多处标了这条理由。
- **dialog 跨 rerun 保持**：用 `session_state["_dialog_node"]` 持有当前编辑节点，每次 `render` 检查并重开弹窗；只有「关闭」按钮或切换节点才清状态。
- **download_button 的 data 不要在每次 rerun 重算**：全库备份用两步法（点「生成备份」先扫描存 session_state，再用 download_button 下载）。
- widget 清空（如 tag_picker 添加后清空输入框）必须在 widget 实例化**之前** `pop` session_state key，否则触发 "cannot be modified after widget instantiated"。

## 数据备份

[app.py](app.py) 侧边栏底部：优先 `export_csv_all`（`apoc.export.csv.all(null, {stream:true})`，无需文件系统访问），APOC 不可用时兜底 `export_csv_all_pure`（纯 Python，节点表 + 边表两段 CSV）。
