"""绿幕立绘 → 缩放 + 去绿透明 PNG（chapter-publisher 搬运处理层）。

原图（06_/07_）不动，只写输出路径。chapter-publisher 在第 2 步把立绘从创作区
搬运到 99_game/assets/ 时调用本脚本：绿幕立绘（#00FF00 背景）先缩放、再去绿，
输出带 alpha 的透明 PNG，供运行时 PortraitLayer 叠在场景背景上。

滤镜链顺序：先 scale 再 colorkey（先缩放后去绿——缩放后色彩边界更稳，去绿更干净）。
- scale: 缩放到指定尺寸（默认 512x768）
- colorkey: 抠掉绿幕成透明（similarity=相似度阈值，blend=边缘混合）

ffmpeg 路径解析：settings.json 的 ffmpeg_path（可执行文件或目录均可，目录自动找
其下 / bin/ 下的 ffmpeg[.exe]）> PATH 回退。与 cypher_exec.py / ofoxai_api.py
同款 find_settings()（项目风格：每脚本自携一份）。

退码：0 成功 / 1 处理失败 / 2 参数错（与 99_game/tools 既有工具对齐）。
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def find_settings() -> dict:
    """从当前工作目录向上搜索 settings.json（最多 8 层）。
    与 cypher_exec.py / ofoxai_api.py 逐字同模式。"""
    dir_path = Path(os.getcwd()).resolve()
    for _ in range(8):
        candidate = dir_path / "settings.json"
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8") as f:
                return json.load(f)
        parent = dir_path.parent
        if parent == dir_path:
            break
        dir_path = parent
    return {}


def resolve_ffmpeg() -> str:
    """解析 ffmpeg 可执行路径：settings.json 的 ffmpeg_path（文件或目录）
    > PATH 回退。若是目录，在其下与 bin/ 子目录下找 ffmpeg[.exe]。"""
    exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    configured = find_settings().get("ffmpeg_path")
    if configured:
        p = Path(configured)
        if p.is_file():
            return str(p)
        if p.is_dir():
            for cand in (p / exe_name, p / "bin" / exe_name):
                if cand.is_file():
                    return str(cand)
    return exe_name  # 回退 PATH


def process(src: str, dst: str, size: str, color: str, similarity: float, blend: float) -> None:
    ffmpeg = resolve_ffmpeg()
    vf = "scale={size},colorkey={color}:{similarity}:{blend}".format(
        size=size, color=color, similarity=similarity, blend=blend
    )
    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-i", src, "-vf", vf, "-update", "1", str(dst_path)]
    # -update 1：ffmpeg 8.x image2 muxer 写单图必需（否则报 sequence pattern 警告）
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write("ffmpeg 失败 (rc=%d):\n%s\n" % (result.returncode, result.stderr[-2000:]))
        raise RuntimeError("ffmpeg 处理失败")


def main(argv):
    p = argparse.ArgumentParser(description="绿幕立绘缩放+去绿 → 透明 PNG（搬运处理层）")
    p.add_argument("src", help="源立绘 PNG（项目根相对路径）")
    p.add_argument("-o", "--out", required=True, help="输出透明 PNG 路径")
    p.add_argument("--size", default="800x1200", help="缩放尺寸（默认 800x1200）")
    p.add_argument("--color", default="0x00FF00", help="chroma key 颜色（默认 0x00FF00 绿幕）")
    p.add_argument("--similarity", type=float, default=0.3, help="colorkey 相似度阈值 0-1（默认 0.3，残留绿可调高）")
    p.add_argument("--blend", type=float, default=0.15, help="colorkey 边缘混合 0-1（默认 0.15）")
    args = p.parse_args(argv)

    if not Path(args.src).is_file():
        sys.stderr.write("源文件不存在: %s\n" % args.src)
        return 2
    try:
        process(args.src, args.out, args.size, args.color, args.similarity, args.blend)
    except (OSError, RuntimeError) as e:
        sys.stderr.write("处理失败: %s\n" % e)
        return 1
    print("OK: %s -> %s (scale=%s, colorkey=%s:%s:%s)" % (
        args.src, args.out, args.size, args.color, args.similarity, args.blend))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
