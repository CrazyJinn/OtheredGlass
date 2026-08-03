// ════════════ 节点（先建节点）════════════

// 角色：咖啡店小姑娘（龙套，名字「小夏」为占位，可改）
MERGE (n:Character {id: 'PHuTf3ogEq'})
SET n.name = '小夏',
    n.gender = '女',
    n.description = '街角咖啡店的年轻女店员，被陆择几句轻佻话撩得脸红',
    n.character_tags = '青涩, 易脸红, 龙套',
    n.priority = 'P2';

// 地点：街角咖啡店
MERGE (n:Location {id: 'PHuTf3ogEr'})
SET n.name = '街角咖啡店',
    n.description = '陆择酒店出门赶飞机路上顺路买咖啡的街角小店';

// 事件：买咖啡撩店员
MERGE (n:Event {id: 'PHuTf3ogEs'})
SET n.title = '陆择买咖啡撩店员',
    n.time = '开场',
    n.description = '陆择在街角咖啡店买咖啡清醒，随口撩了店员小姑娘几句，小姑娘脸红',
    n.type = '交流';

// 事件：遇雨没伞、冲街口赶机场巴士（车祸伏笔——主动闯马路，呼应赶飞机）
MERGE (n:Event {id: 'PHuTf3ogEt'})
SET n.title = '陆择遇雨冲街口赶机场巴士',
    n.time = '开场',
    n.description = '买完咖啡出来碰大雨，陆择没带伞，自言自语抱怨下雨天；内心盘算冲过街口、上马路对面停靠的机场巴士赶飞机',
    n.type = '行动';

// 场景：街角咖啡店-点餐台（dialogue，status=1 数据就绪；背景图层由 scene-layer-designer 后续推进）
MERGE (n:Scene {id: 'PHuTf3ogEu'})
SET n.name = '街角咖啡店-点餐台',
    n.scene_type = 'dialogue',
    n.time_of_day = '清晨',
    n.atmosphere = '清晨清冷的街角小店，咖啡机蒸汽与暖黄灯光',
    n.description = '街角咖啡店点餐台，陆择买咖啡撩店员的小店前台',
    n.status = 1;

// ════════════ 边（节点建完再建边，按依赖排序）════════════

// ── involved：人物参与事件（Character → Event）──
MATCH (a:Character {id: 'NvCkQmFPFo'}), (b:Event {id: 'PHuTf3ogEs'})
MERGE (a)-[:involved {role: '当事人', detail: '买咖啡、撩店员'}]->(b);
MATCH (a:Character {id: 'PHuTf3ogEq'}), (b:Event {id: 'PHuTf3ogEs'})
MERGE (a)-[:involved {role: '参与者', detail: '被撩脸红的店员'}]->(b);
MATCH (a:Character {id: 'NvCkQmFPFo'}), (b:Event {id: 'PHuTf3ogEt'})
MERGE (a)-[:involved {role: '当事人', detail: '出门遇雨'}]->(b);

// ── at：人物—地点（Character → Location）──
MATCH (a:Character {id: 'PHuTf3ogEq'}), (b:Location {id: 'PHuTf3ogEr'})
MERGE (a)-[:at {type: '工作', detail: '街角咖啡店店员'}]->(b);
MATCH (a:Character {id: 'NvCkQmFPFo'}), (b:Location {id: 'PHuTf3ogEr'})
MERGE (a)-[:at {type: '前往', detail: '赶飞机路上买咖啡'}]->(b);

// ── occurred_at：事件发生地点（Event → Location）──
MATCH (a:Event {id: 'PHuTf3ogEs'}), (b:Location {id: 'PHuTf3ogEr'})
MERGE (a)-[:occurred_at {detail: '买咖啡地点'}]->(b);
MATCH (a:Event {id: 'PHuTf3ogEt'}), (b:Location {id: 'NvCkQmFPGP'})
MERGE (a)-[:occurred_at {detail: '咖啡店门口街角，转入马路'}]->(b);

// ── has_scene：地点拥有场景（Location → Scene，sync=true 组成关系）──
MATCH (a:Location {id: 'PHuTf3ogEr'}), (b:Scene {id: 'PHuTf3ogEu'})
MERGE (a)-[:has_scene {sync: true}]->(b);

// ── evt_relation：事件链（Event → Event，先后→因果）──
MATCH (a:Event {id: 'NvCkQmFPFx'}), (b:Event {id: 'PHuTf3ogEs'})
MERGE (a)-[:evt_relation {type: '先后', detail: '酒店出门→买咖啡'}]->(b);
MATCH (a:Event {id: 'PHuTf3ogEs'}), (b:Event {id: 'PHuTf3ogEt'})
MERGE (a)-[:evt_relation {type: '先后', detail: '买完咖啡→出门遇雨'}]->(b);
MATCH (a:Event {id: 'PHuTf3ogEt'}), (b:Event {id: 'NvCkQmFPFy'})
MERGE (a)-[:evt_relation {type: '因果', detail: '没带伞急于赶飞机，冲过街口闯马路→被撞身亡'}]->(b);

// ════════════ 旧残留清理（sec00 改海王时遗留的疏离措辞）════════════
// Event NvCkQmFPFx：title 去「逃离」，description 收尾去「借口离开拒绝」
MATCH (n:Event {id: 'NvCkQmFPFx'})
SET n.title = '陆择酒店醒来',
    n.description = '陆择酒店醒来，顾盈穿着他的白衬衫洗漱。两个海王互撩——顾盈夸陆择昨晚技术、想加微信，陆择以「太激烈、怕床受不了」调侃式拒绝，顾盈洒脱放手，互不留恋告别';

// evt_relation 酒店→车祸 直连边 detail：去「逃离」，概括新链
MATCH (a:Event {id: 'NvCkQmFPFx'})-[r:evt_relation]->(b:Event {id: 'NvCkQmFPFy'})
SET r.detail = '酒店海王式告别→出门买咖啡遇雨→冲街口赶巴士车祸';

// ════════════ sec00 顾盈立绘 description 同步海王版 ════════════
// P2vQL2d9db（玩味）：改 description + status→-1 作废重出图
MATCH (n:StandingIllustration {id: 'P2vQL2d9db'})
SET n.description = '世故妩媚的玩味笑——海王式调侃互撩的笃定。情境：互评昨晚身手、双关试探（「昨晚挺能折腾的」「嘴这么甜」），带着游戏人间的从容与对自身魅力的笃定。笑意加深露齿，身体微倾向陆择，眼神含着钩子。',
    n.status = -1;

// P2vQL2d9dc（挑眉）：仅改 description，图片保留不重出（status 不动）
MATCH (n:StandingIllustration {id: 'P2vQL2d9dc'})
SET n.description = '撩拨试探的挑眉——抛出双关或邀约、带钩子的从容，等对方接招。情境：反撩陆择（「你的衬衫比我的裙子舒服」「留个微信呗」）或被调侃后轻哼收回主动权。单边挑眉，嘴角勾起似笑非笑，下巴微抬，眼神玩味不示弱。';
