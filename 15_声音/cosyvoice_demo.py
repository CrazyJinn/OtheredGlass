# coding: utf-8
"""方案 demo：Qwen3-TTS VoiceDesign 出声音设计 → CosyVoice 3.0 instruct2 clone（情绪可控）。

为什么换 CosyVoice：Qwen3-TTS Base clone 不支持情绪 instruct；CosyVoice3 的 inference_instruct2
支持「参考音频(自定义音色) + instruct(情绪/语速/方言)」组合——正好补 Qwen 的短板。

流程：
  1. ref_audio = 陆择_ref.wav（已由 Qwen VoiceDesign 按 VoiceProfile.instruct 生成，24kHz）
     → 重采样 16kHz（CosyVoice 要求）
  2. CosyVoice3 inference_instruct2(台词, instruct=陆择音色基底+情绪, ref_audio) → 三情绪 wav

前置：
  - 陆择_ref.wav 存在（15_声音/output/陆择_ref.wav，由 luze_voice_build.py / voice_clone_runner 生成）
  - Fun-CosyVoice3-0.5B 模型下完整（D:/model/Fun-CosyVoice3-0.5B，无 .incomplete）
  - cosyvoice 包（D:/CosyVoice，已 clone）

输出：15_声音/output/cosyvoice_test/陆择_{情绪}.wav（不进游戏，纯试听）
"""
import os
import sys

# cosyvoice 包是本地仓库（不在 PyPI），sys.path 指向 clone 的仓库
COSYVOICE_REPO = "D:/CosyVoice"
sys.path.insert(0, COSYVOICE_REPO)
sys.path.insert(0, os.path.join(COSYVOICE_REPO, "third_party", "Matcha-TTS"))  # matcha 模块（flow_matching 依赖）

import torch
import torchaudio
import soundfile as _sf

# torchaudio 2.11 的 load/save 强制走 torchcodec（Windows 无 ffmpeg DLL → libtorchcodec 加载失败），
# monkey-patch 成 soundfile（纯库无外部依赖）。CosyVoice 内部 load_wav 也走这个 patch。
def _sf_load(filepath, **kwargs):
    d, sr = _sf.read(filepath, always_2d=True)   # (T, ch) numpy
    return torch.from_numpy(d).float().T, sr     # (ch, T) tensor

def _sf_save(filepath, src, sample_rate, **kwargs):
    arr = src.detach().cpu().numpy()
    _sf.write(filepath, arr.T if arr.ndim == 2 else arr, sample_rate)

torchaudio.load = _sf_load
torchaudio.save = _sf_save

from cosyvoice.cli.cosyvoice import AutoModel

MODEL_DIR = "D:/model/Fun-CosyVoice3-0.5B"
REF_24K = "15_声音/output/陆择_ref.wav"          # Qwen VoiceDesign 产（24kHz）
REF_16K = "15_声音/output/luze_ref_16k.wav"      # CosyVoice 要 16kHz
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "cosyvoice_test")

TEST_LINE = "行吧，算我倒霉。"

# CosyVoice3 instruct 格式：'You are a helpful assistant. <指令><|endofprompt|>'
# 情绪用中文指令（example.py 用「请用广东话表达」证实中文 instruct 可行）
EMOTIONS = {
    "高兴": "用开心愉悦、带着真心笑意的语气说",
    "悲伤": "用悲伤低沉、强忍哽咽、语速放缓的语气说",
    "震惊": "用震惊意外、短促倒吸气的语气说",
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # 1. ref 重采样到 16kHz（CosyVoice frontend 的 load_wav 要求 16kHz）
    wav, sr = torchaudio.load(REF_24K, backend="soundfile")  # 显式 soundfile，绕过 torchaudio 2.11 的 torchcodec 默认
    if sr != 16000:
        wav = torchaudio.functional.resample(wav, sr, 16000)
    torchaudio.save(REF_16K, wav, 16000)
    print(f"[ref] {REF_24K}({sr}Hz) -> {REF_16K}(16000Hz)")

    # 2. 加载 CosyVoice3
    model = AutoModel(model_dir=MODEL_DIR)
    print(f"[model] loaded, sample_rate={model.sample_rate}")

    # 3. 三情绪 instruct2 clone（ref 锁音色，instruct 控情绪）
    for emo, inst in EMOTIONS.items():
        instruct = f"You are a helpful assistant. {inst}。<|endofprompt|>"
        for j in model.inference_instruct2(TEST_LINE, instruct, REF_16K, stream=False):
            out = os.path.join(OUT_DIR, f"陆择_{emo}.wav")
            torchaudio.save(out, j["tts_speech"], model.sample_rate)
            print(f"[ok] {emo}: {out}")
    print(f"\n试听目录：{OUT_DIR}")


if __name__ == "__main__":
    main()
