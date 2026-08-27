"""图数据库读写：唯一写 Cypher 的地方。所有方法接收/返回普通 dict。"""
import csv
import io
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
_ART_EDGES = "has_appearance|has_voice_style|has_voice_design|has_costume|produces|outfit_for|expands_to|ref_style"

# 场景美术链边类型（限定遍历范围，避免把叙事 Event/Character 拉进场景子图；has_bgm 让 BgmTrack 进场景子图）
_SCENE_EDGES = "has_scene|has_layer|has_bgm"

# 剧情编排边类型（限定章节子图遍历：Chapter→has_section→Section→has_outline→SecOutline→produces→SecScript→produces→LineAudio；
# Section→contains→Scene→depicts→IllusDesign→expands_to→StandingIllustration；LineAudio(scene行)→stages→Scene）
_PLOT_EDGES = "has_section|has_outline|produces|contains|depicts|expands_to|stages"


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


def get_location_graph(loc_id):
    """取地点场景美术链的全部节点与边（仅沿场景边遍历）。Location→Scene→SceneLayer 最深 2 跳。"""
    with _session() as s:
        ids = [r["id"] for r in s.run(
            "MATCH (l:Location)-[:%s*0..3]-(n) WHERE l.id=$id RETURN DISTINCT n.id AS id" % _SCENE_EDGES,
            id=loc_id,
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


def get_chapter_graph(ch_id):
    """取章节编排子图的全部节点与边（Chapter→has_section→Section→contains→Scene→depicts→IllusDesign→expands_to→StandingIllustration）。

    沿 has_section/contains/depicts/expands_to 边遍历；depicts 指向的 IllusDesign 及其 expands_to 立绘变体一并纳入（供立绘缺口查看）。
    有向遍历（->）严格沿上游→下游，避免共享 IllusDesign 反向 depicts 蔓延到其他章 Scene 造成跨章子图污染。
    """
    with _session() as s:
        ids = [ch_id] + [r["id"] for r in s.run(
            "MATCH (ch:Chapter)-[:%s*1..4]->(n) WHERE ch.id=$id RETURN DISTINCT n.id AS id" % _PLOT_EDGES,
            id=ch_id,
        )]
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
    """SET n += props（剥离 id/label）。**value=None 即删除该属性**（Neo4j 不存 null，
    `SET n += {k: null}` 会移除 k）——如 voice_candidates 采用动作用它清空 candidates_path。
    切勿在此过滤 None，会把删属性能力堵死。"""
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
    # status=10 通用待审（Chapter 结构审 / SecScript 定稿审 / LineAudio 逐句音频审 / 美术与音色设计审批）
    with _session() as s:
        rs = s.run(
            "MATCH (n) WHERE n.status IN [10] "
            "RETURN n.id AS id, labels(n)[0] AS label, n.status AS status"
        )
        return [{"id": r["id"], "label": r["label"], "status": r["status"]} for r in rs]


def get_upstream_script_path(vo_id):
    """取 LineAudio 的上游 SecScript.script_path（审批中心逐句音频审的试听数据源）。"""
    with _session() as s:
        rec = s.run(
            "MATCH (sc:SecScript)-[:produces]->(:LineAudio {id:$id}) "
            "RETURN sc.script_path AS p LIMIT 1",
            id=vo_id,
        ).single()
    return rec["p"] if rec else None


def get_section_of_lineaudio(vo_id):
    """取 LineAudio 所属的 Section id（沿产物链回溯：Section→SecOutline→SecScript→LineAudio）。

    逐句审批卡的「重生成」deeplink 需要 section id 唤起 plot-design 单节聚焦。
    """
    with _session() as s:
        rec = s.run(
            "MATCH (sec:Section)-[:has_outline]->()-[:produces]->()-[:produces]->(:LineAudio {id:$id}) "
            "RETURN sec.id AS sid LIMIT 1",
            id=vo_id,
        ).single()
    return rec["sid"] if rec else None


def get_script_lines(sc_id):
    """取 SecScript 的逐句行（LineAudio，按 produces.order 升序）。

    行 dict 含节点属性 + order +（op=scene 行）stages→Scene 的 name/time_of_day。
    块归属/voice key 的 scene 段由调用方按 order 遍历遇 op=scene 行切块推导（行上不冗余存）。
    """
    with _session() as s:
        rs = s.run(
            """
            MATCH (sc:SecScript {id:$id})-[p:produces]->(l:LineAudio)
            OPTIONAL MATCH (l)-[:stages]->(s:Scene)
            RETURN l.id AS id, l.name AS name, l.op AS op, l.who AS who,
                   l.portrait AS portrait, l.pos AS pos, l.text AS text,
                   l.tts_text AS tts_text, l.scene_block_id AS scene_block_id,
                   l.voice_key AS voice_key, l.emotion AS emotion,
                   l.attempts AS attempts, l.text_sha1 AS text_sha1,
                   l.status AS status, p.order AS ord,
                   s.name AS scene_name, s.time_of_day AS scene_time
            ORDER BY p.order
            """,
            id=sc_id,
        )
        return [dict(r) for r in rs]


def get_script_id_of_section(sec_id):
    """取 Section 的 SecScript id + status（行查询入口）。无 SecScript 返回 (None, None)。"""
    with _session() as s:
        rec = s.run(
            "MATCH (:Section {id:$id})-[:has_outline]->()-[:produces]->(sc:SecScript) "
            "RETURN sc.id AS sid, sc.status AS st LIMIT 1",
            id=sec_id,
        ).single()
    return (rec["sid"], rec["st"]) if rec else (None, None)


def get_script_of_line(line_id):
    """取 LineAudio 行节点的上游 SecScript + 所属 Section（逐句审批分组用）。

    返回 {"sc_id", "sc_name", "sec_id"} 或 None。
    """
    with _session() as s:
        rec = s.run(
            "MATCH (sec:Section)-[:has_outline]->()-[:produces]->(sc:SecScript)"
            "-[:produces]->(:LineAudio {id:$id}) "
            "RETURN sc.id AS sc_id, sc.name AS sc_name, sec.id AS sec_id LIMIT 1",
            id=line_id,
        ).single()
    return dict(rec) if rec else None


def get_upstream_character_id(node_id):
    """从节点经美术边回溯到所属 Character（Character 自身经 0 跳返回自己）。"""
    with _session() as s:
        rec = s.run(
            "MATCH (c:Character)-[:%s*0..5]-(n) WHERE n.id=$id "
            "RETURN c.id AS cid LIMIT 1" % _ART_EDGES,
            id=node_id,
        ).single()
    return rec["cid"] if rec else None


def get_upstream_location_id(node_id):
    """从节点经场景边回溯到所属 Location（Location 自身经 0 跳返回自己）。"""
    with _session() as s:
        rec = s.run(
            "MATCH (l:Location)-[:%s*0..3]-(n) WHERE n.id=$id "
            "RETURN l.id AS lid LIMIT 1" % _SCENE_EDGES,
            id=node_id,
        ).single()
    return rec["lid"] if rec else None


def split_cypher_script(text):
    """把含 ; 的多语句 cypher 文本拆成独立语句列表。

    正确处理：字符串字面量内的 ;（不作为分隔符）、\\ 转义、// 行注释（仅字符串外
    视为注释并剥离整行）。规则照搬 .claude/scripts/cypher_exec.py:split_cypher_statements。
    """
    statements = []
    current = []
    in_string = False       # 是否在字符串字面量内
    string_char = None      # 当前字符串的引号字符 (' 或 ")
    escape_next = False     # 上一个字符是否为转义符 \

    i, n = 0, len(text)
    while i < n:
        ch = text[i]

        # 行注释 //（仅字符串外）：跳过到行尾，不写入 current
        if not in_string and ch == '/' and i + 1 < n and text[i + 1] == '/':
            while i < n and text[i] != '\n':
                i += 1
            continue  # 留下 \n 给主循环处理

        if escape_next:
            current.append(ch)
            escape_next = False
            i += 1
            continue
        if ch == '\\' and in_string:
            current.append(ch)
            escape_next = True
            i += 1
            continue
        if in_string:
            current.append(ch)
            if ch == string_char:
                in_string = False
            i += 1
            continue
        # 不在字符串内
        if ch in ("'", '"'):
            current.append(ch)
            in_string = True
            string_char = ch
        elif ch == ';':
            stmt = ''.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(ch)
        i += 1

    tail = ''.join(current).strip()  # 末尾无 ; 的残余
    if tail:
        statements.append(tail)
    return statements


def run_write_script(cypher_text):
    """在单事务内逐条执行多语句 cypher；任一失败整体回滚。返回执行的语句条数。"""
    stmts = split_cypher_script(cypher_text)
    if not stmts:
        return 0

    def _work(tx):
        for stmt in stmts:
            tx.run(stmt).consume()

    with _session() as s:
        s.execute_write(_work)
    return len(stmts)


def export_csv_all():
    """全库导出为 CSV 字符串（APOC stream）。

    用 apoc.export.csv.all(null, {stream:true})：stream+null 文件专为无文件系统访问设计，
    无需 apoc.export.file.enabled。失败（APOC 未注册 / 大数据集 stream 返回空）时 raise，
    由调用方走 export_csv_all_pure 兜底。

    返回 (csv_text, {"nodes": n, "relationships": r})。
    """
    cypher = (
        "CALL apoc.export.csv.all(null, {stream:true}) "
        "YIELD file, nodes, relationships, properties, data "
        "RETURN nodes AS n, relationships AS r, data AS data"
    )
    with _session() as s:
        rec = s.run(cypher).single()
    if rec is None or not rec["data"]:
        raise RuntimeError("APOC stream 返回空 data（数据集过大或 APOC 未注册）")
    return rec["data"], {"nodes": rec["n"], "relationships": rec["r"]}


def export_csv_all_pure():
    """纯 Python 兜底：节点表 + 边表两段 CSV，不依赖 APOC。

    APOC 不可用时使用。返回 (csv_text, {"nodes": n, "relationships": r})。
    """
    with _session() as s:
        node_recs = list(s.run(
            "MATCH (n) RETURN n.id AS id, labels(n) AS labels, properties(n) AS props"
        ))
        rel_recs = list(s.run(
            "MATCH (a)-[r]->(b) "
            "RETURN a.id AS start, b.id AS end, type(r) AS type, properties(r) AS props"
        ))
    node_keys = sorted({k for r in node_recs for k in dict(r["props"])})
    rel_keys = sorted({k for r in rel_recs for k in dict(r["props"])})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["# 节点"])
    w.writerow(["id", "labels"] + node_keys)
    for r in node_recs:
        p = dict(r["props"])
        w.writerow([r["id"], ":".join(r["labels"])] + [p.get(k, "") for k in node_keys])
    w.writerow([])
    w.writerow(["# 边"])
    w.writerow(["_start", "_end", "_type"] + rel_keys)
    for r in rel_recs:
        p = dict(r["props"])
        w.writerow([r["start"], r["end"], r["type"]] + [p.get(k, "") for k in rel_keys])
    return buf.getvalue(), {"nodes": len(node_recs), "relationships": len(rel_recs)}
