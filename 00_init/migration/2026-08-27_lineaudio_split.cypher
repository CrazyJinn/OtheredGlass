// 2026-08-27 LineAudio 逐句化迁移（台词.jsonl 停产，md 定稿转正 + 拆分进图）
//
// 背景见 00_init/Schema/剧情.md（对话逐句入图）。执行方式：
//   python .claude/scripts/cypher_exec.py -f 00_init/migration/2026-08-27_lineaudio_split.cypher --multi
//
// 1. 删除旧「节级单节点」LineAudio（SecScript-produces->LineAudio 1:1 时代的产物）。
//    新逐句行节点由 section-voice-publisher 第一步拆分（script_splitter.py）在
//    SecScript=11 后幂等重建——旧节点只承载节级状态，无行内容，无保留价值。
//    旧 wav（按 <char>-<stem>-<scene>-L<NNNN> 命名）留在 15_声音/，行身份换成节点 id 后
//    无法复用（chapter00 三节音频均为 pending 未批，损失≈0），可事后手动清理。
MATCH (sc:SecScript)-[:produces]->(vo:LineAudio)
WHERE NOT EXISTS { MATCH (vo)-[:stages]->(:Scene) }   // 旧节点不可能有 stages 出边（新 scene 行才有）
DETACH DELETE vo;

// 2. SecScript.script_path 校正指向 台词.md（若旧值指向 台词.jsonl，按同目录同主名改 .md）。
//    台词.md 若尚无（个别节未重跑 dialoguer），后续由 dialoguer 重做时覆盖写入。
MATCH (sc:SecScript)
WHERE sc.script_path ENDS WITH '台词.jsonl'
SET sc.script_path = replace(sc.script_path, '台词.jsonl', '台词.md');

// 3. 台词.md 需按新格式规范增补（scene_block_id 场景标题 / [表情] 标注 / 选择块语法）：
//    由 plot-design 重推各节（sc 置 0 → chapter-dialoguer 重创 → 定稿审 → 拆分）。
//    现存 台词.jsonl 文件保留在创作区不删（链路已无代码读它，仅作历史参考）。
MATCH (sc:SecScript)
WHERE sc.script_path ENDS WITH '台词.md'
SET sc.status = 0;
