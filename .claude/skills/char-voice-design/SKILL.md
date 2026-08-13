---
name: char-voice-design
description: |
  推进 VoiceProfile 图节点（角色声音指纹）：查询状态 → 生成 VoiceDesign instruct/ref_text → 保存结果（MERGE 兜底建节点+has_voice_profile 边，写内容与 status=1）→ 合成 ref_audio 固化可听。
  依据 Character 基础属性（性别/年龄/人设）+ LanguageStyle（语速/尾音/口头禅）+ Info（设定/身份/创伤）+ Event（经历/转折）生成六维 instruct（年龄/性别/音色/气质/语速/尾音）。怪物（enemy）跳过（无台词）。在需要设计角色基线音色、或 VoiceProfile status∈{-1,0} 需推进时使用。
argument-hint: <char_id>
arguments:
  - char_id
allowed-tools: Read, Bash, Write, Edit
---

> **status=-1 = 作废重做**：当 VoiceProfile 被 sync 级联重置为 `status=-1` 时（角色属性变更沿 `has_voice_profile`(sync=true) 触发），即使 instruct/ref_text 已有值，也**必须重新生成并覆盖**。`-1` 与 `0` 都视为"需生成"起点；`-1` 明确表示旧声音指纹作废，**禁止因属性已有值而跳过**，也禁止读旧 instruct/旧 ref_audio。

# 角色声音指纹设计

推进并写入 VoiceProfile（角色基线音色档案 = 声音指纹）图节点，并合成可听的 ref_audio。

> **声音指纹 = VoiceProfile**：`instruct`+`ref_text` 是音色的设计描述（源），`ref_audio` 是这段设计合成出的音频固化（可听载体）。本 skill 产出声音指纹，设计阶段即合成 `ref_audio` 使其可听可试——音色好坏是连续主观判断，靠「听一句不满意就改 instruct 重跑」治理，无二元审批（status=1 即完成，见 [声音.md](../../../00_init/Schema/声音.md)）。

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| char_id | 角色节点 ID（snowflake Base62） | 必传 |

## 流程（三段式：查状态 → 完成任务 → 保存结果）

### 1. 查询目标节点状态 + 生成素材

通过 `${CLAUDE_SKILL_DIR}/../../scripts/cypher_exec.py` 查询角色 + LanguageStyle + 已有 VoiceProfile + 叙事素材（Info/Event）：

```cypher
MATCH (c:Character {id: '<char_id>'})
OPTIONAL MATCH (c)-[:has_voice_style]->(ls:LanguageStyle)
OPTIONAL MATCH (c)-[:has_voice_profile]->(vp:VoiceProfile)
OPTIONAL MATCH (c)-[:link]->(info:Info)
OPTIONAL MATCH (c)-[iv:involved]->(evt:Event)
OPTIONAL MATCH (c)-[:involved]->(e2:Event)-[:link]->(evtInfo:Info)
RETURN c, ls, vp,
       collect(DISTINCT info { .title, .content, .knowledge_level }) AS infos,
       collect(DISTINCT evtInfo { .title, .content, .knowledge_level }) AS event_infos,
       collect(DISTINCT evt { .title, .description, .type, .time }) AS events,
       collect(DISTINCT iv.role) AS event_roles;
```

- **目标节点判定**：
  - 若 `vp` 为空 → 生成新 snowflake id 作为 `VP_ID`（`python "${CLAUDE_SKILL_DIR}/../../scripts/snowflake_base62.py" -n 1 -q`），本次将新建；若存在 → `VP_ID = vp.id`，按 status 决定起点（`-1`/`0` 需重做）。
- **角色类型判断**（决定是否跳过）：

  | 角色类型 | VoiceProfile |
  |---------|--------------|
  | 主角(char) / NPC | 生成 |
  | 怪物(enemy) | **不生成**（无台词无需配音，直接汇报跳过，不写任何节点） |

- 记下角色名 `c.name`（后续 ref_audio_path 与 profiles.json 的键用角色名，与下游 voice-publisher 对齐）。

### 2. 完成任务（生成声音指纹的设计描述）

LLM 按 [references/template-声音设计.md](references/template-声音设计.md) 生成三段内容：`instruct` / `ref_text` / `description`。

**instruct**（VoiceDesign 自然语言，覆盖六维）。依据映射：

| instruct 维度 | 主依据 | 辅助依据 |
|------|------|------|
| 性别 | `Character.gender` | — |
| 年龄 | `Character.birth_year`（用故事基准年算岁数） | — |
| 音色（清冷/低沉/明亮/沙哑） | `Character.description` + `character_tags` | `Event`（`type=转折/状态变化` 的经历影响沧桑感） |
| 气质（冷漠/热情/傲慢/温柔/玩世不恭） | `Character.character_tags` + `description` + `LanguageStyle.description` | `Info`（优先 `knowledge_level=2,3` 深层身份/创伤，塑气质底色） |
| 语速 | `LanguageStyle.rhythm`（短促急迫→快 / 长句思考型→慢） | `character_tags`（沉默寡言→慢） |
| 尾音（拖音/果断收/犹豫嗯啊/玩味上扬） | `LanguageStyle.habits`（口头禅/犹豫模式） | `LanguageStyle.emotion_patterns` |

> instruct 写成**一段自然语言**（非键值对），范例见 [voice_profile_init.cypher](../../../01_叙事数据/voice_profile_init.cypher) 陆择/顾盈的 instruct（如「青年男性，20余岁，中低音略带沙哑；玩世不恭的调侃腔调……尾音常带一丝玩味的上扬」——尾音描述正源自语言风格 habits）。

**ref_text**：1 句短（10-20 字）、**贴近角色语气**的参考句，用于固化音色（不直接对外，仅喂 VoiceDesign）。要能体现该角色的典型腔调（如陆择的慵懒调侃、顾盈的从容玩味）。

**description**：1-2 句音色气质概要（含依据来源，便于回溯）。

### 3. 保存结果（MERGE 兜底 + 写设计描述 + 合成 ref_audio + status=1）

#### 3a. 写图（一次性写入，节点不存在则兜底创建）

```cypher
MERGE (v:VoiceProfile {id: '<VP_ID>'})
  ON CREATE SET v.status = 0;
MATCH (c:Character {id: '<char_id>'}), (v:VoiceProfile {id: '<VP_ID>'})
MERGE (c)-[r:has_voice_profile]->(v) SET r.sync = true;
MATCH (v:VoiceProfile {id: '<VP_ID>'})
SET v.name = '<角色名>声音档案',
    v.instruct = '...',
    v.ref_text = '...',
    v.ref_audio_path = '15_声音/output/<角色名>_ref.wav',
    v.description = '...',
    v.status = 1;
```

> 不写 `clone_prompt_path`：CosyVoice 路线不产 `.pt`（Qwen Base clone 已废弃），该字段为遗留死字段（见 [声音.md](../../../00_init/Schema/声音.md) 废弃说明）。

#### 3b. 合成 ref_audio（固化声音指纹的可听载体）

构造单角色 profiles JSON（键为角色名，与下游 voice-publisher 的 profiles 同构）：

```bash
# 写 99_game/data/.cache/voice-profile-design-<角色名>.json，内容：
# { "<角色名>": { "instruct": "<instruct>", "ref_text": "<ref_text>", "ref_audio_path": "15_声音/output/<角色名>_ref.wav" } }
```

调用 Qwen VoiceDesign 合成（`.venv-qwen`，Python 3.14）：

```bash
.venv-qwen/Scripts/python.exe "${CLAUDE_SKILL_DIR}/../../scripts/voice/voice_clone_runner.py" ensure-ref \
  --profiles '99_game/data/.cache/voice-profile-design-<角色名>.json'
```

`voice_clone_runner.ensure_ref`：`ref_audio_path` 文件存在则复用，否则 `generate_voice_design(text=ref_text, language="Chinese", instruct=instruct)` 合成写盘（24kHz wav）。

> **ref_audio 合成失败不回滚 status**：设计描述（instruct/ref_text）已落库即 status=1 成立；ref_audio 是可后补的可听载体。失败仅报警，提示用户手动重跑 ensure-ref 或检查 `.venv-qwen` 环境（见 [15_声音/README.md](../../../15_声音/README.md)）。

### 4. 汇报

列出：角色名、VP_ID、新建/复用、instruct 全文、ref_text、ref_audio 合成结果（[design]新建 / [reuse]复用 / 失败）、status=1。附试听提示：本地播放 `15_声音/output/<角色名>_ref.wav`，不满意改 instruct 重跑本 skill（status 会被级联重置或手动改 -1/0）。

## 参考文档

- [声音设计模板](references/template-声音设计.md)（instruct 六维写作指南 + 范例）
- 基线音色 Schema：[00_init/Schema/声音.md](../../../00_init/Schema/声音.md)（VoiceProfile 节点 + has_voice_profile 边 + 治理哲学）
- 现有 instruct 范例：[01_叙事数据/voice_profile_init.cypher](../../../01_叙事数据/voice_profile_init.cypher)（陆择/顾盈）
- 下游消费：[voice-publisher](../voice-publisher/SKILL.md)（按 VoiceProfile + say.emotion 批量配音）
- ref 合成脚本：[voice_clone_runner.py](../../../.claude/scripts/voice/voice_clone_runner.py)（ensure-ref）
