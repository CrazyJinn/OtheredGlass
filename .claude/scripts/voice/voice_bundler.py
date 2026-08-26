"""voice 资源键生成与 chapter JSON 绑定（搬运层共享逻辑）。

被 section-voice-publisher / chapter-publisher 与手动流程共用，保证
「wav/ogg 文件名 / manifest.voices 键 / chapter JSON 的 say.voice 字段」三处对齐。

键格式：<char>-<chapter_stem>-<scene_id>-<line_id>
  - chapter_stem = chapter JSON 文件名（去扩展名），如 chapter00_序章
  - scene_id = scene 分隔行的 id（章内唯一，由 chapter-structurer 预分配）
  - line_id = 台词行 id（L<NNNN>，节内递增永不复用，水位在台词.jsonl 的 meta.line_seq）
→ scene_id 章内唯一 + line_id 节内唯一 → 章内全局唯一；stem 保证跨章不冲突。
**稳定寻址**：插入/删除/移动行不改变其他行的 key（替代旧 line_idx 位置寻址的漂移痛点）。

与 portrait_key.make_key 同源设计：纯函数无 I/O、Windows 非法字符清洗、三处对齐契约。
节级读写台词 JSONL 一律经 jsonl_script（.claude/scripts/jsonl_script.py，本项目唯一实现）。
"""
import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]  # .claude/scripts/
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jsonl_script  # noqa: E402

# 键进入 wav/ogg 文件名（assets/voices/<key>.wav），需清洗 Windows 非法字符
_ILLEGAL = re.compile(r'[\\/:*?"<>|]')


def _sanitize(s) -> str:
    if s is None:
        return ""
    return _ILLEGAL.sub("_", str(s).strip())


def make_voice_key(char: str, chapter_stem: str, scene_id, line_id) -> str:
    """生成 voice 资源键：<char>-<chapter_stem>-<scene_id>-<line_id>。

    如 陆择-chapter00_序章-s00_酒店-L0002。line_id 是台词行稳定 id（非数组下标）。
    """
    parts = [_sanitize(char), _sanitize(chapter_stem), _sanitize(scene_id), _sanitize(line_id)]
    return "-".join(parts)


def chapter_stem_from_path(chapter_json_path) -> str:
    """chapter JSON 文件路径 → stem（去目录与 .json）。如 .../chapter00_序章.json → chapter00_序章"""
    return Path(chapter_json_path).stem


def chapter_stem_from_meta(no, title) -> str:
    """Chapter 节点 chapter_no + title → stem（与 chapter-publisher 产出的章 JSON 文件名一致）。

    节级配音（section-voice-publisher）在章 JSON 合并前就要算 key，靠本函数从 Chapter 节点
    字段算出与章级等价的 stem，保证节级/章级 voice key 单一源、不漂移。如 (0, '序章') → 'chapter00_序章'。
    chapter-publisher 算 stem 也应改调本函数。
    """
    return f"chapter{int(no):02d}_{_sanitize(title)}"


# ── 章级（读合并后章 JSON {meta, scenes}；voice 键已由节级 bind-audio 落进台词 JSONL，
#    章 JSON 的 say.voice 是 jsonl_script.project 投影 audio.key 的结果，此处四模式服务
#    全章重算/清单推导等搬运场景）──

def iter_say_lines(chapter: dict):
    """遍历 chapter JSON 的所有 say 行，yield (scene_id, line, line_voice_key_or_None)。"""
    for block in chapter.get("scenes", []):
        scene_id = block.get("id", "")
        for line in block.get("lines", []):
            if line.get("op") == "say":
                yield scene_id, line, line.get("voice")


def collect_voice_keys(chapter: dict) -> list:
    """列本章所有 say 的 voice 键（供 chapter_packs_updater --voices）。

    章内 say.voice 由投影带入；缺失（未配音行）跳过。
    """
    return [v for _, _, v in iter_say_lines(chapter) if v]


def build_manifest_voices(chapter: dict, ext: str = "wav") -> dict:
    """推导 manifest.voices 段：{key: f"assets/voices/{key}.{ext}"}。"""
    ext = ext.lstrip(".")
    return {k: f"assets/voices/{k}.{ext}" for k in collect_voice_keys(chapter)}


# ── 节级（读台词 JSONL，经 jsonl_script）──

def collect_section_tasks(rows, chapter_stem: str, only=(), line_ids=()) -> dict:
    """台词 JSONL rows → 按角色分组的待配任务：{char: [{key, text, scene_id, line_id}]}。

    only：行状态过滤（jsonl_script.needs_regen 的 reason 集合，如 missing,rejected,stale；
    缺省 = 全部 say 行）。line_ids：行 id 白名单（缺省不过滤）。
    emotion **不预填**——由 section-voice-publisher 的 LLM 逐句判别后写入 tasks JSON，
    cosyvoice_runner 缺省兜底 '平静'。
    """
    wanted = {s.strip() for s in line_ids if s.strip()}
    tasks = {}
    for scene_id, r in jsonl_script.iter_say_rows(rows):
        if wanted and r.get("id") not in wanted:
            continue
        if only and jsonl_script.line_state(r) not in only:
            continue
        who = r.get("who", "")
        tasks.setdefault(who, []).append({
            "key": make_voice_key(who, chapter_stem, scene_id, r.get("id", "")),
            "text": r.get("text", ""),
            "scene_id": scene_id,
            "line_id": r.get("id", ""),
        })
    return tasks


def bind_audio(path, tasks: dict, keys=None) -> dict:
    """把（重）生成结果写回台词 JSONL 的 say 行 audio（经 jsonl_script.save，保行字节稳定）。

    tasks：{char: [{key, text, scene_id, line_id, emotion?}]}（cosyvoice publish 的成功集）。
    keys：可选键过滤（只 bind 生成成功的句）。写：key/emotion/status='pending'/
    attempts=旧+1（缺省 1）/text_sha1=当前台词。返回 {bound, skipped} 统计。
    """
    rows = jsonl_script.load(path)
    key_set = {k.strip() for k in keys if k.strip()} if keys else None
    bound = skipped = 0
    for char, items in tasks.items():
        for it in items:
            if key_set is not None and it.get("key") not in key_set:
                skipped += 1
                continue
            row = jsonl_script.find_row(rows, it.get("line_id", ""))
            if row is None:
                skipped += 1
                continue
            old = row.get("audio") or {}
            jsonl_script.set_audio(
                rows, it["line_id"],
                key=it["key"], emotion=it.get("emotion"), status="pending",
                attempts=int(old.get("attempts", 0)) + 1, resha1=True,
            )
            bound += 1
    jsonl_script.save(path, rows)
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
        n_lines = sum(len(v) for v in tasks.values())
        return n_lines
    return sum(len(v) for v in tasks.values())


# ── CLI（4 章级 + 2 节级 + 1 同步）──

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


def _cmd_tasks_from_section(args):
    """台词 JSONL → 按角色分组任务 JSON（节级配音；只挑待配行，emotion 留给 skill 判别）。"""
    stem = chapter_stem_from_meta(args.chapter_no, args.chapter_title)
    rows = jsonl_script.load(args.sec_jsonl)
    only = tuple(s.strip() for s in args.only.split(",") if s.strip()) if args.only else ()
    line_ids = tuple(s.strip() for s in args.lines.split(",")) if args.lines else ()
    tasks = collect_section_tasks(rows, stem, only=only, line_ids=line_ids)
    n_lines = _write_tasks(tasks, args.out)
    print(f"[tasks-from-section] stem={stem} {n_lines} lines / {len(tasks)} chars"
          + (f" only={args.only}" if args.only else "") + f" -> {args.out or 'stdout'}")


def _cmd_bind_audio(args):
    """把生成结果（含判别 emotion）写回台词 JSONL say 行的 audio（pending 待审）。"""
    tasks = _load_json(args.tasks)
    keys = [s.strip() for s in args.keys.split(",")] if args.keys else None
    stats = bind_audio(args.sec_jsonl, tasks, keys)
    print(f"[bind-audio] bound={stats['bound']} skipped={stats['skipped']} -> {args.sec_jsonl}")


def _cmd_sync(args):
    stats = sync_runtime(args.master, args.runtime, ext=args.ext)
    print(f"[sync] copied={stats['copied']} skipped={stats['skipped']} -> {args.runtime}")


def main():
    ap = argparse.ArgumentParser(description="voice 资源键生成与 chapter JSON 绑定（三处对齐）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_man = sub.add_parser("manifest", help="推导 manifest.voices 段并合并写入 manifest.json（读章 JSON）")
    p_man.add_argument("chapter_json")
    p_man.add_argument("--ext", default="wav", choices=["wav", "ogg"])
    p_man.add_argument("--manifest", help="manifest.json 路径（默认 chapter 同级 ../manifest.json）")
    p_man.set_defaults(func=_cmd_manifest)

    p_list = sub.add_parser("list", help="列本章 voice 键（CSV，供 chapter_packs_updater --voices）")
    p_list.add_argument("chapter_json")
    p_list.set_defaults(func=_cmd_list)

    p_tfs = sub.add_parser("tasks-from-section", help="台词 JSONL → 按角色分组任务 JSON（节级配音，供 cosyvoice_runner publish；只挑待配行）")
    p_tfs.add_argument("sec_jsonl", help="台词 JSONL 路径（SecScript.script_path）")
    p_tfs.add_argument("--chapter-no", type=int, required=True, help="Chapter.chapter_no")
    p_tfs.add_argument("--chapter-title", required=True, help="Chapter.title")
    p_tfs.add_argument("--only", default=None,
                       help="行状态过滤（逗号分隔：missing,rejected,stale；缺省=全部 say 行）")
    p_tfs.add_argument("--lines", default=None, help="行 id 白名单（逗号分隔，缺省不过滤）")
    p_tfs.add_argument("-o", "--out", help="输出 JSON 路径（缺省打印到 stdout）")
    p_tfs.set_defaults(func=_cmd_tasks_from_section)

    p_ba = sub.add_parser("bind-audio", help="把生成结果（含判别 emotion）写回台词 JSONL say 行 audio（pending 待审）")
    p_ba.add_argument("sec_jsonl", help="台词 JSONL 路径（SecScript.script_path）")
    p_ba.add_argument("--tasks", required=True, help="tasks JSON 路径（tasks-from-section 产出 + skill 已填 emotion）")
    p_ba.add_argument("--keys", default=None, help="只 bind 指定 key（逗号分隔，cosyvoice 失败句排除用；缺省=全部）")
    p_ba.set_defaults(func=_cmd_bind_audio)

    p_sync = sub.add_parser("sync", help="把 15_声音/<char>/<key>.wav 母带同步拷贝到 99_game/assets/voices/（运行时副本，manifest 键不变）")
    p_sync.add_argument("--master", default="15_声音", help="母带根目录（<master>/<char>/<key>.wav）")
    p_sync.add_argument("--runtime", default="99_game/assets/voices", help="运行时目录（扁平 <key>.wav）")
    p_sync.add_argument("--ext", default="wav", choices=["wav", "ogg"])
    p_sync.set_defaults(func=_cmd_sync)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
