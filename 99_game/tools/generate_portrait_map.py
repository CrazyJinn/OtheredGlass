#!/usr/bin/env python
"""生成章节 portrait-map（搬运时把 say/show.portrait 从纯变体改写为 guid 整键）。

查图：本章 Section-contains->Scene-depicts->IllusDesign<-outfit_for<-CostumeStyle<-has_costume-Character，
       IllusDesign-expands_to->StandingIllustration。
对每个 (scene, char, variant) 算整键 <char>-<costume_short>-<variant>-<stand_id>（见 portrait_key），
填入 map：{scene: {char: {variant: 整键}}}。

merge_sections_to_chapter.py --portrait-map 读本文件，按 scene-block 的 scene 字段重写 portrait。

CLI: generate_portrait_map.py <chapter_id> -o <out.json>
退码：0 成功 / 1 查图或歧义失败 / 2 参数错（与 99_game/tools 既有工具对齐）。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from portrait_key import make_key

ROOT = Path(__file__).resolve().parents[2]  # 99_game/tools/ → 项目根
CYPHER_EXEC = ROOT / ".claude" / "scripts" / "cypher_exec.py"


def _run_cypher(cypher: str) -> list:
    """调 cypher_exec.py --json，提取返回的 JSON 数组（cypher_exec 输出含连接提示行）。

    与 manifest_builder.py 同款（项目风格：每脚本自携一份）。
    """
    proc = subprocess.run(
        [sys.executable, str(CYPHER_EXEC), "-c", cypher, "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    out = proc.stdout
    start, end = out.find("["), out.rfind("]")
    if start == -1 or end == -1:
        raise RuntimeError(
            f"cypher_exec 未返回 JSON（退出码 {proc.returncode}）:\n"
            f"stderr: {proc.stderr}\nstdout: {out}"
        )
    return json.loads(out[start:end + 1])


def generate_map(chapter_id: str) -> dict:
    """查图生成 {scene: {char: {variant: 整键}}}。同 (scene,char,variant) 多着装 → raise。"""
    cypher = (
        "MATCH (ch:Chapter {id:'" + chapter_id + "'})"
        "-[:has_section]->(:Section)-[:contains]->(scene:Scene)"
        "-[:depicts]->(illus:IllusDesign)<-[:outfit_for]-(costume:CostumeStyle)"
        "<-[:has_costume]-(char:Character) "
        "MATCH (illus)-[:expands_to]->(stand:StandingIllustration) "
        "RETURN DISTINCT scene.name AS scene_name, char.name AS char_name, "
        "stand.variant_label AS variant, stand.id AS stand_id, costume.name AS costume_name "
        "ORDER BY scene_name, char_name, variant"
    )
    rows = _run_cypher(cypher)
    m: dict = {}
    seen: dict = {}  # (scene,char,variant) -> costume_name，检测同场换装歧义
    for r in rows:
        scene = (r.get("scene_name") or "").strip()
        char = (r.get("char_name") or "").strip()
        variant = (r.get("variant") or "").strip()
        stand_id = (r.get("stand_id") or "").strip()
        costume = r.get("costume_name")
        if not scene or not char or not variant or not stand_id:
            continue
        trip = (scene, char, variant)
        if trip in seen and seen[trip] != (costume or "").strip():
            raise ValueError(
                f"同场换装歧义：(scene={scene}, char={char}, variant={variant}) "
                f"绑定多个着装 {seen[trip]!r} vs {costume!r}——请拆场景或人工裁决"
            )
        seen[trip] = (costume or "").strip()
        m.setdefault(scene, {}).setdefault(char, {})[variant] = make_key(char, variant, stand_id, costume)
    return m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成章节 portrait-map（搬运 portrait 整键改写用）")
    ap.add_argument("chapter_id", help="Chapter 节点 ID（snowflake）")
    ap.add_argument("-o", "--out", required=True, help="输出 JSON 路径")
    args = ap.parse_args(argv)

    try:
        m = generate_map(args.chapter_id)
    except (RuntimeError, ValueError) as e:
        sys.stderr.write(f"生成失败: {e}\n")
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n_scenes = len(m)
    n_entries = sum(len(vm) for sm in m.values() for vm in sm.values())
    print(f"OK: {args.out}（{n_scenes} scenes, {n_entries} portrait 映射）")
    for scene, sm in m.items():
        for char, vm in sm.items():
            for variant, full_key in vm.items():
                print(f"  {scene} | {char}.{variant} -> {full_key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
