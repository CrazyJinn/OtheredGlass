# coding: utf-8
"""路径 B（推荐）：VoiceDesign → Clone，建立顾盈的可复用声音档案并生成目标台词。

流程：
  1. VoiceDesign 模型按 GU_YING_INSTRUCT 合成一段参考音频（固化顾盈音色）→ guying_ref.wav
  2. Base 模型用该参考构建可复用 voice_clone_prompt
  3. Base 模型用该 prompt 克隆出任意台词，音色一致（整章复用）

依据：06_角色美术 顾盈立绘（挑眉/玩味/慵懒 —— 成熟从容、似笑非笑、反撩高手）。
"""
import os

import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

# ── 配置 ──────────────────────────────────────────────
VOICE_DESIGN_PATH = "D:/model/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
BASE_PATH = "D:/model/Qwen3-TTS-12Hz-1.7B-Base"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

GU_YING_INSTRUCT = (
    "成熟女性，约28岁，中音略偏低、嗓音圆润；"
    "气定神闲、似笑非笑的玩味腔调，从容笃定中暗藏锐利；"
    "是被撩也能反撩的对手，松弛慵懒却始终掌控节奏；"
    "语速不疾不徐，尾音常带一丝戏谑的上扬；表面温和随性，底子自信而漫不经心。"
)

# 参考句：自编，贴合顾盈慵懒玩味气质，长度足够固化音色（不直接对外）
REF_TEXT = "哟，这才醒啊——咖啡都凉了，我可没等你。"
# 目标台词：剧本原句（sec00_酒店醒来，顾盈·玩味）
TARGET_LINE = "这衬衫，我穿可比你顺眼。"
# ─────────────────────────────────────────────────────


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── 1. VoiceDesign 固化顾盈音色为参考音频 ──
    design_model = Qwen3TTSModel.from_pretrained(
        VOICE_DESIGN_PATH, device_map="cuda:0",
        dtype=torch.bfloat16, attn_implementation="sdpa",
    )
    ref_wavs, sr = design_model.generate_voice_design(
        text=REF_TEXT, language="Chinese", instruct=GU_YING_INSTRUCT,
    )
    ref_path = os.path.join(OUT_DIR, "guying_ref.wav")
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
    out = os.path.join(OUT_DIR, "guying_line.wav")
    sf.write(out, wavs[0], sr)
    print(f"[3/3] cloned line -> {out}")

    print("\n后续：把 voice_clone_prompt 缓存起来，对顾盈的所有台词复用第 3 步即可。")


if __name__ == "__main__":
    main()
