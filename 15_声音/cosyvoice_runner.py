"""CosyVoice3 批量 clone（voice-publisher 的 CosyVoice 后端，venv 跑）。

全章配音：按角色 ref_audio（Qwen VoiceDesign 出，锁音色）+ say.emotion（→ instruct 映射）→
CosyVoice3 inference_instruct2 逐句 clone。

**venv（D:/cosyvoice_env, Python 3.10 + transformers 4.51）跑**，不与 Qwen 的系统 3.14 环境冲突。
voice-publisher 用 D:/cosyvoice_env/Scripts/python.exe 调本脚本。

前置：
  - D:/CosyVoice（cosyvoice 包）+ third_party/Matcha-TTS（matcha）已 clone
  - D:/model/Fun-CosyVoice3-0.5B 模型
  - venv D:/cosyvoice_env（transformers 4.51 + onnxruntime-gpu + cosyvoice 依赖）
  - ref_audio（角色 ref，由 voice_clone_runner ensure-ref 用 Qwen VoiceDesign 出，系统 python）

任务 tasks.json（voice_bundler collect_tasks 产，含 emotion）：{char: [{key, text, emotion, ...}]}
emotion → instruct 映射：15_声音/emotion_instruct.json
输出：99_game/assets/voices/<key>.wav（key 同 make_voice_key，三处对齐不变）
"""
import argparse
import json
import os
import sys

COSYVOICE_REPO = os.environ.get("COSYVOICE_REPO", "D:/CosyVoice")
sys.path.insert(0, COSYVOICE_REPO)
sys.path.insert(0, os.path.join(COSYVOICE_REPO, "third_party", "Matcha-TTS"))

import torch
import torchaudio
import soundfile as _sf

# torchaudio 2.11 强制 torchcodec（缺 ffmpeg DLL），monkey-patch 用 soundfile（CosyVoice 内部 load_wav 也走此 patch）
def _sf_load(fp, **kw):
    d, sr = _sf.read(fp, always_2d=True)
    return torch.from_numpy(d).float().T, sr

def _sf_save(fp, src, sr, **kw):
    a = src.detach().cpu().numpy()
    _sf.write(fp, a.T if a.ndim == 2 else a, sr)

torchaudio.load = _sf_load
torchaudio.save = _sf_save

from cosyvoice.cli.cosyvoice import AutoModel

MODEL_DIR = os.environ.get("COSYVOICE_MODEL", "D:/model/Fun-CosyVoice3-0.5B")
EMOTION_INSTRUCT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emotion_instruct.json")
DEFAULT_INSTRUCT = "用自然的语气说"
INSTRUCT_PREFIX = "You are a helpful assistant. "
INSTRUCT_SUFFIX = "<|endofprompt|>"


def load_emotion_instruct(path=EMOTION_INSTRUCT_PATH) -> dict:
    if os.path.exists(path):
        return json.loads(open(path, encoding="utf-8").read())
    return {}


def ensure_ref_16k(ref_path: str) -> str:
    """CosyVoice frontend 要 16k ref；源 ref（Qwen VoiceDesign 24k）重采样落同目录 _16k.wav。"""
    base, _ = os.path.splitext(ref_path)
    out_path = f"{base}_16k.wav"
    if os.path.exists(out_path):
        return out_path
    wav, sr = torchaudio.load(ref_path)
    if sr != 16000:
        wav = torchaudio.functional.resample(wav, sr, 16000)
    torchaudio.save(out_path, wav, 16000)
    return out_path


def publish(tasks: dict, profiles: dict, out_dir) -> dict:
    """按角色批量 CosyVoice clone。

    tasks: {char: [{key, text, emotion, ...}]}（voice_bundler collect_tasks 产）
    profiles: {char: {ref_audio_path, ...}}（VoiceProfile 字典，至少含 ref_audio_path）
    返回 {produced: {char: [wav_path]}, skipped: [char]}。
    """
    emotion_map = load_emotion_instruct()
    model = AutoModel(model_dir=MODEL_DIR)
    os.makedirs(out_dir, exist_ok=True)

    produced = {}
    skipped = []
    for char, items in tasks.items():
        profile = profiles.get(char)
        ref_path = profile.get("ref_audio_path") if profile else None
        if not ref_path or not os.path.exists(ref_path):
            print(f"[skip] {char}: 无 ref_audio_path 或文件不存在（先跑 voice_clone_runner ensure-ref）")
            skipped.append(char)
            continue
        ref_16k = ensure_ref_16k(ref_path)

        paths = []
        for it in items:
            emotion = it.get("emotion", "平静")
            emotion_inst = emotion_map.get(emotion, DEFAULT_INSTRUCT)
            instruct = f"{INSTRUCT_PREFIX}{emotion_inst}。{INSTRUCT_SUFFIX}"
            for j in model.inference_instruct2(it["text"], instruct, ref_16k, stream=False):
                out = os.path.join(out_dir, f"{it['key']}.wav")
                torchaudio.save(out, j["tts_speech"], model.sample_rate)
                paths.append(out)
        produced[char] = paths
        print(f"[ok] {char}: {len(paths)} wav -> {out_dir}")
    return {"produced": produced, "skipped": skipped}


def main():
    ap = argparse.ArgumentParser(description="CosyVoice3 批量 clone（venv，voice-publisher 后端）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_pub = sub.add_parser("publish", help="按角色批量 CosyVoice clone（消费 tasks.json + profiles.json）")
    p_pub.add_argument("tasks", help="voice_bundler.py tasks 产出的 tasks.json（含 emotion）")
    p_pub.add_argument("--profiles", required=True, help="{char: VoiceProfile dict} JSON（至少 ref_audio_path）")
    p_pub.add_argument("--out-dir", default="99_game/assets/voices")
    p_pub.set_defaults(_mode="publish")

    args = ap.parse_args()
    if args._mode == "publish":
        tasks = json.loads(open(args.tasks, encoding="utf-8").read())
        profiles = json.loads(open(args.profiles, encoding="utf-8").read())
        result = publish(tasks, profiles, args.out_dir)
        total = sum(len(v) for v in result["produced"].values())
        print(f"[publish] produced={total} wav, skipped={result['skipped']}")


if __name__ == "__main__":
    main()
