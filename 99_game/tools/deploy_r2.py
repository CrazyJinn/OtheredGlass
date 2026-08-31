#!/usr/bin/env python
"""把 Web 导出产物（含章包）上传到 Cloudflare R2 桶（S3 兼容 API，boto3）。

传输压缩规则（关键约定）：
  - index.wasm / index.pck：brotli 压缩后上传并设 Content-Encoding: br——这两者由
    浏览器侧（index.js fetch）加载，会按 Accept-Encoding 协商自动解压，37MB wasm 实收 ~8MB；
  - 章包 <stem>.pck：**原样上传不压缩**——由 Godot HTTPRequest（ChapterPackLoader）
    下载，其自动解压只支持 gzip，收到 br 会坏数据；
  - 其余小文件原样。
全部对象带 Cache-Control: no-cache（覆盖更新同名，靠 ETag revalidate，304 很快）。

前置（一次性）：
  1. Cloudflare Dashboard → R2 → Manage R2 API Tokens → Create API Token
     （Object Read & Write，限定目标桶），得到 Access Key ID / Secret Access Key；
  2. 凭证写入项目根 settings.json（与 neo4j/ofoxai 凭证同处，已 gitignore）：
     cloudflare_account_id / cloudflare_access_key_id / cloudflare_secret
     （可选 cloudflare_bucket；缺省时自动 list_buckets——单桶直用，多桶列出报错）
     环境变量 R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_BUCKET 优先级更高；
  3. pip install boto3
  4. 桶需开启 r2.dev Public Access，游玩地址 = https://pub-<hash>.r2.dev/index.html

用法：
  python tools/deploy_r2.py [--dir <导出目录>] [--dry-run]
默认导出目录 = export_presets.cfg 的 Web preset 导出目录。
退码：0 成功 / 1 失败。
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / "99_game"
SETTINGS = ROOT / "settings.json"  # 项目根凭证（neo4j/ofoxai/cloudflare 同处，已 gitignore）

# Content-Type 表（缺省 application/octet-stream）
CT = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript",
    ".wasm": "application/wasm",
    ".png": "image/png",
    ".json": "application/json",
}


def load_config() -> dict:
    settings = {}
    if SETTINGS.exists():
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    cfg = {
        "account_id": os.environ.get("R2_ACCOUNT_ID", settings.get("cloudflare_account_id", "")),
        "access_key_id": os.environ.get("R2_ACCESS_KEY_ID", settings.get("cloudflare_access_key_id", "")),
        "secret_access_key": os.environ.get("R2_SECRET_ACCESS_KEY", settings.get("cloudflare_secret", "")),
        "bucket": os.environ.get("R2_BUCKET", settings.get("cloudflare_bucket", "")),
    }
    missing = [k for k, v in cfg.items() if not v and k != "bucket"]
    if missing:
        sys.stderr.write(
            f"缺少 R2 配置 {missing}：在 {SETTINGS} 补 cloudflare_account_id / "
            "cloudflare_access_key_id / cloudflare_secret（或设环境变量 R2_*）\n"
            "（Dashboard → R2 → Manage R2 API Tokens 创建 Object Read & Write token）\n")
        sys.exit(1)
    return cfg


def web_export_dir() -> Path:
    """手写轻量解析（configparser 吃不下 Godot cfg 里 PowerShell 多行脚本的值）。"""
    import re
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
    sys.exit("export_presets.cfg 无 Web preset export_path")


def packs_enabled() -> bool:
    """读 ChapterPackLoader 的分包总开关（与 publish_web.py 同源，避免配置漂移）。"""
    import re
    src = (GAME / "scripts" / "autoload" / "ChapterPackLoader.gd").read_text(encoding="utf-8")
    m = re.search(r"WEB_PACKS_ENABLED\s*:=\s*(true|false)", src)
    return bool(m and m.group(1) == "true")


def main() -> int:
    ap = argparse.ArgumentParser(description="上传 Web 产物到 R2")
    ap.add_argument("--dir", type=Path, default=None, help="导出目录（默认 Web preset 目录）")
    ap.add_argument("--dry-run", action="store_true", help="只打印上传计划")
    args = ap.parse_args()

    src_dir = args.dir or web_export_dir()
    if not src_dir.exists():
        sys.exit(f"导出目录不存在：{src_dir}（先跑 tools/publish_web.py）")

    files = sorted(f for f in src_dir.iterdir() if f.is_file())
    if not files:
        sys.exit(f"目录为空：{src_dir}")

    try:
        import brotli
    except ImportError:
        sys.exit("缺 brotli：pip install brotli")

    # 上传计划：name -> (本地路径, 是否br压缩)；全量模式跳过章包（游戏端不会请求）
    plan = {}
    packs = packs_enabled()
    for f in files:
        if not packs and f.suffix == ".pck" and f.name != "index.pck":
            print(f"  跳过章包 {f.name}（WEB_PACKS_ENABLED=false 全量主包模式）")
            continue
        browser_side = f.name in ("index.wasm", "index.pck")  # 浏览器加载，可 br
        plan[f.name] = (f, browser_side)

    print(f"目标：{src_dir} -> R2 桶（{len(plan)} 个对象）")
    for name, (f, br) in plan.items():
        size = f.stat().st_size
        print(f"  {name:44s} {size / 1048576:7.2f} MB{'（br 压缩后上传）' if br else ''}")

    if args.dry_run:
        print("dry-run 结束，未上传")
        return 0

    try:
        import boto3
    except ImportError:
        sys.exit("缺 boto3：pip install boto3")

    cfg = load_config()
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['account_id']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_access_key"],
        region_name="auto",
    )
    if not cfg["bucket"]:
        names = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
        if len(names) == 1:
            cfg["bucket"] = names[0]
            print(f"未配置桶名，自动选用唯一桶：{names[0]}")
        else:
            sys.exit(f"账号下有 {len(names)} 个桶 {names}，请在 settings.json 加 cloudflare_bucket 指定")

    for name, (f, br) in plan.items():
        body = f.read_bytes()
        extra = {"ContentType": CT.get(f.suffix.lower(), "application/octet-stream"),
                 "CacheControl": "no-cache"}
        if br:
            print(f"压缩 {name} …", end="", flush=True)
            body = brotli.compress(body, quality=5)
            extra["ContentEncoding"] = "br"
            print(f" {len(body) / 1048576:.2f} MB")
        s3.put_object(Bucket=cfg["bucket"], Key=name, Body=body, **extra)
        print(f"已上传 {name}")

    print("\n完成。游玩地址：https://pub-<你的r2.dev域名>/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
