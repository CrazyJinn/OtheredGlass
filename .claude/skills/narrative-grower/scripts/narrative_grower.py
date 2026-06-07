#!/usr/bin/env python3
"""
narrative_grower.py — 叙事自增长脚本
命令：analyze, apply, list-drafts, update-draft

标签约定（与 import.cypher 一致）：
  :Character {id, name, gender, description, birth_year, character_tags}
  :Event     {id, title, time, description, type}
  :Scene     {id, name, description}
  :Info      {id, title, content, knowledge_level}

边类型：relation, involved, occurred_at, at, link, evt_relation
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

# ── Import Neo4jClient ────────────────────────────────────────
_PLUGIN_CANDIDATES = [
    os.path.expanduser(
        "~/.claude/plugins/cache/game-builder/char-design/1.0.0/skills/neo4j-helper/scripts"
    ),
    r"D:\project\GameBuilder\plugins\char-design\skills\neo4j-helper\scripts",
    # 本项目内的 neo4j-helper
    os.path.join(os.path.dirname(__file__), "..", "..", "neo4j-helper", "scripts"),
]
for _p in _PLUGIN_CANDIDATES:
    _p = os.path.normpath(_p)
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break

from neo4j_client import Neo4jClient

# ── Configuration ───────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
DRAFTS_DIR = os.path.join(PROJECT_ROOT, "01_叙事数据", "drafts")

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"


def get_password(args):
    return args.password or os.environ.get("NEO4J_PASSWORD", NEO4J_PASSWORD)


# ═══════════════════════════════════════════════════════════════
# Utility: parse event time to sortable value
# ═══════════════════════════════════════════════════════════════
def _parse_day(time_str):
    """'开场' → -1, 'Day N ...' → N, else None"""
    if not time_str:
        return None
    time_str = str(time_str).strip()
    if time_str == "开场":
        return -1
    m = re.match(r"Day\s*(\d+)", time_str)
    if m:
        return int(m.group(1))
    return None


def _period_label(day):
    """Day number → period name"""
    if day is None:
        return "unknown"
    if day < 0:
        return "开场"
    if day <= 10:
        return "Day 0-10"
    if day <= 20:
        return "Day 11-20"
    if day <= 30:
        return "Day 21-30"
    return "后日谈"


# ═══════════════════════════════════════════════════════════════
# Algorithm 1: Temporal Gap Analysis
# ═══════════════════════════════════════════════════════════════
def analyze_temporal_gaps(client, threshold=3):
    rows = client.run(
        "MATCH (e:Event) RETURN e.id AS id, e.title AS title, e.time AS time"
    )
    events = []
    for r in rows:
        day_num = _parse_day(r["time"])
        if day_num is not None:
            events.append({**r, "day_num": day_num})
    events.sort(key=lambda x: x["day_num"])

    gaps = []
    for i in range(len(events) - 1):
        gap = events[i + 1]["day_num"] - events[i]["day_num"]
        if gap > threshold:
            gaps.append({
                "from_day": events[i]["day_num"],
                "to_day": events[i + 1]["day_num"],
                "gap": gap,
                "from_event": {"id": events[i]["id"], "title": events[i]["title"]},
                "to_event": {"id": events[i + 1]["id"], "title": events[i + 1]["title"]},
            })

    # Check for "待补充" period (Day 21-30)
    max_day = max(e["day_num"] for e in events) if events else 0
    missing_tail = max_day < 30

    return {
        "total_events": len(events),
        "day_range": [events[0]["day_num"], events[-1]["day_num"]] if events else [],
        "gaps": gaps,
        "missing_tail": missing_tail,
        "max_day": max_day,
    }


# ═══════════════════════════════════════════════════════════════
# Algorithm 2: Character Arc Tracking
# ═══════════════════════════════════════════════════════════════
def analyze_character_arcs(client):
    rows = client.run("""
        MATCH (c:Character)-[r:involved]->(e:Event)
        RETURN c.id AS char_id, c.name AS char_name,
               e.id AS evt_id, e.title AS evt_title, e.time AS evt_time,
               r.role AS role
        ORDER BY c.id, e.time
    """)

    chars = {}
    for r in rows:
        cid = r["char_id"]
        if cid not in chars:
            chars[cid] = {"char_id": cid, "name": r["char_name"], "events": []}
        day = _parse_day(r["evt_time"])
        chars[cid]["events"].append({
            "evt_id": r["evt_id"], "title": r["evt_title"],
            "time": r["evt_time"], "day": day, "role": r["role"],
        })

    arcs = []
    for cid, data in chars.items():
        events = data["events"]
        days = [e["day"] for e in events if e["day"] is not None]
        if not days:
            arcs.append({**data, "active_range": None, "gaps": [], "status": "no_events"})
            continue

        active_range = {"min": min(days), "max": max(days)}
        # Find gaps in character involvement
        sorted_days = sorted(set(days))
        char_gaps = []
        for i in range(len(sorted_days) - 1):
            diff = sorted_days[i + 1] - sorted_days[i]
            if diff > 5:
                char_gaps.append({
                    "from": sorted_days[i], "to": sorted_days[i + 1], "gap": diff
                })

        # Detect characters that vanish after early involvement
        status = "active"
        if max(days) < 10 and len(days) >= 2:
            status = "vanished_early"
        elif max(days) < 15 and len(days) >= 3:
            status = "vanished_mid"

        arcs.append({
            "char_id": cid, "name": data["name"],
            "event_count": len(events),
            "active_range": active_range,
            "gaps": char_gaps,
            "status": status,
            "events": events,
        })

    return arcs


# ═══════════════════════════════════════════════════════════════
# Algorithm 3: Implicit Relationship Inference
# ═══════════════════════════════════════════════════════════════
def analyze_implicit_relations(client):
    rows = client.run("""
        MATCH (c1:Character)-[:involved]->(e:Event)<-[:involved]-(c2:Character)
        WHERE c1.id < c2.id
          AND NOT (c1)-[:relation]-(c2)
        RETURN c1.id AS c1_id, c1.name AS c1_name,
               c2.id AS c2_id, c2.name AS c2_name,
               COLLECT(DISTINCT e.title) AS shared_events,
               COLLECT(DISTINCT e.time) AS shared_times,
               COUNT(DISTINCT e) AS strength
        ORDER BY strength DESC
    """)

    inferred = []
    for r in rows:
        # Suggest relationship type based on event context
        suggested_type = _infer_relation_type(r["shared_events"], r["c1_name"], r["c2_name"])
        inferred.append({
            "char1": {"id": r["c1_id"], "name": r["c1_name"]},
            "char2": {"id": r["c2_id"], "name": r["c2_name"]},
            "shared_events": r["shared_events"],
            "shared_times": r["shared_times"],
            "strength": r["strength"],
            "suggested_type": suggested_type,
        })

    return inferred


def _infer_relation_type(shared_events, name1, name2):
    """Heuristic: suggest relationship type based on shared event titles."""
    events_text = " ".join(shared_events)
    if any(kw in events_text for kw in ["约会", "散步", "吃", "约"]):
        return "暧昧/朋友"
    if any(kw in events_text for kw in ["冲突", "吵架", "打"]):
        return "对立/竞争对手"
    if any(kw in events_text for kw in ["训练", "战队", "比赛"]):
        return "同事/队友"
    if any(kw in events_text for kw in ["聊天", "私信", "微信"]):
        return "朋友/熟人"
    return "待定"


# ═══════════════════════════════════════════════════════════════
# Algorithm 4: Event Chain Strength
# ═══════════════════════════════════════════════════════════════
def analyze_event_chains(client):
    # Events without any evt_relation
    unlinked = client.run("""
        MATCH (e:Event)
        WHERE NOT (e)-[:evt_relation]-()
        RETURN e.id AS id, e.title AS title, e.time AS time, e.type AS type
        ORDER BY e.time
    """)

    # Potential links: events sharing characters
    potential_links = client.run("""
        MATCH (e1:Event)<-[:involved]-(c:Character)-[:involved]->(e2:Event)
        WHERE e1.id < e2.id AND NOT (e1)-[:evt_relation]-(e2)
        RETURN e1.id AS from_evt, e1.title AS from_title,
               e2.id AS to_evt, e2.title AS to_title,
               COLLECT(DISTINCT c.name) AS shared_chars,
               COUNT(DISTINCT c) AS overlap
        ORDER BY overlap DESC
        LIMIT 20
    """)

    return {
        "unlinked_count": len(unlinked),
        "unlinked_events": unlinked,
        "potential_links": potential_links,
    }


# ═══════════════════════════════════════════════════════════════
# Algorithm 5: Scene Utilization Analysis
# ═══════════════════════════════════════════════════════════════
def analyze_scene_utilization(client):
    rows = client.run("""
        MATCH (s:Scene)
        OPTIONAL MATCH (e:Event)-[:occurred_at]->(s)
        OPTIONAL MATCH (c:Character)-[:at]->(s)
        WITH s, COUNT(DISTINCT e) AS event_count, COUNT(DISTINCT c) AS char_count
        RETURN s.id AS scene_id, s.name AS scene_name, s.description AS description,
               event_count, char_count, event_count + char_count AS utilization
        ORDER BY utilization ASC
    """)

    scenes = []
    for r in rows:
        underused = r["utilization"] <= 1
        scenes.append({
            "scene_id": r["scene_id"],
            "name": r["scene_name"],
            "description": r["description"] or "",
            "event_count": r["event_count"],
            "char_count": r["char_count"],
            "utilization": r["utilization"],
            "underused": underused,
        })
    return scenes


# ═══════════════════════════════════════════════════════════════
# Algorithm 6: Info Depth Analysis
# ═══════════════════════════════════════════════════════════════
def analyze_info_depth(client):
    # Info per entity with knowledge levels
    rows = client.run("""
        MATCH (n)
        WHERE labels(n)[0] IN ['Character', 'Event', 'Scene']
        OPTIONAL MATCH (n)-[:link]->(i:Info)
        RETURN labels(n)[0] AS entity_type, n.id AS entity_id,
               COALESCE(n.name, n.title) AS entity_name,
               COLLECT(DISTINCT i.knowledge_level) AS knowledge_levels,
               COUNT(DISTINCT i) AS info_count
        ORDER BY info_count ASC
    """)

    entities = []
    for r in rows:
        levels = [l for l in r["knowledge_levels"] if l is not None]
        missing_depth = []
        if 2 not in levels and r["info_count"] > 0:
            missing_depth.append(2)
        if 3 not in levels and r["info_count"] > 0:
            missing_depth.append(3)
        entities.append({
            "entity_type": r["entity_type"],
            "entity_id": r["entity_id"],
            "entity_name": r["entity_name"],
            "info_count": r["info_count"],
            "knowledge_levels": levels,
            "missing_depth": missing_depth,
        })

    # Global info distribution
    dist = client.run("""
        MATCH (i:Info) RETURN i.knowledge_level AS level, COUNT(*) AS cnt
        ORDER BY level
    """)
    distribution = {r["level"]: r["cnt"] for r in dist if r["level"] is not None}

    return {"entities": entities, "distribution": distribution}


# ═══════════════════════════════════════════════════════════════
# Algorithm 7: Subgraph Connectivity
# ═══════════════════════════════════════════════════════════════
def analyze_subgraph_connectivity(client):
    # Character adjacency via shared events
    rows = client.run("""
        MATCH (c1:Character)-[:involved]->(e:Event)<-[:involved]-(c2:Character)
        WHERE c1.id < c2.id
        WITH c1, c2, COUNT(DISTINCT e) AS shared, COLLECT(DISTINCT e.title) AS events
        RETURN c1.id AS c1_id, c1.name AS c1_name,
               c2.id AS c2_id, c2.name AS c2_name,
               shared, events
        ORDER BY shared DESC
    """)

    # Build adjacency for cluster detection
    adjacency = {}
    all_chars = set()
    for r in rows:
        all_chars.add(r["c1_id"])
        all_chars.add(r["c2_id"])
        adjacency.setdefault(r["c1_id"], {})[r["c2_id"]] = r["shared"]
        adjacency.setdefault(r["c2_id"], {})[r["c1_id"]] = r["shared"]

    # Simple connected components via BFS
    visited = set()
    clusters = []
    for cid in all_chars:
        if cid in visited:
            continue
        cluster = set()
        queue = [cid]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            cluster.add(node)
            for neighbor in adjacency.get(node, {}):
                if neighbor not in visited:
                    queue.append(neighbor)
        if cluster:
            clusters.append(list(cluster))

    # Find bridge candidates: character pairs NOT connected
    bridges = []
    chars_list = sorted(all_chars)
    for i, c1 in enumerate(chars_list):
        for c2 in chars_list[i + 1:]:
            if c2 not in adjacency.get(c1, {}):
                bridges.append({
                    "c1_id": c1, "c2_id": c2,
                    "in_same_cluster": any(c1 in cl and c2 in cl for cl in clusters),
                })

    return {
        "clusters": clusters,
        "cluster_count": len(clusters),
        "bridge_candidates": bridges[:10],  # top 10
        "adjacency_strength": rows,
    }


# ═══════════════════════════════════════════════════════════════
# Algorithm 8: Relationship Evolution Tracking
# ═══════════════════════════════════════════════════════════════
def analyze_relationship_evolution(client):
    rows = client.run("""
        MATCH (c1:Character)-[r:relation]->(c2:Character)
        RETURN c1.id AS c1_id, c1.name AS c1_name,
               c2.id AS c2_id, c2.name AS c2_name,
               r.type AS rel_type, r.detail AS detail,
               r.start_time AS start_time, r.end_time AS end_time
        ORDER BY r.start_time
    """)

    relationships = []
    for r in rows:
        has_evolution = r["end_time"] is not None
        suggested_changes = []
        if not has_evolution and r["rel_type"] in ("恋爱", "暧昧", "朋友"):
            suggested_changes.append("关系可能随剧情发展发生变化（分手/升级/变质）")

        relationships.append({
            "c1": {"id": r["c1_id"], "name": r["c1_name"]},
            "c2": {"id": r["c2_id"], "name": r["c2_name"]},
            "type": r["rel_type"],
            "detail": r["detail"],
            "start_time": r["start_time"],
            "end_time": r["end_time"],
            "has_evolution": has_evolution,
            "suggested_changes": suggested_changes,
        })

    return relationships


# ═══════════════════════════════════════════════════════════════
# Algorithm 9: Bridge Scene Suggestions
# ═══════════════════════════════════════════════════════════════
def analyze_bridge_scenes(client):
    rows = client.run("""
        MATCH (c1:Character)-[:at]->(s1:Scene)
        MATCH (c2:Character)-[:at]->(s2:Scene)
        WHERE c1.id < c2.id AND s1.id <> s2.id
          AND NOT (c1)-[:at]->(s2) AND NOT (c2)-[:at]->(s1)
        RETURN c1.id AS c1_id, c1.name AS c1_name,
               c2.id AS c2_id, c2.name AS c2_name,
               s1.id AS s1_id, s1.name AS s1_name,
               s2.id AS s2_id, s2.name AS s2_name
        LIMIT 15
    """)

    suggestions = []
    for r in rows:
        suggestions.append({
            "char1": {"id": r["c1_id"], "name": r["c1_name"], "scene": r["s1_name"]},
            "char2": {"id": r["c2_id"], "name": r["c2_name"], "scene": r["s2_name"]},
            "bridge_type": "shared_event_at_new_scene",
        })
    return suggestions


# ═══════════════════════════════════════════════════════════════
# Algorithm 10: Narrative Density Scoring
# ═══════════════════════════════════════════════════════════════
def analyze_narrative_density(client):
    events = client.run(
        "MATCH (e:Event) RETURN e.id AS id, e.title AS title, e.time AS time"
    )

    periods = {
        "开场": [],
        "Day 0-10": [],
        "Day 11-20": [],
        "Day 21-30": [],
        "后日谈": [],
    }
    for e in events:
        day = _parse_day(e["time"])
        period = _period_label(day)
        if period in periods:
            periods[period].append(e)

    # Info density per period
    info_rows = client.run("""
        MATCH (i:Info)<-[:link]-(n)
        WHERE labels(n)[0] = 'Event'
        RETURN n.time AS time, COUNT(DISTINCT i) AS info_count
    """)
    info_by_period = {}
    for r in info_rows:
        day = _parse_day(r["time"])
        period = _period_label(day)
        info_by_period[period] = info_by_period.get(period, 0) + (r["info_count"] or 0)

    # Character involvement per period
    char_rows = client.run("""
        MATCH (c:Character)-[:involved]->(e:Event)
        RETURN e.time AS time, COUNT(DISTINCT c) AS char_count
    """)
    char_by_period = {}
    for r in char_rows:
        day = _parse_day(r["time"])
        period = _period_label(day)
        char_by_period[period] = char_by_period.get(period, 0) + (r["char_count"] or 0)

    density = []
    total_events = len(events)
    for period, evts in periods.items():
        evt_count = len(evts)
        density_score = evt_count / max(total_events, 1)
        imbalance = False
        if total_events > 0 and evt_count == 0 and period not in ("Day 21-30", "后日谈"):
            imbalance = True
        density.append({
            "period": period,
            "event_count": evt_count,
            "info_count": info_by_period.get(period, 0),
            "char_involvements": char_by_period.get(period, 0),
            "density_ratio": round(density_score, 3),
            "imbalance": imbalance,
        })

    return density


# ═══════════════════════════════════════════════════════════════
# Growth Opportunity Synthesis
# ═══════════════════════════════════════════════════════════════
def synthesize_opportunities(results):
    """Convert raw analysis results into prioritized growth opportunities."""
    opportunities = []

    # From temporal gaps
    tg = results.get("temporal_gaps", {})
    for gap in tg.get("gaps", []):
        opportunities.append({
            "priority": "high",
            "type": "temporal_gap_fill",
            "description": f"Day {gap['from_day']} 到 Day {gap['to_day']} 之间有 {gap['gap']} 天空缺"
                           f"（{gap['from_event']['title']} → {gap['to_event']['title']}）",
            "context": gap,
        })
    if tg.get("missing_tail"):
        max_day = tg.get("max_day", 0)
        opportunities.append({
            "priority": "high",
            "type": "temporal_gap_fill",
            "description": f"Day {max_day} 之后到 Day 30 缺少事件（大纲标注'待补充'）",
            "context": {"from_day": max_day, "to_day": 30, "gap": 30 - max_day},
        })

    # From character arcs
    for arc in results.get("character_arcs", []):
        if arc.get("status") in ("vanished_early", "vanished_mid"):
            opportunities.append({
                "priority": "medium",
                "type": "character_revival",
                "description": f"角色「{arc['name']}」({arc['char_id']}) 在 Day {arc['active_range']['max']} 后消失",
                "context": arc,
            })

    # From implicit relations
    for rel in results.get("implicit_relations", []):
        if rel["strength"] >= 2:
            opportunities.append({
                "priority": "high" if rel["strength"] >= 3 else "medium",
                "type": "implicit_relation",
                "description": f"{rel['char1']['name']}({rel['char1']['id']}) 和 "
                               f"{rel['char2']['name']}({rel['char2']['id']}) "
                               f"共同参与 {rel['strength']} 个事件但无人物关系（建议：{rel['suggested_type']}）",
                "context": rel,
            })

    # From event chains
    ec = results.get("event_chains", {})
    if ec.get("unlinked_count", 0) > 0:
        opportunities.append({
            "priority": "medium",
            "type": "event_chain_gap",
            "description": f"有 {ec['unlinked_count']} 个事件未接入因果/先后/包含链",
            "context": {"unlinked_count": ec["unlinked_count"],
                        "potential_links": ec.get("potential_links", [])[:5]},
        })

    # From scene utilization
    for scene in results.get("scene_utilization", []):
        if scene.get("underused"):
            opportunities.append({
                "priority": "low",
                "type": "underused_scene",
                "description": f"场景「{scene['name']}」({scene['scene_id']}) 利用率低"
                               f"（{scene['event_count']} 事件，{scene['char_count']} 角色）",
                "context": scene,
            })

    # From info depth
    idepth = results.get("info_depth", {})
    for entity in idepth.get("entities", []):
        if entity.get("missing_depth") and entity["info_count"] > 0:
            levels_str = "/".join(str(l) for l in entity["missing_depth"])
            opportunities.append({
                "priority": "medium",
                "type": "info_depth_gap",
                "description": f"{entity['entity_type']}「{entity['entity_name']}」"
                               f"({entity['entity_id']}) 缺少 knowledge_level {levels_str} 的深层信息",
                "context": entity,
            })

    # From narrative density
    for d in results.get("narrative_density", []):
        if d.get("imbalance"):
            opportunities.append({
                "priority": "high",
                "type": "density_imbalance",
                "description": f"时间段「{d['period']}」缺少事件，叙事密度失衡",
                "context": d,
            })

    # Sort by priority
    order = {"high": 0, "medium": 1, "low": 2}
    opportunities.sort(key=lambda o: order.get(o.get("priority", "low"), 3))

    return opportunities


# ═══════════════════════════════════════════════════════════════
# cmd: analyze
# ═══════════════════════════════════════════════════════════════
def cmd_analyze(client):
    results = {}
    algorithms = [
        ("temporal_gaps", analyze_temporal_gaps),
        ("character_arcs", analyze_character_arcs),
        ("implicit_relations", analyze_implicit_relations),
        ("event_chains", analyze_event_chains),
        ("scene_utilization", analyze_scene_utilization),
        ("info_depth", analyze_info_depth),
        ("subgraph_connectivity", analyze_subgraph_connectivity),
        ("relationship_evolution", analyze_relationship_evolution),
        ("bridge_scenes", analyze_bridge_scenes),
        ("narrative_density", analyze_narrative_density),
    ]

    errors = []
    for name, fn in algorithms:
        try:
            results[name] = fn(client)
        except Exception as e:
            results[name] = {"error": str(e)}
            errors.append(name)

    opportunities = synthesize_opportunities(results)

    analysis_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    output = {
        "analysis_id": analysis_id,
        "timestamp": datetime.now().isoformat(),
        "algorithms_run": len(algorithms),
        "errors": errors if errors else None,
        "results": results,
        "growth_opportunities": opportunities,
        "summary": {
            "total_opportunities": len(opportunities),
            "high": sum(1 for o in opportunities if o["priority"] == "high"),
            "medium": sum(1 for o in opportunities if o["priority"] == "medium"),
            "low": sum(1 for o in opportunities if o["priority"] == "low"),
        },
    }

    return output


# ═══════════════════════════════════════════════════════════════
# cmd: apply — parse approved draft → generate Cypher → execute
# ═══════════════════════════════════════════════════════════════
def cmd_apply(client, draft_path):
    """Parse an approved draft and insert entities into Neo4j."""
    if not os.path.isfile(draft_path):
        return {"error": f"文件不存在: {draft_path}"}

    with open(draft_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse frontmatter
    fm = _parse_frontmatter(content)
    if not fm:
        return {"error": "无法解析 YAML frontmatter"}

    status = fm.get("status", "")
    if status != "approved":
        return {"error": f"草案状态为 '{status}'，需要 'approved' 才能导入"}

    # Extract proposed entities from markdown tables
    body = _strip_frontmatter(content)
    events = _extract_events_from_md(body)
    relations = _extract_relations_from_md(body)
    infos = _extract_infos_from_md(body)
    scenes = _extract_scenes_from_md(body)

    cypher_list = []

    # Generate MERGE for scenes
    for s in scenes:
        props = ", ".join(f"{k}: '{str(v).replace(chr(39), chr(92)+chr(39))}'"
                          for k, v in s.items() if k != "id" and v)
        cypher_list.append(f"MERGE (n:Scene {{id: '{s['id']}'}}) SET n += {{{props}}}")

    # Generate MERGE for events
    for e in events:
        props = ", ".join(f"{k}: '{str(v).replace(chr(39), chr(92)+chr(39))}'"
                          for k, v in e.items() if k != "id" and v)
        cypher_list.append(f"MERGE (n:Event {{id: '{e['id']}'}}) SET n += {{{props}}}")

    # Generate MERGE for info nodes
    for i in infos:
        props = ", ".join(f"{k}: '{str(v).replace(chr(39), chr(92)+chr(39))}'"
                          for k, v in i.items() if k != "id" and v)
        cypher_list.append(f"MERGE (n:Info {{id: '{i['id']}'}}) SET n += {{{props}}}")

    # Generate MERGE for edges
    for r in relations:
        edge_type = r.get("edge_type", "relation")
        from_id = r.get("from_id", "")
        to_id = r.get("to_id", "")
        props = r.get("props", {})
        prop_str = ""
        if props:
            prop_parts = []
            for k, v in props.items():
                if isinstance(v, int):
                    prop_parts.append(f"{k}: {v}")
                elif v:
                    prop_parts.append(f"{k}: '{str(v).replace(chr(39), chr(92)+chr(39))}'")
            if prop_parts:
                prop_str = " {" + ", ".join(prop_parts) + "}"

        cypher_list.append(
            f"MATCH (a {{id: '{from_id}'}}) MATCH (b {{id: '{to_id}'}}) "
            f"MERGE (a)-[:{edge_type}{prop_str}]->(b)"
        )

    if not cypher_list:
        return {"error": "未从草案中提取到任何实体或关系", "events": events, "relations": relations,
                "infos": infos, "scenes": scenes}

    # Execute via Neo4jClient transaction
    try:
        result = client.run_in_transaction(cypher_list)
        # Update draft status
        _update_draft_status(draft_path, "applied")
        return {
            "success": True,
            "cypher_count": len(cypher_list),
            "events_created": len(events),
            "relations_created": len(relations),
            "infos_created": len(infos),
            "scenes_created": len(scenes),
            "result": result,
        }
    except Exception as e:
        return {"error": str(e), "cypher_list": cypher_list}


def _parse_frontmatter(content):
    """Extract YAML frontmatter as dict."""
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    yaml_text = content[3:end].strip()
    fm = {}
    for line in yaml_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip().strip('"').strip("'")
            fm[key.strip()] = val
    return fm


def _strip_frontmatter(content):
    """Remove YAML frontmatter, return body."""
    if not content.startswith("---"):
        return content
    end = content.find("---", 3)
    if end == -1:
        return content
    return content[end + 3:].strip()


def _extract_events_from_md(body):
    """Extract events from markdown headers like '### evt_031: Title'."""
    events = []
    pattern = r'###\s+(evt_\d+)\s*:\s*(.+?)(?:\n|$)'
    for m in re.finditer(pattern, body):
        evt_id = m.group(1)
        evt_title = m.group(2).strip()
        # Look for metadata in subsequent blockquote lines
        block = _get_block_after_match(body, m.end())
        evt = {"id": evt_id, "title": evt_title}
        for line in block.split("\n"):
            line = line.strip().lstrip("> ").strip()
            # Strip markdown bold markers
            clean = line.replace("**", "")
            if clean.startswith("时间"):
                evt["time"] = _extract_value(clean)
            elif clean.startswith("类型"):
                evt["type"] = _extract_value(clean)
            elif clean.startswith("场景"):
                evt["scene"] = _extract_value(clean)
            elif clean.startswith("参与角色"):
                evt["characters"] = _extract_value(clean)
        events.append(evt)
    return events


def _extract_relations_from_md(body):
    """Extract relations from markdown tables with headers: 角色A | 角色B | ..."""
    relations = []
    # Find tables with relation-like headers
    table_pattern = r'\|.*角色A.*\|.*角色B.*\|[\s\S]*?(?=\n\n|\n##|\Z)'
    for table_match in re.finditer(table_pattern, body, re.IGNORECASE):
        table_text = table_match.group(0)
        rows = [r for r in table_text.split("\n") if r.strip().startswith("|")]
        if len(rows) < 3:
            continue
        headers = [h.strip() for h in rows[0].split("|")[1:-1]]
        for row in rows[2:]:  # skip header + separator
            cells = [c.strip() for c in row.split("|")[1:-1]]
            if len(cells) < 3:
                continue
            entry = dict(zip(headers, cells))
            rel_type = entry.get("关系类型", "relation")
            relations.append({
                "edge_type": "relation",
                "from_id": entry.get("角色A", ""),
                "to_id": entry.get("角色B", ""),
                "props": {
                    "type": rel_type,
                    "detail": entry.get("详情", ""),
                },
            })
    return relations


def _extract_infos_from_md(body):
    """Extract info from markdown tables with headers: 标题 | 内容 | ..."""
    infos = []
    table_pattern = r'\|.*标题.*\|.*内容.*\|.*知识层.*\|[\s\S]*?(?=\n\n|\n##|\Z)'
    for table_match in re.finditer(table_pattern, body, re.IGNORECASE):
        table_text = table_match.group(0)
        rows = [r for r in table_text.split("\n") if r.strip().startswith("|")]
        if len(rows) < 3:
            continue
        headers = [h.strip() for h in rows[0].split("|")[1:-1]]
        for row in rows[2:]:
            cells = [c.strip() for c in row.split("|")[1:-1]]
            if len(cells) < 3:
                continue
            entry = dict(zip(headers, cells))
            infos.append({
                "id": entry.get("ID", f"info_{len(infos)+1:03d}"),
                "title": entry.get("标题", ""),
                "content": entry.get("内容", ""),
                "knowledge_level": entry.get("知识层", "2"),
            })
    return infos


def _extract_scenes_from_md(body):
    """Extract scene suggestions from markdown."""
    scenes = []
    # Look for scene sections with headers like '### scene_014: Name'
    pattern = r'###\s+(scene_\d+)\s*:\s*(.+?)(?:\n|$)'
    for m in re.finditer(pattern, body):
        scenes.append({
            "id": m.group(1),
            "name": m.group(2).strip(),
        })
    return scenes


def _get_block_after_match(text, start, max_len=500):
    """Get text block after a match until next header or blank line."""
    end = text.find("\n### ", start)
    if end == -1:
        end = min(start + max_len, len(text))
    return text[start:end]


def _extract_value(line):
    """Extract value after ':' or '：' from a metadata line."""
    # Try full-width colon first, then half-width
    for sep in ("：", ":"):
        if sep in line:
            return line.split(sep, 1)[1].strip()
    return line


# ═══════════════════════════════════════════════════════════════
# cmd: list-drafts
# ═══════════════════════════════════════════════════════════════
def cmd_list_drafts(drafts_dir=None):
    ddir = drafts_dir or DRAFTS_DIR
    if not os.path.isdir(ddir):
        return {"drafts": [], "total": 0, "dir": ddir}

    drafts = []
    for fname in sorted(os.listdir(ddir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(ddir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            fm = _parse_frontmatter(content)
            if fm:
                drafts.append({
                    "filename": fname,
                    "path": fpath,
                    "draft_id": fm.get("draft_id", fname),
                    "status": fm.get("status", "unknown"),
                    "priority": fm.get("priority", ""),
                    "title": fm.get("title", fname),
                    "created_at": fm.get("created_at", ""),
                    "opportunity_type": fm.get("opportunity_type", ""),
                })
        except Exception:
            drafts.append({"filename": fname, "path": fpath, "status": "error"})

    return {"drafts": drafts, "total": len(drafts), "dir": ddir}


# ═══════════════════════════════════════════════════════════════
# cmd: update-draft
# ═══════════════════════════════════════════════════════════════
def _update_draft_status(draft_path, new_status):
    """Update the status field in a draft's YAML frontmatter."""
    with open(draft_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace status line in frontmatter
    content = re.sub(
        r"^(status:\s*).+$",
        f"status: {new_status}",
        content,
        count=1,
        flags=re.MULTILINE,
    )

    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(content)


def cmd_update_draft(draft_path, new_status):
    if not os.path.isfile(draft_path):
        return {"error": f"文件不存在: {draft_path}"}
    if new_status not in ("approved", "rejected", "pending", "applied"):
        return {"error": f"无效状态: {new_status}"}
    _update_draft_status(draft_path, new_status)
    return {"success": True, "path": draft_path, "new_status": new_status}


# ═══════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="叙事自增长脚本")
    sub = parser.add_subparsers(dest="command")

    # analyze
    p_analyze = sub.add_parser("analyze", help="图算法分析叙事缺口")
    p_analyze.add_argument("--uri", default=NEO4J_URI)
    p_analyze.add_argument("--user", default=NEO4J_USER)
    p_analyze.add_argument("--password", default=None)

    # apply
    p_apply = sub.add_parser("apply", help="将已批准草案导入 Neo4j")
    p_apply.add_argument("--draft", required=True, help="草案 .md 文件路径")
    p_apply.add_argument("--uri", default=NEO4J_URI)
    p_apply.add_argument("--user", default=NEO4J_USER)
    p_apply.add_argument("--password", default=None)

    # list-drafts
    p_list = sub.add_parser("list-drafts", help="列出所有草案")
    p_list.add_argument("--drafts-dir", default=None, help="草案目录")

    # update-draft
    p_update = sub.add_parser("update-draft", help="更新草案状态")
    p_update.add_argument("--draft", required=True, help="草案 .md 文件路径")
    p_update.add_argument("--status", required=True, choices=["approved", "rejected", "pending", "applied"])

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Commands that don't need Neo4j
    if args.command == "list-drafts":
        result = cmd_list_drafts(args.drafts_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "update-draft":
        result = cmd_update_draft(args.draft, args.status)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Commands that need Neo4j
    pw = get_password(args)
    try:
        with Neo4jClient(uri=args.uri, user=args.user, password=pw) as client:
            client.connect()
            if args.command == "analyze":
                result = cmd_analyze(client)
            elif args.command == "apply":
                result = cmd_apply(client, args.draft)
            else:
                result = {"error": f"未知命令: {args.command}"}
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
