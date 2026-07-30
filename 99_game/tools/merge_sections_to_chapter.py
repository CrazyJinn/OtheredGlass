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


def merge(section_paths, chapter, title):
    """读入各节定稿 YAML（按 section_no 顺序），返回合并后的 {meta, scenes} dict。"""
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

    return {"meta": {"chapter": chapter, "title": title, "requires": requires}, "scenes": scenes}


def main(argv):
    p = argparse.ArgumentParser(description="合并各节定稿 YAML 为章运行时 JSON（N→1 拍平）")
    p.add_argument("inputs", nargs="+", help="各节定稿 YAML 路径，按 section_no 顺序传入")
    p.add_argument("--chapter", required=True, help="章节编号（meta.chapter）")
    p.add_argument("--title", required=True, help="章节标题（meta.title）")
    p.add_argument("-o", "--out", required=True, help="输出章 JSON 路径")
    args = p.parse_args(argv)

    try:
        doc = merge(args.inputs, args.chapter, args.title)
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
