# coding: utf-8
"""路径 B（推荐）：VoiceDesign → Clone，建立陆择的可复用声音档案并生成目标台词。

流程：
  1. VoiceDesign 模型按 LU_ZE_INSTRUCT 合成一段参考音频（固化陆择音色）→ luze_ref.wav
  2. Base 模型用该参考构建可复用 voice_clone_prompt
  3. Base 模型用该 prompt 克隆出任意台词，音色一致（整章复用）

依据：06_角色美术 陆择立绘（轻佻/沉吟 —— 玩世不恭、调侃为壳、慵懒）。
"""
import os

import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

# ── 配置 ──────────────────────────────────────────────
VOICE_DESIGN_PATH = "D:/model/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
BASE_PATH = "D:/model/Qwen3-TTS-12Hz-1.7B-Base"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

LU_ZE_INSTRUCT = (
    "青年男性，20余岁，中低音略带沙哑；"
    "玩世不恭的调侃腔调，嘴角噙笑、语气松弛慵懒，"
    "像用渣男口头话把真实情绪裹起来；"
    "语速不快，尾音常带一丝玩味的上扬；表面从容，底下偶有一沉。"
)

# 参考句：短、语气贴近角色，用于固化音色（不直接对外）
REF_TEXT = "嗯……这床是真不行，我都怕它散架。"
# 目标台词
TARGET_LINE = "没办法。主要是这床不行——再来几次，怕是要塌。"
# ─────────────────────────────────────────────────────


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── 1. VoiceDesign 固化陆择音色为参考音频 ──
    design_model = Qwen3TTSModel.from_pretrained(
        VOICE_DESIGN_PATH, device_map="cuda:0",
        dtype=torch.bfloat16, attn_implementation="sdpa",
    )
    ref_wavs, sr = design_model.generate_voice_design(
        text=REF_TEXT, language="Chinese", instruct=LU_ZE_INSTRUCT,
    )
    ref_path = os.path.join(OUT_DIR, "luze_ref.wav")
    sf.write(ref_path, ref_wavs[0], sr)
    print(f"[1/3] voice-design reference -> {ref_path}")

    # ── 2. Base 模型构建可复用 clone prompt ──
    clone_model = Qwen3TTSModel.from_pretrained(
        BASE_PATH, device_map="cuda:0",
        dtype=torch.bfloat16, attn_implementation="sdpa",
    )
    voice_clone_prompt = clone_model.create_voice_clone_prompt(
        ref_audio=(ref_wavs[0], sr),   # 也可传 ref_path 文件路径
        ref_text=REF_TEXT,
    )
    print("[2/3] voice_clone_prompt built")

    # ── 3. 用该声音克隆目标台词 ──
    wavs, sr = clone_model.generate_voice_clone(
        text=TARGET_LINE, language="Chinese",
        voice_clone_prompt=voice_clone_prompt,
    )
    out = os.path.join(OUT_DIR, "luze_line.wav")
    sf.write(out, wavs[0], sr)
    print(f"[3/3] cloned line -> {out}")

    print("\n后续：把 voice_clone_prompt 缓存起来，对陆择的所有台词复用第 3 步即可。")


if __name__ == "__main__":
    main()
