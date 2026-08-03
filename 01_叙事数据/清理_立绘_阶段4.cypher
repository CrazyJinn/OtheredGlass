// ══ 4a. 删 P16PBEZd32 的 2 个旧疏离 stand（客套笑、婉拒）══
MATCH (stand:StandingIllustration) WHERE stand.id IN ['P2vQL2d9dY','P2vQL2d9dZ'] DETACH DELETE stand;

// ══ 4b. 修 P16PBEZd32 保留 3 stand 的 description（去捏造台词，对齐 sec00 海王版真实台词）══
MATCH (n:StandingIllustration {id:'PHSE4iftNQ'}) SET n.description = '半醒宿醉的松弛自嘲——海王清晨的常态。情境：开场懒懒自语「呵」「有点过头了」；sec01 也复用作多功能松弛变体（咖啡店入场点单、路口遇雨抱怨）。赤裸上身，眼神半眯带倦，嘴角懒懒，姿态松弛靠后。';
MATCH (n:StandingIllustration {id:'PHSE4iftNR'}) SET n.description = '打量与调侃的从容笑——海王式视线调情。情境：sec00 评顾盈穿白衬衫「衬衫穿得挺顺手」「穿着挺好看」，被夸时回「那也是实话实说」。赤裸上身，目光带笑直视，嘴角微微上扬。';
MATCH (n:StandingIllustration {id:'PHSE4iftNS'}) SET n.description = '玩世不恭的洒脱轻佻——海王标志的自信调侃。情境：sec00 回敬「您过奖」「也是您配合得好」「昨晚那么激烈，再约我怕这床先散架」。赤裸上身，站姿放松，嘴角明显上扬带笑，眼神聚焦不躲闪。';

// ══ 4c. OLBbajiuMS（商务休闲）衍生 3 stand + expands_to + ref_style ══
// 3 stand 节点（status=0 待生成）
MERGE (s1:StandingIllustration {id:'PJajqyM6s4'}) ON CREATE SET s1.status = 0, s1.variant_label = '慵懒' SET s1.description = '半醒宿醉的松弛——sec01 咖啡店入场点单（「美式，中杯」懒懒）+ 路口遇雨抱怨（「真讨厌下雨天」）。商务休闲装（开衫+白衬衫+深灰长裤+棕皮鞋）。眼神半眯带倦，姿态松弛。';
MERGE (s2:StandingIllustration {id:'PJajqyM6s5'}) ON CREATE SET s2.status = 0, s2.variant_label = '玩味' SET s2.description = '撩拨的从容笑——sec01 咖啡店撩店员小姑娘（「这么早上班，眼睛还挺亮」）。商务休闲装。目光带笑直视，嘴角微扬。';
MERGE (s3:StandingIllustration {id:'PJajqyM6s6'}) ON CREATE SET s3.status = 0, s3.variant_label = '轻佻' SET s3.description = '调侃顶点的洒脱轻佻——sec01 咖啡店（「夸你呢。别紧张」）。商务休闲装。站姿放松，嘴角明显上扬，眼神聚焦带笑。';

// expands_to: OLBbajiuMS → 3 stand
MATCH (illus:IllusDesign {id:'OLBbajiuMS'}), (s:StandingIllustration {id:'PJajqyM6s4'}) MERGE (illus)-[r:expands_to]->(s) SET r.sync = true, r.variant_label = '慵懒';
MATCH (illus:IllusDesign {id:'OLBbajiuMS'}), (s:StandingIllustration {id:'PJajqyM6s5'}) MERGE (illus)-[r:expands_to]->(s) SET r.sync = true, r.variant_label = '玩味';
MATCH (illus:IllusDesign {id:'OLBbajiuMS'}), (s:StandingIllustration {id:'PJajqyM6s6'}) MERGE (illus)-[r:expands_to]->(s) SET r.sync = true, r.variant_label = '轻佻';

// ref_style: 经 OLBbajiuMS 上游回溯到陆择 LanguageStyle → 3 stand
MATCH (illus:IllusDesign {id:'OLBbajiuMS'})-[:outfit_for]->(:CostumeStyle)<-[:has_costume]-(char:Character)
MATCH (char)-[:has_voice_style]->(voice:LanguageStyle)
MATCH (s:StandingIllustration) WHERE s.id IN ['PJajqyM6s4','PJajqyM6s5','PJajqyM6s6']
MERGE (voice)-[r:ref_style]->(s) SET r.sync = true;

// depicts: sec01 两 Scene → OLBbajiuMS（新结构 Scene→IllusDesign，去重 MERGE）
MATCH (sc1:Scene {id:'PHuTf3ogEu'}), (illus:IllusDesign {id:'OLBbajiuMS'}) MERGE (sc1)-[r:depicts]->(illus) SET r.sync = false;
MATCH (sc2:Scene {id:'Oib4U5kSnI'}), (illus:IllusDesign {id:'OLBbajiuMS'}) MERGE (sc2)-[r:depicts]->(illus) SET r.sync = false;
