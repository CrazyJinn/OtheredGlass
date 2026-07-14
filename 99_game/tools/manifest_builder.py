#!/usr/bin/env python
"""从 Neo4j 图生成/更新 99_game/data/manifest.json。

剧本只写逻辑名，manifest 把逻辑名映射到 Godot res:// 资源路径（见 00_init/剧本.md）。
本脚本从图查：
  - status=11 的 StandingIllustration → portraits（键 = <char_name>.<variant_label>）
  - 所有 Scene                        → scenes   （键 = <Scene.name>）
并保留现有 manifest 的 bgm/sfx/cg（无对应图节点，手写）。

资源路径约定（与当前 manifest.json 一致，运行时缺资源由 PlaceholderGen 兜底）：
  portraits: assets/portraits/<逻辑名>.png
  scenes:    assets/scenes/<逻辑名>.png

用法：
    python 99_game/tools/manifest_builder.py [--manifest <path>] [--dry-run]

注意：本脚本只生成逻辑名→路径映射，不负责把美术产物（06_角色美术/、07_场景美术/）
复制到 99_game/assets/——那是部署步骤。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # 99_game/tools/ → 项目根
CYPHER_EXEC = ROOT / ".claude" / "scripts" / "cypher_exec.py"
DEFAULT_MANIFEST = ROOT / "99_game" / "data" / "manifest.json"

PORTRAIT_PREFIX = "assets/portraits/"
SCENE_PREFIX = "assets/scenes/"

# Character → StandingIllustration 的限定美术边类型集（与 plot-design 一致，阻止越界到叙事 Event）
CHAR_TO_STAND_EDGES = "has_appearance|has_voice_style|has_costume|produces|outfit_for|expands_to|ref_style"


def _run_cypher(cypher: str) -> list:
    """调 cypher_exec.py --json，提取返回的 JSON 数组（cypher_exec 输出含连接提示行）。"""
    proc = subprocess.run(
        [sys.executable, str(CYPHER_EXEC), "-c", cypher, "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    out = proc.stdout
    start = out.find("[")
    end = out.rfind("]")
    if start == -1 or end == -1:
        raise RuntimeError(
            f"cypher_exec 未返回 JSON（退出码 {proc.returncode}）:\n"
            f"stderr: {proc.stderr}\nstdout: {out}"
        )
    return json.loads(out[start:end + 1])


def collect_portraits() -> dict:
    """status=11 的立绘 → <char_name>.<variant_label>: assets/portraits/<...>.png"""
    cypher = (
        "MATCH (char:Character)-[:" + CHAR_TO_STAND_EDGES + "*1..5]->"
        "(stand:StandingIllustration {status:11}) "
        "RETURN DISTINCT char.name AS char_name, stand.variant_label AS variant "
        "ORDER BY char_name, variant"
    )
    portraits = {}
    for r in _run_cypher(cypher):
        char_name = (r.get("char_name") or "").strip()
        variant = (r.get("variant") or "").strip()
        if not char_name or not variant:
            continue
        key = f"{char_name}.{variant}"
        portraits[key] = f"{PORTRAIT_PREFIX}{key}.png"
    return portraits


def collect_scenes() -> dict:
    """所有 Scene → <Scene.name>: assets/scenes/<...>.png"""
    rows = _run_cypher("MATCH (s:Scene) RETURN s.name AS name ORDER BY name")
    scenes = {}
    for r in rows:
        name = (r.get("name") or "").strip()
        if name:
            scenes[name] = f"{SCENE_PREFIX}{name}.png"
    return scenes


def build_manifest(manifest_path: Path) -> dict:
    # 读现有 manifest，保留 bgm/sfx/cg（非图来源）
    existing = {}
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"[warn] {manifest_path} JSON 解析失败，bgm/sfx/cg 从空重建", file=sys.stderr)

    # portraits/scenes 合并：保留现有手写，图查到的覆盖/补充（向后兼容）；bgm/sfx/cg 保留现有
    return {
        "portraits": {**existing.get("portraits", {}), **collect_portraits()},
        "scenes": {**existing.get("scenes", {}), **collect_scenes()},
        "bgm": existing.get("bgm", {}),
        "sfx": existing.get("sfx", {}),
        "cg": existing.get("cg", {}),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="从 Neo4j 图生成/更新 manifest.json")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="manifest.json 路径")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写盘")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    data = build_manifest(manifest_path)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    if args.dry_run:
        sys.stdout.write(text)
        print(
            f"[dry-run] portraits={len(data['portraits'])} scenes={len(data['scenes'])} "
            f"bgm={len(data['bgm'])}(保留) sfx={len(data['sfx'])}(保留) cg={len(data['cg'])}(保留)",
            file=sys.stderr,
        )
        return

    manifest_path.write_text(text, encoding="utf-8")
    print(
        f"已写入 {manifest_path}：portraits={len(data['portraits'])} "
        f"scenes={len(data['scenes'])} bgm={len(data['bgm'])} sfx={len(data['sfx'])} cg={len(data['cg'])}"
    )


if __name__ == "__main__":
    main()
