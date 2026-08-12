"""voice 资源键生成与 chapter JSON 绑定（搬运层共享逻辑）。

被 voice-publisher skill 与手动流程共用，保证
「wav/ogg 文件名 / manifest.voices 键 / chapter JSON 的 say.voice 字段」三处对齐。

键格式：<char>-<chapter_stem>-<scene_id>-<line_idx>
  - chapter_stem = chapter JSON 文件名（去扩展名），如 chapter00_序章
  - scene_id = scene block 的 id（章内唯一，由 chapter-structurer 预分配）
  - line_idx = 该 say 在其 scene block 的 lines 数组下标
  → scene_id 章内唯一 + line_idx 段内唯一 → 章内全局唯一；stem 保证跨章不冲突。

与 portrait_key.make_key 同源设计：纯函数无 I/O、Windows 非法字符清洗、三处对齐契约。
"""
import argparse
import json
import re
from pathlib import Path

# 键进入 wav/ogg 文件名（assets/voices/<key>.wav），需清洗 Windows 非法字符
_ILLEGAL = re.compile(r'[\\/:*?"<>|]')


def _sanitize(s) -> str:
    if s is None:
        return ""
    return _ILLEGAL.sub("_", str(s).strip())


def make_voice_key(char: str, chapter_stem: str, scene_id, line_idx: int) -> str:
    """生成 voice 资源键：<char>-<chapter_stem>-<scene_id>-<line_idx>。

    如 陆择-chapter00_序章-酒店-2
    """
    parts = [_sanitize(char), _sanitize(chapter_stem), _sanitize(scene_id), str(line_idx)]
    return "-".join(parts)


def chapter_stem_from_path(chapter_json_path) -> str:
    """chapter JSON 文件路径 → stem（去目录与 .json）。如 .../chapter00_序章.json → chapter00_序章"""
    return Path(chapter_json_path).stem


def iter_say_lines(chapter: dict):
    """遍历 chapter JSON 的所有 say 行，yield (scene_id, line_idx, line_dict)。"""
    for block in chapter.get("scenes", []):
        scene_id = block.get("id", "")
        for idx, line in enumerate(block.get("lines", [])):
            if line.get("op") == "say":
                yield scene_id, idx, line


def inject_voices(chapter: dict, chapter_stem: str, dry_run: bool = False) -> dict:
    """给 chapter 每个 say 注入 voice 字段（幂等：已有则按当前 line_idx 重算覆盖）。

    返回统计 {total_say, changed, keys}。
    """
    stats = {"total_say": 0, "changed": 0, "keys": []}
    for scene_id, idx, line in iter_say_lines(chapter):
        stats["total_say"] += 1
        who = line.get("who", "")
        key = make_voice_key(who, chapter_stem, scene_id, idx)
        if line.get("voice") != key:
            stats["changed"] += 1
            if not dry_run:
                line["voice"] = key
        stats["keys"].append(key)
    return stats


def collect_voice_keys(chapter: dict, chapter_stem: str) -> list:
    """列本章所有 say 的 voice 键（供 chapter_packs_updater --voices）。"""
    keys = []
    for scene_id, idx, line in iter_say_lines(chapter):
        who = line.get("who", "")
        keys.append(make_voice_key(who, chapter_stem, scene_id, idx))
    return keys


def collect_tasks(chapter: dict, chapter_stem: str) -> dict:
    """按角色分组：{char: [{key, text, scene_id, line_idx}, ...]}，供 voice_clone_runner 消费。"""
    tasks = {}
    for scene_id, idx, line in iter_say_lines(chapter):
        who = line.get("who", "")
        key = make_voice_key(who, chapter_stem, scene_id, idx)
        tasks.setdefault(who, []).append({
            "key": key, "text": line.get("text", ""), "scene_id": scene_id, "line_idx": idx,
            "emotion": line.get("emotion", "平静"),
        })
    return tasks


def build_manifest_voices(chapter: dict, chapter_stem: str, ext: str = "wav") -> dict:
    """推导 manifest.voices 段：{key: f"assets/voices/{key}.{ext}"}。"""
    ext = ext.lstrip(".")
    return {k: f"assets/voices/{k}.{ext}" for k in collect_voice_keys(chapter, chapter_stem)}


def _load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save_json(p, data):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── CLI 四模式 ──

def _cmd_inject(args):
    path = Path(args.chapter_json)
    stem = chapter_stem_from_path(path)
    chapter = _load_json(path)
    stats = inject_voices(chapter, stem, dry_run=args.dry_run)
    if not args.dry_run:
        _save_json(path, chapter)
    verb = "would-change" if args.dry_run else "changed"
    print(f"[inject] stem={stem} say={stats['total_say']} {verb}={stats['changed']}")
    if args.verbose:
        for k in stats["keys"]:
            print("  ", k)


def _cmd_manifest(args):
    path = Path(args.chapter_json)
    stem = chapter_stem_from_path(path)
    chapter = _load_json(path)
    voices = build_manifest_voices(chapter, stem, ext=args.ext)
    manifest_path = Path(args.manifest) if args.manifest else path.parent.parent / "manifest.json"
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    manifest.setdefault("voices", {}).update(voices)
    _save_json(manifest_path, manifest)
    print(f"[manifest] wrote {len(voices)} voices -> {manifest_path} (ext={args.ext})")


def _cmd_list(args):
    path = Path(args.chapter_json)
    stem = chapter_stem_from_path(path)
    chapter = _load_json(path)
    keys = collect_voice_keys(chapter, stem)
    print(",".join(keys))  # CSV，供 chapter_packs_updater --voices


def _cmd_tasks(args):
    path = Path(args.chapter_json)
    stem = chapter_stem_from_path(path)
    chapter = _load_json(path)
    tasks = collect_tasks(chapter, stem)
    data = json.dumps(tasks, ensure_ascii=False, indent=2)
    if not args.out or args.out == "-":
        print(data)
    else:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(data, encoding="utf-8")
        n_lines = sum(len(v) for v in tasks.values())
        print(f"[tasks] {n_lines} lines / {len(tasks)} chars -> {args.out}")


def main():
    ap = argparse.ArgumentParser(description="voice 资源键生成与 chapter JSON 绑定（三处对齐）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_inject = sub.add_parser("inject", help="给 chapter JSON 每个 say 注入 voice 字段（幂等）")
    p_inject.add_argument("chapter_json")
    p_inject.add_argument("--dry-run", action="store_true")
    p_inject.add_argument("-v", "--verbose", action="store_true")
    p_inject.set_defaults(func=_cmd_inject)

    p_man = sub.add_parser("manifest", help="推导 manifest.voices 段并合并写入 manifest.json")
    p_man.add_argument("chapter_json")
    p_man.add_argument("--ext", default="wav", choices=["wav", "ogg"])
    p_man.add_argument("--manifest", help="manifest.json 路径（默认 chapter 同级 ../manifest.json）")
    p_man.set_defaults(func=_cmd_manifest)

    p_list = sub.add_parser("list", help="列本章 voice 键（CSV，供 chapter_packs_updater --voices）")
    p_list.add_argument("chapter_json")
    p_list.set_defaults(func=_cmd_list)

    p_tasks = sub.add_parser("tasks", help="输出按角色分组的任务清单 JSON（供 voice_clone_runner publish）")
    p_tasks.add_argument("chapter_json")
    p_tasks.add_argument("-o", "--out", help="输出 JSON 路径（缺省打印到 stdout）")
    p_tasks.set_defaults(func=_cmd_tasks)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
