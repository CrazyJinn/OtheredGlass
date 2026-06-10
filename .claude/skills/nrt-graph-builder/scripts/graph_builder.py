"""
graph_builder.py — 自增长图构建器
命令：auto-ids, add-nodes, add-edges, execute-tx, discover
"""

import argparse
import json
import os
import re
import sys

# 导入 neo4j-helper 的 Neo4jClient（已改名为 infra-neo4j-helper）
_NEO4J_HELPER = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "infra-neo4j-helper", "scripts"
))
if os.path.isdir(_NEO4J_HELPER):
    sys.path.insert(0, _NEO4J_HELPER)

from neo4j_client import Neo4jClient, create_client

# ─── ID 前缀映射 ───────────────────────────────────────────────
ID_CONFIG = {
    "char":         {"prefix": "char_",  "label": "char"},
    "Location":     {"prefix": "loc_",   "label": "Location"},
    "Event":        {"prefix": "evt_",   "label": "Event"},
    "Info":         {"prefix": "info_",  "label": "Info"},
    "Faction":      {"prefix": "faction_", "label": "Faction"},
    "LocationType": {"prefix": "loctype_", "label": "LocationType"},
}

# 显示名映射
DISPLAY_NAME = {
    "char": "姓名", "Location": "名称", "Event": "标题",
    "Info": "标题", "Faction": "name", "LocationType": "name",
}


def get_password(args):
    return args.password or os.environ.get("NEO4J_PASSWORD", "12345678")


# ═══════════════════════════════════════════════════════════════
# auto-ids: 查询各节点类型当前最大编号，返回下一个可用 ID
# ═══════════════════════════════════════════════════════════════
def cmd_auto_ids(client, labels):
    result = {}
    for label in labels:
        cfg = ID_CONFIG.get(label)
        if not cfg:
            result[label] = {"error": f"未知标签: {label}"}
            continue
        prefix = cfg["prefix"]
        rows = client.run(
            f"MATCH (n:{cfg['label']}) RETURN n.编号 AS id ORDER BY n.编号 DESC LIMIT 1"
        )
        if rows and rows[0]["id"]:
            raw = rows[0]["id"]
            # 从 prefix_NNN 或 prefix_scope_NNN 提取最后一段数字
            num_str = raw.replace(prefix, "")
            parts = num_str.split("_")
            current_max = int(parts[-1]) if parts[-1].isdigit() else 0
        else:
            current_max = 0
        next_num = current_max + 1
        next_id = f"{prefix}{next_num:03d}"
        result[label] = {"current_max": current_max, "next_id": next_id}
    return result


# ═══════════════════════════════════════════════════════════════
# add-nodes: 原子创建节点（事务内查max+MERGE）
# ═══════════════════════════════════════════════════════════════
def cmd_add_nodes(client, nodes_json):
    """nodes_json: [{"label":"char", "props":{"姓名":"张三","性别":"男"}}]"""
    nodes = json.loads(nodes_json) if isinstance(nodes_json, str) else nodes_json
    created = []
    cypher_list = []

    # 先收集每种 label 的 max 查询 + MERGE 语句
    label_counters = {}
    for node in nodes:
        label = node["label"]
        props = node.get("props", {})
        cfg = ID_CONFIG.get(label)
        if not cfg:
            return {"error": f"未知标签: {label}"}

        prefix = cfg["prefix"]
        label_key = cfg["label"]

        # 如果没有显式提供编号，则自增分配
        if "编号" not in props:
            # 获取当前 max
            if label_key not in label_counters:
                rows = client.run(
                    f"MATCH (n:{label_key}) RETURN n.编号 AS id ORDER BY n.编号 DESC LIMIT 1"
                )
                if rows and rows[0]["id"]:
                    raw = rows[0]["id"]
                    num_str = raw.replace(prefix, "")
                    parts = num_str.split("_")
                    label_counters[label_key] = int(parts[-1]) if parts[-1].isdigit() else 0
                else:
                    label_counters[label_key] = 0
            label_counters[label_key] += 1
            next_num = label_counters[label_key]
            props["编号"] = f"{prefix}{next_num:03d}"

        # 构建 MERGE + SET
        assigned_id = props["编号"]
        set_parts = []
        for k, v in props.items():
            if isinstance(v, int):
                set_parts.append(f"n.{k} = {v}")
            elif v is None:
                continue
            else:
                escaped = str(v).replace("'", "\\'")
                set_parts.append(f"n.{k} = '{escaped}'")
        set_clause = ", ".join(set_parts) if set_parts else ""
        cypher = f"MERGE (n:{label_key} {{编号: '{assigned_id}'}})"
        if set_clause:
            cypher += f" SET {set_clause}"
        cypher_list.append(cypher)
        created.append({"label": label, "id": assigned_id, "name": props.get(DISPLAY_NAME.get(label, ""), "")})

    # 原子执行
    client.run_in_transaction(cypher_list)
    return {"created": created}


# ═══════════════════════════════════════════════════════════════
# add-edges: 创建边（验证端点存在）
# ═══════════════════════════════════════════════════════════════
def cmd_add_edges(client, edges_json):
    """edges_json: [{"type":"involved","from_id":"char_010","to_id":"evt_014","props":{"role":"参与者"}}]"""
    edges = json.loads(edges_json) if isinstance(edges_json, str) else edges_json
    created, skipped, errors = [], [], []

    # 边方向规则: edge_type -> (from_label_pattern, to_label_pattern)
    EDGE_RULES = {
        "relation":       ("char", "char"),
        "at":             ("char", "Location"),
        "link":           (None, "Info"),        # from 可以是任意类型
        "involved":       ("char", "Event"),
        "occurred_at":    ("Event", "Location"),
        "evt_relation":   ("Event", "Event"),
        "BELONGS_TO":     ("char", "Faction"),
        "CATEGORIZED_AS": ("Location", "LocationType"),
    }

    for edge in edges:
        etype = edge["type"]
        from_id = edge["from_id"]
        to_id = edge["to_id"]
        props = edge.get("props", {})

        rule = EDGE_RULES.get(etype)
        if not rule:
            errors.append({"type": etype, "error": f"未知边类型: {etype}"})
            continue

        from_label, to_label = rule

        # 验证端点
        from_match = f"MATCH (a {{编号: '{from_id}'}})" if from_label is None else f"MATCH (a:{from_label} {{编号: '{from_id}'}})"
        to_match = f"MATCH (b {{编号: '{to_id}'}})" if to_label is None else f"MATCH (b:{to_label} {{编号: '{to_id}'}})"

        # 构建属性
        prop_parts = []
        for k, v in props.items():
            if isinstance(v, int):
                prop_parts.append(f"{k}: {v}")
            else:
                escaped = str(v).replace("'", "\\'")
                prop_parts.append(f"{k}: '{escaped}'")
        prop_str = " {" + ", ".join(prop_parts) + "}" if prop_parts else ""

        cypher = f"{from_match} {to_match} MERGE (a)-[:{etype}{prop_str}]->(b)"

        try:
            stats = client.run_write(cypher)
            if stats.get("relationships_created", 0) > 0:
                created.append({"type": etype, "from": from_id, "to": to_id})
            else:
                skipped.append({"type": etype, "from": from_id, "to": to_id, "reason": "已存在"})
        except Exception as e:
            errors.append({"type": etype, "from": from_id, "to": to_id, "error": str(e)})

    return {"created": created, "skipped": skipped, "errors": errors}


# ═══════════════════════════════════════════════════════════════
# execute-tx: 在一个事务内执行多条 Cypher
# ═══════════════════════════════════════════════════════════════
def cmd_execute_tx(client, cypher_json):
    """cypher_json: JSON array of Cypher strings"""
    statements = json.loads(cypher_json) if isinstance(cypher_json, str) else cypher_json
    results = client.run_in_transaction(statements)
    return {"executed": len([s for s in statements if s.strip() and not s.strip().startswith("//")]),
            "results": results}


# ═══════════════════════════════════════════════════════════════
# discover: 图算法发现 — 6种检查 + 可操作建议
# ═══════════════════════════════════════════════════════════════

def _node_name(record):
    """从查询结果中提取节点显示名"""
    return record.get("name", record.get("标题", record.get("id", "?")))


def _parse_day(time_str):
    """将事件时间解析为可排序的数值。'开场' → -1, 'Day N ...' → N, 否则返回 None"""
    if not time_str:
        return None
    time_str = str(time_str).strip()
    if time_str == "开场":
        return -1
    m = re.match(r"Day\s*(\d+)", time_str)
    if m:
        return int(m.group(1))
    return None


def discover_orphans(client):
    """检查1: 孤立节点（零边）"""
    rows = client.run("""
        MATCH (n) WHERE NOT (n)--()
        RETURN labels(n)[0] AS label, n.编号 AS id,
               COALESCE(n.姓名, n.名称, n.标题, n.name) AS name
    """)
    suggestions = []
    for r in rows:
        suggestions.append({
            "priority": "medium",
            "type": "orphan",
            "description": f"{r['label']} {r['name']}({r['id']}) 没有任何关联关系",
            "action": f"建议为 {r['id']} 添加至少一条边（relation/at/involved/link 等）",
        })
    return {"findings": rows, "suggestions": suggestions}


def discover_missing_relations(client):
    """检查2: 共享事件但无 relation 边的角色对"""
    rows = client.run("""
        MATCH (c1:char)-[:involved]->(e:Event)<-[:involved]-(c2:char)
        WHERE c1.编号 < c2.编号
          AND NOT (c1)-[:relation]-(c2)
        RETURN c1.编号 AS char1_id, c1.姓名 AS char1_name,
               c2.编号 AS char2_id, c2.姓名 AS char2_name,
               COLLECT(DISTINCT e.标题) AS shared_events,
               COUNT(DISTINCT e) AS shared_count
        ORDER BY shared_count DESC
    """)
    suggestions = []
    for r in rows:
        events_str = "、".join(r["shared_events"][:3])
        if len(r["shared_events"]) > 3:
            events_str += f"等{r['shared_count']}个事件"
        suggestions.append({
            "priority": "high",
            "type": "missing_relation",
            "description": f"{r['char1_name']}({r['char1_id']}) 和 {r['char2_name']}({r['char2_id']}) 共同参与 {events_str}，但没有人物关系边",
            "action": f"ADD_EDGE relation({r['char1_id']}, {r['char2_id']}) {{type: '?', detail: '?'}}",
            "char1_id": r["char1_id"],
            "char2_id": r["char2_id"],
        })
    return {"findings": rows, "suggestions": suggestions}


def discover_events_no_location(client):
    """检查3: 无地点关联的事件"""
    rows = client.run("""
        MATCH (e:Event)
        WHERE NOT (e)-[:occurred_at]->(:Location)
        RETURN e.编号 AS id, e.标题 AS title, e.时间 AS time, e.类型 AS type
        ORDER BY e.时间
    """)
    suggestions = []
    for r in rows:
        suggestions.append({
            "priority": "medium",
            "type": "event_no_location",
            "description": f"事件「{r['title']}」({r['id']}, {r['time']}) 缺少地点关联",
            "action": f"ADD_EDGE occurred_at({r['id']}, loc_???) {{detail: '?'}}",
            "event_id": r["id"],
        })
    return {"findings": rows, "suggestions": suggestions}


def discover_temporal_gaps(client, threshold=3):
    """检查4: 时间线缺口（超过 threshold 天无事件）"""
    rows = client.run("MATCH (e:Event) RETURN e.编号 AS id, e.标题 AS title, e.时间 AS time")
    # 在 Python 中处理时间排序（因为时间格式混合）
    events = []
    for r in rows:
        day_num = _parse_day(r["time"])
        if day_num is not None:
            events.append({**r, "day_num": day_num})

    events.sort(key=lambda x: x["day_num"])
    suggestions = []
    for i in range(len(events) - 1):
        gap = events[i + 1]["day_num"] - events[i]["day_num"]
        if gap > threshold:
            suggestions.append({
                "priority": "high",
                "type": "temporal_gap",
                "description": f"{events[i]['time']} 到 {events[i+1]['time']} 之间有 {gap} 天空缺"
                               f"（{events[i]['title']} → {events[i+1]['标题'] if '标题' in events[i+1] else events[i+1]['title']}）",
                "action": f"建议在 Day {events[i]['day_num']+1} ~ Day {events[i+1]['day_num']-1} 之间补充事件",
                "from_day": events[i]["day_num"],
                "to_day": events[i + 1]["day_num"],
                "gap": gap,
            })
    return {"findings": events, "suggestions": suggestions}


def discover_info_no_links(client):
    """检查5: 未关联任何实体的 Info 节点"""
    rows = client.run("""
        MATCH (i:Info)
        WHERE NOT ()-[:link]->(i)
        RETURN i.编号 AS id, i.标题 AS title, i.知识层 AS level
        ORDER BY i.知识层
    """)
    suggestions = []
    for r in rows:
        suggestions.append({
            "priority": "medium",
            "type": "info_no_link",
            "description": f"信息「{r['title']}」({r['id']}, 知识层{r['level']}) 未关联到任何实体",
            "action": f"ADD_EDGE link(???, {r['id']}) {{type: '涉及', detail: '?'}}",
            "info_id": r["id"],
        })
    return {"findings": rows, "suggestions": suggestions}


def discover_chars_no_faction(client):
    """检查6: 无阵营归属的角色（有 involved 边但无 BELONGS_TO）"""
    rows = client.run("""
        MATCH (c:char)
        WHERE NOT (c)-[:BELONGS_TO]->(:Faction)
          AND (c)-[:involved]->(:Event)
        RETURN c.编号 AS id, c.姓名 AS name,
               COUNT { (c)-[:involved]->(:Event) } AS event_count
        ORDER BY event_count DESC
    """)
    suggestions = []
    for r in rows:
        suggestions.append({
            "priority": "low",
            "type": "char_no_faction",
            "description": f"角色「{r['name']}」({r['id']}) 参与了 {r['event_count']} 个事件但无阵营归属",
            "action": f"如果属于某阵营: ADD_EDGE BELONGS_TO({r['id']}, faction_???) {{role: '?'}}",
            "char_id": r["id"],
        })
    return {"findings": rows, "suggestions": suggestions}


# ─── 额外检查: 事件无 evt_relation 链 ──────────────────────────
def discover_unlinked_events(client):
    """检查7: 未接入事件链的事件（无 evt_relation 出入边）"""
    rows = client.run("""
        MATCH (e:Event)
        WHERE NOT (e)-[:evt_relation]-()
        RETURN e.编号 AS id, e.标题 AS title, e.时间 AS time
        ORDER BY e.时间
    """)
    suggestions = []
    for r in rows:
        suggestions.append({
            "priority": "low",
            "type": "event_unlinked",
            "description": f"事件「{r['title']}」({r['id']}, {r['time']}) 未接入事件链（无因果/先后/包含关系）",
            "action": f"ADD_EDGE evt_relation(evt_???, {r['id']}) {{type: '因果|先后|包含', detail: '?'}}",
            "event_id": r["id"],
        })
    return {"findings": rows, "suggestions": suggestions}


def cmd_discover(client, check_types=None):
    """运行所有发现检查，汇总建议"""
    ALL_CHECKS = {
        "orphans":           ("孤立节点",       discover_orphans),
        "missing-relations": ("缺失人物关系",    discover_missing_relations),
        "events-no-location":("事件无地点",      discover_events_no_location),
        "temporal-gaps":     ("时间线缺口",      discover_temporal_gaps),
        "info-no-links":     ("信息未关联",      discover_info_no_links),
        "chars-no-faction":  ("角色无阵营",      discover_chars_no_faction),
        "events-unlinked":   ("事件未入链",      discover_unlinked_events),
    }

    if check_types is None:
        check_types = list(ALL_CHECKS.keys())

    results = {}
    all_suggestions = []

    for check_key in check_types:
        if check_key not in ALL_CHECKS:
            results[check_key] = {"error": f"未知检查类型: {check_key}"}
            continue
        check_name, check_fn = ALL_CHECKS[check_key]
        try:
            result = check_fn(client)
            results[check_key] = result
            all_suggestions.extend(result.get("suggestions", []))
        except Exception as e:
            results[check_key] = {"error": str(e)}

    # 按优先级排序建议
    priority_order = {"high": 0, "medium": 1, "low": 2}
    all_suggestions.sort(key=lambda s: priority_order.get(s.get("priority", "low"), 3))

    return {
        "summary": {
            "total_checks": len(check_types),
            "total_suggestions": len(all_suggestions),
            "high": sum(1 for s in all_suggestions if s["priority"] == "high"),
            "medium": sum(1 for s in all_suggestions if s["priority"] == "medium"),
            "low": sum(1 for s in all_suggestions if s["priority"] == "low"),
        },
        "suggestions": all_suggestions,
        "details": results,
    }


# ═══════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="自增长图构建器")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password", default=None)
    sub = parser.add_subparsers(dest="command")

    # auto-ids
    p_ids = sub.add_parser("auto-ids", help="查询各类型下一个可用ID")
    p_ids.add_argument("--labels", default="char,Location,Event,Info", help="逗号分隔的标签列表")

    # add-nodes
    p_nodes = sub.add_parser("add-nodes", help="原子创建节点")
    p_nodes.add_argument("--nodes", required=True, help="JSON数组")

    # add-edges
    p_edges = sub.add_parser("add-edges", help="创建边（验证端点）")
    p_edges.add_argument("--edges", required=True, help="JSON数组")

    # execute-tx
    p_tx = sub.add_parser("execute-tx", help="事务内执行多条Cypher")
    p_tx.add_argument("--cypher", required=True, help="JSON数组，每项一条Cypher")

    # discover
    p_disc = sub.add_parser("discover", help="图算法发现缺失实体和关系")
    p_disc.add_argument("--type", dest="check_type", default=None,
                        help="指定检查类型: orphans, missing-relations, events-no-location, temporal-gaps, info-no-links, chars-no-faction, events-unlinked")
    p_disc.add_argument("--all", dest="run_all", action="store_true", help="运行全部检查（默认）")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    pw = get_password(args)

    try:
        with Neo4jClient(password=pw) as client:
            if args.command == "auto-ids":
                labels = [l.strip() for l in args.labels.split(",")]
                result = cmd_auto_ids(client, labels)
            elif args.command == "add-nodes":
                result = cmd_add_nodes(client, args.nodes)
            elif args.command == "add-edges":
                result = cmd_add_edges(client, args.edges)
            elif args.command == "execute-tx":
                result = cmd_execute_tx(client, args.cypher)
            elif args.command == "discover":
                if args.check_type:
                    result = cmd_discover(client, [args.check_type])
                else:
                    result = cmd_discover(client)
            else:
                result = {"error": f"未知命令: {args.command}"}

            print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
