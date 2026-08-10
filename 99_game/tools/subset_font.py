"""字体子集化工具：按游戏实际用字子集化霞鹜文楷，**导出减包**用。

开发期保持完整字体（编辑器预览能看全字，新创作不缺字）；导出 Web/Steam 前用本工具
子集化（实测 25MB → 0.36MB，缩 99%），导出后恢复完整字体。

文本源（决定子集字符集）：
  - 99_game/data/chapters/*.json：已发布章的全部文本（say/narrate/choice/ending/title/...）
  - 99_game/scripts/**/*.gd：UI 脚本里硬编码的中文
  - 常用 ASCII 字母 / 数字 / 标点
  - --extra 指定的额外文本文件（如 .tscn、占位文字等）

用法：
  python subset_font.py                # 子集 → LXGWWenKai-Medium.subset.ttf（独立文件，仅预览大小）
  python subset_font.py --inplace      # 完整字体备份为 .full.ttf，子集覆盖原文件（导出前用）
  python subset_font.py --restore      # 从 .full.ttf 恢复完整字体（导出后用）
  python subset_font.py --extra foo.txt --extra bar.txt   # 追加额外文本源

子集源始终优先用完整备份 .full.ttf（若存在），避免「子集的子集」导致缺字累积。

退码：0 成功 / 1 失败 / 2 参数错（与 99_game/tools 既有工具对齐）。
"""
import argparse
import glob
import json
import re
import shutil
import sys
from pathlib import Path

from fontTools.subset import Subsetter, Options
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]              # 99_game/tools/ → 项目根
FONT_DIR = ROOT / "99_game" / "fonts"
FONT = FONT_DIR / "LXGWWenKai-Medium.ttf"               # GameManager 加载的字体（路径不变）
FULL_BACKUP = FONT_DIR / "LXGWWenKai-Medium.full.ttf"   # 完整字体备份（--inplace 生成，gitignore）
SUBSET_OUT = FONT_DIR / "LXGWWenKai-Medium.subset.ttf"  # 默认独立子集产物（gitignore）

# CJK 统一汉字 + CJK 符号标点 + 全角 ASCII
_CJK = re.compile(r"[一-鿿　-〿＀-￯]")


def collect_chars(extra_files: list[str]) -> set[str]:
    """收集游戏用到的全部字符（章 JSON + UI 脚本 + 额外文件 + 常用 ASCII）。"""
    chars: set[str] = set()
    for jp in glob.glob(str(ROOT / "99_game" / "data" / "chapters" / "*.json")):
        text = json.dumps(json.load(open(jp, encoding="utf-8")), ensure_ascii=False)
        chars |= set(_CJK.findall(text))
    for gp in glob.glob(str(ROOT / "99_game" / "scripts" / "**" / "*.gd"), recursive=True):
        chars |= set(_CJK.findall(open(gp, encoding="utf-8").read()))
    for ef in extra_files:
        chars |= set(_CJK.findall(open(ef, encoding="utf-8").read()))
    chars |= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                 "0123456789 .,!?:;\'\"-_/()[]@#$%&*+<>=")
    return chars


def do_subset(src: Path, dst: Path, chars: set[str]) -> None:
    font = TTFont(str(src))
    opts = Options()
    opts.desubroutinize = True
    sub = Subsetter(options=opts)
    sub.populate(text="".join(chars))
    sub.subset(font)
    font.save(str(dst))


def _full_source() -> Path:
    """子集源：优先完整备份 .full.ttf（避免子集的子集），否则当前字体。"""
    return FULL_BACKUP if FULL_BACKUP.exists() else FONT


def main(argv) -> int:
    p = argparse.ArgumentParser(description="字体子集化（霞鹜文楷，导出减包）")
    p.add_argument("--inplace", action="store_true",
                   help="完整字体备份为 .full.ttf，子集覆盖原字体（导出前用）")
    p.add_argument("--restore", action="store_true", help="从 .full.ttf 恢复完整字体（导出后用）")
    p.add_argument("--extra", action="append", default=[], help="额外文本源文件（可多次）")
    args = p.parse_args(argv)

    if args.restore:
        if not FULL_BACKUP.exists():
            sys.stderr.write("无完整字体备份: %s\n" % FULL_BACKUP.name)
            return 1
        shutil.copy(FULL_BACKUP, FONT)
        print("已恢复完整字体 -> %s (%.1f MB)" % (FONT.name, FONT.stat().st_size / 1e6))
        return 0

    src = _full_source()
    if args.inplace:
        if not FULL_BACKUP.exists() and FONT.exists():   # 首次：备份当前完整字体
            shutil.copy(FONT, FULL_BACKUP)
            print("已备份完整字体 -> %s（%.1f MB；请加入 .gitignore）" % (
                FULL_BACKUP.name, FULL_BACKUP.stat().st_size / 1e6))
            src = FULL_BACKUP
        dst = FONT
    else:
        dst = SUBSET_OUT

    if not src.exists():
        sys.stderr.write("源字体不存在: %s\n" % src)
        return 1

    chars = collect_chars(args.extra)
    do_subset(src, dst, chars)
    n_han = len([c for c in chars if "一" <= c <= "鿿"])
    print("子集 -> %s  %.2f MB（%d 字符，汉字 %d）" % (
        dst.name, dst.stat().st_size / 1e6, len(chars), n_han))
    if args.inplace:
        print("⚠️ 当前为子集字体（导出用）。导出后务必跑 --restore 恢复完整字体。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
