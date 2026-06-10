---
name: char-costume-designer
description: |
  为角色的每个事件设计着装方案。创建 CostumeStyle 节点 + wears 边（Event → CostumeStyle），
  建议内容写入后设 approve='pending'，等待 dashboard 审批。
  在需要为角色创建/追加着装方案时使用。
argument-hint: <char_id>
arguments:
  - char_id
allowed-tools: Read, Bash, Write, Edit
---

# 着装设计（CostumeStyle）

为角色的每个事件分析着装需求，创建 CostumeStyle 节点并绑定 `wears` 边。建议内容写入后设 `approve='pending'`，等待 dashboard 审批通过后参与下游 IllusDesign 生产。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| char_id | 角色节点 ID（如 `char_007`） | 必传 |

## 流程

### 1. 获取角色数据

通过 neo4j-helper 查询以下数据：

```cypher
// 角色 + 外貌 + 已有着装
MATCH (ch:Character {id: 'char_NNN'})
OPTIONAL MATCH (ch)-[:has_appearance]->(app:AppearanceStyle)
OPTIONAL MATCH (ch)-[:has_costume]->(cos:CostumeStyle)
RETURN ch, app, collect(cos) AS costumes;

// 事件 + 场景 + 已有着装绑定
MATCH (ch:Character {id: 'char_NNN'})-[r:involved]->(e:Event)
OPTIONAL MATCH (e)-[:occurred_at]->(s:Scene)
OPTIONAL MATCH (e)-[:wears]->(cos:CostumeStyle)
RETURN e.id AS event_id, e.title AS event_title,
       r.role AS role, r.detail AS detail,
       s.id AS scene_id, s.name AS scene_name, s.description AS scene_desc,
       cos.id AS costume_id, cos.name AS costume_name
ORDER BY e.id;
```

### 2. 分析事件着装需求

对每个**没有 `wears` 边的 Event**：

1. 提取事件上下文：
   - 事件 detail（角色在事件中的行为）
   - Scene 环境（如果 `occurred_at` 边存在）
   - 角色身份（character_tags）
2. 判断是否可复用已有 CostumeStyle：
   - 比较事件环境与已有着装的适配度
   - 例如：已有"职场御姐着装"，事件发生在"星耀电竞办公室" → 可复用
   - 例如：已有"职场御姐着装"，事件发生在"咖啡店约会" → 需要新着装
3. 按着装需求分组：
   - 同一着装可覆盖的事件归为一组
   - 每组对应一个 CostumeStyle 节点

### 3. 复用已有 CostumeStyle

对可复用已有 CostumeStyle 的事件组，直接创建 `wears` 边：

```cypher
MATCH (e:Event {id: 'evt_NNN'}), (cos:CostumeStyle {id: 'costume_NNN'})
MERGE (e)-[r:wears]->(cos) SET r.sync = false;
```

复用操作无需审批，直接生效。

### 4. 创建新 CostumeStyle（建议 → 待审批）

对需要新着装的事件组：

#### 4.1 确定节点 ID

查询已有最大编号：
```cypher
MATCH (n:CostumeStyle) WHERE n.id STARTS WITH 'costume_' RETURN n.id ORDER BY n.id DESC LIMIT 1
```

取最大编号 + 1 作为新 ID。

#### 4.2 创建节点和边

```cypher
MERGE (cos:CostumeStyle {id: 'costume_NNN'})
SET cos.name = '角色名-着装描述',
    cos.status = 1, cos.approve = 'pending';

MATCH (ch:Character {id: 'char_NNN'}), (cos:CostumeStyle {id: 'costume_NNN'})
MERGE (ch)-[r:has_costume]->(cos) SET r.sync = true;

MATCH (e:Event) WHERE e.id IN ['evt_NNN', 'evt_NNN', ...]
MATCH (cos:CostumeStyle {id: 'costume_NNN'})
MERGE (e)-[r:wears]->(cos) SET r.sync = false;
```

#### 4.3 生成并填写内容

基于事件上下文和角色信息，填写以下字段：

| 字段 | 内容来源 | 示例 |
|------|---------|------|
| name | 角色名 + 着装场景描述 | `沈暮雪-休闲约会着装` |
| default_outfit | 根据事件环境设计的完整着装描述 | `米色针织开衫, 白色T恤, 浅色牛仔裤, 白色帆布鞋` |
| material_direction | 与着装匹配的材质/质感 | `针织（柔软垂坠感）+ 纯棉（哑光透气）+ 帆布（轻便休闲）` |
| posture | 与着装场景匹配的体态气质 | `重心居中偏放松, 肩线自然下垂, 带有随性舒适的站姿` |
| accessories | 与着装搭配的配饰 | `银框半框眼镜, 左手腕细链玫瑰金手表, 小巧珍珠耳钉` |

**内容生成规则**：
- 参考 `00_init/世界设定.md`、`00_init/人物设定.md`、角色 tags
- 参考 AppearanceStyle 的 `color_direction` 保持配色体系一致
- 体态气质中的站姿必须是可用于三视图的**静态站姿**（肩线、重心、躯干状态），不包含手部动作
- 标志性道具放在 accessories 中

### 5. 报告结果

汇总所有操作：
- 复用了哪些已有 CostumeStyle（哪些事件）
- 新建了哪些 CostumeStyle（哪些事件，approve='pending'）
- 提示用户在 dashboard 中审批新建的着装方案

## 参考文档

- [着装设定模板](references/template-着装设定.md) — 各字段规则 + 体态气质反例
