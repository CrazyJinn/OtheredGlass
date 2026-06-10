---
name: char-stand-designer
description: |
  管理 StandingIllustration 图节点的完整生命周期：创建表情变体节点、组装提示词、生成立绘图片。
  每个 IllusDesign 按角色优先级（P0/P1/P2）拓展不同数量的表情变体，支持一次推进多个 status（0→1→2）。
  在需要生成立绘变体或 StandingIllustration 节点需推进时使用。
argument-hint: <char_id> [target_status]
arguments:
  - char_id
  - target_status
allowed-tools: Read, Bash, Write, Edit
---

# 立绘变体（StandingIllustration）

从 IllusDesign 拓展出不同表情、动作的单张立绘，表情和动作参考 LanguageStyle 生成。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| char_id | 角色 ID（如 `char_001`） | 由 agent 传入 |
| target_status | 推进目标：`1`（仅提示词）或 `2`（到图片） | `2` |

## 流程

### 1. 读取前驱

从 Character 节点出发，仅返回 StandingIllustration 的直接前驱（IllusDesign、LanguageStyle）：

```cypher
MATCH (ch:Character {id: 'char_NNN'})
MATCH (ch)-[:has_voice_style]->(voice:LanguageStyle)
MATCH (ch)-[:has_appearance]->(:AppearanceStyle)-[:produces]->(:DesignSheet)-[:produces]->(illus:IllusDesign)
RETURN illus, voice
```

获取：IllusDesign[]（立绘设计图列表）、LanguageStyle（语言风格参考，含 emotion_patterns）。Character 仅用于定位查询，不返回。

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

调用 char-prompt-assembler skill（Mode C StandingIllustration 模式）：

将步骤 1 查询到的 stand、voice 和 character 数据序列化为 JSON 字符串，作为 data 参数传入。

使用 Skill 工具调用 `char-prompt-assembler`，传入参数 `<node_id> StandingIllustration '<data_json>'`。

data 参数结构：
```json
{
  "stand": { "variant_label": "..." },
  "voice": { "emotion_patterns": "...", "description": "..." }
}
```

char-prompt-assembler 将：
- 解析 data 参数获取变体信息 + 语言风格数据
- 读取 `00_init/美术风格.md`
- 按固定格式组装：`[角色名]立绘，纯绿背景，全身像，[表情描述]，[手部动作]，[脚部动作]，[风格标签]`
- 提取要素：眼部、眉毛、嘴部、面部肌肉、头部角度 + 手部动作 + 脚部动作
- 参考语言风格的 emotion_patterns 补充情绪表达
- 更新节点：写入 prompt 字段，status → 1

#### 1 → 2：生成图片

调用 infra-image-generator skill（StandingIllustration 图生图模式）：

使用 Skill 工具调用 `infra-image-generator`，传入参数 `<node_id>`。

infra-image-generator 将：
- 读取节点 prompt 字段
- 图生图模式：参考 IllusDesign.image_path（`expands_to` 边上游）
- 输出路径：`./06_角色美术/<char_id>/立绘/<costume_id>/<variant_label>/立绘.png`
- 更新节点：写入 image_path，status → 2，approve → 'pending'

### 4. 保存结果

最终通过 neo4j-helper 确认所有变体节点状态已正确更新。
