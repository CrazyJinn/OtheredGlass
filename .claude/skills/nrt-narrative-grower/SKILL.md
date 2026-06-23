---
name: nrt-narrative-grower
description: |
  叙事图诊断与修改建议：用图算法（10 种检查）识别叙事基础层中可完善之处，产出结构化修改建议——一个 JSON 数组，每项含简短自然语言描述 + 开箱可执行的 cypher 语句。
  只读图、不写图、不产 MD 草案。无参数执行：跑检查 → 落盘 02_剧情数据/日期_建议.json → 对话仅报路径。
  在需要给叙事图做体检、找出可完善缺口并产出可执行补全建议时使用。
allowed-tools: Read, Bash, Write
---

# 叙事图诊断与修改建议（nrt-narrative-grower）

用图算法扫描叙事基础层的缺口与可完善之处，产出**结构化修改建议**（JSON 数组）落盘。每条建议 = 简短自然语言描述 + 开箱可执行的 cypher。

> **只读不写**：本 skill 仅查询图，不修改图。产出的 cypher 是供人工审阅/执行的**建议**，skill 自身不执行任何写操作、不创建节点/边、不产 MD 草案。
>
> **输出**：`02_剧情数据/<YYYY-MM-DD>_建议.json`（顶层 JSON 数组）。对话仅报文件路径与建议条数，不展开内容。

## 前置

```bash
CYPHER_EXEC="python ${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py"
SF_GEN="python ${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DATE=$(echo $TIMESTAMP | cut -dT -f1)        # YYYY-MM-DD，用于文件名
OUTPUT_DIR="02_剧情数据"                     # 建议 JSON 落盘目录（仓库根相对）
```

- Schema：[叙事基础.md](../../../00_init/Schema/叙事基础.md)（节点/边定义，生成 cypher 的事实来源）。
- 写 cypher 规则：见 [cypher_exec.py](../../scripts/cypher_exec.py) 顶部 docstring（内联值、MERGE 幂等、必须指定标签、查询加 LIMIT）。

---

## 流程

### 1. analyze — 跑 10 种图算法检查

用 `$CYPHER_EXEC -c "<cypher>" --json` 依次跑 10 种叙事缺口检查（Cypher + 必要 Python 后处理），详见 [references/analyze-queries.md](references/analyze-queries.md)：

temporal_gaps、character_arcs、implicit_relations、event_chains、scene_utilization、info_depth、subgraph_connectivity、relationship_evolution、bridge_scenes、narrative_density

需 Python 后处理的（temporal_gaps 的 Day 解析等）由 LLM 读 `--json` 输出后自行计算（参照 graph_builder `discover_temporal_gaps`）。

### 2. 构造修改建议 JSON 数组

把 analyze 结果归纳为**修改建议 JSON 数组**，每项 = `{check, priority, reason, content, cypher}`（reason=提出建议的原因/发现，content=建议内容）。生成规则（含补边/补节点两类 cypher 模板）见 [references/analyze-queries.md](references/analyze-queries.md) 末尾「输出格式」：

- **补边类**（implicit_relations→relation、event_chains→evt_relation、info_depth→link 等）：端点用 analyze 查出的**真实 id** `MATCH`，再 `MERGE` 边；创意字段（type/detail/role）由 LLM 推断**建议值**填入，并在 content 标注「可调整」。
- **补节点类**（temporal_gaps / character_arcs 需新增 Event）：`$SF_GEN -n 1 -q` 生成新 id，创意字段（title/time/type/description）LLM 推断建议值；需挂边时节点语句在前、边语句在后，`;` 分隔。
- 纯统计型检查（scene_utilization / bridge_scenes / narrative_density）若无明确补全动作则**不产出**，避免噪声。
- 全程 `MERGE`（幂等）、内联值、必须指定标签、字符串单引号转义。

### 3. 落盘 JSON

用 Write 工具写 `${OUTPUT_DIR}/${DATE}_建议.json`，内容为建议 JSON 数组（顶层即 `[...]`）。

报告：仅文件路径 `${OUTPUT_DIR}/${DATE}_建议.json` + 建议总条数与 priority 分布（high/medium/low 各几条）。提示用户：审阅后可自行挑选 cypher 逐条执行。

---

## 参考文档

- [分析查询（10 种检查）+ 输出格式与 cypher 模板](references/analyze-queries.md)
- 节点/边定义：[00_init/Schema/叙事基础.md](../../../00_init/Schema/叙事基础.md)
