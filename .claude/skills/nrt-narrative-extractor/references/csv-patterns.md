# CSV 格式规范与 LOAD CSV 导入模板

## CSV 格式规范

| 规则 | 说明 |
|------|------|
| 编码 | UTF-8 with BOM（Excel 兼容） |
| 分隔符 | 逗号 `,` |
| 引用 | 双引号 `"` 包裹含逗号/换行/引号的字段 |
| 转义 | 字段内双引号用 `""` 表示 |
| 表头 | 首行为列名，与叙事基础字段名一致 |
| 空值 | 必填列不可空，选填列留空（不写 NULL） |

### 引用示例

```csv
id,title,content,knowledge_level
info_001,正常标题,正常内容,1
info_002,"含逗号，需要引号","内容也有逗号，和换行
第二行",2
info_003,含"引号"的标题,"内容含""引号""需转义",3
```

## 文件命名

- 节点: `nodes_{节点类型小写}.csv`（如 `nodes_char.csv`、`nodes_info.csv`、`nodes_scene.csv`）
- 边: `edges_{边类型小写}.csv`（如 `edges_relation.csv`、`edges_involved.csv`）
- 导入脚本: `import.cypher`
- 摘要: `_summary.md`
- 输出目录: `01_叙事数据/csv/`

只生成有数据的文件。

## 列定义

### 节点 CSV

#### nodes_char.csv

| 列名 | 必填 | 类型 | 说明 |
|------|------|------|------|
| id | 是 | string | `char_NNN` |
| name | 是 | string | |
| gender | 否 | string | 男/女 |
| description | 否 | string | 人物简介 |
| birth_year | 否 | int | 如 2003 |
| character_tags | 否 | string | 人设标签，逗号分隔，如"沉默寡言, 外冷内热" |

#### nodes_scene.csv

| 列名 | 必填 | 类型 | 说明 |
|------|------|------|------|
| id | 是 | string | `scene_NNN` |
| name | 是 | string | |
| description | 否 | string | |

#### nodes_info.csv

| 列名 | 必填 | 类型 | 说明 |
|------|------|------|------|
| id | 是 | string | `info_NNN` |
| title | 是 | string | |
| content | 是 | string | |
| knowledge_level | 是 | int | 1/2/3 |

#### nodes_event.csv

| 列名 | 必填 | 类型 | 说明 |
|------|------|------|------|
| id | 是 | string | `evt_NNN` |
| title | 是 | string | |
| time | 是 | string | 日期格式，如 2024-04-11 |
| description | 否 | string | |
| type | 否 | string | 行动/交流/转折/状态变化 |

### 边 CSV

所有边 CSV 均以 `from_id` 和 `to_id` 开头。

#### edges_relation.csv

Character → Character

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | char 编号 |
| to_id | 是 | char 编号 |
| type | 是 | 关系类型，如"恋爱""亲属""同事""仇人" |
| detail | 否 | 关系详情，如"恋爱中""已分手""姐弟" |
| start_time | 否 | 关系建立时间 |
| end_time | 否 | 关系结束时间（空=持续中） |

#### edges_involved.csv

Character → Event

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | char 编号 |
| to_id | 是 | evt 编号 |
| role | 是 | 如"当事人""目击者""受害者""施害者""参与者" |
| detail | 否 | 角色详情 |

#### edges_occurred_at.csv

Event → Scene

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | evt 编号 |
| to_id | 是 | scene 编号 |
| detail | 否 | 如"跳江地点""约会地点" |

#### edges_at.csv

Character → Scene

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | char 编号 |
| to_id | 是 | scene 编号 |
| type | 是 | 关联类型，如"居住""前往""工作" |
| detail | 否 | |
| start_time | 否 | 关联开始时间 |
| end_time | 否 | 关联结束时间（空=持续中） |

#### edges_link.csv

Character / Event / Scene → Info（因果仅限 Info → Info）

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | char/evt/scene/info 编号 |
| to_id | 是 | info 编号 |
| type | 是 | "涉及" 或 "因果" |
| detail | 否 | 关联说明 |
| time | 否 | 信息关联发生的时间 |

> type=`因果` 仅用于 Info → Info，表示原因→结果。
> from_id 仅限 Character、Event、Scene、Info 四种节点。

#### edges_evt_relation.csv

Event → Event

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | evt 编号 |
| to_id | 是 | evt 编号 |
| type | 是 | "因果"/"先后"/"包含" |
| detail | 否 | 关联说明 |

> type 方向语义：因果 = 前因→后果；先后 = 时间顺序；包含 = 大事件→子事件

## LOAD CSV 导入模板

### 节点导入模板

```cypher
// 角色
LOAD CSV WITH HEADERS FROM 'file:///nodes_char.csv' AS row
MERGE (n:Character {id: row.id})
SET n.name = row.name,
    n.gender = row.gender,
    n.description = row.description,
    n.birth_year = toInteger(row.birth_year),
    n.character_tags = row.character_tags
;;

// 场景
LOAD CSV WITH HEADERS FROM 'file:///nodes_scene.csv' AS row
MERGE (n:Scene {id: row.id})
SET n.name = row.name,
    n.description = row.description
;;

// 事件
LOAD CSV WITH HEADERS FROM 'file:///nodes_event.csv' AS row
MERGE (n:Event {id: row.id})
SET n.title = row.title,
    n.time = row.time,
    n.description = row.description,
    n.type = row.type
;;

// 信息
LOAD CSV WITH HEADERS FROM 'file:///nodes_info.csv' AS row
MERGE (n:Info {id: row.id})
SET n.title = row.title,
    n.content = row.content,
    n.knowledge_level = toInteger(row.knowledge_level)
;;
```

### 边导入模板

```cypher
// relation: Character → Character
LOAD CSV WITH HEADERS FROM 'file:///edges_relation.csv' AS row
MATCH (a:Character {id: row.from_id})
MATCH (b:Character {id: row.to_id})
MERGE (a)-[:relation {type: row.type, detail: row.detail, start_time: row.start_time, end_time: row.end_time}]->(b)
;;

// involved: Character → Event
LOAD CSV WITH HEADERS FROM 'file:///edges_involved.csv' AS row
MATCH (a:Character {id: row.from_id})
MATCH (b:Event {id: row.to_id})
MERGE (a)-[:involved {role: row.role, detail: row.detail}]->(b)
;;

// occurred_at: Event → Scene
LOAD CSV WITH HEADERS FROM 'file:///edges_occurred_at.csv' AS row
MATCH (a:Event {id: row.from_id})
MATCH (b:Scene {id: row.to_id})
MERGE (a)-[:occurred_at {detail: row.detail}]->(b)
;;

// at: Character → Scene
LOAD CSV WITH HEADERS FROM 'file:///edges_at.csv' AS row
MATCH (a:Character {id: row.from_id})
MATCH (b:Scene {id: row.to_id})
MERGE (a)-[:at {type: row.type, detail: row.detail, start_time: row.start_time, end_time: row.end_time}]->(b)
;;

// link: Character/Event/Scene/Info → Info
LOAD CSV WITH HEADERS FROM 'file:///edges_link.csv' AS row
MATCH (a) WHERE a.id = row.from_id AND (labels(a) = ['Character'] OR labels(a) = ['Event'] OR labels(a) = ['Scene'] OR labels(a) = ['Info'])
MATCH (b:Info {id: row.to_id})
MERGE (a)-[:link {type: row.type, detail: row.detail, time: row.time}]->(b)
;;

// evt_relation: Event → Event
LOAD CSV WITH HEADERS FROM 'file:///edges_evt_relation.csv' AS row
MATCH (a:Event {id: row.from_id})
MATCH (b:Event {id: row.to_id})
MERGE (a)-[:evt_relation {type: row.type, detail: row.detail}]->(b)
;;
```

> 节点导入在前，边导入在后。整数类型字段需 `toInteger()` 转换。时间字段保持字符串格式。
