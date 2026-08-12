# coding: utf-8
"""诊断 CosyVoice 吐字不清：对比「自带真人 ref」vs「Qwen 合成陆择 ref」。

若自带 ref 清晰、陆择 ref 模糊 → Qwen 合成 ref 不适合做 CosyVoice clone（域不匹配）。
若都模糊 → CosyVoice/instruct 参数问题。
"""
import os
import sys

COSYVOICE_REPO = "D:/CosyVoice"
sys.path.insert(0, COSYVOICE_REPO)
sys.path.insert(0, os.path.join(COSYVOICE_REPO, "third_party", "Matcha-TTS"))

import torch
import torchaudio
import soundfile as _sf

def _sf_load(fp, **kw):
    d, sr = _sf.read(fp, always_2d=True)
    return torch.from_numpy(d).float().T, sr

def _sf_save(fp, src, sr, **kw):
    a = src.detach().cpu().numpy()
    _sf.write(fp, a.T if a.ndim == 2 else a, sr)

torchaudio.load = _sf_load
torchaudio.save = _sf_save

from cosyvoice.cli.cosyvoice import AutoModel

MODEL_DIR = "D:/model/Fun-CosyVoice3-0.5B"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "cosyvoice_test")
BUILTIN_REF = "D:/CosyVoice/asset/zero_shot_prompt.wav"
LUZE_REF = "15_声音/output/luze_ref_16k.wav"

model = AutoModel(model_dir=MODEL_DIR)
os.makedirs(OUT_DIR, exist_ok=True)

# 1. 自带真人 ref + 标准 zero_shot（example.py 用法，验证 CosyVoice 基本工作）
print("=== 1. 自带 ref + zero_shot（应清晰）===")
for j in model.inference_zero_shot(
    "收到好友从远方寄来的生日礼物。",
    "You are a helpful assistant.<|endofprompt|>希望你以后能够做的比我还好呦。",
    BUILTIN_REF, stream=False,
):
    torchaudio.save(f"{OUT_DIR}/diag_自带ref_zeroshot.wav", j["tts_speech"], model.sample_rate)
    print("saved diag_自带ref_zeroshot.wav")

# 2. 陆择(Qwen 合成)ref + zero_shot（无 instruct，验证 Qwen ref 能否 clone 清晰）
print("=== 2. 陆择 ref + zero_shot（无 instruct）===")
for j in model.inference_zero_shot(
    "行吧，算我倒霉。",
    "You are a helpful assistant.<|endofprompt|>嗯，这床是真不行。",
    LUZE_REF, stream=False,
):
    torchaudio.save(f"{OUT_DIR}/diag_陆择ref_zeroshot.wav", j["tts_speech"], model.sample_rate)
    print("saved diag_陆择ref_zeroshot.wav")

# 3. 自带真人 ref + instruct2 情绪（长文本，验证 instruct 本身不毁吐字）
print("=== 3. 自带 ref + instruct2 悲伤（验证 instruct）===")
for j in model.inference_instruct2(
    "收到好友从远方寄来的生日礼物。",
    "You are a helpful assistant. 用悲伤低沉的语气说。<|endofprompt|>",
    BUILTIN_REF, stream=False,
):
    torchaudio.save(f"{OUT_DIR}/diag_自带ref_instruct2_悲伤.wav", j["tts_speech"], model.sample_rate)
    print("saved diag_自带ref_instruct2_悲伤.wav")
