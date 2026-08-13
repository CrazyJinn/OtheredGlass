# 15_声音 — 角色配音（Qwen VoiceDesign + CosyVoice3 + emotion）

「Qwen VoiceDesign 设计音色 → CosyVoice3 clone（按情绪）」两段式配音。
基线音色由图 VoiceProfile 治理（1:1 per 角色）；每句情绪（emotion）由 chapter-dialoguer 创作时标注。

## 谁负责什么

| 环节 | 职责 |
|---|---|
| **char-voice-design**（声音指纹设计） | 读 Character+LanguageStyle+Info+Event 生成 VoiceProfile（instruct/ref_text）+ 合成 ref_audio；`char-design` 管 |
| **chapter-dialoguer**（创作） | 写台词时标 `say.emotion`（每句情绪，词表选）——气氛源头 |
| **section-voice-publisher**（节级配音） | 单节定稿后（sec=31）Qwen VoiceDesign 出 ref（`.venv-qwen`）→ CosyVoice3 按 emotion clone（`.venv-cosyvoice`）→ voice 写回节 YAML（sec→32）；`plot-design` 管 |
| **voice-publisher**（章级兜底配音） | 未走节级配音的老章：全章 TTS + 绑定 voice 字段 |
| VoiceProfile（图） | 角色基线音色档案 = 声音指纹（instruct / ref_text / ref_audio_path） |

## 两套 venv（项目内，uv 管理；transformers 冲突 → 隔离）

Qwen 要 `transformers==4.57`，CosyVoice 要 4.51，同环境冲突。两个 venv 隔离（项目内，gitignore）：

| venv | Python | 用途 | 锁文件 |
|---|---|---|---|
| `.venv-qwen` | 3.14 | Qwen VoiceDesign 出 ref_audio | [requirements/qwen.txt](requirements/qwen.txt) |
| `.venv-cosyvoice` | 3.10 | CosyVoice3 clone（按 emotion） | [requirements/cosyvoice.txt](requirements/cosyvoice.txt) |

**建 venv**（uv）：
```bash
uv venv --python 3.14 .venv-qwen
uv pip install --python .venv-qwen/Scripts/python.exe -r 15_声音/requirements/qwen.txt
# cosyvoice 同（--python 3.10 + requirements/cosyvoice.txt）
```

## 路径配置（paths.py）

模型/仓库路径统一在 [paths.py](../.claude/scripts/voice/paths.py)（脚本已迁 `.claude/scripts/voice/`，本模块按 `_PROJECT_ROOT` 定位 `15_声音/vendor/CosyVoice`）：读 `settings.json` 的 `voice.model_dir` + env + 默认。所有脚本 `from paths import *`，**不硬编码 D:/**。

- **模型权重**：`D:/model`（settings.json `voice.model_dir`，外部共享，gitignore）
- **CosyVoice 仓库**：`15_声音/vendor/CosyVoice/`（vendored，含 Matcha-TTS，gitignore）

迁机器：改 settings.json `voice.model_dir` + 建 venv（requirements 锁）+ vendor CosyVoice（见下）。

## vendor CosyVoice（第三方，不入 git）

`15_声音/vendor/CosyVoice/` 含 cosyvoice 包 + Matcha-TTS（.gitignore `15_声音/vendor/`）。

```bash
git clone https://github.com/FunAudioLLM/CosyVoice.git 15_声音/vendor/CosyVoice
cd 15_声音/vendor/CosyVoice && git submodule update --init third_party/Matcha-TTS
# 或直接从已 clone 的仓库 cp（含 Matcha-TTS）
```

## 工具（脚本统一在 `.claude/scripts/voice/`，本目录只留数据/依赖：output/ + vendor/ + requirements/）

| 文件 | 用途 | venv |
|---|---|---|
| [voice_clone_runner.py](../.claude/scripts/voice/voice_clone_runner.py) | Qwen VoiceDesign 出 ref（ensure-ref） | `.venv-qwen` |
| [cosyvoice_runner.py](../.claude/scripts/voice/cosyvoice_runner.py) | CosyVoice3 按 emotion clone（publish） | `.venv-cosyvoice` |
| [voice_bundler.py](../.claude/scripts/voice/voice_bundler.py) | voice 键生成 + 章/节 YAML 绑定（make_voice_key / inject / inject-yaml / tasks / tasks-from-section / chapter_stem_from_meta） | 系统 python |
| [emotion_instruct.json](../.claude/scripts/voice/emotion_instruct.json) | emotion → CosyVoice instruct 映射 | — |
| [paths.py](../.claude/scripts/voice/paths.py) | 路径配置（模型/仓库，读 settings.json） | — |

## emotion（每句情绪）

- 由 **chapter-dialoguer** 标（创作时 say.emotion）
- 词表 + 映射：[emotion_instruct.json](../.claude/scripts/voice/emotion_instruct.json)
- 未映射 → 默认"用自然的语气说"

## 配音（生产）

- **节级配音**（主线，plot-design 单节聚焦触发）：`section-voice-publisher <section_id>`——单节定稿后即配音，sec=31→32，dashboard 声音审 32→33。
- **章级兜底**（未走节级的老章）：`voice-publisher <chapter_id>`——全章 TTS + 绑定。

章级 chapter-publisher 合并时节 YAML 的 voice 随 pure concat 进章 JSON，末尾补 manifest.voices / chapter_packs.voices。

## 运行时

Godot `AudioManager.play_voice(key)` 播音；运行时只看 `say.voice` → manifest → wav，**对后端（Qwen/CosyVoice）无感**，换后端零运行时改动。

## 参考

- 基线音色 Schema：[00_init/Schema/声音.md](../00_init/Schema/声音.md)
- 剧本 emotion 字段：[00_init/剧本.md](../00_init/剧本.md)
- voice 键三处对齐：[voice_bundler.py](../.claude/scripts/voice/voice_bundler.py)
