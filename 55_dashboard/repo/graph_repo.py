"""图数据库读写：唯一写 Cypher 的地方。所有方法接收/返回普通 dict。"""
from contextlib import contextmanager
from repo.neo4j_conn import get_driver


@contextmanager
def _session():
    with get_driver().session() as s:
        yield s


def _label_of(node_id):
    """查节点 label。"""
    with _session() as s:
        rec = s.run("MATCH (n) WHERE n.id=$id RETURN labels(n)[0] AS label", id=node_id).single()
        return rec["label"] if rec else None


def get_node(node_id):
    with _session() as s:
        rec = s.run(
            "MATCH (n) WHERE n.id=$id RETURN n.id AS id, labels(n)[0] AS label, properties(n) AS props",
            id=node_id,
        ).single()
    if not rec:
        return None
    props = dict(rec["props"])
    label = rec["label"]
    props.update(id=rec["id"], label=label)
    return props


def get_nodes(label):
    out = []
    with _session() as s:
        rs = s.run(
            "MATCH (n:`%s`) RETURN n.id AS id, labels(n)[0] AS label, properties(n) AS props" % label
        )
        for rec in rs:  # 必须在 session 内消费 result（neo4j 6.x：session 关闭即 consume）
            props = dict(rec["props"])
            props.update(id=rec["id"], label=rec["label"])
            out.append(props)
    return out


# 美术生产链边类型（限定遍历范围，避免把叙事 Event/Info/其他角色拉进美术子图）
_ART_EDGES = "has_appearance|has_voice_style|has_costume|produces|outfit_for|expands_to|ref_style"


def get_character_graph(char_id):
    """取角色美术生产链的全部节点与边（仅沿美术边遍历）。"""
    with _session() as s:
        ids = [r["id"] for r in s.run(
            "MATCH (c:Character)-[:%s*0..5]-(n) WHERE c.id=$id RETURN DISTINCT n.id AS id" % _ART_EDGES,
            id=char_id,
        )]
        if not ids:
            return {"nodes": [], "edges": []}
        nodes = [
            {"id": r["id"], "label": r["label"], "status": r["status"], "name": r["name"]}
            for r in s.run(
                "MATCH (n) WHERE n.id IN $ids "
                "RETURN n.id AS id, labels(n)[0] AS label, n.status AS status, n.name AS name",
                ids=ids,
            )
        ]
        edges = [
            {"from": r["f"], "to": r["t"], "type": r["ty"], "sync": r["sync"]}
            for r in s.run(
                "MATCH (a)-[r]->(b) WHERE a.id IN $ids AND b.id IN $ids "
                "RETURN a.id AS f, b.id AS t, type(r) AS ty, r.sync AS sync",
                ids=ids,
            )
        ]
    return {"nodes": nodes, "edges": edges}


def get_sync_downstream(node_id):
    """一跳内 sync=true 出边指向的下游。"""
    with _session() as s:
        rs = s.run(
            """
            MATCH (a)-[r]->(b)
            WHERE a.id=$id AND r.sync=true
            RETURN b.id AS id, labels(b)[0] AS label, b.status AS status
            """,
            id=node_id,
        )
        return [{"id": r["id"], "label": r["label"], "status": r["status"]} for r in rs]


def update_node(node_id, props):
    clean = {k: v for k, v in props.items() if k not in ("id", "label")}
    with _session() as s:
        s.run(
            "MATCH (n) WHERE n.id=$id SET n += $props",
            id=node_id, props=clean,
        ).consume()


def set_status(node_id, status):
    set_status_batch([node_id], status)


def set_status_batch(node_ids, status):
    with _session() as s:
        s.run(
            "UNWIND $ids AS x MATCH (n) WHERE n.id=x SET n.status=$status",
            ids=node_ids, status=status,
        ).consume()


def get_pending_approvals():
    with _session() as s:
        rs = s.run(
            "MATCH (n) WHERE n.status=10 RETURN n.id AS id, labels(n)[0] AS label, n.status AS status"
        )
        return [{"id": r["id"], "label": r["label"], "status": r["status"]} for r in rs]


def get_upstream_character_id(node_id):
    """从节点经美术边回溯到所属 Character（Character 自身经 0 跳返回自己）。"""
    with _session() as s:
        rec = s.run(
            "MATCH (c:Character)-[:%s*0..5]-(n) WHERE n.id=$id "
            "RETURN c.id AS cid LIMIT 1" % _ART_EDGES,
            id=node_id,
        ).single()
    return rec["cid"] if rec else None
