# Mermaid 流程图解析指南

README 包含两个 mermaid 图，只解析 `flowchart TB`（游戏开发流程），忽略 `sequenceDiagram`。

## 提取规则

### 子图 → workflow 节点

每个 `subgraph` 映射为一个 workflow 节点（执行单元）。

| mermaid 元素 | workflow 字段 | 说明 |
|-------------|--------------|------|
| `subgraph nar["叙事设计 [图]"]` | node_id: `nar`, name: `叙事设计` | ID 取 subgraph 后的标识符 |
| 子图标题中的 `[图]` | reads_neo4j: true | 标记该阶段从 Neo4j 读取 |
| 子图内部的产出物节点 | description | 产出物列表写入 description 字段 |

### 产出物节点 → description

节点 ID 格式为 `O_<子图缩写><序号>`，产出物名称写入父节点的 description：

```
subgraph nar["叙事设计 [图]"]
    O_nar1[叙事节奏.md]
    O_nar2[角色声线.md]
end
```

→ `叙事设计.description: "叙事节奏.md、角色声线.md"`

### Neo4j 数据源节点

圆柱形节点 `neo[("Neo4j 数据就绪")]` 是纯数据源，execution_type 为 `input`，不参与执行。

### 连接线 → 依赖关系

| 连接模式 | 映射规则 |
|---------|---------|
| `neo --> nar` | nar.predecessors: [neo] |
| `O_char1 & O_char2 --> artp` | artp.predecessors: [char]（追溯到子图级别） |
| `O_artp2 --> t2i` | t2i.predecessors: [artp] |

节点间连线追溯到所属子图，依赖关系始终在子图（workflow 节点）级别建立。

### 样式类 → execution_type

| 样式类 | 含义 | execution_type |
|--------|------|----------------|
| `neo4j` | Neo4j 数据源（圆柱节点） | `input` |
| `graphSkill` | 从 Neo4j 读取的 Skill（标题带 `[图]`） | `skill` |
| `auto` | 自动化完成 | `auto` |
| `manual` | 人工完成 | `manual` |

样式应用到子图级别：`class nar,char,scended,script,sol,audio graphSkill`。

## 解析原则

- 实时从 README.md 的 mermaid 代码块解析，不硬编码不缓存
- 子图是 workflow 的核心单元，产出物节点仅用于生成 description
- 依赖关系在子图级别维护（节点间连线追溯到子图）
- 拓扑排序用于确定执行顺序
