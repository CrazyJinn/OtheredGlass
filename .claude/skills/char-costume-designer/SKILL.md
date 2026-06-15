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

基于事件上下文和角色信息，填写以下字段（标签字段值用分号 `;` 分隔，参考 `55_manage/标签库.json`）：

| 维度 | 属性 | 示例 | 说明 |
|------|------|------|------|
| 名称 | name | `沈暮雪-休闲约会着装` | 自由文本（角色名 + 着装场景描述） |
| 着装风格 | outfit_style | 休闲 / 正式 / 运动 / 性感 / 可爱 / 学院 / 街头 / 古风 / 慵懒 | 可多选 |
| 服装 | garment | `棉白衬衫` | `棉质白衬衫;蕾丝女式三角内裤;黑色丝袜` |
| 鞋类 | footwear | 运动鞋 / 皮鞋 / 靴 / 帆布鞋 / 凉鞋 / 高跟鞋 / 赤足 | 单选 |
| 配饰类型 | accessory_type | 耳饰 / 项链 / 手表 / 眼镜 / 戒指 / 发饰 / 手持物 | 可多选 |

**内容生成规则**：
1. 可以参考以下内容：
   - `00_init/世界设定.md`，确保服装风格不违背世界观
   - 角色配色参考 Character 的 `color_direction` ，**但是不强求一致**
2. 服装款式/颜色统一记录在 `garment` 属性，多件服饰用 `;` 分隔
   每件服饰包含以下内容：
   - 必选：材质+颜色+类型
   - 可选：领型、滚边、层次、剪裁、质感氛围等。可以适当补充但是不宜太多
3. 配饰内容放入 `accessory_type` ，具体样式用自定义标签值补充

### 5. 报告结果

汇总所有操作：
- 复用了哪些已有 CostumeStyle（哪些事件）
- 新建了哪些 CostumeStyle（哪些事件，approve='pending'）
- 提示用户在 dashboard 中审批新建的着装方案

## 参考文档

- [着装设定模板](references/template-着装设定.md) — 各字段规则
