---
name: char-concept-designer
description: |
  从 Neo4j 提取角色信息，创建 AppearanceStyle / LanguageStyle 图节点并写入内容。
  CostumeStyle 由 char-costume-designer skill 负责。
  在需要设计角色外貌方向（外貌/色彩/材质）、生成语言风格、
  或角色数据节点 status=0 需推进时使用。
allowed-tools: Read, Bash, Write, Edit
---

# 角色概念设计

创建并写入 AppearanceStyle（外貌）和 LanguageStyle（语言风格）图节点

## 流程

### 1. 获取角色数据

通过 neo4j-helper 执行单条 Cypher 查询角色完整信息：

```cypher
MATCH (ch:Character {id: 'char_NNN'})
OPTIONAL MATCH (ch)-[:has_appearance]->(app:AppearanceStyle)
OPTIONAL MATCH (ch)-[:has_voice_style]->(voice:LanguageStyle)
RETURN ch, app, voice;
```

仅处理 status=0 的节点。

### 2. 判断产出

| 角色类型 | AppearanceStyle | LanguageStyle |
|---------|----------------|---------------|
| 主角(char) / NPC | 完整版 | 生成 |
| 怪物(enemy) | 简化版 | 不生成 |

### 3. 创建节点和边

通过 neo4j-helper 执行 Cypher 创建节点和边。

#### 3.1 AppearanceStyle（1 个）

创建节点 + `has_appearance` 边（Character → AppearanceStyle）：

```cypher
MERGE (app:AppearanceStyle {id: 'appearance_NNN'})
SET app.name = '角色名外貌特征', app.status = 0
WITH app
MATCH (ch:Character {id: 'char_NNN'})
MERGE (ch)-[r:has_appearance]->(app)
SET r.sync = true;
```

#### 3.2 LanguageStyle（1 个，怪物跳过）

创建节点 + `has_voice_style` 边（Character → LanguageStyle）：

```cypher
MERGE (voice:LanguageStyle {id: 'voice_NNN'})
SET voice.name = '角色名语言风格', voice.status = 0
WITH voice
MATCH (ch:Character {id: 'char_NNN'})
MERGE (ch)-[r:has_voice_style]->(voice)
SET r.sync = true;
```

### 4. 生成内容并写入图节点

按模板（见 references/）生成内容，直接通过 neo4j-helper 写入图节点字段。

**AppearanceStyle**（status → 1）：

| 内容 | 属性 |
|------|------|
| 外貌描述 | appearance |
| 主色调 | color_direction |
| 形状语言 | shape_language |
| 视觉气质 | visual_tone |
| 第一印象 | first_impression |
| 记忆点 | memory_points |

**LanguageStyle**（怪物跳过，status → 1）：

| 内容 | 属性 |
|------|------|
| 词汇风格 | vocabulary |
| 句子节奏 | rhythm |
| 语言习惯 | habits |
| 情绪模式（5 种情境） | emotion_patterns |
| 概要（1-2 句，含身份/绝不会说的话/标准台词） | description |

## 参考文档

- [角色美术设定模板](references/template-角色美术设定.md)
- [角色语言风格模板](references/template-角色语言风格.md)
