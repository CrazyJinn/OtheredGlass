"""声音脚本路径配置：模型权重 + CosyVoice 仓库，统一读 settings.json/env/默认。

本模块位于 .claude/scripts/voice/，被同目录的 voice_clone_runner / cosyvoice_runner
`from paths import` 引用。所有脚本不硬编码 D:/。
优先级：env var > settings.json（项目根，gitignore），无默认值——未配置即报错。

迁机器：改 settings.json 的 voice.model_dir（或设 VOICE_MODEL_DIR 环境变量）即可，不动代码。
cosyvoice_runner 的 CosyVoice/Matcha-TTS import 路径由本模块 `--pythonpath` 输出，
调用方以 PYTHONPATH 环境变量注入（不再用 sys.path.insert）。
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))  # .claude/scripts/voice/
# voice → scripts → .claude → 项目根
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))


# 项目根（manifest / 图字段里的产物路径惯例为项目根相对，正斜杠分隔）
PROJECT_ROOT = _PROJECT_ROOT


def to_abs(p: str) -> str:
    """项目根相对路径 → 绝对路径（已是绝对路径则原样返回）。"""
    return p if os.path.isabs(p) else os.path.join(PROJECT_ROOT, p)


def to_rel(p: str) -> str:
    """绝对路径 → 项目根相对路径（统一正斜杠，manifest/图字段惯例）。"""
    return os.path.relpath(p, PROJECT_ROOT).replace(os.sep, "/")


def _read_voice_settings() -> dict:
    """读项目根 settings.json 的 voice 节（gitignore，可选）。"""
    p = os.path.join(_PROJECT_ROOT, "settings.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f).get("voice", {})
        except Exception:
            pass
    return {}


_voice = _read_voice_settings()

# 模型权重根（Qwen VoiceDesign/Base + Fun-CosyVoice3 都在这下）。
# 无默认值：未配置即报错（settings.json voice.model_dir 或 VOICE_MODEL_DIR 环境变量）。
_model_dir = os.environ.get("VOICE_MODEL_DIR") or _voice.get("model_dir")
if not _model_dir:
    raise RuntimeError(
        "未配置模型目录：在项目根 settings.json 设 voice.model_dir 或设 VOICE_MODEL_DIR 环境变量"
    )
MODEL_DIR = _model_dir
QWEN_VOICE_DESIGN = os.path.join(MODEL_DIR, "Qwen3-TTS-12Hz-1.7B-VoiceDesign")
QWEN_BASE = os.path.join(MODEL_DIR, "Qwen3-TTS-12Hz-1.7B-Base")  # Voice Clone（多候选试听，voice_clone_runner audition）
COSYVOICE_MODEL = os.path.join(MODEL_DIR, "Fun-CosyVoice3-0.5B")

# CosyVoice 仓库（vendored 在 env/vendor/CosyVoice，含 Matcha-TTS；外部依赖统一收口 env/）。
COSYVOICE_REPO = os.environ.get(
    "COSYVOICE_REPO",
    _voice.get("cosyvoice_repo") or os.path.join(_PROJECT_ROOT, "env", "vendor", "CosyVoice"),
)


def pythonpath() -> str:
    """CosyVoice + Matcha-TTS 的 PYTHONPATH（cosyvoice_runner 调用方注入，替代 sys.path.insert）。"""
    return os.pathsep.join([
        COSYVOICE_REPO,
        os.path.join(COSYVOICE_REPO, "third_party", "Matcha-TTS"),
    ])


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="voice 脚本路径配置查询")
    ap.add_argument("--pythonpath", action="store_true",
                    help="输出 CosyVoice+Matcha-TTS 的 PYTHONPATH（供 cosyvoice_runner 调用方注入）")
    a = ap.parse_args()
    if a.pythonpath:
        print(pythonpath())
