// ========================================
// OtheredGlass 叙事数据导入脚本
// 生成时间：2026-06-10
// 数据来源：00_init/大纲.md
// ========================================

// --- 节点导入 ---

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

// --- 边导入 ---

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
