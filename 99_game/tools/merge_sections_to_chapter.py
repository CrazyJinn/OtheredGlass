"""从图投影全章各节台词行（LineAudio），合并拍平为单一章运行时 JSON。

chapter-publisher 在全章各节产物就绪时调用：图（SecScript-produces{order}->LineAudio 逐句行）
→ 1 个章级 JSON。台词.jsonl 已停产，图是唯一结构化真相。

- 图查询：Chapter→has_section→Section(按 section_no)→has_outline→SecOutline→produces→SecScript
  -[p:produces]->LineAudio（ORDER BY p.order）+ scene 行 stages→Scene（取 time_of_day）。
- 投影：graph_lines_to_doc 图行 → {meta, scenes}（requires 从行推导；voice_key→voice）。
- meta：chapter/title 取 Chapter 节点；requires = 各节并集（保序去重）。
- scenes：按节序拼接各 scene-block（scene_block_id 由 structurer 预分配、章内唯一，纯 concat）。
- portrait 整键改写：--chapter-map 的 portraits 段（generate_portrait_map.py 查图产）。
- BGM 注入：--chapter-map 的 bgm 段（Scene-has_bgm->BgmTrack，status=2 才进 map）写入 scene-block.bgm。
- 合并后校验 scene-block id 章内唯一（防御性）。

前置校验：各节 SecOutline=1 ∧ SecScript=11 ∧ 该节全部行 LineAudio=11（不满足报缺口并退出）。
choice/jump 行暂不进图（建模后续设计），投影自然不含分支跳转行。
不做 schema 校验（校验由 validate_chapter.py 负责，保持工具正交）。
退码：0 成功 / 1 查图/校验/IO 失败 / 2 参数错。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "scripts"  # 项目根/.claude/scripts
CYPHER_EXEC = _SCRIPTS_DIR / "cypher_exec.py"


def _run_cypher(cypher: str) -> list:
    """调 cypher_exec.py --json，提取返回的 JSON 数组（与 generate_portrait_map 同款）。"""
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


def graph_lines_to_doc(lines: list, chapter_no, sec_title: str) -> dict:
    """一节的图行（按 ord 升序）→ 投影 doc {meta, scenes}（与运行时章 JSON 同构）。

    行 dict 形状（fetch_chapter 查询返回）：op/who/portrait/pos/text/kind/scene_block_id/
    voice_key/scene_name/scene_time/line_status。requires 从行推导（distinct who/scene/portrait 保序）。
    label 行 text → name；ending 行 text → title；say 行 voice_key → voice。
    """
    chars, scenes_seq, portraits = [], [], []
    def _keep(seq, v):
        if v and v not in seq:
            seq.append(v)

    scenes, cur = [], None
    for l in lines:
        op = l.get("op")
        if op == "scene":
            cur = {"id": l.get("scene_block_id") or "", "scene": l.get("scene_name") or ""}
            if l.get("scene_time"):
                cur["time"] = l["scene_time"]
            scenes.append(cur)
            _keep(scenes_seq, cur["scene"])
        elif cur is None:
            continue  # 图行来自拆分器（scene 行保证在首），防御跳过
        elif op == "say":
            say = {"op": "say", "who": l.get("who") or "",
                   "portrait": l.get("portrait") or "",
                   "pos": l.get("pos") or "left", "text": l.get("text") or ""}
            if l.get("voice_key"):
                say["voice"] = l["voice_key"]
            cur.setdefault("lines", []).append(say)
            _keep(chars, l.get("who"))
            _keep(portraits, l.get("portrait"))
        elif op == "narrate":
            cur.setdefault("lines", []).append({"op": "narrate", "text": l.get("text") or ""})
        elif op == "label":
            cur.setdefault("lines", []).append({"op": "label", "name": l.get("text") or ""})
        elif op == "ending":
            end = {"op": "ending", "kind": l.get("kind") or "NE"}
            if l.get("text"):
                end["title"] = l["text"]
            cur.setdefault("lines", []).append(end)

    meta = {"chapter": chapter_no, "title": sec_title,
            "requires": {"characters": chars, "scenes": scenes_seq, "portraits": portraits}}
    return {"meta": meta, "scenes": scenes}


def fetch_chapter(chapter_id: str) -> dict:
    """查全章图 → {chapter_no, title, sections: [投影doc 按节序]}；前置不满足 raise ValueError。

    前置：每节 SecOutline=1 ∧ SecScript=11 ∧ 该节全部行 LineAudio=11。
    """
    rows = _run_cypher(
        "MATCH (ch:Chapter {id:'" + chapter_id + "'})-[:has_section]->(sec:Section) "
        "OPTIONAL MATCH (sec)-[:has_outline]->(ol:SecOutline) "
        "OPTIONAL MATCH (ol)-[:produces]->(sc:SecScript) "
        "OPTIONAL MATCH (sc)-[p:produces]->(l:LineAudio) "
        "OPTIONAL MATCH (l)-[:stages]->(s:Scene) "
        "RETURN ch.chapter_no AS no, ch.title AS title, sec.section_no AS section_no, "
        "sec.title AS sec_title, ol.status AS ol_status, sc.status AS sc_status, "
        "l.id AS lid, l.op AS op, l.who AS who, l.portrait AS portrait, l.pos AS pos, "
        "l.text AS text, l.kind AS kind, l.scene_block_id AS scene_block_id, "
        "l.voice_key AS voice_key, l.status AS line_status, p.order AS ord, "
        "s.name AS scene_name, s.time_of_day AS scene_time "
        "ORDER BY sec.section_no, p.order"
    )
    if not rows:
        raise ValueError(f"Chapter {chapter_id} 不存在或无 Section")
    chapter_no, chapter_title = rows[0]["no"], rows[0]["title"]

    by_sec = {}
    for r in rows:
        key = (r["section_no"], r["sec_title"], r["ol_status"], r["sc_status"])
        by_sec.setdefault(key, []).append(r)

    problems, sections = [], []
    for (section_no, sec_title, ol_status, sc_status), sec_rows in sorted(by_sec.items()):
        sec_tag = f"sec{int(section_no):02d}（{sec_title}）"
        if ol_status != 1:
            problems.append(f"{sec_tag}：SecOutline.status={ol_status}（须 1）")
        if sc_status != 11:
            problems.append(f"{sec_tag}：SecScript.status={sc_status}（须 11）")
            continue
        line_rows = [r for r in sec_rows if r.get("lid")]
        if not line_rows:
            problems.append(f"{sec_tag}：无 LineAudio 行（先跑 section-voice-publisher 拆分进图）")
            continue
        not_done = [r for r in line_rows if r.get("line_status") != 11]
        if not_done:
            problems.append(f"{sec_tag}：{len(not_done)} 行 LineAudio.status≠11"
                            f"（逐句音频审未完成，如 {not_done[0].get('text') or not_done[0].get('scene_block_id')!r}）")
            continue
        sections.append(graph_lines_to_doc(line_rows, chapter_no, sec_title))
    if problems:
        raise ValueError("全章产物未就绪：\n  " + "\n  ".join(problems))
    return {"chapter_no": chapter_no, "title": chapter_title, "sections": sections}


def _union(*lists):
    """保序去重并集（None 安全：缺省子字段视作空）。"""
    out = []
    seen = set()
    for lst in lists:
        for x in (lst or []):
            if x not in seen:
                seen.add(x)
                out.append(x)
    return out


_PORTRAIT_OPS = ("say",)  # 立绘随 say 槽位自动出场


def _rewrite_portraits(scenes, pmap):
    """按 scene-block 的 scene 字段查 pmap，把 say.portrait 从纯变体改写为整键。

    pmap = {scene_name: {char: {variant: 整键}}}（generate_portrait_map.py 产出的 portraits 段）。
    着装是 Scene 属性，同 scene_name 的所有 block 共享同一组绑定。
    """
    for blk in scenes:
        char_map = pmap.get(blk.get("scene"))
        if not char_map:
            continue
        for line in blk.get("lines", []) or []:
            if line.get("op") in _PORTRAIT_OPS:
                new = char_map.get(line.get("who"), {}).get(line.get("portrait"))
                if new is not None:
                    line["portrait"] = new


def _derive_portraits_from_lines(scenes):
    """从改写后的全章 say.portrait 字段保序去重收集（整键集合）。

    带 chapter-map 时 requires.portraits 用此重推导，保证与 lines 内引用一致。
    """
    out, seen = [], set()
    for blk in scenes:
        for line in blk.get("lines", []) or []:
            if line.get("op") in _PORTRAIT_OPS:
                p = line.get("portrait")
                if p and p not in seen:
                    seen.add(p)
                    out.append(p)
    return out


def _inject_bgm(scenes, bgm_map):
    """把 bgm_map（{scene_name: {track, mode, loop}}）写入对应 scene-block 的 bgm 字段。

    map 由 generate_portrait_map.py 查图产出（仅 status=2 的 BgmTrack 进 map，
    未就绪的上游已打警告）。mode/loop 在 map 侧已填默认（play/true），此处原样写入。
    """
    for blk in scenes:
        info = bgm_map.get(blk.get("scene"))
        if not info or not info.get("track"):
            continue
        blk["bgm"] = {"track": info["track"], "mode": info.get("mode", "play"), "loop": info.get("loop", True)}


def merge(sections, chapter, title, chapter_map=None):
    """合并各节投影 doc（按节序，fetch_chapter.sections 或手工构造）→ {meta, scenes}。

    chapter_map 非 None 时（generate_portrait_map.py 产出，{"portraits":…, "bgm":…}）：
    合并后按 scene 改写 say.portrait 为 guid 整键、注入 scene-block.bgm，
    requires.portraits 从改写后的 lines 重推导。为 None 时两者均不处理。
    """
    # requires 并集（characters/scenes/portraits）
    reqs = [(s.get("meta", {}) or {}).get("requires", {}) or {} for s in sections]
    requires = {
        "characters": _union(*[r.get("characters") for r in reqs]),
        "scenes": _union(*[r.get("scenes") for r in reqs]),
        "portraits": _union(*[r.get("portraits") for r in reqs]),
    }

    # scenes 按节序拼接 + id 章内唯一性校验
    scenes = []
    seen_ids = set()
    for s in sections:
        for blk in s.get("scenes", []) or []:
            bid = blk.get("id")
            if bid in seen_ids:
                raise ValueError(
                    f"scene-block id 重复（非章内唯一）：{bid!r}——structurer 应在分节规划时预分配唯一 id"
                )
            seen_ids.add(bid)
            scenes.append(blk)

    # 演出注入（portrait 整键改写 + BGM）
    if chapter_map:
        pmap = chapter_map.get("portraits") or {}
        bgm_map = chapter_map.get("bgm") or {}
        if pmap:
            _rewrite_portraits(scenes, pmap)
            requires["portraits"] = _derive_portraits_from_lines(scenes)
        if bgm_map:
            _inject_bgm(scenes, bgm_map)

    return {"meta": {"chapter": chapter, "title": title, "requires": requires}, "scenes": scenes}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="从图投影全章台词行合并为章运行时 JSON（图→1 拍平，演出由图注入）")
    p.add_argument("--chapter", required=True, help="Chapter 节点 ID（snowflake）")
    p.add_argument("-o", "--out", required=True, help="输出章 JSON 路径")
    p.add_argument("--chapter-map", default=None,
                   help="章映射 JSON 路径（generate_portrait_map.py 产出，含 portraits/bgm 两段）；"
                        "传入则改写 say.portrait 为 guid 整键并注入 scene-block.bgm")
    args = p.parse_args(argv)

    chapter_map = None
    if args.chapter_map:
        try:
            chapter_map = json.loads(Path(args.chapter_map).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            sys.stderr.write(f"读取 chapter-map 失败: {e}\n")
            return 1

    try:
        info = fetch_chapter(args.chapter)
        doc = merge(info["sections"], info["chapter_no"], info["title"], chapter_map)
    except (RuntimeError, ValueError) as e:
        sys.stderr.write(f"合并失败: {e}\n")
        return 1
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"OK: {len(info['sections'])} 节合并 -> {args.out}（{len(doc['scenes'])} 场景段）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
