// 步骤1：建 Scene→IllusDesign（按 stand 反推 IllusDesign，MERGE 自动去重，预期 4 条）
MATCH (s:Scene)-[old:depicts]->(stand:StandingIllustration)<-[:expands_to]-(illus:IllusDesign)
MERGE (s)-[new:depicts]->(illus) SET new.sync = false;

// 步骤2：删旧 Scene→stand depicts（14 条，不删 stand 节点）
// ⚠️ expands_to（IllusDesign→stand）保留不动——新结构第二跳
MATCH (s:Scene)-[old:depicts]->(stand:StandingIllustration) DELETE old;
