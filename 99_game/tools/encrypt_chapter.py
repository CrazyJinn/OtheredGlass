#!/usr/bin/env python
"""加密运行时剧本 JSON（AES-256-CBC + PKCS7 + base64 + OGCRYPT1 magic）。

与 Godot 运行时 scripts/util/ScriptCipher.gd 共享 KEY/IV/magic，两端务必一致。
密文为文本文件：首行 magic，后续 base64 密文。ChapterLoader 检测 magic 头自动解密，
明文文件原样加载（桌面/开发期兼容）。

用途：Web 发布前给剧本 JSON 套壳，挡自动解包工具直接拿到明文剧本。
⚠️ 挡不住逆向（密钥在运行时可见），属防御层级而非安全边界。

CLI: encrypt_chapter.py <src.json> <dest.json>
退码：0 成功 / 1 IO或加解密失败 / 2 参数错（与 validate_chapter.py 对齐）
依赖：cryptography（pip install -r tools/requirements.txt）
"""
import base64
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ImportError:
    sys.stderr.write("缺少依赖：pip install -r tools/requirements.txt (cryptography)\n")
    raise

# 32 字节 AES-256 密钥 —— 与 99_game/scripts/util/ScriptCipher.gd 的 KEY 完全一致
KEY = b"ProxyLove_2024_ScriptKey_v1!!"
# 16 字节 CBC IV —— 与 ScriptCipher.gd 的 IV 完全一致
IV = b"ProxyLoveIV01"
MAGIC = b"OGCRYPT1\n"


def encrypt_bytes(data: bytes) -> bytes:
    """AES-256-CBC + PKCS7(128bit block) + base64，前置 magic 头。"""
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(data) + padder.finalize()
    encryptor = Cipher(algorithms.AES(KEY), modes.CBC(IV)).encryptor()
    ct = encryptor.update(padded) + encryptor.finalize()
    return MAGIC + base64.b64encode(ct) + b"\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write("用法: python encrypt_chapter.py <src.json> <dest.json>\n")
        return 2
    src, dest = Path(argv[1]), Path(argv[2])
    try:
        data = src.read_bytes()
        enc = encrypt_bytes(data)
        # 支持 src == dest（原地加密）：先读完再写
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(enc)
    except OSError as e:
        sys.stderr.write(f"加密失败: {e}\n")
        return 1
    print(f"OK: {src} -> {dest} ({len(data)}B -> {len(enc)}B)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
