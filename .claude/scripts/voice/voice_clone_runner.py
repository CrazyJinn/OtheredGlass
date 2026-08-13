"""Qwen VoiceDesign ref 生成器（voice-publisher 的 ref 来源，系统 python 3.14 跑）。

全章配音的 ref_audio 由本脚本用 Qwen3-TTS VoiceDesign 合成（按 VoiceProfile.instruct）。
CosyVoice clone（[cosyvoice_runner.py](cosyvoice_runner.py)，venv 跑）消费这些 ref_audio。

**系统 Python 3.14（Qwen3-TTS）跑**；CosyVoice clone 在 venv（D:/cosyvoice_env, Python 3.10）跑——
两个环境分离（transformers 4.51 vs 4.57 冲突）。voice-publisher 编排两套 python。

> 本脚本只负责「设计音色 → 出 ref_audio」。clone（逐句台词 → wav）由 cosyvoice_runner 做。
> 早期版本的 Qwen Base clone（.pt + generate_voice_clone）已废弃——CosyVoice 替代（支持情绪 instruct）。

前置：
  - Qwen3-TTS VoiceDesign 模型 D:/model/Qwen3-TTS-12Hz-1.7B-VoiceDesign
  - VoiceProfile（instruct + ref_text + ref_audio_path）

输出：ref_audio 落 VoiceProfile.ref_audio_path（如 15_声音/output/<char>_ref.wav，24kHz），CosyVoice 用。
"""
import argparse
import json
import os

import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

VOICE_DESIGN_PATH = os.environ.get("QWEN_VOICE_DESIGN_PATH", "D:/model/Qwen3-TTS-12Hz-1.7B-VoiceDesign")


def load_design_model(path=VOICE_DESIGN_PATH, device="cuda:0") -> Qwen3TTSModel:
    return Qwen3TTSModel.from_pretrained(
        path, device_map=device, dtype=torch.bfloat16, attn_implementation="sdpa",
    )


def ensure_ref(voice_profile: dict, design_model=None, device="cuda:0") -> str:
    """确保角色 ref_audio 就绪：ref_audio_path 文件存在则复用，否则 VoiceDesign 合成并写盘。

    voice_profile 字段：instruct / ref_text / ref_audio_path
    返回 ref_audio 路径。
    """
    ref_audio_path = voice_profile.get("ref_audio_path")
    if ref_audio_path and os.path.exists(ref_audio_path):
        return ref_audio_path
    if design_model is None:
        design_model = load_design_model(device=device)
    instruct = voice_profile["instruct"]
    ref_text = voice_profile["ref_text"]
    ref_wavs, sr = design_model.generate_voice_design(text=ref_text, language="Chinese", instruct=instruct)
    if ref_audio_path:
        os.makedirs(os.path.dirname(ref_audio_path) or ".", exist_ok=True)
        sf.write(ref_audio_path, ref_wavs[0], sr)
    return ref_audio_path


def ensure_refs(profiles: dict, device="cuda:0") -> dict:
    """批量 ensure_ref：profiles={char: VoiceProfile}。复用 design_model（整批加载一次）。

    跳过缺 instruct/ref_text 的角色（警告不阻断）。
    返回 {char: ref_audio_path}。
    """
    design_model = None
    produced = {}
    for char, profile in profiles.items():
        if not profile.get("instruct") or not profile.get("ref_text"):
            print(f"[skip] {char}: 缺 instruct/ref_text")
            continue
        ref_path = profile.get("ref_audio_path")
        if ref_path and os.path.exists(ref_path):
            print(f"[reuse] {char}: {ref_path}")
            produced[char] = ref_path
            continue
        if design_model is None:
            design_model = load_design_model(device=device)
        ref = ensure_ref(profile, design_model=design_model, device=device)
        produced[char] = ref
        print(f"[design] {char}: {ref}")
    return produced


def main():
    ap = argparse.ArgumentParser(description="Qwen VoiceDesign ref 生成器（voice-publisher ref 来源，系统 python）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ref = sub.add_parser("ensure-ref", help="确保各角色 ref_audio 就绪（复用或 VoiceDesign 合成）")
    p_ref.add_argument("--profiles", required=True, help="{char: VoiceProfile dict} JSON")
    p_ref.add_argument("--device", default="cuda:0")
    p_ref.set_defaults(_mode="ensure-ref")

    args = ap.parse_args()
    if args._mode == "ensure-ref":
        profiles = json.loads(open(args.profiles, encoding="utf-8").read())
        result = ensure_refs(profiles, device=args.device)
        print(f"[ensure-ref] {len(result)} 角色就绪")


if __name__ == "__main__":
    main()
