# 序章 sec01 咖啡店场景 · 叙事数据增量 Cypher

> 为 sec01「意外突生」插入「咖啡店买咖啡 → 出门遇雨 → 衔接街角车祸」准备的数据增量。
> **新增**：1 角色（咖啡店店员小姑娘）+ 1 地点（街角咖啡店）+ 2 事件（买咖啡撩店员 / 遇雨冲街口赶机场巴士）+ 1 场景节点（街角咖啡店-点餐台）+ 11 条边；**另含**：旧残留清理（Event 酒店醒来 + 酒店→车祸边「逃离」措辞）+ sec00 顾盈立绘 description 同步海王版（玩味 `P2vQL2d9db` 重出图、挑眉 `P2vQL2d9dc` 仅改描述）。
> **执行方式**：把下方 ```cypher 代码块**去掉围栏**存成 `.cypher` 文件，再跑：
> ```bash
> python .claude/scripts/cypher_exec.py -f <文件>.cypher --multi
> ```
> `--multi` 单事务顺序执行；全部 MERGE 幂等，可重复跑。

---

## ⚠️ 决策点：咖啡店 Location 复用 or 新建？

数据库**已存在**一个 `咖啡店` Location（id `NvCkQmFPGU`，description「沈暮雪约见男主的咖啡店」，后文章节用）。

本脚本默认**新建** `街角咖啡店`——序章陆择赶飞机路上顺手找的街边小店，与后文沈暮雪约见的咖啡店未必同一家，且现有 description 已绑定后文语义。

- **新建（默认）**：直接执行下方脚本。
- **复用已有**：删掉「街角咖啡店」那条 Location MERGE，把所有引用 `PHuTf3ogEr` 的边替换成 `NvCkQmFPGU`，并把已有 Location 的 description 泛化（去掉「沈暮雪约见」独占）。

---

## 已分配 ID（本次新增）

| 节点 | id |
|---|---|
| Character · 咖啡店小姑娘 | `PHuTf3ogEq` |
| Location · 街角咖啡店 | `PHuTf3ogEr` |
| Event · 陆择买咖啡撩店员 | `PHuTf3ogEs` |
| Event · 陆择遇雨冲街口赶机场巴士 | `PHuTf3ogEt` |
| Scene · 街角咖啡店-点餐台 | `PHuTf3ogEu` |

## 引用的现有节点 id

| 节点 | id |
|---|---|
| 陆择（Character） | `NvCkQmFPFo` |
| 酒店醒来（Event） | `NvCkQmFPFx` |
| 车祸（Event） | `NvCkQmFPFy` |
| 马路（Location） | `NvCkQmFPGP` |

---

## Cypher

```cypher
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
// 注：Info NvCkQmFPGd 经查已是海王版（title「陆择是海王」），无需清理。
// Event NvCkQmFPFx：title 去「逃离」，description 收尾去「借口离开拒绝」（当前为半改状态）
MATCH (n:Event {id: 'NvCkQmFPFx'})
SET n.title = '陆择酒店醒来',
    n.description = '陆择酒店醒来，顾盈穿着他的白衬衫洗漱。两个海王互撩——顾盈夸陆择昨晚技术、想加微信，陆择以「太激烈、怕床受不了」调侃式拒绝，顾盈洒脱放手，互不留恋告别';

// evt_relation 酒店→车祸 直连边 detail：去「逃离」，概括新链
MATCH (a:Event {id: 'NvCkQmFPFx'})-[r:evt_relation]->(b:Event {id: 'NvCkQmFPFy'})
SET r.detail = '酒店海王式告别→出门买咖啡遇雨→冲街口赶巴士车祸';

// ════════════ sec00 顾盈立绘 description 同步海王版 ════════════
// 旧 description 基于疏离语境（顾盈「主动示好加微信」/「被婉拒自尊不悦」），与 sec00 海王版（势均力敌互撩、被撩也能反撩）冲突。
// P2vQL2d9db（玩味）：改 description + status→-1 作废重出图（旧图不满意，强制覆盖旧 prompt / 旧图）
MATCH (n:StandingIllustration {id: 'P2vQL2d9db'})
SET n.description = '世故妩媚的玩味笑——海王式调侃互撩的笃定。情境：互评昨晚身手、双关试探（「昨晚挺能折腾的」「嘴这么甜」），带着游戏人间的从容与对自身魅力的笃定。笑意加深露齿，身体微倾向陆择，眼神含着钩子。',
    n.status = -1;

// P2vQL2d9dc（挑眉）：仅改 description，图片保留不重出（status 不动，仍 10）
MATCH (n:StandingIllustration {id: 'P2vQL2d9dc'})
SET n.description = '撩拨试探的挑眉——抛出双关或邀约、带钩子的从容，等对方接招。情境：反撩陆择（「你的衬衫比我的裙子舒服」「留个微信呗」）或被调侃后轻哼收回主动权。单边挑眉，嘴角勾起似笑非笑，下巴微抬，眼神玩味不示弱。';
```

---

## 执行后的事件链

```
酒店醒来 ─先后→ 买咖啡撩店员 ─先后→ 遇雨冲街口赶巴士 ─因果→ 车祸
```

> 原 `酒店醒来 -因果→ 车祸` 直连边保留作为粗粒度因果，其 detail 已由上方「旧残留清理」段从「逃离酒店→过马路车祸」更新为海王版概括。若想让细粒度链独占，执行后手动删该直连边。

---

## 后续推进（不在本 cypher 范围）

1. **sec01 剧本重写**：sec01 当前是单一「路口」scene 直接车祸，需扩为两个 scene-block——`街角咖啡店-点餐台`（买咖啡撩店员 + 出门遇雨自白）→ `马路-路口`（车祸）。sec01 当前 `status=31`，需走 plot-design 重做（或手动 `-1`）才会重跑 outliner/dialoguer。
2. **咖啡店背景图**：Scene 节点建完仅 `status=1`（数据就绪），背景图层 `SceneLayer`（dialogue 场景只需 `background` 层）由 `scene-layer-designer` 推进出图。
3. **小姑娘立绘**：龙套建议用 `narrate` 描写脸红（不 `show` 立绘），省出图成本；若一定要立绘，另建 `StandingIllustration` 节点推进。
4. **旧残留清理已并入本脚本末尾**（Event `NvCkQmFPFx` 标题/描述、酒店→车祸直连边 detail 的「逃离」措辞 → 海王版）。Info `NvCkQmFPGd` 经查已是海王版（title「陆择是海王」），无需清理。
5. **顾盈「玩味」立绘重出图**：`P2vQL2d9db` description 已改 + status 降至 -1，入库后需调 `char-stand-designer P2vQL2d9db` 重新组装 prompt 出图（旧图基于「主动示好加微信」疏离语境）。⚠️ 出图 prompt 注意 OfoxAI 安全审核——「妩媚玩味、钩子眼神」易被判性暗示情境，组词聚焦表情/光影/姿态，剥离叙事。`P2vQL2d9dc`（挑眉）仅改 description，图片保留。
