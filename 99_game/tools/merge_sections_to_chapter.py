"""把全章各节定稿 YAML 合并拍平为单一章运行时 JSON。

chapter-publisher 在全章各 Section.status==31 时调用：N 个节级 YAML → 1 个章级 JSON。
- meta：chapter/title 取 CLI 参数；requires = 各节 meta.requires 的 characters/scenes/portraits 并集（保序去重）。
- scenes：按节传入顺序拼接各节 scenes[]（scene-block id 由 structurer 预分配、章内唯一，纯 concat 不改写）。
- 合并后校验 scene-block id 章内唯一（防御性，重复则报错）。

与 yaml_to_chapter_json.py 正交（那是 1:1 转换，本工具是 N:1 合并）。不做 schema 校验
（校验由 validate_chapter.py 负责，保持工具正交）。
退码：0 成功 / 1 解析或 IO 或 id 冲突失败 / 2 参数错（与 yaml_to_chapter_json.py 对齐）。
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("缺少依赖：pip install -r tools/requirements.txt (PyYAML)\n")
    raise


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


_PORTRAIT_OPS = ("say", "show")


def _rewrite_portraits(scenes, pmap):
    """按 scene-block 的 scene 字段查 pmap，把 say/show.portrait 从纯变体改写为整键。

    pmap = {scene_name: {char: {variant: 整键}}}（generate_portrait_map.py 产出）。
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
    """从改写后的全章 say/show.portrait 字段保序去重收集（整键集合）。

    带 portrait-map 时 requires.portraits 用此重推导，保证与 lines 内引用一致。
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


def merge(section_paths, chapter, title, portrait_map=None):
    """读入各节定稿 YAML（按 section_no 顺序），返回合并后的 {meta, scenes} dict。

    portrait_map 非 None 时：合并后按 scene 改写 say/show.portrait 为 guid 整键，
    requires.portraits 从改写后的 lines 重推导（不再取各节并集）。
    portrait_map 为 None 时行为不变（向后兼容）。
    """
    sections = []
    for sp in section_paths:
        with open(sp, "r", encoding="utf-8") as f:
            sections.append(yaml.safe_load(f) or {})

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

    # portrait 整键改写（搬运层 guid 唯一键，解决同角色换装同名覆盖）
    if portrait_map:
        _rewrite_portraits(scenes, portrait_map)
        requires["portraits"] = _derive_portraits_from_lines(scenes)

    return {"meta": {"chapter": chapter, "title": title, "requires": requires}, "scenes": scenes}


def main(argv):
    p = argparse.ArgumentParser(description="合并各节定稿 YAML 为章运行时 JSON（N→1 拍平）")
    p.add_argument("inputs", nargs="+", help="各节定稿 YAML 路径，按 section_no 顺序传入")
    p.add_argument("--chapter", required=True, help="章节编号（meta.chapter）")
    p.add_argument("--title", required=True, help="章节标题（meta.title）")
    p.add_argument("-o", "--out", required=True, help="输出章 JSON 路径")
    p.add_argument("--portrait-map", default=None,
                   help="portrait-map JSON 路径（generate_portrait_map.py 产出）；"
                        "传入则把 say/show.portrait 改写为 guid 整键")
    args = p.parse_args(argv)

    portrait_map = None
    if args.portrait_map:
        try:
            portrait_map = json.loads(Path(args.portrait_map).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            sys.stderr.write(f"读取 portrait-map 失败: {e}\n")
            return 1

    try:
        doc = merge(args.inputs, args.chapter, args.title, portrait_map)
    except (OSError, yaml.YAMLError, ValueError) as e:
        sys.stderr.write(f"合并失败: {e}\n")
        return 1
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"OK: {len(args.inputs)} 节合并 -> {args.out}（{len(doc['scenes'])} 场景段）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
