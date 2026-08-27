"""台词.md 拆分对齐进图（SecScript → 逐句 LineAudio，produces{order} 大间距排序）。

section-voice-publisher 第一步「拆分进图」的唯一实现。把已批定稿（SecScript=11 的
台词.md，人读 Markdown）幂等拆分为图节点：

  parse_md  解析 台词.md → 行序列（scene/say/narrate/label/ending；**选择**块跳过——
            choice 及配套 jump 暂不进图，建模后续设计；解析失败抛 ValueError 带行号）
  align     md 行 vs 图已有行 difflib 对齐（签名 = op+who+text）→ 保留/更新/新建/删除
  split     经 cypher_exec.py（--stdin --multi 单事务）写图 + 产出报告 JSON

数据模型（00_init/Schema/剧情.md）：
  行身份 = 节点雪花 id（voice key 末段，插入/删除行不影响其他行）
  顺序   = produces 边 order：初始 (i+1)*1000；两句之间插入取 (上+下)//2 中点；
           同缝隙多行均分；中点耗尽（分配后非严格递增）→ 全节重排（order 不进
           voice key，重排安全）
  恢复   = sync 级联置 -1 的行：text_sha1 匹配且 wav 在 → 10（音频复用，保守进审）；
           非 say 行 → 11（无音频语义，拆分即完成）；否则 0
  微调   = 人工改 md 重批后重拆：未变行原样保留（含已批 11），只有改动句置 0
           ——单句修改不丢

CLI:
  python script_splitter.py split --section <sec_id> [--report out.json] [--dry-run]
退码：0 成功（或 dry-run）/ 1 前置校验或解析失败 / 2 参数错。
"""
import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # .claude/scripts/ → 项目根
CYPHER_EXEC = Path(__file__).resolve().parent / "cypher_exec.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from snowflake_base62 import SnowflakeGenerator  # noqa: E402

ORDER_STEP = 1000          # 初始间距
SAY_DEFAULT_POS = "left"   # 新 say 行缺省立绘位（md 不写 pos）

_GEN = SnowflakeGenerator()


def text_sha1(text: str) -> str:
    """台词文本指纹（stale 判定唯一依据，不做 normalize）。与 voice_bundler._text_sha1 同实现。"""
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()


def _q(v) -> str:
    """Cypher 字符串字面量（单引号，转义 \\ 与 '）。None → null。"""
    if v is None:
        return "null"
    s = str(v).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


def _run_cypher(cypher: str) -> list:
    """调 cypher_exec.py --json，提取返回的 JSON 数组（cypher_exec 输出含连接提示行）。"""
    proc = subprocess.run(
        [sys.executable, str(CYPHER_EXEC), "-c", cypher, "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    out = proc.stdout
    start, end = out.find("["), out.rfind("]")
    if start == -1 or end == -1:
        raise RuntimeError(
            f"cypher_exec 未返回 JSON（退出码 {proc.returncode}）:\nstderr: {proc.stderr}\nstdout: {out}"
        )
    return json.loads(out[start:end + 1])


def _run_cypher_multi(statements: list) -> None:
    """多语句单事务写图（--stdin --multi）；任一失败整体回滚。"""
    tx = "\n".join(statements)
    proc = subprocess.run(
        [sys.executable, str(CYPHER_EXEC), "--stdin", "--multi"],
        input=tx, capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"写图失败（退出码 {proc.returncode}）:\n{proc.stderr}")


# ── 解析 台词.md ─────────────────────────────────────────────

_SCENE_RE = re.compile(r"^##\s+(\S+)\s+(.+?)\s*(?:（([^）]*)）)?\s*$")
_NARRATE_RE = re.compile(r"^旁白\s*:\s*(.+)$")
_SAY_RE = re.compile(r"^([^:\[\]]+?)\s*(?:\[([^\[\]]+)\])?\s*:\s*(.+)$")
_LABEL_RE = re.compile(r"^\*\*分支\s*[:：]\s*(.+?)\s*\*\*$")
_ENDING_RE = re.compile(r"^\*\*结局\*\*\s*[:：]\s*(BE|TE|HE|NE)\s*(?:——|—)\s*(.+)$")
_CHOICE_RE = re.compile(r"^\*\*选择\*\*\s*$")


def parse_md(path) -> list:
    """解析 台词.md → 行 dict 列表（op/who/portrait/text/kind/scene_block_id/scene_name）。

    `#` 节标题与空行忽略；`**选择**` 块（含其下 `- ` 选项行）整体跳过（choice 不进图）。
    无法识别的行抛 ValueError（带行号与原文）——skill 依报错修 md。
    """
    rows = []
    in_choice = False
    text = Path(path).read_text(encoding="utf-8")
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") and not line.startswith("##"):
            continue  # 空行 / 一级节标题
        if _CHOICE_RE.match(line):
            in_choice = True
            continue
        if in_choice:
            if line.startswith("-"):
                continue  # 选择块内的选项行
            in_choice = False  # 其他行 = 选择块结束，继续正常解析
        if line.startswith("##"):
            m = _SCENE_RE.match(line)
            if not m:
                raise ValueError(f"台词.md 第 {n} 行场景标题格式错误：{raw!r}"
                                 "（应为 ## <scene_block_id> <Scene 名>（<时段>））")
            rows.append({"op": "scene", "scene_block_id": m.group(1),
                         "scene_name": m.group(2).strip(), "text": None})
            continue
        m = _NARRATE_RE.match(line)
        if m:
            rows.append({"op": "narrate", "text": m.group(1).strip()})
            continue
        m = _LABEL_RE.match(line)
        if m:
            rows.append({"op": "label", "text": m.group(1).strip()})
            continue
        m = _ENDING_RE.match(line)
        if m:
            rows.append({"op": "ending", "kind": m.group(1), "text": m.group(2).strip()})
            continue
        m = _SAY_RE.match(line)
        if m:
            rows.append({"op": "say", "who": m.group(1).strip(),
                         "portrait": (m.group(2) or "").strip() or None,
                         "text": m.group(3).strip()})
            continue
        raise ValueError(f"台词.md 第 {n} 行无法解析：{raw!r}（格式规范见 chapter-dialoguer SKILL.md）")
    if not any(r["op"] == "scene" for r in rows):
        raise ValueError("台词.md 缺场景二级标题（## <scene_block_id> <Scene 名>（<时段>））")
    return rows


def _sig(r: dict) -> tuple:
    """对齐签名：scene 行用块 id、ending 行用 kind+落点，其余 op+who+text。"""
    op = r.get("op")
    if op == "scene":
        return ("scene", "", r.get("scene_block_id") or "")
    if op == "ending":
        return ("ending", "", (r.get("kind") or "") + "——" + (r.get("text") or ""))
    return (op, r.get("who") or "", r.get("text") or "")


def _row_name(m: dict) -> str:
    """行正文即 name（scene 行 = scene_block_id）。"""
    if m["op"] == "scene":
        return m.get("scene_block_id") or ""
    return m.get("text") or ""


def _wav_exists(who: str, voice_key: str) -> bool:
    return bool(who and voice_key and (ROOT / "15_声音" / who / f"{voice_key}.wav").exists())


# ── 对齐 ─────────────────────────────────────────────────────

def align(md_rows: list, graph_rows: list) -> dict:
    """md 行 vs 图行（须按 order 升序）→ {keep, update, create, delete} 计划。

    keep   equal：签名全同（text 必相同）。-1 恢复 / 演出字段 diff 在 build_actions 处理
    update replace 块按位置配对：沿用图行 id/order，字段全量更新，status=0（stale 重配）
    create md 独有：新节点（雪花 id）+ order 中点
    delete 图独有：DETACH DELETE（wav 留盘）
    """
    sm = difflib.SequenceMatcher(None, [_sig(r) for r in graph_rows], [_sig(r) for r in md_rows])
    plan = {"keep": [], "update": [], "create": [], "delete": []}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                plan["keep"].append({"graph": graph_rows[i1 + k], "md": md_rows[j1 + k]})
        elif tag == "delete":
            plan["delete"].extend({"graph": g} for g in graph_rows[i1:i2])
        elif tag == "insert":
            plan["create"].extend({"md": m} for m in md_rows[j1:j2])
        else:  # replace：按位置配对，多出部分按删/建
            n = min(i2 - i1, j2 - j1)
            for k in range(n):
                plan["update"].append({"graph": graph_rows[i1 + k], "md": md_rows[j1 + k]})
            plan["delete"].extend({"graph": g} for g in graph_rows[i1 + n:i2])
            plan["create"].extend({"md": m} for m in md_rows[j1 + n:j2])
    return plan


def assign_orders(md_rows: list, plan: dict) -> tuple:
    """给最终序列（md 顺序）分配 order。返回 (seq, reordered)。

    seq = [{md, action, graph?, id, order}]。create 行取上下邻居中点（同缝隙多行均分
    gap/(n+1)）；头/尾插入外推 ±1000；分配后非严格递增（或旧行缺 order）→ 全节重排
    (i+1)*1000（reordered=True，order 不进 voice key，重排安全）。
    """
    by_md = {}
    for action in ("keep", "update"):
        for it in plan[action]:
            by_md[id(it["md"])] = (action, it)
    seq = []
    for m in md_rows:
        hit = by_md.get(id(m))
        if hit:
            action, it = hit
            seq.append({"md": m, "action": action,
                        "graph": it["graph"], "id": it["graph"]["id"],
                        "order": it["graph"].get("ord")})
        else:
            seq.append({"md": m, "action": "create", "graph": None,
                        "id": _GEN.next_id_base62(), "order": None})
    if any(item["action"] != "create" and item["order"] is None for item in seq):
        for i, item in enumerate(seq, 1):  # 旧图行缺 order：直接全节重排
            item["order"] = i * ORDER_STEP
        return seq, True
    _fill_creates(seq)
    if not _strictly_increasing(seq):
        for i, item in enumerate(seq, 1):
            item["order"] = i * ORDER_STEP
        return seq, True
    return seq, False


def _fill_creates(seq: list) -> None:
    """为连续 create 段分配中点 order（同缝隙多行均分；头尾外推）。原地修改。"""
    i = 0
    while i < len(seq):
        if seq[i]["action"] != "create":
            i += 1
            continue
        j = i
        while j < len(seq) and seq[j]["action"] == "create":
            j += 1
        n = j - i
        prev_o = seq[i - 1]["order"] if i > 0 else None
        next_o = seq[j]["order"] if j < len(seq) else None
        if prev_o is None and next_o is None:      # 全新节：顺序铺开
            for k in range(n):
                seq[i + k]["order"] = (k + 1) * ORDER_STEP
        elif prev_o is None:                        # 头部插入：向左外推
            for k in range(n):
                seq[i + k]["order"] = next_o - ORDER_STEP * (n - k)
        elif next_o is None:                        # 尾部插入：向右外推
            for k in range(n):
                seq[i + k]["order"] = prev_o + ORDER_STEP * (k + 1)
        else:                                       # 缝隙均分 (prev, next)
            gap = next_o - prev_o
            step = gap // (n + 1)
            for k in range(n):
                seq[i + k]["order"] = prev_o + step * (k + 1) if step > 0 else prev_o
        i = j


def _strictly_increasing(seq: list) -> bool:
    return all(a["order"] < b["order"] for a, b in zip(seq, seq[1:]))


# ── 动作生成（恢复 / 演出 diff / 字段更新 / 建删） ──────────────

def _set_props(m: dict, pos) -> str:
    """行字段全量 SET 子句（update/create 用）：status=0（say）/ 11（非 say）。"""
    return ", ".join([
        f"l.name={_q(_row_name(m))}",
        f"l.op={_q(m['op'])}",
        f"l.who={_q(m.get('who'))}",
        f"l.portrait={_q(m.get('portrait'))}",
        f"l.pos={_q(pos)}",
        f"l.text={_q(m.get('text'))}",
        f"l.kind={_q(m.get('kind'))}",
        f"l.scene_block_id={_q(m.get('scene_block_id'))}",
        f"l.text_sha1={_q(text_sha1(m.get('text') or ''))}",
        f"l.status={0 if m['op'] == 'say' else 11}",
    ])


def build_actions(seq: list, plan: dict, sc_id: str, scene_names: set) -> tuple:
    """最终序列 → (cypher 语句列表, 报告 dict)。含 keep 的 -1 恢复与演出字段 diff。"""
    stmts = []
    report = {"counts": {"kept": 0, "created": 0, "updated": 0, "deleted": 0, "restored": 0},
              "created": [], "updated": [], "deleted": [], "restored": [], "warnings": []}

    for it in plan["delete"]:  # 图有 md 无：删行（wav 留盘成孤儿，报告列出）
        g = it["graph"]
        stmts.append(f"MATCH (l:LineAudio {{id:{_q(g['id'])}}}) DETACH DELETE l;")
        report["deleted"].append({"id": g["id"], "op": g.get("op"),
                                  "text": (g.get("text") or "")[:30]})

    pos_map = {}  # 场景块内各角色上一次 pos（新 say 行缺省沿用）
    for item in seq:
        m, action, oid, order = item["md"], item["action"], item["id"], item["order"]
        if m["op"] == "scene":
            pos_map = {}  # pos 沿用以场景块为界
        if action == "create":
            pos = (pos_map.get(m.get("who") or "") or SAY_DEFAULT_POS) if m["op"] == "say" else None
            stmts.append(
                f"MERGE (l:LineAudio {{id:{_q(oid)}}}) "
                f"ON CREATE SET {_set_props(m, pos)} "
                f"WITH l MATCH (sc:SecScript {{id:{_q(sc_id)}}}) "
                f"MERGE (sc)-[r:produces]->(l) SET r.order={order}, r.sync=true;"
            )
            if m["op"] == "scene":
                if m.get("scene_name") in scene_names:
                    stmts.append(
                        f"MATCH (l:LineAudio {{id:{_q(oid)}}}), (s:Scene {{name:{_q(m['scene_name'])}}}) "
                        f"MERGE (l)-[e:stages]->(s) SET e.sync=false;"
                    )
                else:
                    report["warnings"].append(
                        f"Scene {m.get('scene_name')!r} 不存在，scene 行 {oid} 的 stages 边未建")
            if m["op"] == "say":
                pos_map[m.get("who") or ""] = pos
            report["created"].append({"id": oid, "op": m["op"], "order": order,
                                      "text": (m.get("text") or m.get("scene_block_id") or "")[:30]})
        elif action == "update":  # 台词变了（stale）：沿用 id/order，全量更新，置 0 重配
            g = item["graph"]
            pos = g.get("pos")
            if m["op"] == "say" and not pos:
                pos = SAY_DEFAULT_POS
            stmts.append(f"MATCH (l:LineAudio {{id:{_q(oid)}}}) SET {_set_props(m, pos)};")
            if m["op"] == "scene" and m.get("scene_name") in scene_names \
                    and m.get("scene_name") != g.get("scene_name"):
                stmts.append(
                    f"MATCH (l:LineAudio {{id:{_q(oid)}}})-[old:stages]->() DELETE old;",
                    f"MATCH (l:LineAudio {{id:{_q(oid)}}}), (s:Scene {{name:{_q(m['scene_name'])}}}) "
                    f"MERGE (l)-[e:stages]->(s) SET e.sync=false;")
            if m["op"] == "say":
                pos_map[m.get("who") or ""] = pos or SAY_DEFAULT_POS
            report["updated"].append({"id": oid, "op": m["op"],
                                      "text": (m.get("text") or "")[:30]})
        else:  # keep：未变行。仅 -1 恢复与演出字段 diff，status 0/10/11 原样保留
            g = item["graph"]
            if g.get("status") == -1:
                if m["op"] != "say":
                    new_status = 11
                elif g.get("voice_key") and g.get("text_sha1") == text_sha1(m.get("text") or "") \
                        and _wav_exists(g.get("who") or "", g.get("voice_key")):
                    new_status = 10
                else:
                    new_status = 0
                stmts.append(f"MATCH (l:LineAudio {{id:{_q(oid)}}}) SET l.status={new_status};")
                report["restored"].append({"id": oid, "to": new_status})
            if m["op"] == "say" and (m.get("portrait") or None) != (g.get("portrait") or None):
                stmts.append(f"MATCH (l:LineAudio {{id:{_q(oid)}}}) "
                             f"SET l.portrait={_q(m.get('portrait'))};")
            if m["op"] == "say" and g.get("pos"):
                pos_map[m.get("who") or ""] = g["pos"]
            report["counts"]["kept"] += 1

    report["counts"].update(created=len(report["created"]), updated=len(report["updated"]),
                            deleted=len(report["deleted"]), restored=len(report["restored"]))
    return stmts, report


def _order_statements(seq: list, sc_id: str, reordered: bool) -> list:
    """order 写入：create 行已在建边语句带 order；重排时对已有行补 SET order。"""
    if not reordered:
        return []
    return [
        f"MATCH (sc:SecScript {{id:{_q(sc_id)}}})-[r:produces]->(l:LineAudio {{id:{_q(item['id'])}}}) "
        f"SET r.order={item['order']};"
        for item in seq if item["action"] != "create"
    ]


# ── split 主流程 ─────────────────────────────────────────────

def split(section_id: str, dry_run: bool = False) -> dict:
    """拆分对齐进图。前置：SecScript=11。返回报告 dict（查询/解析/写图失败 raise）。"""
    rows = _run_cypher(
        "MATCH (:Section {id:'" + section_id + "'})-[:has_outline]->(:SecOutline)"
        "-[:produces]->(sc:SecScript) "
        "RETURN sc.id AS sc_id, sc.script_path AS p, sc.status AS st LIMIT 1"
    )
    if not rows:
        raise ValueError(f"Section {section_id} 无 SecScript（先跑 chapter-dialoguer 产定稿）")
    sc_id, script_path, st = rows[0]["sc_id"], rows[0]["p"], rows[0]["st"]
    if st != 11:
        raise ValueError(f"SecScript.status={st}（须 11 定稿已批才能拆分进图）")
    if not script_path:
        raise ValueError("SecScript.script_path 为空")
    md_rows = parse_md(script_path)

    graph_rows = _run_cypher(
        "MATCH (sc:SecScript {id:'" + sc_id + "'})-[p:produces]->(l:LineAudio) "
        "OPTIONAL MATCH (l)-[:stages]->(s:Scene) "
        "RETURN l.id AS id, l.op AS op, l.who AS who, l.portrait AS portrait, l.pos AS pos, "
        "l.text AS text, l.kind AS kind, l.scene_block_id AS scene_block_id, "
        "l.status AS status, l.attempts AS attempts, l.voice_key AS voice_key, "
        "l.text_sha1 AS text_sha1, p.order AS ord, s.name AS scene_name "
        "ORDER BY p.order"
    )

    wanted = sorted({m["scene_name"] for m in md_rows if m["op"] == "scene"})
    scene_names = set()
    if wanted:
        found = _run_cypher(
            "MATCH (s:Scene) WHERE s.name IN [" + ",".join(_q(n) for n in wanted) + "] RETURN s.name AS name"
        )
        scene_names = {r["name"] for r in found}

    plan = align(md_rows, graph_rows)
    seq, reordered = assign_orders(md_rows, plan)
    stmts, report = build_actions(seq, plan, sc_id, scene_names)
    stmts = _order_statements(seq, sc_id, reordered) + stmts
    report.update({"section_id": section_id, "sc_id": sc_id, "script_path": script_path,
                   "reordered": reordered, "statements": len(stmts), "dry_run": dry_run})
    if stmts and not dry_run:
        _run_cypher_multi(stmts)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="台词.md 拆分对齐进图（SecScript→逐句 LineAudio）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_split = sub.add_parser("split", help="拆分进图")
    p_split.add_argument("--section", required=True, help="Section 节点 ID（snowflake）")
    p_split.add_argument("--report", help="报告 JSON 落盘路径（缺省仅 stdout）")
    p_split.add_argument("--dry-run", action="store_true", help="只产计划不写图")
    args = ap.parse_args(argv)

    try:
        report = split(args.section, dry_run=args.dry_run)
    except (ValueError, RuntimeError) as e:
        sys.stderr.write(f"拆分失败: {e}\n")
        return 1
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    c = report["counts"]
    print(f"OK: kept={c['kept']} created={c['created']} updated={c['updated']} "
          f"deleted={c['deleted']} restored={c['restored']} reordered={report['reordered']}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
