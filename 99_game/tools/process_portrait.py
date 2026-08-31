"""绿幕立绘 → opencv 抠绿 + grabCut 发丝精修 + 头位归一化 → 透明 PNG（chapter-publisher 搬运处理层）。

替换原 ffmpeg ``scale,colorkey`` 单滤镜链。4 阶段管线（单图独立处理）：

  ① 4 角采样绿幕实际 HSV 范围 → ``inRange`` 自适应抠绿（替代硬编码 #00FF00）
  ② 抠绿 mask 初始化 ``grabCut`` → 发丝 / 半透明边缘精修
  ③ mask 合 alpha → BGRA
  ④ 头位归一化：**人物前景高 ÷ 7.5 头身**作尺度 → 各变体等高；垂直贴顶贴底（alpha bbox
     上下）；**水平以 YuNet 双眼中心为锚**——左右对称取 max(到左身,到右身) 使双眼中心落在
     PNG 水平中线 ⇒ 运行时居中显示，任意立绘切换头部水平 x 恒定；等高+贴顶 ⇒ 头部 y 同
     水平线。身体不对称可能单侧留透明（为保双眼居中）。PNG 宽高比不固定 2:3，需 PortraitLayer
     按实际宽高比显示。回退：L2 用 bbox 中心（无脸），L3 贴底 letterbox。

原图（06_/07_）不动，只写输出路径。CLI 与旧版兼容：
``python process_portrait.py <src> -o <dst>``，chapter-publisher 调用处零改动。

依赖：opencv-python（自带 numpy）。YuNet onnx 与本脚本同目录自带
（``face_detection_yunet.onnx``，opencv zoo 官方模型）。

中文路径：cv2.imread/imwrite 不支持非 ASCII 文件名，统一用
np.fromfile + imdecode / imencode + tofile。

退码：0 成功 / 1 处理失败 / 2 参数错（与 99_game/tools 既有工具对齐）。
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

# ── 画布与归一化规范（默认，CLI 可调）──────────────────────────────
CANVAS_W, CANVAS_H = 800, 1200          # 输出画布（2:3，与 PortraitLayer 素材比一致）
HEAD_RATIO = 7.5                         # 头身比（00_init/美术风格.md：7.5 头身）
DEFAULT_TARGET_HEAD_PX = round(CANVAS_H / HEAD_RATIO)   # 160：目标头长（=画布高/7.5），缩放使各变体人物等高（高 1200）

_HERE = Path(__file__).resolve().parent
_YUNET_PATH = _HERE / "face_detection_yunet.onnx"

_K3 = np.ones((3, 3), np.uint8)


# ── 中文路径 IO ───────────────────────────────────────────────────
def imread_unicode(path: str):
    """cv2.imread 不支持非 ASCII 路径；用 fromfile + imdecode 绕过。"""
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


def imwrite_unicode(path: str, img) -> None:
    """cv2.imwrite 不支持非 ASCII 路径；用 imencode + tofile 绕过。"""
    ext = Path(path).suffix or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise RuntimeError("imencode 失败: %s" % path)
    buf.tofile(str(path))


# ── ① 4 角采样 + 自适应抠绿 ────────────────────────────────────────
def find_green_range(bgr, corner: int = 20, h_slack: int = 10, sv_slack: int = 50):
    """4 个角各取 corner×corner 像素块，统计绿幕实际色。

    仅保留落在绿色先验区间（H∈[40,80]、S>50、V>50）的采样点，抗角块偶然非绿
    （如人物贴边）。返回 (center, lower, upper)：
      - center = 绿幕 BGR 均值（float32）→ 供连续 alpha chroma key（默认模式）
      - lower/upper = HSV 上下界（uint8）→ 供 inRange 二值模式 / grabCut（可选）
    """
    h, w = bgr.shape[:2]
    m = max(2, min(corner, h // 4, w // 4))
    blocks = [
        bgr[0:m, 0:m], bgr[0:m, w - m:w],
        bgr[h - m:h, 0:m], bgr[h - m:h, w - m:w],
    ]
    pts = np.concatenate([b.reshape(-1, 3) for b in blocks], axis=0).astype(np.uint8)
    hsv = cv2.cvtColor(pts.reshape(1, -1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.int16)
    green = (hsv[:, 0] >= 40) & (hsv[:, 0] <= 80) & (hsv[:, 1] > 50) & (hsv[:, 2] > 50)
    if green.sum() == 0:                      # 角块全非绿（异常图）→ 退回硬编码纯绿
        return (np.array([0, 255, 0], np.float32),
                np.array([50, 80, 80], np.uint8), np.array([70, 255, 255], np.uint8))
    center = pts[green].astype(np.float32).mean(axis=0)
    hsv = hsv[green]
    lower = np.array([
        max(int(hsv[:, 0].min()) - h_slack, 0),
        max(int(hsv[:, 1].min()) - sv_slack, 0),
        max(int(hsv[:, 2].min()) - sv_slack, 0),
    ], np.uint8)
    upper = np.array([
        min(int(hsv[:, 0].max()) + h_slack, 179),
        min(int(hsv[:, 1].max()) + sv_slack, 255),
        min(int(hsv[:, 2].max()) + sv_slack, 255),
    ], np.uint8)
    return center, lower, upper


def chroma_key(bgr, lower, upper):
    """inRange 抠绿 + 形态学清理。返回 uint8 mask（255=前景）。"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    bg = cv2.inRange(hsv, lower, upper)             # 255=绿/背景
    fg = cv2.bitwise_not(bg)                        # 255=前景
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, _K3)  # 去前景噪点
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))  # 补小洞
    return fg


def chroma_key_soft(bgr, center, similarity: float = 0.3, blend: float = 0.15, sv_floor: int = 50):
    """连续 alpha 抠绿（仿 ffmpeg ``colorkey <c>:<similarity>:<blend>``）+ S/V 门控保暗色。

    每像素到绿幕中心（BGR 欧氏距离，归一化到 [0,1]，最大 √(3·255²)≈441.34）：
      - dist < similarity        → alpha = 0（确定背景）
      - dist > similarity+blend  → alpha = 255（确定前景）
      - 中间                      → 线性渐变（半透明过渡带，发丝/绒毛自然柔和）

    **S/V 门控**：低饱和（S < sv_floor）或暗色（V < sv_floor）强制 alpha = 255——防止
    黑色 / 灰色衣物（内裤、深色布料、阴影）因带绿幕反光、颜色距离落在渐变带而被误抠成
    半透明。绿幕 S/V 极高不受影响。返回 uint8 alpha（0-255 连续）。
    """
    diff = bgr.astype(np.float32) - center
    dist = np.sqrt((diff * diff).sum(axis=2)) / 441.34
    alpha = np.clip((dist - similarity) / max(blend, 1e-6), 0.0, 1.0) * 255.0
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    not_green = (hsv[:, :, 1] < sv_floor) | (hsv[:, :, 2] < sv_floor)
    alpha[not_green] = 255.0
    return alpha.astype(np.uint8)


# ── ② grabCut 发丝精修（可选，--refine-grabcut 开启）──────────────
def refine_grabcut(bgr, fg_mask, scale: float = 0.5, iters: int = 5):
    """用抠绿 mask 构造 4 态 init mask 跑 grabCut，精修发丝边缘。

    下采样到 ``scale`` 跑（提速），mask 再 INTER_NEAREST 放回原尺寸。
    返回 uint8 mask（255=前景）。
    """
    H, W = bgr.shape[:2]
    if scale < 1.0:
        nw, nh = max(8, int(W * scale)), max(8, int(H * scale))
        small = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA)
        msmall = cv2.resize(fg_mask, (nw, nh), interpolation=cv2.INTER_NEAREST)
    else:
        small, msmall = bgr, fg_mask

    # 4 态：确定前景（erode 核）/ 确定背景（dilate 之外）/ 前景边缘=PR_FGD / 其余=PR_BGD
    sure_fg = cv2.erode(msmall, _K3, iterations=2)
    sure_bg = cv2.bitwise_not(cv2.dilate(msmall, _K3, iterations=2))
    gc = np.full(msmall.shape, cv2.GC_PR_BGD, np.uint8)
    gc[sure_bg > 0] = cv2.GC_BGD
    gc[sure_fg > 0] = cv2.GC_FGD
    gc[(msmall > 0) & (sure_fg == 0)] = cv2.GC_PR_FGD

    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(small, gc, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
    out = np.where((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    if scale < 1.0:
        out = cv2.resize(out, (W, H), interpolation=cv2.INTER_NEAREST)
    return out


# ── ③ 合 alpha + 温和去绿溢 ────────────────────────────────────────
def to_rgba(bgr, alpha, despill_factor: float = 0.5):
    """BGR + alpha → BGRA。

    - alpha 轻微 3×3 blur 抗锯齿。
    - 去绿溢（温和）：alpha>0 区把 G 通道超出 max(R,B) 的部分压掉 ``despill_factor``
      （默认 0.5 半压——保肤色自然；1.0=全压激进，0=不去溢）。比旧版 ``min(G,max(R,B))``
      的强压更不易让肤色/浅色衣服偏红偏暗。
    """
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA).astype(np.float32)
    a = cv2.GaussianBlur(alpha, (3, 3), 0)
    b_, g_, r_ = rgba[:, :, 0], rgba[:, :, 1], rgba[:, :, 2]
    spill = np.maximum(g_ - np.maximum(r_, b_), 0.0)
    rgba[:, :, 1] = np.where(a > 0, g_ - spill * despill_factor, g_)
    rgba = rgba.astype(np.uint8)
    rgba[:, :, 3] = a
    return rgba


# ── ④ 头位归一化 ──────────────────────────────────────────────────
def _fallback_letterbox(rgba):
    """L3：贴底居中、等比放进画布（不做头位对齐）。"""
    H, W = rgba.shape[:2]
    s = min(CANVAS_W / W, CANVAS_H / H)
    nw, nh = max(1, int(W * s)), max(1, int(H * s))
    sc = cv2.resize(rgba, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    canvas = np.zeros((CANVAS_H, CANVAS_W, 4), np.uint8)
    x0 = (CANVAS_W - nw) // 2
    y0 = CANVAS_H - nh                               # 贴底（与 PortraitLayer 脚踩地面线一致）
    canvas[y0:y0 + nh, x0:x0 + nw] = sc
    return canvas


def normalize_head(rgba, target_head_px: int,
                   score_thr: float = 0.5, yunet_path: Path = _YUNET_PATH):
    """头位归一化：等高缩放 + 以双眼中心为水平锚定裁剪（头部水平居中）。

    尺度：人物前景高 ÷ 7.5 头身（稳定）→ 各变体人物等高（默认 1200）。裁剪：垂直贴顶
    贴底（alpha bbox 上下）；水平以 YuNet 双眼中心为锚——左右相对双眼中心对称取
    max(双眼到左身, 双眼到右身)，使双眼中心落在 PNG 水平中线。⇒ 运行时 PortraitLayer
    居中显示，**任意立绘切换头部（双眼）水平 x 恒定**；等高+贴顶 ⇒ 头部 y 同水平线。
    身体不对称时可能单侧留透明（为保双眼居中）。输出 PNG 宽高比不固定 2:3，需 PortraitLayer
    按实际宽高比显示。YuNet 失败则用 bbox 中心（L2），前景过小贴底 letterbox（L3）。

    返回 (out_rgba, level, info)：level ∈ {'L1','L2','L3'}。
    """
    H, W = rgba.shape[:2]
    alpha = rgba[:, :, 3]
    ys, xs = np.where(alpha > 127)

    if len(xs) == 0 or (ys.max() - ys.min()) < H * 0.2:
        return _fallback_letterbox(rgba), "L3", "no foreground"
    person_h = float(ys.max() - ys.min())
    s = target_head_px / (person_h / HEAD_RATIO)     # 等高（默认 → 人物高 1200）
    new_w, new_h = max(1, int(round(W * s))), max(1, int(round(H * s)))
    interp = cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR
    scaled = cv2.resize(rgba, (new_w, new_h), interpolation=interp)

    a2 = scaled[:, :, 3]
    ys2, xs2 = np.where(a2 > 127)
    if len(xs2) == 0:
        return scaled, "L3", "no fg after scale"
    top, bot = int(ys2.min()), int(ys2.max())
    lf, rt = int(xs2.min()), int(xs2.max())

    # 水平锚：YuNet 双眼中心（缩放后坐标）/ bbox 中心（L2）
    cx_s = (lf + rt) / 2.0
    level = "L2"
    if yunet_path.exists():
        try:
            bgr = cv2.cvtColor(rgba, cv2.COLOR_BGRA2BGR)
            det = cv2.FaceDetectorYN_create(str(yunet_path), "", (W, H), score_thr, 0.3, 1)
            det.setInputSize((W, H))
            _, faces = det.detect(bgr)
            if faces is not None and len(faces) > 0:
                f = faces[0]                          # x,y,w,h,re_x,re_y,le_x,le_y,...,score
                cx_s = (float(f[4]) + float(f[6])) / 2.0 * s
                level = "L1"
        except cv2.error:
            pass

    # 双眼中心居中：左右对称取 max(到左身,到右身)，含整个身体；越界侧补透明
    half_w = max(cx_s - lf, rt - cx_s)
    x0 = int(round(cx_s - half_w))
    x1 = int(round(cx_s + half_w))
    out_w = x1 - x0 + 1
    out = np.zeros((bot - top + 1, out_w, 4), np.uint8)
    sx0 = max(x0, 0)
    sx1 = min(x1, scaled.shape[1] - 1)
    if sx1 >= sx0:
        out[:, sx0 - x0:sx1 - x0 + 1] = scaled[top:bot + 1, sx0:sx1 + 1]
    return out, level, "person_h=%d s=%.3f out=%dx%d eye@center" % (
        int(person_h), s, out.shape[1], out.shape[0])


# ── 主管线 ────────────────────────────────────────────────────────
def process(src: str, dst: str, *, corner=20, h_slack=10, sv_slack=50,
            similarity=0.3, blend=0.15, despill_factor=0.5, sv_floor=50,
            use_grabcut=False, grabcut_scale=0.5, grabcut_iters=5,
            target_head_px=DEFAULT_TARGET_HEAD_PX,
            normalize=True, score_thr=0.5) -> dict:
    bgr = imread_unicode(src)
    if bgr is None:
        raise RuntimeError("读图失败（路径/格式）: %s" % src)

    center, lower, upper = find_green_range(bgr, corner, h_slack, sv_slack)
    if use_grabcut:
        # 二值 + grabCut 模式：边缘更干净，但半透明发丝易丢（旧默认行为，需 --refine-grabcut）
        alpha = chroma_key(bgr, lower, upper)
        alpha = refine_grabcut(bgr, alpha, grabcut_scale, grabcut_iters)
        mode = "grabcut"
    else:
        # 连续 alpha 模式（默认，仿 ffmpeg blend）：发丝/边缘半透明过渡自然
        alpha = chroma_key_soft(bgr, center, similarity, blend, sv_floor)
        mode = "soft"
    rgba = to_rgba(bgr, alpha, despill_factor)

    if normalize:
        rgba, level, info = normalize_head(rgba, target_head_px, score_thr)
    else:
        rgba = _fallback_letterbox(rgba)
        level, info = "skip", "normalize disabled"

    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    imwrite_unicode(dst, rgba)
    return {
        "center": [int(x) for x in center], "lower": lower.tolist(), "upper": upper.tolist(),
        "mode": mode, "level": level, "info": info,
        "out_size": "%dx%d" % (rgba.shape[1], rgba.shape[0]),
    }


def main(argv) -> int:
    p = argparse.ArgumentParser(description="绿幕立绘 → opencv 连续 alpha 抠绿 + 头位归一化 → 透明 PNG")
    p.add_argument("src", help="源立绘 PNG（项目根相对路径）")
    p.add_argument("-o", "--out", required=True, help="输出透明 PNG 路径")
    p.add_argument("--corner", type=int, default=20, help="4 角采样块边长（默认 20）")
    p.add_argument("--h-slack", type=int, default=10, help="HSV-H 通道松弛裕度（默认 10；仅 grabCut 模式）")
    p.add_argument("--sv-slack", type=int, default=50, help="HSV-S/V 通道松弛裕度（默认 50；仅 grabCut 模式）")
    p.add_argument("--similarity", type=float, default=0.3,
                   help="连续 alpha：确定背景距离阈值 0-1（默认 0.3，仿 ffmpeg colorkey similarity）")
    p.add_argument("--blend", type=float, default=0.15,
                   help="连续 alpha：边缘渐变带宽 0-1（默认 0.15，仿 ffmpeg blend；大→发丝柔和）")
    p.add_argument("--despill-factor", type=float, default=0.5,
                   help="去绿溢强度 0-1（默认 0.5 温和保肤色；1.0 激进；0 关）")
    p.add_argument("--sv-floor", type=int, default=50,
                   help="S/V 门控地板（默认 50）：低饱和或暗色（黑/灰衣物）强制前景，防误抠透明")
    p.add_argument("--refine-grabcut", action="store_true",
                   help="改用 inRange+grabCut 二值模式（边缘更干净、发丝可能丢；默认连续 alpha）")
    p.add_argument("--grabcut-scale", type=float, default=0.5, help="grabCut 下采样比例（默认 0.5；仅 --refine-grabcut）")
    p.add_argument("--grabcut-iters", type=int, default=5, help="grabCut 迭代次数（默认 5；仅 --refine-grabcut）")
    p.add_argument("--target-head-px", type=int, default=DEFAULT_TARGET_HEAD_PX,
                   help="目标头长像素（默认 %d，= 画布高/7.5 头身）" % DEFAULT_TARGET_HEAD_PX)
    p.add_argument("--score-thr", type=float, default=0.5, help="YuNet 检测置信度阈值（默认 0.5）")
    p.add_argument("--no-normalize", action="store_true", help="跳过头位归一化，仅抠绿+贴底居中")
    args = p.parse_args(argv)

    if not Path(args.src).is_file():
        sys.stderr.write("源文件不存在: %s\n" % args.src)
        return 2
    try:
        r = process(args.src, args.out,
                    corner=args.corner, h_slack=args.h_slack, sv_slack=args.sv_slack,
                    similarity=args.similarity, blend=args.blend, despill_factor=args.despill_factor, sv_floor=args.sv_floor,
                    use_grabcut=args.refine_grabcut,
                    grabcut_scale=args.grabcut_scale, grabcut_iters=args.grabcut_iters,
                    target_head_px=args.target_head_px,
                    normalize=not args.no_normalize, score_thr=args.score_thr)
    except (OSError, RuntimeError, cv2.error) as e:
        sys.stderr.write("处理失败: %s\n" % e)
        return 1
    print("OK: %s -> %s [%s] %s (level=%s, green BGR%s H[%d~%d], %s)" % (
        args.src, args.out, r["mode"], r["out_size"], r["level"],
        r["center"], r["lower"][0], r["upper"][0], r["info"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
