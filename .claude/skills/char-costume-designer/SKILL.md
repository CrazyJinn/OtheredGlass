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
| char_id | 角色节点 ID（snowflake Base62） | 必传 |

## 流程

### 1. 获取角色数据

通过 neo4j-helper 查询以下数据：

```cypher
// 角色 + 外貌 + 已有着装
MATCH (ch:Character {id: $char_id})
OPTIONAL MATCH (ch)-[:has_appearance]->(app:AppearanceStyle)
OPTIONAL MATCH (ch)-[:has_costume]->(cos:CostumeStyle)
RETURN ch, app, collect(cos) AS costumes;

// 事件 + 场景 + 已有着装绑定
MATCH (ch:Character {id: $char_id})-[r:involved]->(e:Event)
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
MATCH (e:Event {id: '<event_id>'}), (cos:CostumeStyle {id: '<costume_id>'})
MERGE (e)-[r:wears]->(cos) SET r.sync = false;
```

复用操作无需审批，直接生效。

### 4. 创建新 CostumeStyle（建议 → 待审批）

对需要新着装的事件组：

#### 4.1 生成节点 ID

生成 snowflake ID：

```bash
python "${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py" -n 1 -q
```

#### 4.2 创建节点和边

```cypher
MERGE (cos:CostumeStyle {id: '<snowflake_id>'})
SET cos.name = '角色名-着装描述',
    cos.status = 1, cos.approve = 'pending';

MATCH (ch:Character {id: $char_id}), (cos:CostumeStyle {id: '<snowflake_id>'})
MERGE (ch)-[r:has_costume]->(cos) SET r.sync = true;

MATCH (e:Event) WHERE e.id IN ['<event_id_1>', '<event_id_2>', ...]
MATCH (cos:CostumeStyle {id: '<snowflake_id>'})
MERGE (e)-[r:wears]->(cos) SET r.sync = false;
```

#### 4.3 生成并填写内容

基于事件上下文和角色信息，填写以下字段。

**自由文本字段**：

| 字段 | 内容来源 | 示例 |
|------|---------|------|
| name | 角色名 + 着装场景描述 | `沈暮雪-休闲约会着装` |

**设计元素标签字段**（值=分号 `;` 分隔标签，参考 `55_manage/标签库.json`）：

| 维度 | 属性 | 候选 |
|------|------|------|
| 着装风格 | outfit_style | 休闲/正式/运动/性感/可爱/学院/街头/古风/慵懒（可多选） |
| 服装 | garment | 合成组合：材质+颜色+服装类型（配对型，每组≤1自动合成），如 `棉白衬衫`；多件手动添加多个 `棉白衬衫;蕾丝黑内衣` |
| 鞋类 | footwear | 运动鞋/皮鞋/靴/帆布鞋/凉鞋/高跟鞋/赤足 |
| 配饰类型 | accessory_type | 耳饰/项链/手表/眼镜/戒指/发饰/手持物（可多选） |

**内容生成规则**：
- 参考 `00_init/世界设定.md`、`00_init/人物设定.md`、角色 tags
- 参考 Character 的 `color_direction` 保持配色体系一致
- 服装款式/颜色统一用 `garment` 标签（材质+颜色+类型）表达，是服装信息的**唯一数据源**；标签未覆盖的款式细节（领型、滚边、层次、剪裁、质感氛围）用标签库的**自定义输入**补充到标签值，不另设自由文本字段
- 标志性道具的**类型**放入 `accessory_type` 标签，具体样式用自定义标签值补充
- 着装不再单独设计体态——IllusDesign 复用 DesignSheet 的静态站姿（角色默认体态已在外貌层）

### 5. 报告结果

汇总所有操作：
- 复用了哪些已有 CostumeStyle（哪些事件）
- 新建了哪些 CostumeStyle（哪些事件，approve='pending'）
- 提示用户在 dashboard 中审批新建的着装方案

## 参考文档

- [着装设定模板](references/template-着装设定.md) — 各字段规则
