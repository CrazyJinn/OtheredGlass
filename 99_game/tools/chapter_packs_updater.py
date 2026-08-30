#!/usr/bin/env python
"""更新 data/chapter_packs.json 中某章节的资源清单（幂等）。

Web 按章分包的依据：导出工具读本文件，把每章列出的资源打进 <stem>.pck。
pck 内部资源路径与全局 manifest 一致（如 assets/portraits/陈默.沉重.png），
故各章包挂载后 res:// 全局路径都能命中，跨章复用的资源在各章包内各自存在副本。

结构：
    {
      "chapter01_新皮肤": {
        "portraits": ["陆择-赤裸上身-慵懒-PHSE4iftNQ", ...],
        "scenes": ["长江大桥-栏杆", ...],
        "voices": ["陈默-chapter01_新皮肤-桥上-0", ...]
      },
      ...
    }

数据源由 chapter-publisher 提供（合并章 JSON 的 requires.portraits——uses 边投影的 guid 整键；+ has_layer 背景）；
voices 由 chapter-publisher 提供（从合并后章 JSON 的 say.voice 推导，voice_bundler list 出 voice 键 CSV）。
幂等：覆盖该 stem 条目，保留其他章。无依赖（仅标准库）。

CLI: chapter_packs_updater.py <stem> [--portraits a,b] [--scenes x,y] [--voices k1,k2] [--packs <path>]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # 99_game/tools/ → 项目根
DEFAULT_PACKS = ROOT / "99_game" / "data" / "chapter_packs.json"


def _split_csv(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="更新 chapter_packs.json 的某章资源清单")
    ap.add_argument("stem", help="章节 stem（如 chapter01_新皮肤）")
    ap.add_argument("--portraits", default="", help="立绘整键 CSV（<char>-<costume>-<variant>-<stand_id>，取合并章 JSON requires.portraits）")
    ap.add_argument("--scenes", default="", help="场景逻辑名 CSV（<Scene.name>）")
    ap.add_argument("--voices", default="", help="语音键 CSV（<char>-<stem>-<scene_id>-<line_idx>）")
    ap.add_argument("--sfx", default="", help="环境音 track CSV（amb-<stem>-<block>-<行id>，本章已批 ambient 行）")
    ap.add_argument("--packs", default=str(DEFAULT_PACKS), help="chapter_packs.json 路径")
    args = ap.parse_args(argv)

    path = Path(args.packs)
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except json.JSONDecodeError:
            print(f"[warn] {path} JSON 解析失败，从空重建", file=sys.stderr)
            data = {}

    entry = data.get(args.stem, {})
    # 仅更新显式传入（非空）的字段，保留未传字段（部分更新，避免调用方只传 --voices 时清空 portraits/scenes）
    if args.portraits:
        entry["portraits"] = _split_csv(args.portraits)
    if args.scenes:
        entry["scenes"] = _split_csv(args.scenes)
    if args.voices:
        entry["voices"] = _split_csv(args.voices)
    if args.sfx:
        entry["sfx"] = _split_csv(args.sfx)
    data[args.stem] = entry

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"OK: {args.stem} portraits={len(entry.get('portraits', []))} "
        f"scenes={len(entry.get('scenes', []))} voices={len(entry.get('voices', []))} "
        f"sfx={len(entry.get('sfx', []))} -> {path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
