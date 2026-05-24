// === 导入节点 ===

// 导入节点：人物
LOAD CSV WITH HEADERS FROM 'file:///nodes_char.csv' AS row
MERGE (n:char {编号: row.编号})
SET n.姓名 = row.姓名,
    n.性别 = row.性别,
    n.description = row.description
;;

// 导入节点：地点
LOAD CSV WITH HEADERS FROM 'file:///nodes_location.csv' AS row
MERGE (n:Location {编号: row.编号})
SET n.名称 = row.名称,
    n.描述 = row.描述
;;

// 导入节点：信息
LOAD CSV WITH HEADERS FROM 'file:///nodes_info.csv' AS row
MERGE (n:Info {编号: row.编号})
SET n.标题 = row.标题,
    n.内容 = row.内容,
    n.知识层 = toInteger(row.知识层)
;;

// 导入节点：事件
LOAD CSV WITH HEADERS FROM 'file:///nodes_event.csv' AS row
MERGE (n:Event {编号: row.编号})
SET n.标题 = row.标题,
    n.时间 = row.时间,
    n.描述 = row.描述,
    n.类型 = row.类型
;;

// === 导入边 ===

// 导入边：人物关系 (char → char)
LOAD CSV WITH HEADERS FROM 'file:///edges_relation.csv' AS row
MATCH (a:char {编号: row.from_id})
MATCH (b:char {编号: row.to_id})
MERGE (a)-[:relation {type: row.type, detail: row.detail}]->(b)
;;

// 导入边：人物—地点 (char → Location)
LOAD CSV WITH HEADERS FROM 'file:///edges_at.csv' AS row
MATCH (a:char {编号: row.from_id})
MATCH (b:Location {编号: row.to_id})
MERGE (a)-[:at {type: row.type, detail: row.detail}]->(b)
;;

// 导入边：人物—事件 (char → Event)
LOAD CSV WITH HEADERS FROM 'file:///edges_involved.csv' AS row
MATCH (a:char {编号: row.from_id})
MATCH (b:Event {编号: row.to_id})
MERGE (a)-[:involved {role: row.role, detail: row.detail}]->(b)
;;

// 导入边：事件—地点 (Event → Location)
LOAD CSV WITH HEADERS FROM 'file:///edges_occurred_at.csv' AS row
MATCH (a:Event {编号: row.from_id})
MATCH (b:Location {编号: row.to_id})
MERGE (a)-[:occurred_at {detail: row.detail}]->(b)
;;

// 导入边：信息关联 (任意 → Info)
LOAD CSV WITH HEADERS FROM 'file:///edges_link.csv' AS row
MATCH (a {编号: row.from_id})
MATCH (b:Info {编号: row.to_id})
MERGE (a)-[:link {type: row.type, detail: row.detail, time: row.time}]->(b)
;;

// 导入边：事件—事件 (Event → Event)
LOAD CSV WITH HEADERS FROM 'file:///edges_evt_relation.csv' AS row
MATCH (a:Event {编号: row.from_id})
MATCH (b:Event {编号: row.to_id})
MERGE (a)-[:evt_relation {type: row.type, detail: row.detail}]->(b)
;;
