"""把全章各节台词 JSONL 合并拍平为单一章运行时 JSON。

chapter-publisher 在全章各节产物就绪时调用：N 个节级 `台词.jsonl` → 1 个章级 JSON。
- meta：chapter/title 取 CLI 参数；requires = 各节 meta.requires 的 characters/scenes/portraits 并集（保序去重）。
- scenes：按节传入顺序拼接各 scene-block（scene 分隔行 id 由 structurer 预分配、章内唯一，纯 concat 不改写）。
- portrait 整键改写：--chapter-map 的 portraits 段（generate_portrait_map.py 查图产）。
- BGM 注入：--chapter-map 的 bgm 段（Scene-has_bgm->BgmTrack，status=2 才进 map）写入 scene-block.bgm
  ——台词文件不含感官演出 op，演出信息全部由图推导注入（背景=scene 名、立绘=say 槽位、BGM=本注入）。
- 合并后校验 scene-block id 章内唯一（防御性，重复则报错）。

不做 schema 校验（校验由 validate_chapter.py 负责，保持工具正交）。
退码：0 成功 / 1 解析或 IO 或 id 冲突失败 / 2 参数错。
"""
import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "scripts"  # 项目根/.claude/scripts
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jsonl_script  # noqa: E402


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


_PORTRAIT_OPS = ("say",)  # 台词 JSONL 已无 show（立绘随 say 槽位自动出场）


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


def merge(section_paths, chapter, title, chapter_map=None):
    """读入各节台词 JSONL（按 section_no 顺序），返回合并后的 {meta, scenes} dict。

    chapter_map 非 None 时（generate_portrait_map.py 产出，{"portraits":…, "bgm":…}）：
    合并后按 scene 改写 say.portrait 为 guid 整键、注入 scene-block.bgm，
    requires.portraits 从改写后的 lines 重推导。为 None 时两者均不处理。
    """
    sections = []
    for sp in section_paths:
        rows = jsonl_script.load(sp)
        sections.append(jsonl_script.project(rows))

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


def main(argv):
    p = argparse.ArgumentParser(description="合并各节台词 JSONL 为章运行时 JSON（N→1 拍平，演出由图注入）")
    p.add_argument("inputs", nargs="+", help="各节 台词.jsonl 路径，按 section_no 顺序传入")
    p.add_argument("--chapter", required=True, help="章节编号（meta.chapter）")
    p.add_argument("--title", required=True, help="章节标题（meta.title）")
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
        doc = merge(args.inputs, args.chapter, args.title, chapter_map)
    except (OSError, ValueError) as e:
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
