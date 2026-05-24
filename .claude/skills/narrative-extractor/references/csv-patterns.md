# CSV 格式规范与 LOAD CSV 导入模板

## CSV 格式规范

| 规则 | 说明 |
|------|------|
| 编码 | UTF-8 with BOM（Excel 兼容） |
| 分隔符 | 逗号 `,` |
| 引用 | 双引号 `"` 包裹含逗号/换行/引号的字段 |
| 转义 | 字段内双引号用 `""` 表示 |
| 表头 | 首行为列名，与 Schema 字段名一致 |
| 空值 | 必填列不可空，选填列留空（不写 NULL） |

### 引用示例

```csv
编号,标题,内容,知识层
info_001,正常标题,正常内容,1
info_002,"含逗号，需要引号","内容也有逗号，和换行
第二行",2
info_003,含"引号"的标题,"内容含""引号""需转义",3
```

## 文件命名

- 节点: `nodes_{节点类型小写}.csv`（如 `nodes_char.csv`、`nodes_info.csv`）
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
| 编号 | 是 | string | `char_NNN` |
| 姓名 | 是 | string | |
| 性别 | 否 | string | 男/女 |
| description | 否 | string | |
| 籍贯 | 否 | string | |
| 出生年份 | 否 | int | |

#### nodes_location.csv

| 列名 | 必填 | 类型 | 说明 |
|------|------|------|------|
| 编号 | 是 | string | `loc_NNN` |
| 名称 | 是 | string | |
| 描述 | 否 | string | |

#### nodes_info.csv

| 列名 | 必填 | 类型 | 说明 |
|------|------|------|------|
| 编号 | 是 | string | `info_NNN` |
| 标题 | 是 | string | |
| 内容 | 是 | string | |
| 知识层 | 是 | int | 1/2/3 |

#### nodes_event.csv

| 列名 | 必填 | 类型 | 说明 |
|------|------|------|------|
| 编号 | 是 | string | `evt_NNN` |
| 标题 | 是 | string | |
| 时间 | 是 | string | 如 Day 0、开场 |
| 描述 | 否 | string | |
| 类型 | 否 | string | 行动/交流/转折/状态变化 |

### 边 CSV

所有边 CSV 均以 `from_id` 和 `to_id` 开头。

#### edges_relation.csv

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | char 编号 |
| to_id | 是 | char 编号 |
| type | 是 | 关系类型 |
| detail | 否 | 关系详情 |

#### edges_at.csv

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | char 编号 |
| to_id | 是 | Location 编号 |
| type | 否 | 如"居住" |
| detail | 否 | |

#### edges_involved.csv

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | char 编号 |
| to_id | 是 | Event 编号 |
| role | 是 | 如"当事人"、"发起者"、"照顾者" |
| detail | 否 | 角色详情 |

#### edges_occurred_at.csv

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | Event 编号 |
| to_id | 是 | Location 编号 |
| detail | 否 | 如"跳江地点" |

#### edges_link.csv

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | 任意实体编号 |
| to_id | 是 | Info 编号 |
| type | 是 | "涉及" 或 "因果" |
| detail | 否 | 因果说明 |
| time | 否 | 发生时间 |

> type=`因果` 仅用于 Info → Info。

#### edges_evt_relation.csv

| 列名 | 必填 | 说明 |
|------|------|------|
| from_id | 是 | Event 编号 |
| to_id | 是 | Event 编号 |
| type | 是 | "因果"/"先后"/"包含" |
| detail | 否 | 关联说明 |

## LOAD CSV 导入模板

### 节点导入模板

```cypher
LOAD CSV WITH HEADERS FROM 'file:///nodes_char.csv' AS row
MERGE (n:char {编号: row.编号})
SET n.姓名 = row.姓名,
    n.性别 = row.性别,
    n.description = row.description
;;
```

### 边导入模板

```cypher
LOAD CSV WITH HEADERS FROM 'file:///edges_relation.csv' AS row
MATCH (a:char {编号: row.from_id})
MATCH (b:char {编号: row.to_id})
MERGE (a)-[:relation {type: row.type, detail: row.detail}]->(b)
;;
```

> 节点导入在前，边导入在后。整数类型字段需 `toInteger()` 转换。
