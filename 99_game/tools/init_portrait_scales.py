#!/usr/bin/env python
"""初始化立绘显示缩放：迁移 AppearanceStyle 身高 + 推算 IllusDesign.display_scale。

两步，均幂等（只填 IS NULL，人工已设的不覆盖）：
  A. 从 AppearanceStyle.appearance 文本（如"约185cm"）抽数值身高，写入 height_cm。
  B. 对 IllusDesign.display_scale 为空的节点，回溯上游 AppearanceStyle.height_cm，
     按 scale = height_cm / REF_HEIGHT 推算（1.0 = 占满立绘层满高），写回 display_scale。
     主回溯路径：IllusDesign<-produces-DesignSheet<-produces-AppearanceStyle；
     兜底路径：IllusDesign<-outfit_for-CostumeStyle<-has_costume-Character-has_appearance->AppearanceStyle。

缺上游身高的 IllusDesign 在报告中列出（提示人工填身高或手设 scale）。

CLI: init_portrait_scales.py [--ref-height <cm>]
退码：0 成功 / 1 查图或写回失败 / 2 参数错（与 99_game/tools 既有工具对齐）。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # 99_game/tools/ → 项目根
CYPHER_EXEC = ROOT / ".claude" / "scripts" / "cypher_exec.py"

REF_HEIGHT_DEFAULT = 200  # 参考身高（cm），= scale 1.0 满高
_HEIGHT_RE = re.compile(r"([0-9]{3})\s*cm")


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


def _exec_write(cypher: str) -> None:
    """执行写操作（MERGE/SET），仅校验退出码。"""
    proc = subprocess.run(
        [sys.executable, str(CYPHER_EXEC), "-c", cypher],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"写操作失败（退出码 {proc.returncode}）:\nstderr: {proc.stderr}\nstdout: {proc.stdout}"
        )


def migrate_heights() -> tuple[int, list[str]]:
    """从 appearance 文本抽身高写入 height_cm（仅 IS NULL）。

    WHERE 用 Cypher 正则预过滤（含三位数+cm），Python 端再精确提取，避免 toInteger 对
    "约185cm..." 这种带前缀文本返回 null。
    返回 (写入数, 无身高文本跳过的 name 列表)。
    """
    cypher = (
        "MATCH (ap:AppearanceStyle) "
        "WHERE ap.height_cm IS NULL AND ap.appearance =~ '.*[0-9]{3} *cm.*' "
        "RETURN ap.id AS id, ap.name AS name, ap.appearance AS appearance "
        "ORDER BY name"
    )
    written, skipped = 0, []
    for r in _run_cypher(cypher):
        ap_id = (r.get("id") or "").strip()
        appearance = r.get("appearance") or ""
        name = r.get("name") or ap_id
        m = _HEIGHT_RE.search(appearance)
        if not m or not ap_id:
            skipped.append(name)
            continue
        _exec_write(
            "MERGE (ap:AppearanceStyle {id:'" + ap_id + "'}) "
            "SET ap.height_cm = " + m.group(1)
        )
        written += 1
    return written, skipped


def _collect_illus_heights() -> list[dict]:
    """查所有 display_scale IS NULL 的 IllusDesign 及其上游身高。

    主路径（DesignSheet 上游）优先；其未覆盖的（缺 DesignSheet 链）走兜底路径
    （CostumeStyle→Character→AppearanceStyle）。主路径已写的节点此时 display_scale 已非 null，
    兜底查询的 WHERE IS NULL 自然排除，不会重复。
    """
    main = (
        "MATCH (illus:IllusDesign) "
        "WHERE illus.display_scale IS NULL "
        "MATCH (illus)<-[:produces]-(ds:DesignSheet)<-[:produces]-(ap:AppearanceStyle) "
        "WHERE ap.height_cm IS NOT NULL "
        "RETURN illus.id AS illus_id, ap.height_cm AS height"
    )
    rows = {r["illus_id"]: r for r in _run_cypher(main)}

    fallback = (
        "MATCH (illus:IllusDesign) "
        "WHERE illus.display_scale IS NULL "
        "MATCH (illus)<-[:outfit_for]-(costume:CostumeStyle)"
        "<-[:has_costume]-(char:Character)-[:has_appearance]->(ap:AppearanceStyle) "
        "WHERE ap.height_cm IS NOT NULL "
        "RETURN DISTINCT illus.id AS illus_id, ap.height_cm AS height"
    )
    for r in _run_cypher(fallback):
        rows.setdefault(r["illus_id"], r)  # 主路径未覆盖才用兜底
    return list(rows.values())


def init_scales(ref_height: float) -> tuple[int, list[str]]:
    """按 height_cm/ref_height 推算 display_scale 写回（仅 IS NULL）。

    返回 (写入数, 仍缺身高的 illus_id 列表)。
    """
    orphan_ids = {
        (r.get("illus_id") or "").strip()
        for r in _run_cypher(
            "MATCH (illus:IllusDesign) WHERE illus.display_scale IS NULL "
            "RETURN illus.id AS illus_id"
        )
    }

    written = 0
    for r in _collect_illus_heights():
        illus_id = (r.get("illus_id") or "").strip()
        height = r.get("height")
        if not illus_id or height is None:
            continue
        scale = round(float(height) / ref_height, 4)
        _exec_write(
            "MERGE (i:IllusDesign {id:'" + illus_id + "'}) "
            "SET i.display_scale = " + str(scale)
        )
        written += 1
        orphan_ids.discard(illus_id)
    return written, sorted(x for x in orphan_ids if x)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="迁移身高 + 初始化 IllusDesign.display_scale（幂等）")
    ap.add_argument("--ref-height", type=float, default=REF_HEIGHT_DEFAULT,
                    help=f"参考身高 cm（= scale 1.0 满高），默认 {REF_HEIGHT_DEFAULT}")
    args = ap.parse_args(argv)

    try:
        n_h, skip_h = migrate_heights()
        n_s, skip_s = init_scales(args.ref_height)
    except RuntimeError as e:
        sys.stderr.write(f"失败: {e}\n")
        return 1

    skip_h_msg = f"，跳过(无身高文本) {skip_h}" if skip_h else ""
    print(f"身高迁移：写入 {n_h} 个 AppearanceStyle.height_cm{skip_h_msg}")
    print(f"scale 初始化：写入 {n_s} 个 IllusDesign.display_scale"
          f"（ref_height={args.ref_height:g}cm）")
    if skip_s:
        print(f"[warn] {len(skip_s)} 个 IllusDesign 缺上游身高，未设 scale：{skip_s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
