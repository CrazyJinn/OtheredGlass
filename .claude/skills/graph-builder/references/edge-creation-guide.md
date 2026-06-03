# 边创建指南

10 种边类型的方向规则、属性 schema 和 Cypher 模板。

---

## 叙事关系边（6种）

### 1. relation — 人物关系

- **方向**：`char → char`
- **属性**：`type`（关系类型，如"恋爱""亲属""同事"）、`detail`（如"恋爱中""已分手""姐弟"）
- **方向语义**：有向，A→B 表示 A 对 B 的关系描述

```cypher
MATCH (a:char {编号: $from}), (b:char {编号: $to})
MERGE (a)-[:relation {type: $type, detail: $detail}]->(b)
```

### 2. at — 人物—地点

- **方向**：`char → Location`
- **属性**：`type`（如"居住""前往""工作"）、`detail`

```cypher
MATCH (a:char {编号: $from}), (b:Location {编号: $to})
MERGE (a)-[:at {type: $type, detail: $detail}]->(b)
```

### 3. link — 信息关联

- **方向**：`任意实体 → Info`
- **属性**：`type`（如"涉及""因果"）、`detail`、`time`
- **特殊规则**：`type=因果` 时仅用于 `Info → Info`

```cypher
// 实体关联信息
MATCH (a {编号: $from}), (b:Info {编号: $to})
MERGE (a)-[:link {type: $type, detail: $detail, time: $time}]->(b)

// 信息因果链（仅 Info→Info）
MATCH (a:Info {编号: $from}), (b:Info {编号: $to})
MERGE (a)-[:link {type: '因果', detail: $detail}]->(b)
```

### 4. involved — 人物—事件

- **方向**：`char → Event`
- **属性**：`role`（如"当事人""目击者""受害者""施害者""参与者"）、`detail`

```cypher
MATCH (a:char {编号: $from}), (b:Event {编号: $to})
MERGE (a)-[:involved {role: $role, detail: $detail}]->(b)
```

### 5. occurred_at — 事件—地点

- **方向**：`Event → Location`
- **属性**：`detail`（如"跳江地点""约会地点"）

```cypher
MATCH (a:Event {编号: $from}), (b:Location {编号: $to})
MERGE (a)-[:occurred_at {detail: $detail}]->(b)
```

### 6. evt_relation — 事件—事件

- **方向**：`Event → Event`
- **属性**：`type`（`因果`/`先后`/`包含`）、`detail`
- **方向语义**：`因果` = 前因→后果；`先后` = 时间顺序；`包含` = 大事件→子事件

```cypher
MATCH (a:Event {编号: $from}), (b:Event {编号: $to})
MERGE (a)-[:evt_relation {type: $type, detail: $detail}]->(b)
```

---

## 美术风格边（4种）

### 7. HAS_STYLE — 实体—风格

- **方向**：`char / Faction / LocationType / Location → ArtStyle`
- **属性**：无
- **含义**：实体拥有的风格节点

```cypher
// 角色
MATCH (a:char {编号: $from}), (b:ArtStyle {编号: $to})
MERGE (a)-[:HAS_STYLE]->(b)

// 阵营
MATCH (a:Faction {编号: $from}), (b:ArtStyle {编号: $to})
MERGE (a)-[:HAS_STYLE]->(b)

// 地点类型
MATCH (a:LocationType {编号: $from}), (b:ArtStyle {编号: $to})
MERGE (a)-[:HAS_STYLE]->(b)

// 地点
MATCH (a:Location {编号: $from}), (b:ArtStyle {编号: $to})
MERGE (a)-[:HAS_STYLE]->(b)
```

### 8. INHERITS — 风格继承

- **方向**：`ArtStyle → ArtStyle`（子 → 父）
- **属性**：`override_fields`（逗号分隔的被覆盖字段名列表）
- **含义**：子风格继承父风格，非空字段覆盖

```cypher
MATCH (child:ArtStyle {编号: $from}), (parent:ArtStyle {编号: $to})
MERGE (child)-[:INHERITS {override_fields: $override_fields}]->(parent)
```

### 9. BELONGS_TO — 角色—阵营

- **方向**：`char → Faction`
- **属性**：`role`（如"战队经理""战队队长""成员"）
- **注意**：无阵营角色无此边

```cypher
MATCH (a:char {编号: $from}), (b:Faction {编号: $to})
MERGE (a)-[:BELONGS_TO {role: $role}]->(b)
```

### 10. CATEGORIZED_AS — 地点—类型

- **方向**：`Location → LocationType`
- **属性**：无

```cypher
MATCH (a:Location {编号: $from}), (b:LocationType {编号: $to})
MERGE (a)-[:CATEGORIZED_AS]->(b)
```

---

## 方向验证规则

创建边前必须验证方向正确：

| from 标签 | 允许的边类型 | to 标签 |
|-----------|------------|---------|
| char | relation, at, link, involved, HAS_STYLE, BELONGS_TO | → char / Location / Info / Event / ArtStyle / Faction |
| Event | occurred_at, evt_relation, link | → Location / Event / Info |
| Location | HAS_STYLE, CATEGORIZED_AS, link | → ArtStyle / LocationType / Info |
| Info | link | → Info |
| Faction | HAS_STYLE | → ArtStyle |
| LocationType | HAS_STYLE | → ArtStyle |
| ArtStyle | INHERITS | → ArtStyle |
| 任意 | link | → Info |
