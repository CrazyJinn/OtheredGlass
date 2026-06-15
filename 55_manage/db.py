#!/usr/bin/env python3
"""
数据库层：Neo4j 连接管理 + 所有 Cypher 查询 + 封装函数
"""

import os
import sys
import re
import time
import json

# ── Import Neo4jClient ────────────────────────────────────────
_NEO4J_HELPER_SCRIPTS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    ".claude", "skills", "infra-neo4j-helper", "scripts"
))
if os.path.isdir(_NEO4J_HELPER_SCRIPTS):
    sys.path.insert(0, _NEO4J_HELPER_SCRIPTS)
from neo4j_client import Neo4jClient

# ── Paths ──────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DRAFTS_DIR = os.path.join(PROJECT_ROOT, "01_叙事数据", "drafts")
TAGLIB_PATH = os.path.join(SCRIPT_DIR, "标签库.json")

# ── Client singleton ──────────────────────────────────────────
_client: Neo4jClient = None


def init_client(uri="bolt://localhost:7687", user="neo4j", password="12345678"):
    global _client
    _client = Neo4jClient(uri=uri, user=user, password=password)
    _client.connect()
    return _client


def get_client() -> Neo4jClient:
    return _client


def close_client():
    global _client
    if _client:
        _client.close()
        _client = None


# ═══════════════════════════════════════════════════════════════
# Cypher Queries — 叙事基础
# ═══════════════════════════════════════════════════════════════

NAR_STATS_QUERY = """
MATCH (c:Character) WITH count(c) AS chars
MATCH (e:Event) WITH chars, count(e) AS events
MATCH (s:Scene) WITH chars, events, count(s) AS scenes
MATCH (i:Info) WITH chars, events, scenes, count(i) AS infos
RETURN chars, events, scenes, infos
"""

NAR_LIST_QUERIES = {
    "Character": """
        MATCH (n:Character)
        RETURN n.id AS id, n.name AS name, n.gender AS gender,
               n.description AS description, n.character_tags AS tags,
               n.birth_year AS birth_year
        ORDER BY n.name LIMIT 200
    """,
    "Event": """
        MATCH (n:Event)
        RETURN n.id AS id, n.title AS title, n.time AS time,
               n.type AS type, n.description AS description
        ORDER BY n.time LIMIT 200
    """,
    "Scene": """
        MATCH (n:Scene)
        RETURN n.id AS id, n.name AS name, n.description AS description
        ORDER BY n.name LIMIT 200
    """,
    "Info": """
        MATCH (n:Info)
        RETURN n.id AS id, n.title AS title, n.content AS content,
               n.knowledge_level AS level
        ORDER BY n.id LIMIT 200
    """,
}

NAR_RELATIONS_QUERY = """
MATCH (n {id: $node_id})-[r]-(m)
RETURN type(r) AS rel_type,
       labels(m)[0] AS target_label,
       m.id AS target_id,
       COALESCE(m.name, m.title, m.id) AS target_name,
       CASE WHEN startNode(r).id = $node_id THEN 'out' ELSE 'in' END AS direction,
       properties(r) AS rel_props
ORDER BY rel_type, target_name
"""

NAR_EDGE_STATS_QUERY = """
MATCH (a)-[r]->(b)
WHERE type(r) IN ['relation','involved','occurred_at','at','link','evt_relation']
RETURN type(r) AS edge_type, count(r) AS cnt
ORDER BY cnt DESC
"""


# ═══════════════════════════════════════════════════════════════
# Cypher Queries — 角色美术
# ═══════════════════════════════════════════════════════════════

STATUS_QUERY = """
MATCH (c:Character)
OPTIONAL MATCH (c)-[:has_appearance]->(ap:AppearanceStyle)
OPTIONAL MATCH (c)-[:has_voice_style]->(ls:LanguageStyle)
OPTIONAL MATCH (ap)-[:produces]->(ds:DesignSheet)
RETURN c.id AS char_id, c.name AS char_name, c.gender AS char_gender,
       ap.id AS appearance_id, ap.status AS appearance_status,
       ls.id AS language_id, ls.status AS language_status,
       ds.id AS design_id, ds.status AS design_status,
       ds.approve AS design_approve,
       ds.image_path AS design_image
ORDER BY c.id
"""

COSTUME_QUERY = """
MATCH (c:Character)
OPTIONAL MATCH (c)-[:has_costume]->(co:CostumeStyle)
RETURN c.id AS char_id,
       collect({id: co.id, status: co.status, name: co.name, approve: co.approve}) AS costumes
"""

COSTUME_APPROVAL_QUERY = """
MATCH (c:Character)-[:has_costume]->(co:CostumeStyle)
WHERE co.approve = 'pending'
RETURN c.id AS char_id, c.name AS char_name,
       co.id AS costume_id, co.name AS costume_name,
       co.garment AS outfit, co.accessory_type AS accessories
ORDER BY co.id
"""

DOWNSTREAM_QUERY = """
MATCH (ds:DesignSheet)-[r1:produces]->(id:IllusDesign)
OPTIONAL MATCH (id)-[:expands_to]->(si:StandingIllustration)
RETURN ds.id AS design_id,
       id.id AS illus_id, id.status AS illus_status,
       id.approve AS illus_approve, id.image_path AS illus_image,
       collect(DISTINCT {
           id: si.id, status: si.status, approve: si.approve,
           image_path: si.image_path, label: si.variant_label
       }) AS stands
"""

SYNC_APPROVAL_QUERY = """
MATCH (a)-[r]->(b)
WHERE type(r) IN ['produces','outfit_for']
  AND (r.sync = false OR r.sync IS NULL)
  AND labels(b)[0] = 'IllusDesign'
RETURN type(r) AS edge_type,
       labels(a)[0] AS from_label, a.id AS from_id,
       COALESCE(a.name, a.id) AS from_name,
       b.id AS to_id
ORDER BY b.id
"""

IMAGE_APPROVAL_QUERY = """
MATCH (n)
WHERE n.approve = 'pending'
  AND (n:DesignSheet OR n:IllusDesign OR n:StandingIllustration)
RETURN labels(n)[0] AS type, n.id AS id, n.image_path AS image_path
ORDER BY n.id
"""


# ═══════════════════════════════════════════════════════════════
# Cypher Queries — 通用节点操作
# ═══════════════════════════════════════════════════════════════

NODE_QUERY = """
MATCH (n {id: $node_id})
RETURN labels(n)[0] AS type, properties(n) AS props
"""

UPDATE_NODE_CYPHER = """
MATCH (n {id: $node_id})
SET n += $props
RETURN n.id AS id
"""

CASCADE_PREVIEW_CYPHER = """
MATCH path = (source {id: $node_id})-[r*1..6]->(downstream)
WHERE ALL(rel IN relationships(path) WHERE rel.sync <> false)
  AND downstream.status IS NOT NULL
RETURN DISTINCT labels(downstream)[0] AS type, downstream.id AS id
"""

CASCADE_RESET_CYPHER = """
MATCH path = (source {id: $node_id})-[r*1..6]->(downstream)
WHERE ALL(rel IN relationships(path) WHERE rel.sync <> false)
  AND downstream.status IS NOT NULL
WITH DISTINCT downstream
SET downstream.status = 0, downstream.approve = null, downstream.image_path = null
RETURN labels(downstream)[0] AS type, downstream.id AS id
"""

SELF_RESET_CYPHER = """
MATCH (n {id: $node_id})
WHERE labels(n)[0] IN ['DesignSheet', 'IllusDesign', 'StandingIllustration']
  AND n.status >= 2
SET n.status = 1, n.approve = null, n.image_path = null
RETURN labels(n)[0] AS type, n.id AS id
"""

APPROVE_NODE_CYPHER = """
MATCH (n {id: $node_id}) SET n.approve = 'approved' RETURN n.id AS id
"""

REJECT_NODE_CYPHER = """
MATCH (n {id: $node_id}) SET n.status = 0, n.approve = null RETURN n.id AS id
"""

SYNC_APPROVE_CYPHER = """
MATCH (a {id: $from_id})-[r]->(b {id: $to_id})
WHERE type(r) = $edge_type
SET r.sync = true
RETURN type(r) AS edge_type
"""


# ═══════════════════════════════════════════════════════════════
# Query Functions — 叙事基础
# ═══════════════════════════════════════════════════════════════

def get_narrative_stats():
    """返回叙事节点统计 + 边统计"""
    stats = _client.run(NAR_STATS_QUERY)
    edges = _client.run(NAR_EDGE_STATS_QUERY)
    result = stats[0] if stats else {"chars": 0, "events": 0, "scenes": 0, "infos": 0}
    result["edges"] = edges
    return result


def get_narrative_list(label: str):
    """按类型列出节点"""
    query = NAR_LIST_QUERIES.get(label)
    if not query:
        return []
    return _client.run(query)


def get_narrative_relations(node_id: str):
    """查询节点关系"""
    return _client.run(NAR_RELATIONS_QUERY, {"node_id": node_id})


def get_node_detail(node_id: str):
    """查询单个节点详情"""
    rows = _client.run(NODE_QUERY, {"node_id": node_id})
    return rows[0] if rows else None


# ═══════════════════════════════════════════════════════════════
# Query Functions — 角色美术
# ═══════════════════════════════════════════════════════════════

def get_art_full_status():
    """角色美术完整状态"""
    characters = _client.run(STATUS_QUERY)
    seen = set()
    deduped = []
    for c in characters:
        if c["char_id"] not in seen:
            seen.add(c["char_id"])
            deduped.append(c)
    characters = deduped

    costumes_rows = _client.run(COSTUME_QUERY)
    downstream = _client.run(DOWNSTREAM_QUERY)
    sync_approvals = [a for a in _client.run(SYNC_APPROVAL_QUERY) if a.get("from_id")]
    image_approvals = _client.run(IMAGE_APPROVAL_QUERY)
    costume_approvals = _client.run(COSTUME_APPROVAL_QUERY)

    costume_map = {}
    for row in costumes_rows:
        cid = row.get("char_id")
        cos = row.get("costumes") or []
        costume_map[cid] = [c for c in cos if c.get("id")]

    illus_by_design = {}
    stands_by_illus = {}
    for row in downstream:
        did = row.get("design_id")
        iid = row.get("illus_id")
        if did and iid:
            illus_by_design.setdefault(did, []).append({
                "id": iid, "status": row["illus_status"],
                "approve": row.get("illus_approve"),
                "image_path": row.get("illus_image"),
            })
            for s in (row.get("stands") or []):
                if s and s.get("id"):
                    stands_by_illus.setdefault(iid, []).append(s)

    for char in characters:
        did = char.get("design_id")
        char["costumes"] = costume_map.get(char["char_id"], [])
        illus_list = illus_by_design.get(did, [])
        char["illus"] = illus_list
        all_stands = []
        for il in illus_list:
            all_stands.extend(stands_by_illus.get(il["id"], []))
        char["stands"] = all_stands

    todos = _derive_todos(characters)

    return {
        "characters": characters,
        "todos": todos,
        "sync_approvals": sync_approvals,
        "image_approvals": image_approvals,
        "costume_approvals": costume_approvals,
        "total": len(characters),
        "completed": sum(1 for c in characters if _is_complete(c)),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _is_complete(char):
    return (
        char.get("appearance_status") is not None and char["appearance_status"] >= 1
        and char.get("language_status") is not None and char["language_status"] >= 1
        and all(c.get("status") is not None and c["status"] >= 1 for c in char.get("costumes", []))
        and char.get("design_status") is not None and char["design_status"] >= 2
        and char.get("design_approve") == "approved"
    )


def _derive_todos(characters):
    todos = []
    for char in characters:
        cid, name = char["char_id"], char["char_name"]
        ap_s = char.get("appearance_status")
        co_list = char.get("costumes", [])
        ls_s = char.get("language_status")

        concept_ok = (
            (ap_s is not None and ap_s >= 1)
            and (ls_s is not None and ls_s >= 1)
        )
        if not concept_ok:
            todos.append({
                "char_id": cid, "char_name": name,
                "node_type": "数据节点", "node_type_cn": "外貌+语言",
                "status": "missing",
                "action": "char-concept-designer", "action_cn": "概念设计",
                "prompt": f"为 {cid} ({name}) 构建美术图",
            })
            continue

        # 着装只看生产状态(status)；approve='pending' 属于审批事项，
        # 由专门的"着装审批"区呈现，不阻塞生产待办链（否则会掩盖下游级联重置）
        costume_ok = (
            len(co_list) > 0
            and all(c.get("status") is not None and c["status"] >= 1 for c in co_list)
        )
        if not costume_ok:
            if not co_list:
                st = "missing"
            else:
                sts = [c.get("status") for c in co_list if c.get("status") is not None]
                st = min(sts) if sts else "missing"
            todos.append({
                "char_id": cid, "char_name": name,
                "node_type": "着装", "node_type_cn": "着装",
                "status": st,
                "action": "char-costume-designer", "action_cn": "着装设计",
                "prompt": f"为 {cid} ({name}) 设计着装方案",
            })
            continue

        ds = char.get("design_status")
        ds_ap = char.get("design_approve")
        if ds is None or ds == 0:
            todos.append(_todo(cid, name, "DesignSheet", "设计图",
                                "missing" if ds is None else "0",
                                "char-design-sheet", "设计图",
                                f"处理 {char.get('design_id', cid)}"))
            continue
        if ds == 1:
            todos.append(_todo(cid, name, "DesignSheet", "设计图", "1",
                                "infra-image-generator", "图片生成",
                                f"为 {char.get('design_id')} 生成图片"))
            continue
        if ds == 2 and ds_ap != "approved":
            todos.append(_todo(cid, name, "DesignSheet", "设计图", "2",
                                "approve", "待审批", "", approve=ds_ap))
            continue

        illus = char.get("illus", [])
        if not illus:
            todos.append(_todo(cid, name, "IllusDesign", "立绘设计图", "missing",
                                "art-prompter", "创建立绘设计",
                                f"为 {cid} ({name}) 创建立绘设计图"))
            continue

        pending_illus = [il for il in illus if il["status"] is None or il["status"] < 2 or il.get("approve") != "approved"]
        if pending_illus:
            for il in pending_illus[:3]:
                il_s = il["status"]
                il_ap = il.get("approve")
                if il_s is None or il_s == 0:
                    todos.append(_todo(cid, name, "IllusDesign", "立绘设计",
                                        "missing" if il_s is None else "0",
                                        "char-illus-designer", "立绘设计", f"处理 {il['id']}"))
                elif il_s == 1:
                    todos.append(_todo(cid, name, "IllusDesign", "立绘设计", "1",
                                        "infra-image-generator", "图片生成", f"为 {il['id']} 生成图片"))
                elif il_s == 2 and il_ap != "approved":
                    todos.append(_todo(cid, name, "IllusDesign", "立绘设计", "2",
                                        "approve", "待审批", "", approve=il_ap))
            continue

        stands = char.get("stands", [])
        if not stands:
            todos.append(_todo(cid, name, "StandingIllustration", "立绘变体", "missing",
                                "char-stand-designer", "创建立绘",
                                f"为 {cid} ({name}) 处理立绘变体"))
    return todos


def _todo(cid, name, ntype, ntype_cn, status, action, action_cn, prompt, approve=None):
    return {
        "char_id": cid, "char_name": name,
        "node_type": ntype, "node_type_cn": ntype_cn,
        "status": status, "action": action, "action_cn": action_cn,
        "prompt": prompt, "approve": approve,
    }


# ═══════════════════════════════════════════════════════════════
# Query Functions — 通用节点操作
# ═══════════════════════════════════════════════════════════════

def update_node(node_id: str, props: dict):
    """更新节点属性，返回级联重置结果"""
    cascade = _client.run(CASCADE_PREVIEW_CYPHER, {"node_id": node_id})
    # 过滤掉不可修改的字段
    safe_props = {k: v for k, v in props.items() if k not in ("id", "status", "approve")}
    _client.run(UPDATE_NODE_CYPHER, {"node_id": node_id, "props": safe_props})
    self_reset = _client.run(SELF_RESET_CYPHER, {"node_id": node_id})
    reset = _client.run(CASCADE_RESET_CYPHER, {"node_id": node_id})
    return {"self_reset": self_reset, "cascade_reset": reset}


def approve_node(node_id: str):
    r = _client.run(APPROVE_NODE_CYPHER, {"node_id": node_id})
    return bool(r)


def reject_node(node_id: str):
    r = _client.run(REJECT_NODE_CYPHER, {"node_id": node_id})
    return bool(r)


def approve_sync(from_id: str, to_id: str, edge_type: str):
    r = _client.run(SYNC_APPROVE_CYPHER, {"from_id": from_id, "to_id": to_id, "edge_type": edge_type})
    return bool(r)


def cascade_preview(node_id: str):
    return _client.run(CASCADE_PREVIEW_CYPHER, {"node_id": node_id})


def get_taglib():
    """读取设计元素标签库（受控词表），按节点类型分组"""
    if not os.path.isfile(TAGLIB_PATH):
        return {}
    with open(TAGLIB_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


# ═══════════════════════════════════════════════════════════════
# Draft Management（叙事草案文件操作）
# ═══════════════════════════════════════════════════════════════

def _parse_frontmatter(content: str):
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


def _update_draft_status_on_disk(filepath: str, new_status: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(
        r"^(status:\s*).+$", f"status: {new_status}",
        content, count=1, flags=re.MULTILINE,
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def get_all_drafts():
    if not os.path.isdir(DRAFTS_DIR):
        return []
    drafts = []
    for fname in sorted(os.listdir(DRAFTS_DIR)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(DRAFTS_DIR, fname)
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
                    "title": fm.get("title", fname.replace(".md", "")),
                    "created_at": fm.get("created_at", ""),
                    "opportunity_type": fm.get("opportunity_type", ""),
                })
        except Exception:
            drafts.append({"filename": fname, "path": fpath, "status": "error",
                           "title": fname, "priority": "", "draft_id": fname})
    return drafts


def get_draft_content(draft_id: str):
    if not os.path.isdir(DRAFTS_DIR):
        return None
    for fname in os.listdir(DRAFTS_DIR):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(DRAFTS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            fm = _parse_frontmatter(content)
            did = fm.get("draft_id", "") if fm else ""
            if fname == draft_id or did == draft_id or fname.replace(".md", "") == draft_id:
                return {"frontmatter": fm, "content": content, "path": fpath, "filename": fname}
        except Exception:
            continue
    return None


def approve_draft(draft_id: str):
    result = get_draft_content(draft_id)
    if not result:
        return None
    _update_draft_status_on_disk(result["path"], "approved")
    return {"draft_id": draft_id, "status": "approved"}


def reject_draft(draft_id: str):
    result = get_draft_content(draft_id)
    if not result:
        return None
    _update_draft_status_on_disk(result["path"], "rejected")
    return {"draft_id": draft_id, "status": "rejected"}
