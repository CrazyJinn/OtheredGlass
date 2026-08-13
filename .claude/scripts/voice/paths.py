"""声音脚本路径配置：模型权重 + CosyVoice 仓库，统一读 settings.json/env/默认。

本模块位于 .claude/scripts/voice/，被同目录的 voice_clone_runner / cosyvoice_runner
`from paths import` 引用。所有脚本不硬编码 D:/。
优先级：env var > settings.json（项目根，gitignore）> 默认值。

迁机器：改 settings.json 的 voice.model_dir（或设 VOICE_MODEL_DIR 环境变量）即可，不动代码。
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))  # .claude/scripts/voice/
# voice → scripts → .claude → 项目根
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))


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

# 模型权重根（Qwen VoiceDesign/Base + Fun-CosyVoice3 都在这下）
MODEL_DIR = os.environ.get("VOICE_MODEL_DIR", _voice.get("model_dir", "D:/model"))
QWEN_VOICE_DESIGN = os.path.join(MODEL_DIR, "Qwen3-TTS-12Hz-1.7B-VoiceDesign")
QWEN_BASE = os.path.join(MODEL_DIR, "Qwen3-TTS-12Hz-1.7B-Base")
COSYVOICE_MODEL = os.path.join(MODEL_DIR, "Fun-CosyVoice3-0.5B")

# CosyVoice 仓库（vendored 在 15_声音/vendor，含 Matcha-TTS）；脚本已迁 .claude/scripts/voice/，
# 故按项目根定位 vendor。
COSYVOICE_REPO = os.environ.get(
    "COSYVOICE_REPO", os.path.join(_PROJECT_ROOT, "15_声音", "vendor", "CosyVoice")
)
