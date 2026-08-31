// 2026-08-19 Section 职责拆分迁移：提纲/定稿从 Section 字段拆为独立产物节点
//
// 背景：Section 回归纯编排容器（删 outline_path/script_path/status），产物链独立成节点：
//   Section -[has_outline, sync=true]-> Outline -[produces, sync=true]-> Script -[produces, sync=true]-> Voiceover
//
// 迁移前存量：3 个 Section 全部 status=31（定稿已批、未配音），均带 outline_path + script_path。
// 迁移动作：
//   - 每节建 Outline(status=1 提纲就绪) + Script(status=11 定稿已批) + has_outline/produces 边
//   - REMOKE Section 的 outline_path/script_path/status
//   - 不建 Voiceover（存量节未配音，由 section-voice-publisher 后续兜底建）
//
// 执行：python .claude/scripts/cypher_exec.py -f 00_init/migration/2026-08-19_section_split.cypher --multi

// ── sec00 酒店醒来 ──
MERGE (ol:Outline {id:'PjyaIOZwGG'})
SET ol.name = '酒店醒来提纲',
    ol.outline_path = '25_剧本/chapter00_序章/sec00_酒店醒来/outline.md',
    ol.status = 1;
MERGE (sc:Script {id:'PjyaIOZwGH'})
SET sc.name = '酒店醒来定稿',
    sc.script_path = '25_剧本/chapter00_序章/sec00_酒店醒来/完整对话.yaml',
    sc.status = 11;
MATCH (sec:Section {id:'PCnEpf6apM'}), (ol:Outline {id:'PjyaIOZwGG'})
MERGE (sec)-[r:has_outline]->(ol) SET r.sync = true;
MATCH (ol:Outline {id:'PjyaIOZwGG'}), (sc:Script {id:'PjyaIOZwGH'})
MERGE (ol)-[r:produces]->(sc) SET r.sync = true;

// ── sec01 意外突生 ──
MERGE (ol:Outline {id:'PjyaIOZwGI'})
SET ol.name = '意外突生提纲',
    ol.outline_path = '25_剧本/chapter00_序章/sec01_意外突生/outline.md',
    ol.status = 1;
MERGE (sc:Script {id:'PjyaIOZwGJ'})
SET sc.name = '意外突生定稿',
    sc.script_path = '25_剧本/chapter00_序章/sec01_意外突生/完整对话.yaml',
    sc.status = 11;
MATCH (sec:Section {id:'PCnEpf6apN'}), (ol:Outline {id:'PjyaIOZwGI'})
MERGE (sec)-[r:has_outline]->(ol) SET r.sync = true;
MATCH (ol:Outline {id:'PjyaIOZwGI'}), (sc:Script {id:'PjyaIOZwGJ'})
MERGE (ol)-[r:produces]->(sc) SET r.sync = true;

// ── sec02 灵魂夹缝 ──
MERGE (ol:Outline {id:'PjyaIOZwGK'})
SET ol.name = '灵魂夹缝提纲',
    ol.outline_path = '25_剧本/chapter00_序章/sec02_灵魂夹缝/outline.md',
    ol.status = 1;
MERGE (sc:Script {id:'PjyaIOZwGL'})
SET sc.name = '灵魂夹缝定稿',
    sc.script_path = '25_剧本/chapter00_序章/sec02_灵魂夹缝/完整对话.yaml',
    sc.status = 11;
MATCH (sec:Section {id:'PCnEpf6apO'}), (ol:Outline {id:'PjyaIOZwGK'})
MERGE (sec)-[r:has_outline]->(ol) SET r.sync = true;
MATCH (ol:Outline {id:'PjyaIOZwGK'}), (sc:Script {id:'PjyaIOZwGL'})
MERGE (ol)-[r:produces]->(sc) SET r.sync = true;

// ── 清 Section 旧字段（纯编排容器化）──
MATCH (sec:Section)
WHERE sec.outline_path IS NOT NULL OR sec.script_path IS NOT NULL OR sec.status IS NOT NULL
REMOVE sec.outline_path, sec.script_path, sec.status;
