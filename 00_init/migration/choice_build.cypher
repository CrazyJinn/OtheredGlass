// galgame 选择分叉（Choice）迁移 —— 第1步：建节点与边（不删原包含边）
// 用 MERGE on {name}（语义锚，幂等可重跑），id 作为属性 SET

// ===== 选择点1：跳江 =====
MERGE (ch1:Choice {name:'跳江选择'})
  SET ch1.id='OdraDmqprU', ch1.description='陈默深夜站在长江大桥栏杆上，是否跳江', ch1.time='Day 0 深夜';

MATCH (hub1:Event {title:'陈默跳江陆择灵魂挤入'}), (ch1:Choice {name:'跳江选择'})
MERGE (hub1)-[:presents {sync:false}]->(ch1);

MATCH (ch1:Choice {name:'跳江选择'}), (ea:Event {title:'姐姐来电（分支A）'}), (ebe:Event {title:'跳江BE（分支B）'})
MERGE (ch1)-[:option {label:'再想想', leads_to_ending:false, sync:false}]->(ea)
MERGE (ch1)-[:option {label:'跳江', leads_to_ending:true, sync:false}]->(ebe);

MATCH (ebe:Event {title:'跳江BE（分支B）'}) SET ebe.ending_kind='BE';

// ===== 选择点2：三选一（下游女主线起点 Event 待 Day 21-30 补完后连 option）=====
MERGE (ch2:Choice {name:'三选一'})
  SET ch2.id='OdraDmqprV', ch2.description='三个未接来电后，选择一个女主推进后续剧情', ch2.time='Day 22';

MATCH (hub2:Event {title:'三选一抉择'}), (ch2:Choice {name:'三选一'})
MERGE (hub2)-[:presents {sync:false}]->(ch2);
