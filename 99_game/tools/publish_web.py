#!/usr/bin/env python
"""Web 一键发布流水线（字体子集化已并入——原 subset_font.py 于 2026-08-30 合并进本脚本）。

流程（产物目录 = export_presets.cfg 里 Web preset 的导出目录）：
  1. 字体子集化：收集游戏用字（章 JSON + UI 脚本的**全部非 ASCII 字符** + 关键标点保底）
     → 子集临时覆盖 fonts/LXGWWenKai-Medium.ttf（完整版备份在 .full.ttf，已 gitignore）；
     做完断言省略号/破折号等关键标点确在子集内（2026-08-30 省略号 Web 豆腐教训：
     旧收集正则只覆盖 CJK 区段，…(U+2026)/—(U+2014)/弯引号 全漏）；
  2. godot --headless --export-release "Web"  主 pck 导出（exclude_filter 只排 full.ttf）；
  3. （WEB_PACKS_ENABLED=true 时）build_chapter_packs.gd 产各章 <stem>.pck；
  4. finally 恢复完整字体——开发环境绝不能留在子集上。

godot 定位：环境变量 GODOT_BIN → PATH → 常见安装路径兜底。
上传 R2 用 deploy_r2.py。

用法：
  python tools/publish_web.py            # 完整流水线
  python tools/publish_web.py --skip-export   # 只重产章包（改了章清单/资源时）

⚠️ 运行前关闭 Godot 编辑器（字体被临时覆盖，编辑器开着会抢 .godot/ 导入缓存）。
退码：0 成功 / 1 失败。
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # 项目根
GAME = ROOT / "99_game"
TOOLS = GAME / "tools"
FONT_DIR = GAME / "fonts"
FONT = FONT_DIR / "LXGWWenKai-Medium.ttf"           # GameManager 加载的字体（路径不变）
FULL_BACKUP = FONT_DIR / "LXGWWenKai-Medium.full.ttf"  # 完整字体备份（gitignore）
GODOT_CANDIDATES = [
    Path("D:/godot/Godot_v4.7.1-stable_win64.exe"),
    Path("C:/Program Files/Godot/Godot_v4.7.1-stable_win64.exe"),
]

# 关键标点保底：General Punctuation 区（U+2000-U+206F）不在 CJK 区段，文本源漏收时
# 由这份保底兜住——省略号/破折号/弯引号是中文对白高频符号，缺了直接豆腐块
_FALLBACK_PUNCT = (
    "…—‐‘’“”„‧•·、。，！？；：（）【】《》〈〉「」『』％℃°"
    "±×÷←→↑↓∈∋∏∑√∞∠∥∧∨∩∪∫∴∵∶∷∽≒≡≦≧⊕⊙⊥⊿"
)


def find_godot() -> str:
    import os
    if os.environ.get("GODOT_BIN"):
        return os.environ["GODOT_BIN"]
    which = shutil.which("godot")
    if which:
        return which
    for p in GODOT_CANDIDATES:
        if p.exists():
            return str(p)
    sys.stderr.write("找不到 godot：设环境变量 GODOT_BIN 或安装到 PATH\n")
    sys.exit(1)


def check_editor_closed() -> None:
    """字体临时覆盖期间编辑器必须关闭（重导入会与 headless 导出抢 .godot/ 缓存）。"""
    import subprocess as sp
    n = 0
    try:
        out = sp.run(["tasklist"], capture_output=True, text=True).stdout or ""
        n = len([l for l in out.splitlines() if l.lower().startswith("godot")])
    except FileNotFoundError:
        try:
            out = sp.run(["pgrep", "-i", "-c", "godot"], capture_output=True, text=True)
            n = int(out.stdout.strip() or 0)
        except (FileNotFoundError, ValueError):
            n = 0  # 检测手段不可用时放行
    if n:
        sys.exit(f"检测到 Godot 正在运行（{n} 个进程）——请先关闭编辑器再跑本流水线")


def run(cmd: list, cwd: Path, desc: str) -> None:
    print(f"\n=== {desc} ===\n$ {' '.join(str(c) for c in cmd)}", flush=True)
    r = subprocess.run([str(c) for c in cmd], cwd=cwd)
    if r.returncode != 0:
        sys.exit(f"失败（退码 {r.returncode}）：{desc}")


def _web_export_dir() -> Path | None:
    """手写轻量解析 Web preset 的 export_path 目录（configparser 吃不下多行脚本值）。"""
    cur_name = None
    for line in (GAME / "export_presets.cfg").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            cur_name = None
            continue
        m = re.match(r'name="([^"]+)"', s)
        if m:
            cur_name = m.group(1)
            continue
        m = re.match(r'export_path="([^"]+)"', s)
        if m and cur_name == "Web":
            return Path(m.group(1)).parent
    return None


def packs_enabled() -> bool:
    """读 ChapterPackLoader 的分包总开关（单一事实源，避免流水线与游戏端配置漂移）。"""
    src = (GAME / "scripts" / "autoload" / "ChapterPackLoader.gd").read_text(encoding="utf-8")
    m = re.search(r"WEB_PACKS_ENABLED\s*:=\s*(true|false)", src)
    return bool(m and m.group(1) == "true")


def collect_chars() -> set[str]:
    """收集游戏用字：章 JSON + UI 脚本的全部非 ASCII 字符（出现啥收啥，不再按区段筛）
    + 关键标点保底 + 常用 ASCII。"""
    chars: set[str] = set(_FALLBACK_PUNCT)
    for jp in (GAME / "data" / "chapters").glob("*.json"):
        text = json.dumps(json.load(open(jp, encoding="utf-8")), ensure_ascii=False)
        chars |= {c for c in text if ord(c) > 127}
    for gp in (GAME / "scripts").rglob("*.gd"):
        chars |= {c for c in gp.read_text(encoding="utf-8") if ord(c) > 127}
    chars |= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                 "0123456789 .,!?:;\'\"-_/()[]@#$%&*+<>=")
    return chars


def subset_inplace() -> None:
    """完整字体备份 → 子集覆盖开发字体（导出用；跑完流水线 restore_font 恢复）。"""
    try:
        from fontTools.subset import Subsetter, Options
        from fontTools.ttLib import TTFont
    except ImportError:
        sys.exit("缺 fontTools：pip install fonttools")
    if not FULL_BACKUP.exists():
        shutil.copy(FONT, FULL_BACKUP)
        print(f"已备份完整字体 -> {FULL_BACKUP.name}（{FULL_BACKUP.stat().st_size / 1e6:.1f} MB）")
    chars = collect_chars()
    font = TTFont(str(FULL_BACKUP))
    opts = Options()
    opts.desubroutinize = True
    sub = Subsetter(options=opts)
    sub.populate(text="".join(chars))
    sub.subset(font)
    font.save(str(FONT))
    n_han = len([c for c in chars if 0x4E00 <= ord(c) <= 0x9FFF])
    print(f"子集字体已覆盖 {FONT.name}：{FONT.stat().st_size / 1e6:.2f} MB"
          f"（{len(chars)} 字符，汉字 {n_han}）")
    # 断言关键标点在子集内（cmap 命中）——省略号豆腐教训的防回归闸
    cmap = TTFont(str(FONT)).getBestCmap()
    for ch in "…—“”「」":
        if ord(ch) not in cmap:
            sys.exit(f"子集缺关键标点 {ch!r}(U+{ord(ch):04X})——字符收集逻辑回归，中止导出")


def restore_font() -> None:
    if FULL_BACKUP.exists():
        shutil.copy(FULL_BACKUP, FONT)
        print(f"已恢复完整字体 -> {FONT.name}（{FONT.stat().st_size / 1e6:.1f} MB）", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Web 一键发布流水线")
    ap.add_argument("--skip-export", action="store_true", help="跳过字体/导出，只重产章包")
    args = ap.parse_args()

    godot = find_godot()
    if not args.skip_export:
        check_editor_closed()

    try:
        if not args.skip_export:
            print("\n=== 字体子集化（临时覆盖） ===", flush=True)
            subset_inplace()
            run([godot, "--headless", "--export-release", "Web"], GAME, "导出 Web 主包")
        if packs_enabled():
            run([godot, "--headless", "-s", "tools/build_chapter_packs.gd", "--"], GAME, "生成章包")
        else:
            print("\n=== 生成章包 ===\n跳过（WEB_PACKS_ENABLED=false 全量主包模式）", flush=True)
    finally:
        if not args.skip_export:
            restore_font()

    print("\n=== 产物清单 ===")
    out_dir = _web_export_dir()
    if out_dir and out_dir.exists():
        total = 0
        for f in sorted(out_dir.iterdir()):
            if f.is_file():
                total += f.stat().st_size
                print(f"  {f.name:40s} {f.stat().st_size / 1048576:7.2f} MB")
        print(f"  {'合计':40s} {total / 1048576:7.2f} MB")
    print("\n完成。上传：python tools/deploy_r2.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
