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

通过 neo4j-helper 按名称查找角色，获取完整信息：

```cypher
MATCH (ch:Character) WHERE ch.name = '角色名'
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

先生成 snowflake ID（AppearanceStyle 和 LanguageStyle 各需一个）：

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py" -n 2 -q
```

通过 neo4j-helper 执行 Cypher 创建节点和边。

#### 3.1 AppearanceStyle（1 个）

创建节点 + `has_appearance` 边（Character → AppearanceStyle）：

```cypher
MERGE (app:AppearanceStyle {id: '<snowflake_id_1>'})
SET app.name = '角色名外貌特征', app.status = 0
WITH app
MATCH (ch:Character) WHERE ch.name = '角色名'
MERGE (ch)-[r:has_appearance]->(app)
SET r.sync = true;
```

#### 3.2 LanguageStyle（1 个，怪物跳过）

创建节点 + `has_voice_style` 边（Character → LanguageStyle）：

```cypher
MERGE (voice:LanguageStyle {id: '<snowflake_id_2>'})
SET voice.name = '角色名语言风格', voice.status = 0
WITH voice
MATCH (ch:Character) WHERE ch.name = '角色名'
MERGE (ch)-[r:has_voice_style]->(voice)
SET r.sync = true;
```

### 4. 生成内容并写入图节点

按模板（见 references/）生成内容，直接通过 neo4j-helper 写入图节点字段。

**AppearanceStyle**（status → 1）：

自由文本字段：

| 内容 | 属性 |
|------|------|
| 外貌描述（综合气质/身高） | appearance |
| 视觉气质 | visual_tone |
| 第一印象 | first_impression |

**角色配色**（写入 Character 节点，非 AppearanceStyle）：

| 内容 | 属性 |
|------|------|
| 配色逻辑（主辅点缀色 + 明暗逻辑） | Character.color_direction |

通过 neo4j-helper 写入 Character 节点（步骤 1 已查询 `ch:Character`）：

```cypher
MATCH (ch:Character) WHERE ch.name = '角色名'
SET ch.color_direction = '<配色逻辑自由文本>';
```

设计元素标签字段（值=分号 `;` 分隔标签，参考 `55_manage/标签库.json` 受控词表）：

| 维度 | 属性 | 候选 |
|------|------|------|
| 形状语言 | shape_language | 三角型/方型/倒三角/细长型/圆形/不对称 |
| 年龄感 | age_impression | 少女/青年/成熟/御姐/正太/少年 |
| 体态 | body_type | 曼妙/修长/健壮/娇小/丰腴/少年感/匀称 |
| 肤色 | skin_tone | 象牙白/瓷白/苍白/蜜色/健康粉/小麦/古铜 |
| 头发 | hair | 合成组合：发色+发型+发长，如 `深棕色大波浪长发`（dashboard 选子维度自动合成） |
| 眼睛 | eye | 合成组合：瞳色+眼型，如 `琥珀色上挑眼` |
| 唇形 | lip_shape | 薄唇/饱满/厚唇/微笑唇 |
| 特殊标记 | marks | 无/疤痕/纹身/胎记/泪痣（可多选） |

标签从角色设定提取并合成（"深棕色大波浪长发"→ `hair=深棕色大波浪长发`；"琥珀色上挑眼"→ `eye=琥珀色上挑眼`）。无明确值的维度可留空。

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
