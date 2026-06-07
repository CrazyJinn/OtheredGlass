---
name: stand-designer
description: |
  管理 StandingIllustration 图节点的完整生命周期：创建表情变体节点、组装提示词、生成立绘图片。
  每个 IllusDesign 按角色优先级（P0/P1/P2）拓展不同数量的表情变体，支持一次推进多个 status（0→1→2）。
  在需要生成立绘变体或 StandingIllustration 节点需推进时使用。
argument-hint: <node_id> [target_status]
arguments:
  - node_id
  - target_status
allowed-tools: Read, Bash, Write, Edit
---

# 立绘变体（StandingIllustration）

从 IllusDesign 拓展出不同表情、动作的单张立绘，表情和动作参考 LanguageStyle 生成。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| node_id | 目标节点 ID（如 `stand_001`），或 IllusDesign ID 以批量创建所有变体 | 由 agent 传入 |
| target_status | 推进目标：`1`（仅提示词）或 `2`（到图片） | `2` |

## 流程

### 1. 读取前驱

通过 neo4j-helper 一次性查询所有前驱节点：

```cypher
MATCH (illus:IllusDesign)-[:expands_to]->(stand:StandingIllustration {id: 'stand_NNN'})
MATCH (ds:DesignSheet)-[:produces]->(illus)
MATCH (voice:LanguageStyle)-[:ref_style]->(stand)
RETURN stand, illus, ds, voice
```

获取：IllusDesign（设计图基础）、LanguageStyle（语言风格参考）。

如需批量创建变体，先查询 IllusDesign 和角色信息：

```cypher
MATCH (illus:IllusDesign {id: 'illus_NNN'})
MATCH (voice:LanguageStyle)-[:ref_style]->(stand)
RETURN illus, voice
```

### 2. 创建变体节点（如不存在）

根据角色优先级决定变体数量：

| 角色优先级 | 变体数量 | 示例变体标签 |
|-----------|---------|------------|
| P0（主角） | 10 | 默认、微笑、生气、悲伤、惊讶、思考、坚定、恐惧、战斗姿态、受伤 |
| P1（核心 NPC） | 6 | 按角色定制 |
| P2（一般 NPC） | 2 | 默认、微笑 |

为每个变体创建节点和边：

```cypher
MERGE (stand:StandingIllustration {id: 'stand_NNN'})
SET stand.variant_label = '微笑', stand.status = 0, stand.approve = null;
MATCH (illus:IllusDesign {id: 'illus_NNN'}), (stand:StandingIllustration {id: 'stand_NNN'})
MERGE (illus)-[r:expands_to]->(stand) SET r.sync = true, r.variant_label = '微笑';
MATCH (voice:LanguageStyle {id: 'voice_NNN'}), (stand:StandingIllustration {id: 'stand_NNN'})
MERGE (voice)-[r:ref_style]->(stand) SET r.sync = true;
```

### 3. 推进状态

对每个变体节点按序执行：

#### 0 → 1：组装提示词

调用 prompt-assembler skill（Mode C StandingIllustration 模式）：

使用 Skill 工具调用 `char-design:prompt-assembler`，传入参数 `<node_id> StandingIllustration`。

prompt-assembler 将：
- 读取 IllusDesign + LanguageStyle 数据
- 读取 `00_init/美术风格.md`
- 按固定格式组装：`[角色名]立绘，纯白背景，半身像，[表情描述]，[姿态描述]，手绘动漫风格`
- 提取表情要素：眼部、眉毛、嘴部、面部肌肉、头部角度
- 参考语言风格的情绪模式补充情绪表达
- 更新节点：写入 prompt 字段，status → 1

#### 1 → 2：生成图片

调用 image-generator skill（StandingIllustration 图生图模式）：

使用 Skill 工具调用 `char-design:image-generator`，传入参数 `<node_id>`。

image-generator 将：
- 读取节点 prompt 字段
- 图生图模式：参考 IllusDesign.image_path（`expands_to` 边上游）
- 输出路径：`./06_角色美术/<char_id>/立绘/<costume_id>/<variant_label>/立绘.png`
- 更新节点：写入 image_path，status → 2，approve → 'pending'

### 4. 保存结果

最终通过 neo4j-helper 确认所有变体节点状态已正确更新。
