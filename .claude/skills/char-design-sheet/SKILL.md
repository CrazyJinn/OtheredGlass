---
name: char-design-sheet
description: |
  管理 DesignSheet 图节点的完整生命周期：创建节点、组装提示词、生成三视图设计稿。
  支持一次推进多个 status（0→1→2）。在需要生成角色设计图或 DesignSheet 节点需推进时使用。
argument-hint: <node_id> [target_status]
arguments:
  - node_id
  - target_status
allowed-tools: Read, Bash, Write, Edit
---

# 设计图（DesignSheet）

每个角色一个 DesignSheet 节点，对应三视图设计稿。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| node_id | 目标节点 ID（如 `design_001`） | 由 agent 传入 |
| target_status | 推进目标：`1`（仅提示词）或 `2`（到图片） | `2` |

## 流程

### 1. 读取前驱

通过 neo4j-helper 一次性查询所有前驱节点：

```cypher
MATCH (app:AppearanceStyle)-[:produces]->(ds:DesignSheet {id: 'design_NNN'})
MATCH (ch:Character)-[:has_appearance]->(app)
OPTIONAL MATCH (ch)-[:has_costume]->(cos:CostumeStyle)
RETURN app, ds, cos, ch
```

获取：AppearanceStyle（外貌数据）、CostumeStyle（着装数据）、Character（角色基础信息）。

### 2. 创建节点（如不存在）

如果 DesignSheet 节点不存在，创建节点和 `produces` 边：

```cypher
MERGE (ds:DesignSheet {id: 'design_NNN'})
SET ds.status = 0, ds.approve = null;
MATCH (app:AppearanceStyle {id: 'appearance_NNN'}), (ds:DesignSheet {id: 'design_NNN'})
MERGE (app)-[r:produces]->(ds) SET r.sync = true;
```

### 3. 推进状态

根据当前 status 和 target_status 逐步推进：

#### 0 → 1：组装提示词

调用 char-prompt-assembler skill（Mode A DesignSheet 模式）：

将步骤 1 查询到的 appearance 和 character 数据序列化为 JSON 字符串，作为 data 参数传入。

使用 Skill 工具调用 `char-prompt-assembler`，传入参数 `<node_id> DesignSheet '<data_json>'`。

data 参数结构：
```json
{
  "appearance": { "appearance": "...", "color_direction": "...", "shape_language": "...", "visual_tone": "...", "first_impression": "...", "memory_points": "..." },
  "character": { "id": "char_NNN", "name": "..." }
}
```

char-prompt-assembler 将：
- 解析 data 参数获取 AppearanceStyle + Character 数据
- 读取 `00_init/美术风格.md` 全局风格参数
- 按 `主体→细节→风格` 组装提示词
- 更新节点：写入 prompt 字段，status → 1

#### 1 → 2：生成图片

调用 infra-image-generator skill（DesignSheet 文生图模式）：

使用 Skill 工具调用 `infra-image-generator`，传入参数 `<node_id>`。

infra-image-generator 将：
- 读取节点 prompt 字段
- 文生图模式（无参考图）
- 输出路径：`./06_角色美术/<char_id>/设计图.png`
- 更新节点：写入 image_path，status → 2，approve → 'pending'

### 4. 保存结果

最终通过 neo4j-helper 确认节点状态已正确更新。
