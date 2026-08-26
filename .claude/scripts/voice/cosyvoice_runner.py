"""CosyVoice3 批量 clone（section-voice-publisher 的 CosyVoice 后端，env/.venv-cosyvoice 跑）。

全章配音：按角色 ref_audio（Qwen VoiceDesign 出，锁音色）+ say.emotion（→ instruct 映射）→
CosyVoice3 inference_instruct2 逐句 clone。

**env/.venv-cosyvoice（项目内 venv, Python 3.10 + transformers 4.51）跑**，不与 Qwen 的 env/.venv-qwen（4.57）冲突。
section-voice-publisher 用 env/.venv-cosyvoice/Scripts/python.exe 调本脚本。

前置：
  - env/vendor/CosyVoice（项目根，cosyvoice 包 vendored）+ third_party/Matcha-TTS
  - 模型路径 + CosyVoice 仓库：from paths import（读 settings.json，不硬编码）
  - env/.venv-cosyvoice（transformers 4.51 + onnxruntime-gpu + cosyvoice 依赖）
  - ref_audio（角色 ref，由 voice_clone_runner ensure-ref 用 Qwen VoiceDesign 出，env/.venv-qwen）

任务 tasks.json（voice_bundler collect_tasks 产，含 emotion）：{char: [{key, text, emotion, ...}]}
emotion → instruct 映射：emotion_instruct.json（同目录）
输出（母带）：out_dir/<char>/<key>.wav（默认 15_声音/<char>/，按角色名整理；
key 同 make_voice_key）。运行时副本由 voice_bundler.py sync 拷贝到 99_game/assets/voices/。

子命令：`publish`（逐句 clone，下游配音用）。多候选流程的试听（audition）已迁移到
voice_clone_runner.py（Qwen3 Base Voice Clone，env/.venv-qwen）——本脚本只服务下游配音。
"""
import argparse
import json
import os
import sys

# 脚本所在目录自动在 sys.path[0]，无需 insert 即可 `from paths import`；
# CosyVoice 仓库与 Matcha-TTS 的 import 路径由调用方注入 PYTHONPATH：
#   PYTHONPATH="$(python .claude/scripts/voice/paths.py --pythonpath)" <venv-python> cosyvoice_runner.py ...
from paths import COSYVOICE_MODEL

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

MODEL_DIR = COSYVOICE_MODEL  # from paths（已 import）
EMOTION_INSTRUCT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emotion_instruct.json")
DEFAULT_INSTRUCT = "用自然的语气说"
INSTRUCT_PREFIX = "You are a helpful assistant. "
INSTRUCT_SUFFIX = "<|endofprompt|>"


def load_emotion_instruct(path=EMOTION_INSTRUCT_PATH) -> dict:
    if os.path.exists(path):
        return json.loads(open(path, encoding="utf-8").read())
    return {}


def ensure_ref_16k(ref_path: str) -> str:
    """CosyVoice frontend 要 16k ref；源 ref（Qwen VoiceDesign 24k）重采样落同目录 _16k.wav。

    源文件名已以 _16k.wav 结尾（多候选流程的正式 ref / 候选 ref 均直接存 16k）时直接
    返回原路径，不产 <base>_16k_16k.wav 冗余副本；存量 24k ref 照旧走重采样。
    """
    if ref_path.endswith("_16k.wav"):
        return ref_path
    base, _ = os.path.splitext(ref_path)
    out_path = f"{base}_16k.wav"
    if os.path.exists(out_path):
        return out_path
    wav, sr = torchaudio.load(ref_path)
    if sr != 16000:
        wav = torchaudio.functional.resample(wav, sr, 16000)
    torchaudio.save(out_path, wav, 16000)
    return out_path


def publish(tasks: dict, profiles: dict, out_dir, keys=None) -> dict:
    """按角色批量 CosyVoice clone（母带落 out_dir/<char>/<key>.wav）。

    tasks: {char: [{key, text, emotion, ...}]}（voice_bundler tasks-from-section 产 + skill 填 emotion）
    profiles: {char: {ref_audio_path, ...}}（VoiceDesign 字典，至少含 ref_audio_path）
    keys: 可选键过滤（逗号分隔列表）——单句/批量重生成只跑指定句；缺省 = tasks 全部。
    返回 {produced: {char: [wav_path]}, skipped: [char], failed: [{char, key, error}]}。
    逐句 try/except：单句推理失败记入 failed 不炸整批（bind-audio 只 bind 成功句，失败句保持
    missing/rejected 下轮重挑）。
    """
    emotion_map = load_emotion_instruct()
    model = AutoModel(model_dir=MODEL_DIR)
    os.makedirs(out_dir, exist_ok=True)

    key_set = {k.strip() for k in keys if k.strip()} if keys else None
    produced = {}
    skipped = []
    failed = []
    for char, items in tasks.items():
        profile = profiles.get(char)
        ref_path = profile.get("ref_audio_path") if profile else None
        if not ref_path or not os.path.exists(ref_path):
            print(f"[skip] {char}: 无 ref_audio_path 或文件不存在（先跑 voice_clone_runner ensure-ref）")
            skipped.append(char)
            continue
        ref_16k = ensure_ref_16k(ref_path)

        char_dir = os.path.join(out_dir, char)
        os.makedirs(char_dir, exist_ok=True)
        paths = []
        for it in items:
            if key_set is not None and it.get("key") not in key_set:
                continue
            try:
                emotion = it.get("emotion", "平静")
                emotion_inst = emotion_map.get(emotion, DEFAULT_INSTRUCT)
                instruct = f"{INSTRUCT_PREFIX}{emotion_inst}。{INSTRUCT_SUFFIX}"
                for j in model.inference_instruct2(it["text"], instruct, ref_16k, stream=False):
                    out = os.path.join(char_dir, f"{it['key']}.wav")
                    torchaudio.save(out, j["tts_speech"], model.sample_rate)
                    paths.append(out)
            except Exception as e:  # 单句失败不炸整批
                failed.append({"char": char, "key": it.get("key"), "error": str(e)})
                print(f"[fail] {char}/{it.get('key')}: {e}")
        produced[char] = paths
        print(f"[ok] {char}: {len(paths)} wav -> {char_dir}")
    return {"produced": produced, "skipped": skipped, "failed": failed}


def main():
    ap = argparse.ArgumentParser(description="CosyVoice3 批量 clone（venv，配音链后端）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_pub = sub.add_parser("publish", help="按角色批量 CosyVoice clone（消费 tasks.json + profiles.json）")
    p_pub.add_argument("tasks", help="voice_bundler.py tasks-from-section 产出的 tasks.json（skill 已填 emotion）")
    p_pub.add_argument("--profiles", required=True, help="{char: VoiceDesign dict} JSON（至少 ref_audio_path）")
    p_pub.add_argument("--out-dir", default="15_声音", help="母带根目录（写 <out-dir>/<char>/<key>.wav；运行时副本走 voice_bundler sync）")
    p_pub.add_argument("--keys", default=None, help="只生成指定 key（逗号分隔，单句/批量重生成用；缺省=全部）")
    p_pub.set_defaults(_mode="publish")

    args = ap.parse_args()
    if args._mode == "publish":
        tasks = json.loads(open(args.tasks, encoding="utf-8").read())
        profiles = json.loads(open(args.profiles, encoding="utf-8").read())
        keys = args.keys.split(",") if args.keys else None
        result = publish(tasks, profiles, args.out_dir, keys=keys)
        total = sum(len(v) for v in result["produced"].values())
        print(f"[publish] produced={total} wav, skipped={result['skipped']}, failed={len(result['failed'])}")
        if result["failed"]:
            for f in result["failed"]:
                print(f"  failed: {f['char']}/{f['key']}: {f['error']}")
            sys.exit(1)


if __name__ == "__main__":
    main()
