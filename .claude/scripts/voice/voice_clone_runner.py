"""Qwen VoiceDesign ref 生成器（char-voice-design 候选/试听 + section-voice-publisher ref 复用，env/.venv-qwen 跑）。

全章配音的 ref_audio 由本脚本用 Qwen3-TTS VoiceDesign 合成（按 VoiceDesign.instruct）。
CosyVoice clone（[cosyvoice_runner.py](cosyvoice_runner.py)，env/.venv-cosyvoice 跑）消费这些 ref_audio。

**env/.venv-qwen（项目内 venv, Python 3.14 + Qwen3-TTS）跑**；CosyVoice clone 在 env/.venv-cosyvoice（Python 3.10）跑——
两个 venv 分离（transformers 4.51 vs 4.57 冲突）。调用方 skill 编排两套 venv。

> 本脚本只负责「设计音色 → 出 ref_audio」。clone（逐句台词 → wav）由 cosyvoice_runner 做。
> 早期版本的 Qwen Base clone（.pt + generate_voice_clone）已废弃——CosyVoice 替代（支持情绪 instruct）。
>
> 子命令：`ensure-ref`（单 ref，下游配音用） / `design-candidates`（多候选流程第一步：
> 同一 instruct × N 次采样出候选 ref 24k + candidates.json manifest） / `audition`
> （第二步：Qwen3 Base Voice Clone 出每候选 3 情绪试听，情绪靠试听句文本语义自适应）。

前置：
  - Qwen VoiceDesign 模型路径：from paths import（QWEN_VOICE_DESIGN，读 settings.json）
  - VoiceDesign（instruct + ref_text + ref_audio_path）

输出：ref_audio 落 VoiceDesign.ref_audio_path（如 14_声音设计/<char>/<char>_ref.wav，24kHz），CosyVoice 用。
"""
import argparse
import json
import os

# 脚本所在目录自动在 sys.path[0]，无需 insert 即可 `from paths import`
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel
from paths import QWEN_VOICE_DESIGN as VOICE_DESIGN_PATH, QWEN_BASE, to_abs, to_rel

# 多候选流程默认值：每角色候选数 + 情绪试听文本（每情绪一句，语义与情绪匹配）。
# audition_texts 固化进 candidates.json（单一源），本脚本 audition 子命令消费——
# Qwen3 Base clone 无 instruct 通道，情绪演绎靠试听句文本语义自适应（README 明示能力）。
DEFAULT_COUNT = 3
DEFAULT_AUDITION_TEXTS = {
    "平静": "今天的会议记录我已经整理好了，放在你桌上了。",
    "高兴": "太好了，我们真的赢了，今晚我请大家吃饭！",
    "愤怒": "我说过多少次了，这份文件不能再出错！",
}


def load_design_model(path=VOICE_DESIGN_PATH, device="cuda:0") -> Qwen3TTSModel:
    return Qwen3TTSModel.from_pretrained(
        path, device_map=device, dtype=torch.bfloat16, attn_implementation="sdpa",
    )


def load_base_model(path=QWEN_BASE, device="cuda:0") -> Qwen3TTSModel:
    """Qwen3-TTS-Base（Voice Clone 用；与 VoiceDesign 是两个权重两个实例）。"""
    return Qwen3TTSModel.from_pretrained(
        path, device_map=device, dtype=torch.bfloat16, attn_implementation="sdpa",
    )


def ensure_ref(voice_design: dict, design_model=None, device="cuda:0") -> str:
    """确保角色 ref_audio 就绪：ref_audio_path 文件存在则复用，否则 VoiceDesign 合成并写盘。

    voice_design 字段：instruct / ref_text / ref_audio_path
    返回 ref_audio 路径。
    """
    ref_audio_path = voice_design.get("ref_audio_path")
    if ref_audio_path and os.path.exists(ref_audio_path):
        return ref_audio_path
    if design_model is None:
        design_model = load_design_model(device=device)
    instruct = voice_design["instruct"]
    ref_text = voice_design["ref_text"]
    ref_wavs, sr = design_model.generate_voice_design(text=ref_text, language="Chinese", instruct=instruct)
    if ref_audio_path:
        os.makedirs(os.path.dirname(ref_audio_path) or ".", exist_ok=True)
        sf.write(ref_audio_path, ref_wavs[0], sr)
    return ref_audio_path


def ensure_refs(profiles: dict, device="cuda:0") -> dict:
    """批量 ensure_ref：profiles={char: VoiceDesign}。复用 design_model（整批加载一次）。

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


def design_candidates(profiles: dict, device="cuda:0") -> dict:
    """按 profiles={char: {instruct, ref_text, candidates_dir, count?}} 出 N 个候选 ref + manifest。

    同一 instruct × N 次独立采样（库默认 do_sample 开）出 N 个音色变体；候选 wav 已存在
    即跳过（断点续跑）。写 candidates_dir/candidates.json：候选 ref（24kHz 原生，
    设计阶段不产 16k）+ audition_texts 常量（单一源）。情绪试听由本脚本 audition
    子命令（Qwen3 Base clone）接续。
    返回 {char: manifest 相对路径}。
    """
    design_model = None
    manifests = {}
    for char, profile in profiles.items():
        if not profile.get("instruct") or not profile.get("ref_text"):
            print(f"[skip] {char}: 缺 instruct/ref_text")
            continue
        instruct, ref_text = profile["instruct"], profile["ref_text"]
        count = int(profile.get("count", DEFAULT_COUNT))
        cand_dir = to_abs(profile["candidates_dir"])
        os.makedirs(cand_dir, exist_ok=True)

        entries = []  # [{key, ref(24k 原生)}]
        todo = []
        for i in range(1, count + 1):
            key = f"c{i}"
            ref = os.path.join(cand_dir, f"{char}_{key}_ref.wav")
            entries.append({"key": key, "ref": ref})
            if not os.path.exists(ref):
                todo.append(key)
        if todo:
            if design_model is None:
                design_model = load_design_model(device=device)
            # 批量采样：单 instruct 广播到多条 text，同批独立采样出不同音色变体
            ref_wavs, sr = design_model.generate_voice_design(
                text=[ref_text] * len(todo), language="Chinese", instruct=instruct)
            for key, wav in zip(todo, ref_wavs):
                sf.write(next(e["ref"] for e in entries if e["key"] == key), wav, sr)
            print(f"[design] {char}: {len(todo)} 候选 -> {cand_dir}")
        else:
            print(f"[reuse] {char}: {count} 候选已存在")

        manifest_path = os.path.join(cand_dir, "candidates.json")
        manifest = {
            "char": char,
            "instruct": instruct,
            "ref_text": ref_text,
            "audition_texts": DEFAULT_AUDITION_TEXTS,
            "candidates": [
                {"key": e["key"], "ref": to_rel(e["ref"]), "auditions": {}}
                for e in entries
            ],
        }
        # 断点续跑：保留 audition 已回填的产物路径
        if os.path.exists(manifest_path):
            try:
                old = json.loads(open(manifest_path, encoding="utf-8").read())
                old_aud = {c.get("key"): c.get("auditions", {}) for c in old.get("candidates", [])}
                for c in manifest["candidates"]:
                    c["auditions"] = old_aud.get(c["key"], {}) or {}
            except (ValueError, OSError):
                pass
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        manifests[char] = to_rel(manifest_path)
        print(f"[manifest] {char}: {manifest_path}")
    return manifests


def audition(manifest_path: str, device="cuda:0") -> dict:
    """按 candidates.json 给每候选出情绪试听（Qwen3 Base Voice Clone，env/.venv-qwen）。

    README「Voice Design then Clone」流程：每候选一次 create_voice_clone_prompt(ref, ref_text)
    （ref_text 须与 ref 音频逐字一致——统一长句天然满足），逐情绪 generate_voice_clone。
    Base clone 无 instruct 通道，情绪演绎靠试听句文本语义自适应（试听句本身语义与情绪匹配）。
    试听 wav 已存在即跳过（断点续跑）；回填 manifest 的 auditions 并落盘。
    返回 {"produced": wav 数, "failed": [候选 key]}；failed 非空时调用方视为失败。
    """
    manifest_path = to_abs(manifest_path)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    char = manifest["char"]
    ref_text = manifest["ref_text"]
    audition_texts = manifest.get("audition_texts") or DEFAULT_AUDITION_TEXTS
    model = load_base_model(device=device)

    produced, failed = 0, []
    for cand in manifest["candidates"]:
        key = cand["key"]
        ref = to_abs(cand["ref"])
        if not os.path.exists(ref):
            print(f"[skip] {char}/{key}: 无候选 ref（先跑 design-candidates）")
            failed.append(key)
            continue
        # 每候选构建一次可复用 prompt（提取 codec code + 说话人向量）
        prompt = model.create_voice_clone_prompt(ref_audio=ref, ref_text=ref_text)
        auditions = cand.setdefault("auditions", {})
        for emo, text in audition_texts.items():
            out = os.path.join(os.path.dirname(ref), f"{char}_{key}_{emo}.wav")
            if not os.path.exists(out):
                wavs, sr = model.generate_voice_clone(
                    text=text, language="Chinese", voice_clone_prompt=prompt)
                sf.write(out, wavs[0], sr)
                produced += 1
                print(f"[audition] {char}/{key} {emo} -> {to_rel(out)}")
            auditions[emo] = to_rel(out)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[audition] {char}: produced={produced}, failed={failed}")
    return {"produced": produced, "failed": failed}


def main():
    ap = argparse.ArgumentParser(description="Qwen VoiceDesign ref 生成器（配音链 ref 来源，系统 python）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ref = sub.add_parser("ensure-ref", help="确保各角色 ref_audio 就绪（复用或 VoiceDesign 合成）")
    p_ref.add_argument("--profiles", required=True, help="{char: VoiceDesign dict} JSON")
    p_ref.add_argument("--device", default="cuda:0")
    p_ref.set_defaults(_mode="ensure-ref")

    p_cand = sub.add_parser(
        "design-candidates",
        help="同一 instruct × N 次采样出候选 ref（24k）+ manifest（多候选流程第一步）")
    p_cand.add_argument("--profiles", required=True,
                        help="{char: {instruct, ref_text, candidates_dir, count?}} JSON")
    p_cand.add_argument("--device", default="cuda:0")
    p_cand.set_defaults(_mode="design-candidates")

    p_aud = sub.add_parser(
        "audition",
        help="按 candidates.json 给每候选出 3 情绪试听（Qwen3 Base Voice Clone，多候选流程第二步）")
    p_aud.add_argument("--manifest", required=True,
                       help="design-candidates 产的 candidates.json（回填 auditions）")
    p_aud.add_argument("--device", default="cuda:0")
    p_aud.set_defaults(_mode="audition")

    args = ap.parse_args()
    if args._mode == "ensure-ref":
        profiles = json.loads(open(args.profiles, encoding="utf-8").read())
        result = ensure_refs(profiles, device=args.device)
        print(f"[ensure-ref] {len(result)} 角色就绪")
    elif args._mode == "design-candidates":
        profiles = json.loads(open(args.profiles, encoding="utf-8").read())
        manifests = design_candidates(profiles, device=args.device)
        print(f"[design-candidates] {len(manifests)} 角色 manifest 就绪")
    elif args._mode == "audition":
        import sys
        result = audition(args.manifest, device=args.device)
        if result["failed"]:
            sys.exit(1)  # 供 skill 感知失败（先产物后写图约束）


if __name__ == "__main__":
    main()
