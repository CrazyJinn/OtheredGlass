# 15_声音 — 角色配音（Qwen VoiceDesign + CosyVoice3 + emotion）

「**Qwen VoiceDesign 设计音色 → CosyVoice3 clone（按情绪）**」两段式配音。基线音色由图 `VoiceProfile` 治理（1:1 per 角色）；每句台词的情绪（`emotion`）由 `chapter-dialoguer` 创作时标注。

## 谁负责什么（关键分工）

| 环节 | 职责 | 产物 |
|---|---|---|
| **chapter-dialoguer**（创作） | 写台词时标 `say.emotion`（每句情绪，从词表选，据台词当下情绪）——**这是创作意图，是"气氛"的源头** | chapter JSON / YAML 的 `say.emotion` 字段 |
| **voice-publisher**（配音） | 消费 emotion：Qwen VoiceDesign 出角色 ref（锁音色）→ CosyVoice3 按 emotion 映射 instruct clone（控语气）→ 绑定 voice 字段 | `99_game/assets/voices/<key>.wav` |
| **VoiceProfile**（图治理） | 角色基线音色档案（instruct / ref_text / ref_audio_path），每角色 1 个 | Neo4j `Character→has_voice_profile→VoiceProfile` |

> **emotion 不是配音阶段决定的**——是 chapter-dialoguer 创作台词时就定好的（像写剧本时标表情）。配音只是执行这个意图。

## 模型权重（本地）

- `D:/model/Qwen3-TTS-12Hz-1.7B-VoiceDesign` — Qwen 声音设计（出 ref_audio，**系统 python**）
- `D:/model/Fun-CosyVoice3-0.5B` — CosyVoice3 clone（按 emotion，**venv python**）

## 两套 Python 环境（必须分离）

CosyVoice 要 `transformers==4.51`，Qwen3-TTS 锁 4.57，冲突；且 CosyVoice 官方 torch 不支持 RTX 5060 Ti（Blackwell）。故两套环境隔离（详见 memory `cosyvoice-python314-windows-setup`）：

| 环境 | Python | 用途 | 关键包 |
|---|---|---|---|
| **系统** | 3.14 | Qwen VoiceDesign 出 ref_audio | qwen-tts, transformers 4.57, torch cu128 |
| **venv `D:/cosyvoice_env`** | 3.10 | CosyVoice3 clone（按 emotion） | transformers 4.51, onnxruntime-gpu, torch cu128 |

venv 建法见 [plan 文件](C:\Users\crazy\.claude\plans\99-game-next-floofy-summit.md) 的 CosyVoice 集成段 + memory。

## 流程（voice-publisher 5 步，双环境编排）

```
chapter-dialoguer 标 say.emotion（创作）
       ↓
voice-publisher:
  1. 查图 VoiceProfile（角色 ref_audio_path）
  2. voice_bundler tasks（chapter JSON say → {char:[{key,text,emotion}]}）
  3a. 系统 python: voice_clone_runner ensure-ref（Qwen VoiceDesign 出/复用 ref_audio）
  3b. venv python:  cosyvoice_runner publish（CosyVoice3 按 emotion instruct clone）
  4. voice_bundler inject（voice 字段 + manifest + chapter_packs）
  5. 汇报
```

## emotion 词表 + 映射

- **词表**（可扩）：`平静/高兴/悲伤/愤怒/震惊/无奈/调侃/温柔/冷漠/紧张/恐惧/坚定`
- **emotion → CosyVoice instruct 映射**：[emotion_instruct.json](emotion_instruct.json)（如 `悲伤 → 用悲伤低沉、强忍哽咽的语气说`）
- 未映射的 emotion → 默认"用自然的语气说"
- 改映射措辞调情绪强度，重跑 voice-publisher 即生效

## 工具清单

| 文件 | 用途 | 环境 |
|---|---|---|
| [voice_clone_runner.py](voice_clone_runner.py) | Qwen VoiceDesign 出 ref_audio（ensure-ref） | 系统 python 3.14 |
| [cosyvoice_runner.py](cosyvoice_runner.py) | CosyVoice3 按 emotion clone（publish） | venv python 3.10 |
| [emotion_instruct.json](emotion_instruct.json) | emotion → instruct 映射配置 | — |
| [label_chapter00_emotion.py](label_chapter00_emotion.py) | 一次性：序章 emotion 标注（替 dialoguer，迁移用） | 系统 python |
| [cosyvoice_demo.py](cosyvoice_demo.py) | CosyVoice emotion demo（三情绪试听） | venv python |
| [luze_voice_build.py](luze_voice_build.py) / [guying_voice_build.py](guying_voice_build.py) | 单角色验证（Qwen 路径B，老参考） | 系统 python |

## 单角色验证（开发用）

```bash
# Qwen VoiceDesign → 单句（老路径，验证音色）
python 15_声音/luze_voice_build.py

# CosyVoice 三情绪（venv，验证 emotion）
D:/cosyvoice_env/Scripts/python.exe 15_声音/cosyvoice_demo.py
```

## 全章配音（生产）

voice-publisher skill（在 Claude Code 里调）：

```
/voice-publisher <chapter_id>
```

它会查图 + tasks + 双环境（Qwen design ref 系统 python / CosyVoice clone venv python）+ inject + manifest。详见 [.claude/skills/voice-publisher/SKILL.md](../.claude/skills/voice-publisher/SKILL.md)。

## 运行时播放

Godot 侧 `AudioManager.play_voice(key)` 同步播音；点 next / Auto / Skip / Ctrl 推进时自覆盖停旧播新。运行时层只看 `say.voice` 键 → manifest → wav，**对"wav 是 Qwen 还是 CosyVoice 产的"无感**——换后端零运行时改动。

## 参考

- 基线音色 Schema：[00_init/Schema/声音.md](../00_init/Schema/声音.md)（VoiceProfile 节点）
- 剧本 emotion 字段：[00_init/剧本.md](../00_init/剧本.md)（say.emotion + 词表）
- voice 键三处对齐：[99_game/tools/voice_bundler.py](../99_game/tools/voice_bundler.py)（make_voice_key）
