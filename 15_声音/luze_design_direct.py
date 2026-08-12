# coding: utf-8
"""路径 A：用 VoiceDesign 模型直接生成陆择的单句台词（验证音色用，不可复用）。

每次调用都据 instruct 重新合成，适合"先听听这角色什么声"。
要跨台词复用音色，见 luze_voice_build.py。
"""
import os

import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

# ── 配置 ──────────────────────────────────────────────
VOICE_DESIGN_PATH = "D:/model/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# 陆择声音设计：依据 06_角色美术 立绘变体（轻佻/沉吟 —— 玩世不恭、调侃为壳、慵懒）
LU_ZE_INSTRUCT = (
    "青年男性，20余岁，中低音略带沙哑；"
    "玩世不恭的调侃腔调，嘴角噙笑、语气松弛慵懒，"
    "像用渣男口头话把真实情绪裹起来；"
    "语速不快，尾音常带一丝玩味的上扬；表面从容，底下偶有一沉。"
)

TARGET_LINE = "Hello World."
# ─────────────────────────────────────────────────────


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tts = Qwen3TTSModel.from_pretrained(
        VOICE_DESIGN_PATH,
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",   # Windows 装不上 flash_attention_2，改用 PyTorch 原生 SDPA
    )
    wavs, sr = tts.generate_voice_design(
        text=TARGET_LINE,
        language="Chinese",
        instruct=LU_ZE_INSTRUCT,
    )
    out = os.path.join(OUT_DIR, "luze_design_direct.wav")
    sf.write(out, wavs[0], sr)
    print(f"[ok] saved -> {out}")


if __name__ == "__main__":
    main()
