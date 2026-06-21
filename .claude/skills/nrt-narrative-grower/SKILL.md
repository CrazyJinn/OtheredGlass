---
name: nrt-narrative-grower
description: |
  叙事自增长：图算法分析叙事图缺口 → 生成创意草案（Markdown 文件，frontmatter status=10 待审）→ 审批通过后提取基础节点写回 Neo4j。
  草案以 .md 文件存于 02_剧情数据/，文件名=日期+概述，不写入图数据库。无参数执行 analyze + generate 产出新草案；传 draft_id（文件名 stem）执行 apply 写回。
argument-hint: [draft_id]
arguments:
  - draft_id
allowed-tools: Read, Bash, Write, Edit, Glob
---

# 叙事自增长（nrt-narrative-grower）

分析叙事图的创意增长机会，生成自然语言创意草案（**Markdown 文件**，存于 `02_剧情数据/`），经人工审批后提取为基础节点写回叙事基础层。

> **存储介质**：草案为 `02_剧情数据/<日期_概述>.md` 文件（YAML frontmatter 承载流程状态 + Markdown 正文承载创意与分析），**不写入 Neo4j**。审批 = 手动把 frontmatter `status` 由 `10` 改为 `11`。
>
> **文件命名**：`YYYY-MM-DD_<概述>.md`，概述取自标题核心主题（简短，清洗 Windows 非法字符 `: / \ * ? " < > |`）。frontmatter `id`（snowflake）仅作稳定唯一锚点，不参与文件名。

## 参数

| 参数 | 说明 |
|------|------|
| draft_id | （可选）要 apply 的草案文件名 stem（`日期_概述`，如 `2026-06-21_试炼回扣与暧昧显化`）。**省略** → 执行 analyze + generate 产出新草案（frontmatter `status=10`）；**提供** → 执行 apply 写回（skill 在 `02_剧情数据/` 下 Glob 模糊匹配该文件，要求 frontmatter `status=11`）。 |

## 前置

```bash
CYPHER_EXEC="python ${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py"
SF_GEN="python ${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)   # ISO 时间戳
DATE=$(echo $TIMESTAMP | cut -dT -f1)        # YYYY-MM-DD，用于文件名
OUTPUT_DIR="02_剧情数据"                     # 草案 MD 落盘目录（仓库根相对）
```

- Schema：[叙事基础.md](../../../00_init/Schema/叙事基础.md)（提取规则）+ [剧情.md](../../../00_init/Schema/剧情.md)（草案文件规范）。
- 写 Cypher 规则：见 [cypher_exec.py](../../scripts/cypher_exec.py) 顶部 docstring（内联值、MERGE 幂等、必须指定标签、查询加 LIMIT 等）。

---

## 模式一：analyze + generate（无 draft_id）

### 1. analyze — 图算法分析缺口

用 `$CYPHER_EXEC -c "<cypher>" --json` 依次跑 10 种叙事创意检查（Cypher + 必要的 Python 后处理），详见 [references/analyze-queries.md](references/analyze-queries.md)：

temporal_gaps、character_arcs、implicit_relations、event_chains、scene_utilization、info_depth、subgraph_connectivity、relationship_evolution、bridge_scenes、narrative_density

LLM 汇总为内存对象 `growth_opportunities`，结构沿用 graph-builder discover 的 `{summary, suggestions[], details}`，priority 用 high/medium/low。需 Python 后处理的（temporal_gaps 的 Day 解析等）由 LLM 读 `--json` 输出后自行计算（参照 graph_builder `discover_temporal_gaps`）。

### 2. generate — 撰写草案并落盘为 MD

1. LLM 据 growth_opportunities 撰写自然语言叙事创意草案（Markdown，含拟增角色/事件/地点/信息 + 关系），并拟定一个简短标题。
2. 取 frontmatter 稳定锚点 id：`$SF_GEN -n 1 -q` → `DRAFT_ID`（仅写入 frontmatter `id`，不用作文件名）。
3. 定文件名：`概述` = 标题核心主题（简短，清洗非法字符 `: / \ * ? " < > |`）；文件名 = `${DATE}_${概述}.md`。
4. **用 Write 工具写** `${OUTPUT_DIR}/${DATE}_${概述}.md`，结构如下（frontmatter 承载流程状态，正文承载草案 + 分析）：

```markdown
---
id: <DRAFT_ID>
title: '<标题>'
status: 10              # 10 待审 / 11 批准 / 0 驳回 / -1 作废
created_at: '<TIMESTAMP>'
applied_at: null        # null=未应用；apply 成功后写 ISO 时间（幂等标记）
applied_node_ids: ''    # apply 写入的基础节点 id，分号分隔
---

# <标题>

<创意草案正文：拟增角色/事件/地点/信息 + 关系，apply 据此提取>

## 分析依据（analyze）

<人类可读摘要 analyze_summary>

（growth_opportunities 的 summary / suggestions[] / details 可作为参考置于正文或省略）
```

5. **不写图**：本 skill 不创建任何图节点（草案不进图），不建任何边。
6. 报告：草案文件路径 `${OUTPUT_DIR}/${DATE}_${概述}.md`（frontmatter `status=10`）。提示用户审批方式：**手动编辑该 MD 的 frontmatter，把 `status: 10` 改为 `status: 11`**，随后用 `nrt-narrative-grower <DATE>_<概述>` 执行 apply。

---

## 模式二：apply（提供 draft_id）

> 仅对 frontmatter `status==11`（已批准）且 `applied_at IS NULL`（未应用）的草案执行。

### 1. 定位并读取已批准草案

传入参数为文件名 stem（`日期_概述`，支持部分匹配——可只传日期或概述关键词）。用 Glob 工具在 `${OUTPUT_DIR}/` 下匹配 `*<draft_id>*.md` 定位唯一文件，再用 Read 工具读取，校验 frontmatter：

- `status == 11` 且 `applied_at == null` → 继续。
- 否则（未批准 / 已驳回 / 已应用）→ 停止并提示用户当前 frontmatter 状态。
- 若 Glob 命中 0 个或多个文件 → 停止并提示用户补全文件名。

### 2. 提取基础节点 + 边

按 [references/apply-extraction.md](references/apply-extraction.md)（= nrt-narrative-extractor 的 [csv-patterns.md](../nrt-narrative-extractor/references/csv-patterns.md) 提取规则）从草案**正文**提取 4 类节点（Character/Event/Location/Info）+ 6 种边：

- **已有实体**：按名称 `MATCH` 查 id 复用，不新建。
- **新增实体**：`$SF_GEN -n <数量> -q` 分配 snowflake id。
- 边端点先全部解析为 id（已有 or 新建），再生成 `MATCH (a{id}), (b{id}) MERGE (a)-[:type{...}]->(b)`。

### 3. 原子写入 + 回写 frontmatter

合并为 `;` 分隔串（节点在前、边在后），`$CYPHER_EXEC --stdin --multi --json` 单事务执行（与 extractor import.cypher 同模式，零 LOAD CSV，不含 `//` 注释）。成功后**用 Edit 工具回写 MD frontmatter**：

```yaml
applied_at: '<TIMESTAMP>'
applied_node_ids: '<id;id;...>'
```

**幂等**：MERGE 保证重复 apply 不产生重复节点；apply 开头校验 `applied_at IS NULL`，已应用则拒绝二次 apply。

报告：写入的节点/边数量 + `applied_node_ids` + 回写后的 MD 文件路径。

---

## 参考文档

- [分析查询（10 种检查）](references/analyze-queries.md)
- [apply 提取规则](references/apply-extraction.md)
- 提取规则来源：[nrt-narrative-extractor/references/csv-patterns.md](../nrt-narrative-extractor/references/csv-patterns.md)
- 草案文件规范：[00_init/Schema/剧情.md](../../../00_init/Schema/剧情.md)
