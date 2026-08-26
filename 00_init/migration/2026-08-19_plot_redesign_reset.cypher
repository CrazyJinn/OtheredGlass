// 2026-08-19 剧情链重构清空重跑（plot redesign reset）
// 背景：剧情产物链重构——label 改名（Outline→SecOutline、Script→SecScript、Voiceover→LineAudio）
// + 台词 YAML→JSONL + voice key 从 line_idx 位置寻址改为稳定行 id。
// 存量 chapter00 视为试验数据清空重跑；Voiceover label 在库中不存在，零迁移。
//
// 保留（不在删除范围）：
//   - Scene 节点与 depicts 边（Scene→IllusDesign）、美术链全部（IllusDesign/StandingIllustration 等）
//   - VoiceDesign（角色基线音色设计）
//   - 叙事基础（Character/Event/Location/Info/Choice）
//
// 同步手动清理的文件（git 可恢复）：
//   - 25_剧本/chapter00_序章/（整目录：设计简报 + 3×outline.md + 3×完整对话.yaml）
//   - 99_game/data/chapters/chapter00_序章.json
//   - 99_game/assets/voices/*.wav（40 个旧键 wav，新 voice key 含行 id 不与旧键同名）
//   - 99_game/data/.cache/ 下 chapter00_序章 相关缓存（portrait-map / voice-profiles / voice-tasks / voices CSV）
//   - 99_game/data/manifest.json 清空 voices 段（update 合并语义会残留旧键）
//   - 99_game/data/chapter_packs.json 删除 chapter00_序章 条目

MATCH (n) WHERE n:Chapter OR n:Section OR n:Outline OR n:Script
DETACH DELETE n;
