---
name: char-illus-designer
description: |
  管理 IllusDesign 图节点的完整生命周期：创建节点、填充着装补充说明、组装提示词、生成着装适配设计图。
  每组 (DesignSheet, CostumeStyle) 对应一个节点，支持一次推进多个 status（0→1→2）。
  在需要生成立绘设计图或 IllusDesign 节点需推进时使用。
argument-hint: <char_id> [target_status]
arguments:
  - char_id
  - target_status
allowed-tools: Read, Bash, Write, Edit
---

# 立绘设计图（IllusDesign）

角色穿着特定着装的三视图设计图，由 DesignSheet（外貌基础）和 CostumeStyle（着装方案）共同决定。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| char_id | 角色 ID（snowflake Base62） | 由 agent 传入 |
| target_status | 推进目标：`1`（仅提示词）或 `2`（到图片） | `2` |

## 流程

### 1. 读取前驱

从 Character 节点出发，仅返回 IllusDesign 的直接前驱（DesignSheet、CostumeStyle）：

```cypher
MATCH (ch:Character {id: $char_id})
MATCH (ch)-[:has_appearance]->(:AppearanceStyle)-[:produces]->(ds:DesignSheet)
MATCH (ch)-[:has_costume]->(cos:CostumeStyle)
RETURN ds, collect(cos) AS costumes
```

获取：DesignSheet（设计图基础）、CostumeStyle[]（着装方案列表）。Character 仅用于定位查询，不返回。

### 2. 创建节点（如不存在）

对每套装扮（CostumeStyle），如果对应的 IllusDesign 节点不存在，先生成 snowflake ID：

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py" -n 1 -q
```

然后创建节点和边：

```cypher
MERGE (illus:IllusDesign {id: '<snowflake_id>'})
SET illus.status = 0;
MATCH (ds:DesignSheet {id: '<design_id>'}), (illus:IllusDesign {id: '<snowflake_id>'})
MERGE (ds)-[r:produces]->(illus) SET r.sync = false;
MATCH (cos:CostumeStyle {id: '<costume_id>'}), (illus:IllusDesign {id: '<snowflake_id>'})
MERGE (cos)-[r:outfit_for]->(illus) SET r.sync = false;
```

根据着装补充需求，填写 `adaptation_notes`（如"左臂夹持文件夹"，如无特殊补充可留空）。

### 3. 推进状态

#### 0 → 1：组装提示词

调用 char-prompt-assembler skill（Mode B IllusDesign 模式）：

将步骤 1 查询到的 costume、illus 和 character 数据序列化为 JSON 字符串，作为 data 参数传入。

使用 Skill 工具调用 `char-prompt-assembler`，传入参数 `<node_id> IllusDesign '<data_json>'`。

data 参数结构：
```json
{
  "costume": { "tags": {"outfit_style":"...","garment":"...","footwear":"...","accessory_type":"..."} },
  "illus": { "adaptation_notes": "..." }
}
```

char-prompt-assembler 将：
- 解析 data 参数获取 CostumeStyle + IllusDesign 数据
- 读取 `00_init/美术风格.md`
- 按 `着装描述→适配说明→风格` 组装提示词（聚焦着装，不重复角色外貌）
- 更新节点：写入 prompt 字段，status → 1

#### 1 → 2：生成图片

调用 infra-image-generator skill（IllusDesign 图生图模式）：

使用 Skill 工具调用 `infra-image-generator`，传入参数 `<node_id>`。

infra-image-generator 将：
- 读取节点 prompt 字段
- 图生图模式：参考 DesignSheet.image_path（`produces` 边上游）
- 输出路径：`./06_角色美术/<char_name>/<CostumeStyle.name>/立绘设计图.png`
- 更新节点：写入 image_path，status → 10

### 4. 保存结果

最终通过 neo4j-helper 确认节点状态已正确更新。
