"""voice 资源键生成与图行级 audio 绑定（搬运层共享逻辑）。

被 section-voice-publisher / chapter-publisher 与手动流程共用，保证
「wav/ogg 文件名 / manifest.voices 键 / 章 JSON 的 say.voice 字段」三处对齐。

键格式：<char>-<chapter_stem>-<scene_block_id>-<行节点id>
  - chapter_stem = chapter JSON 文件名（去扩展名），如 chapter00_序章
  - scene_block_id = scene 行的块 id（章内唯一，由 chapter-structurer 预分配）；
    行上不冗余存块归属，由挑行时按 produces.order 遍历遇 op=scene 行切块推导
  - 行节点 id = LineAudio 节点雪花 id（行身份，永不复用；台词.jsonl 已停产）
→ scene_block_id 章内唯一 + 节点 id 全局唯一 → 章内全局唯一；stem 保证跨章不冲突。
**稳定寻址**：md 插入/删除/移动行不改变其他行的 key（wav 不成孤儿）。

节级挑行/绑定走图（tasks-from-graph / bind-graph，经 cypher_exec.py）：
拆分对齐进图见 script_splitter.py（section-voice-publisher 第一步）。
与 portrait_key.make_key 同源设计：纯函数无 I/O、Windows 非法字符清洗、三处对齐契约。
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]  # .claude/scripts/
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
CYPHER_EXEC = _SCRIPTS_DIR / "cypher_exec.py"

# 键进入 wav/ogg 文件名（assets/voices/<key>.wav），需清洗 Windows 非法字符
_ILLEGAL = re.compile(r'[\\/:*?"<>|]')


def _sanitize(s) -> str:
    if s is None:
        return ""
    return _ILLEGAL.sub("_", str(s).strip())


def _text_sha1(text: str) -> str:
    """与 script_splitter.text_sha1 同实现（stale 判定依据，不做 normalize）。"""
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
    proc = subprocess.run(
        [sys.executable, str(CYPHER_EXEC), "--stdin", "--multi"],
        input="\n".join(statements), capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"写图失败（退出码 {proc.returncode}）:\n{proc.stderr}")


def make_voice_key(char: str, chapter_stem: str, scene_block_id, node_id) -> str:
    """生成 voice 资源键：<char>-<chapter_stem>-<scene_block_id>-<行节点id>。

    如 陆择-chapter00_序章-s00_酒店-Nv93TkkkgC。末段是 LineAudio 行节点雪花 id
    （行身份，永不复用）。
    """
    parts = [_sanitize(char), _sanitize(chapter_stem), _sanitize(scene_block_id), _sanitize(node_id)]
    return "-".join(parts)


def chapter_stem_from_path(chapter_json_path) -> str:
    """chapter JSON 文件路径 → stem（去目录与 .json）。如 .../chapter00_序章.json → chapter00_序章"""
    return Path(chapter_json_path).stem


def chapter_stem_from_meta(no, title) -> str:
    """Chapter 节点 chapter_no + title → stem（与 chapter-publisher 产出的章 JSON 文件名一致）。

    节级配音（section-voice-publisher）在章 JSON 合并前就要算 key，靠本函数从 Chapter 节点
    字段算出与章级等价的 stem，保证节级/章级 voice key 单一源、不漂移。如 (0, '序章') → 'chapter00_序章'。
    """
    return f"chapter{int(no):02d}_{_sanitize(title)}"


# ── 章级（读合并后章 JSON {meta, scenes}；say.voice 是发布投影 voice_key 的结果，
#    此处三模式服务全章重算/清单推导等搬运场景）──

def iter_say_lines(chapter: dict):
    """遍历 chapter JSON 的所有 say 行，yield (scene_id, line, line_voice_key_or_None)。"""
    for block in chapter.get("scenes", []):
        scene_id = block.get("id", "")
        for line in block.get("lines", []):
            if line.get("op") == "say":
                yield scene_id, line, line.get("voice")


def collect_voice_keys(chapter: dict) -> list:
    """列本章所有 say 的 voice 键（供 chapter_packs_updater --voices）。"""
    return [v for _, _, v in iter_say_lines(chapter) if v]


def build_manifest_voices(chapter: dict, ext: str = "wav") -> dict:
    """推导 manifest.voices 段：{key: f"assets/voices/{key}.{ext}"}。"""
    ext = ext.lstrip(".")
    return {k: f"assets/voices/{k}.{ext}" for k in collect_voice_keys(chapter)}


# ── 节级（图行：LineAudio 按 produces.order；拆分对齐见 script_splitter.py）──

def fetch_section(section_id: str) -> dict:
    """查节产物链 + Chapter（stem）+ 全部行（ORDER BY order）。

    返回 {sc_id, sc_status, script_path, chapter_no, chapter_title, lines:[...]}。
    行含 op/who/text/status 等节点属性 + ord + scene 行的 scene_block_id。
    """
    head = _run_cypher(
        "MATCH (ch:Chapter)-[:has_section]->(:Section {id:'" + section_id + "'})"
        "-[:has_outline]->(:SecOutline)-[:produces]->(sc:SecScript) "
        "RETURN sc.id AS sc_id, sc.status AS sc_status, sc.script_path AS p, "
        "ch.chapter_no AS no, ch.title AS title LIMIT 1"
    )
    if not head:
        raise ValueError(f"Section {section_id} 无产物链（先跑 chapter-dialoguer）")
    lines = _run_cypher(
        "MATCH (:Section {id:'" + section_id + "'})-[:has_outline]->(:SecOutline)"
        "-[:produces]->(sc:SecScript)-[p:produces]->(l:LineAudio) "
        "RETURN l.id AS id, l.op AS op, l.who AS who, l.text AS text, "
        "l.status AS status, l.attempts AS attempts, l.voice_key AS voice_key, "
        "l.text_sha1 AS text_sha1, l.scene_block_id AS scene_block_id, p.order AS ord "
        "ORDER BY p.order"
    )
    out = dict(head[0])
    out["lines"] = lines
    return out


def collect_graph_tasks(lines: list, chapter_stem: str, node_ids=()) -> dict:
    """图行 → 按角色分组的待配任务：{char: [{key, text, scene_id, node_id}]}。

    挑行条件 = say 行 status=0（待配/被驳回；stale 句在拆分对齐时已被置 0）。
    node_ids：行节点 id 白名单（重生成 deeplink 定位被驳回句；缺省不过滤）。
    emotion / tts_text **不预填**——由 section-voice-publisher 的 LLM 逐句判别/变体后
    写入 tasks JSON，publish 缺省回落原文。
    """
    wanted = {s.strip() for s in node_ids if s.strip()}
    tasks = {}
    scene_id = ""
    for l in lines:
        if l.get("op") == "scene":
            scene_id = l.get("scene_block_id") or ""
            continue
        if l.get("op") != "say" or l.get("status") != 0:
            continue
        if wanted and l.get("id") not in wanted:
            continue
        who = l.get("who") or ""
        tasks.setdefault(who, []).append({
            "key": make_voice_key(who, chapter_stem, scene_id, l.get("id", "")),
            "text": l.get("text") or "",
            "scene_id": scene_id,
            "node_id": l.get("id", ""),
        })
    return tasks


def bind_graph(tasks: dict, keys=None) -> dict:
    """把（重）生成结果写回图行节点（经 cypher_exec --stdin --multi 单事务）。

    tasks：{char: [{key, text, node_id, emotion?, tts_text?}]}（publish 的成功集）。
    keys：可选键过滤（只 bind 生成成功的句）。写：voice_key/emotion/tts_text/
    attempts=旧+1/text_sha1=当前台词 sha1/status=10（配完待审）。
    返回 {bound, skipped} 统计。
    """
    key_set = {k.strip() for k in keys if k.strip()} if keys else None
    stmts = []
    bound = skipped = 0
    for char, items in tasks.items():
        for it in items:
            if key_set is not None and it.get("key") not in key_set:
                skipped += 1
                continue
            node_id = it.get("node_id") or ""
            if not node_id:
                skipped += 1
                continue
            stmts.append(
                f"MATCH (l:LineAudio {{id:{_q(node_id)}}}) "
                f"SET l.voice_key={_q(it.get('key'))}, "
                f"l.emotion={_q(it.get('emotion'))}, "
                f"l.tts_text={_q(it.get('tts_text'))}, "
                f"l.attempts=coalesce(l.attempts,0)+1, "
                f"l.text_sha1={_q(_text_sha1(it.get('text') or ''))}, "
                f"l.status=10;"
            )
            bound += 1
    if stmts:
        _run_cypher_multi(stmts)
    return {"bound": bound, "skipped": skipped}


def sync_runtime(master_dir, runtime_dir, ext: str = "wav"):
    """把 15_声音/<char>/<key>.wav 母带同步拷贝到 99_game/assets/voices/<key>.wav（扁平）。

    幂等：按 mtime+size 跳过未变文件。只拷 *.wav（.import 等 Godot 产物忽略）。
    返回 {copied, skipped, missing_master} 统计。
    """
    import shutil
    master, runtime = Path(master_dir), Path(runtime_dir)
    runtime.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    for wav in sorted(master.glob(f"*/*.{ext}")):
        dst = runtime / wav.name
        if dst.exists() and dst.stat().st_mtime == wav.stat().st_mtime and dst.stat().st_size == wav.stat().st_size:
            skipped += 1
            continue
        shutil.copy2(wav, dst)
        copied += 1
    return {"copied": copied, "skipped": skipped}


def _load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save_json(p, data):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _write_tasks(tasks, out):
    data = json.dumps(tasks, ensure_ascii=False, indent=2)
    if not out or out == "-":
        print(data)
    else:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(data, encoding="utf-8")
    return sum(len(v) for v in tasks.values())


# ── CLI（3 章级 + 2 节级图版 + 1 同步）──

def _cmd_manifest(args):
    path = Path(args.chapter_json)
    chapter = _load_json(path)
    voices = build_manifest_voices(chapter, ext=args.ext)
    manifest_path = Path(args.manifest) if args.manifest else path.parent.parent / "manifest.json"
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    manifest.setdefault("voices", {}).update(voices)
    _save_json(manifest_path, manifest)
    print(f"[manifest] wrote {len(voices)} voices -> {manifest_path} (ext={args.ext})")


def _cmd_list(args):
    chapter = _load_json(args.chapter_json)
    keys = collect_voice_keys(chapter)
    print(",".join(keys))  # CSV，供 chapter_packs_updater --voices


def _cmd_tasks_from_graph(args):
    """图行（say 且 status=0）→ 按角色分组任务 JSON（节级配音；emotion/tts_text 留给 skill）。"""
    info = fetch_section(args.section)
    if info["sc_status"] != 11:
        raise ValueError(f"SecScript.status={info['sc_status']}（须 11 定稿已批；先拆分对齐见 script_splitter）")
    stem = chapter_stem_from_meta(info["no"], info["title"])
    node_ids = tuple(s.strip() for s in args.nodes.split(",")) if args.nodes else ()
    tasks = collect_graph_tasks(info["lines"], stem, node_ids=node_ids)
    n_lines = _write_tasks(tasks, args.out)
    print(f"[tasks-from-graph] stem={stem} {n_lines} lines / {len(tasks)} chars"
          + (f" nodes={args.nodes}" if args.nodes else "") + f" -> {args.out or 'stdout'}")


def _cmd_bind_graph(args):
    """把生成结果（含判别 emotion + tts_text 变体）写回图行节点（status=10 待审）。"""
    tasks = _load_json(args.tasks)
    keys = [s.strip() for s in args.keys.split(",")] if args.keys else None
    stats = bind_graph(tasks, keys)
    print(f"[bind-graph] bound={stats['bound']} skipped={stats['skipped']} -> LineAudio")


def _cmd_sync(args):
    stats = sync_runtime(args.master, args.runtime, ext=args.ext)
    print(f"[sync] copied={stats['copied']} skipped={stats['skipped']} -> {args.runtime}")


def main():
    ap = argparse.ArgumentParser(description="voice 资源键生成与图行级 audio 绑定（三处对齐）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_man = sub.add_parser("manifest", help="推导 manifest.voices 段并合并写入 manifest.json（读章 JSON）")
    p_man.add_argument("chapter_json")
    p_man.add_argument("--ext", default="wav", choices=["wav", "ogg"])
    p_man.add_argument("--manifest", help="manifest.json 路径（默认 chapter 同级 ../manifest.json）")
    p_man.set_defaults(func=_cmd_manifest)

    p_list = sub.add_parser("list", help="列本章 voice 键（CSV，供 chapter_packs_updater --voices）")
    p_list.add_argument("chapter_json")
    p_list.set_defaults(func=_cmd_list)

    p_tfg = sub.add_parser("tasks-from-graph", help="图行（say 且 status=0）→ 按角色分组任务 JSON（节级配音，供 voice_clone_runner publish）")
    p_tfg.add_argument("--section", required=True, help="Section 节点 ID（snowflake）")
    p_tfg.add_argument("--nodes", default=None, help="行节点 id 白名单（逗号分隔，重生成被驳回句用；缺省不过滤）")
    p_tfg.add_argument("-o", "--out", help="输出 JSON 路径（缺省打印到 stdout）")
    p_tfg.set_defaults(func=_cmd_tasks_from_graph)

    p_bg = sub.add_parser("bind-graph", help="把生成结果（含 emotion + tts_text 变体）写回图行节点（status=10 待审）")
    p_bg.add_argument("--tasks", required=True, help="tasks JSON 路径（tasks-from-graph 产出 + skill 已填 emotion/tts_text）")
    p_bg.add_argument("--keys", default=None, help="只 bind 指定 key（逗号分隔，publish 失败句排除用；缺省=全部）")
    p_bg.set_defaults(func=_cmd_bind_graph)

    p_sync = sub.add_parser("sync", help="把 15_声音/<char>/<key>.wav 母带同步拷贝到 99_game/assets/voices/（运行时副本，manifest 键不变）")
    p_sync.add_argument("--master", default="15_声音", help="母带根目录（<master>/<char>/<key>.wav）")
    p_sync.add_argument("--runtime", default="99_game/assets/voices", help="运行时目录（扁平 <key>.wav）")
    p_sync.add_argument("--ext", default="wav", choices=["wav", "ogg"])
    p_sync.set_defaults(func=_cmd_sync)

    args = ap.parse_args()
    try:
        args.func(args)
    except (ValueError, RuntimeError) as e:
        sys.stderr.write(f"失败: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
