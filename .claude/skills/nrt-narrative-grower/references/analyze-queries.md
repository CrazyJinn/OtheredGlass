# analyze 查询：10 种叙事创意检查

> analyze 阶段依次跑下列检查，输出 `--json` 结果供 LLM 汇总为 `growth_opportunities`。
> 这些检查偏向**叙事创意发现**（与 nrt-graph-builder 的 7 种**数据质量**检查互补，仅 temporal_gaps 重叠）。
> 节点/边定义见 [00_init/Schema/叙事基础.md](../../../00_init/Schema/叙事基础.md)（Character / Event / Location / Info + 6 边）。

每条查询示例用 `python ${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py -c "<cypher>" --json` 执行。LLM 读 JSON 输出后做必要的后处理与建议生成。

---

## 1. temporal_gaps（时间线缺口）

找出事件时间线上的大间隔（叙事空白期，可能需要补过渡事件）。

```cypher
MATCH (e:Event) WHERE e.time IS NOT NULL
RETURN e.id AS id, e.title AS title, e.time AS time
ORDER BY e.time LIMIT 200
```

后处理：LLM 解析 `time`（如"第N天"），计算相邻事件间隔，间隔过大处标记 high 优先级建议（补桥接事件）。

## 2. character_arcs（角色弧完整性）

判断每个角色的活跃度：active（持续参与）/ vanished（中途消失）/ no_events（无事件）。

```cypher
MATCH (c:Character)
OPTIONAL MATCH (c)-[:involved]->(e:Event)
RETURN c.id AS id, c.name AS name, c.priority AS priority,
       count(e) AS events, collect(e.time) AS times
ORDER BY events DESC
```

后处理：核心角色（P0/P1）若 events 少或时间分布断层 → medium/high 建议补角色弧事件。

## 3. implicit_relations（隐含关系）

共同参与事件但无 `relation` 边的角色对——可能存在未显式记录的关系。

```cypher
MATCH (a:Character)-[:involved]->(e:Event)<-[:involved]-(b:Character)
WHERE elementId(a) < elementId(b)
  AND NOT (a)-[:relation]-(b)
RETURN a.name AS a, b.name AS b,
       collect(e.title) AS shared_events, count(e) AS shared
ORDER BY shared DESC LIMIT 50
```

建议：shared ≥ 2 的角色对 → high 建议补充 `relation` 边（建议 action：`ADD_EDGE relation(a_id, b_id){type, detail}`）。

## 4. event_chains（事件链断裂）

孤立事件（无 `evt_relation` 因果/时序链接）。

```cypher
MATCH (e:Event)
WHERE NOT (e)-[:evt_relation]->() AND NOT (e)<-[:evt_relation]-()
RETURN e.id AS id, e.title AS title, e.time AS time
ORDER BY e.time LIMIT 100
```

建议：孤立的关键事件 → medium 建议建立因果链。

## 5. scene_utilization（场景利用率）

各 Location 承载的事件数，找未被充分利用或过载的场景。

```cypher
MATCH (l:Location)
OPTIONAL MATCH (e:Event)-[:occurred_at]->(l)
RETURN l.id AS id, l.name AS name, count(e) AS events
ORDER BY events ASC LIMIT 100
```

## 6. info_depth（信息深度）

知识层（Info.knowledge_level 1/2/3）分布 + 孤立信息（无任何边）。

```cypher
MATCH (i:Info)
RETURN i.knowledge_level AS level, count(i) AS cnt ORDER BY level
```

```cypher
MATCH (i:Info) WHERE NOT (i)--()
RETURN i.id AS id, i.title AS title LIMIT 100
```

建议：孤立 Info → medium 建议链接到实体（`at` / `link` 边）。

## 7. subgraph_connectivity（子图连通性）

各角色的连接广度（涉及的 Location / 事件 / 其他角色）。

```cypher
MATCH (c:Character)
OPTIONAL MATCH (c)-[:involved]->(e:Event)-[:occurred_at]->(l:Location)
RETURN c.id AS id, c.name AS name,
       count(DISTINCT e) AS events, count(DISTINCT l) AS locations
ORDER BY locations ASC LIMIT 100
```

建议：核心角色 locations 偏少 → low 建议拓展场景。

## 8. relationship_evolution（关系演化）

现有 `relation` 边，判断是否需要记录演化（关系随时间变化）。

```cypher
MATCH (a:Character)-[r:relation]-(b:Character)
WHERE elementId(a) < elementId(b)
RETURN a.name AS a, b.name AS b, r.type AS type, r.detail AS detail
LIMIT 100
```

建议：长跨度关系 → low 建议补充关系变化事件。

## 9. bridge_scenes（桥接场景）

连接多个人物/故事线的场景（高价值枢纽）。

```cypher
MATCH (l:Location)<-[:occurred_at]-(e:Event)<-[:involved]-(c:Character)
WITH l, collect(DISTINCT c.name) AS chars, count(DISTINCT e) AS events
WHERE size(chars) >= 3
RETURN l.name AS location, chars, events
ORDER BY size(chars) DESC LIMIT 50
```

## 10. narrative_density（叙事密度）

每天/每时间段的事件密度，找过密或过稀处。

```cypher
MATCH (e:Event) WHERE e.time IS NOT NULL
RETURN e.time AS time, count(e) AS events
ORDER BY e.time LIMIT 200
```

后处理：LLM 计算每个时间段的事件数，过密（需拆分/详写）或过稀（需补充）处标记建议。

---

## growth_opportunities 汇总结构

LLM 把上述结果汇总为（沿用 graph-builder discover 结构）：

```json
{
  "summary": "本次分析的整体结论（1-2 句）",
  "suggestions": [
    {
      "check": "implicit_relations",
      "priority": "high",
      "description": "陆择与沈暮雪共同参与 3 个事件但无人物关系边",
      "action": "ADD_EDGE relation(<id_a>, <id_b>) {type: '?', detail: '?'}"
    }
  ],
  "details": { /* 各检查的原始统计，供 generate 参考 */ }
}
```

`generate` 阶段据此撰写创意草案（不仅是补边，更鼓励补充叙事事件/角色弧/桥接场景等创意内容）。
