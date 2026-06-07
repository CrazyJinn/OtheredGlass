// ========== Character 节点 ==========
MERGE (n:Character {id: 'char_001'}) SET n.name = '陆择', n.gender = '男', n.description = '灵魂穿越者男主角·卷毛', n.character_tags = '渣男';
MERGE (n:Character {id: 'char_002'}) SET n.name = '伊芙', n.gender = '女', n.description = '天使·灵魂引路人', n.character_tags = '天使·天然呆';
MERGE (n:Character {id: 'char_003'}) SET n.name = '陈默', n.gender = '男', n.description = '代练高手·微胖·戴眼镜', n.character_tags = '舔狗·游戏高手·宅男';
MERGE (n:Character {id: 'char_004'}) SET n.name = '温蔓青', n.gender = '女', n.description = '陈默前女友', n.character_tags = '绿茶婊';
MERGE (n:Character {id: 'char_005'}) SET n.name = '苏晓禾', n.gender = '女', n.description = '运动康复师·马甲线·扎马尾', n.character_tags = '运动·阳光·心思细腻';
MERGE (n:Character {id: 'char_006'}) SET n.name = '林梦', n.gender = '女', n.description = '代练客户·网名"梦回峡谷"·富家千金·JK装扮白丝双马尾红色发带', n.character_tags = '黏人·话痨';
MERGE (n:Character {id: 'char_007'}) SET n.name = '沈暮雪', n.gender = '女', n.description = '星耀电竞战队经理·眼镜黑丝包臀裙', n.character_tags = '御姐·小资·外冷内热';
MERGE (n:Character {id: 'char_008'}) SET n.name = '顾盈', n.gender = '女', n.description = '陆择的一夜情对象·大波浪丰满·穿男士白衬衫', n.character_tags = '性感';
MERGE (n:Character {id: 'char_009'}) SET n.name = '江烈', n.gender = '男', n.description = '星耀电竞战队队长', n.character_tags = '';

// ========== Scene 节点 ==========
MERGE (n:Scene {id: 'scene_001'}) SET n.name = '酒店', n.description = '陆择开场醒来的酒店·顾盈在一旁洗漱';
MERGE (n:Scene {id: 'scene_002'}) SET n.name = '长江大桥', n.description = '重庆长江大桥·陈默跳江的地点';
MERGE (n:Scene {id: 'scene_003'}) SET n.name = '八楼出租屋', n.description = '陈默的住所·八楼无电梯·条件简陋';
MERGE (n:Scene {id: 'scene_004'}) SET n.name = '南滨路', n.description = '重庆南滨路·晨跑的滨江路';
MERGE (n:Scene {id: 'scene_005'}) SET n.name = '星耀电竞', n.description = '星耀电竞战队训练基地';
MERGE (n:Scene {id: 'scene_006'}) SET n.name = '咖啡店', n.description = 'Day 10 沈暮雪约见男主的咖啡店';
MERGE (n:Scene {id: 'scene_007'}) SET n.name = '西餐厅', n.description = 'Day 11 沈暮雪拉男主去吃牛排的西餐厅';
MERGE (n:Scene {id: 'scene_008'}) SET n.name = '超市', n.description = 'Day 13 苏晓禾拉男主去买菜的地方';
MERGE (n:Scene {id: 'scene_009'}) SET n.name = '漫展', n.description = 'Day 16 林梦拉男主去的漫展';
MERGE (n:Scene {id: 'scene_010'}) SET n.name = '林梦家', n.description = '超级大平层·很大但没人很安静像酒店';
MERGE (n:Scene {id: 'scene_011'}) SET n.name = '路边摊', n.description = 'Day 18 男主拉沈暮雪去吃的路边摊';
MERGE (n:Scene {id: 'scene_012'}) SET n.name = '地铁', n.description = 'Day 15 爬山后返程的地铁';
MERGE (n:Scene {id: 'scene_013'}) SET n.name = '山', n.description = 'Day 15 爬山的山';

// ========== Event 节点 ==========
MERGE (n:Event {id: 'evt_001'}) SET n.title = '陆择酒店醒来逃离', n.time = '开场', n.description = '陆择在酒店醒来·顾盈正在洗漱准备离开（穿着男主白衬衫）·陆择用"手机没电"逃离', n.type = '行动';
MERGE (n:Event {id: 'evt_002'}) SET n.title = '陆择车祸死亡', n.time = '开场', n.description = '过马路遭遇车祸·陆择死亡', n.type = '转折';
MERGE (n:Event {id: 'evt_003'}) SET n.title = '伊芙告知试炼规则', n.time = '开场', n.description = '伊芙告知试炼规则：六个试炼·每个30天·灵魂穿越拯救弱者', n.type = '交流';
MERGE (n:Event {id: 'evt_004'}) SET n.title = '陈默跳江与灵魂穿越', n.time = 'Day 0 深夜', n.description = '陈默长江大桥跳江·陆择灵魂挤入身体·翻回栏杆', n.type = '转折';
MERGE (n:Event {id: 'evt_005'}) SET n.title = '姐姐来电（主线分支A）', n.time = 'Day 0', n.description = '选择"再想想"→姐姐的电话打了过来·主线继续', n.type = '交流';
MERGE (n:Event {id: 'evt_006'}) SET n.title = '跳江BE（分支B）', n.time = 'Day 0', n.description = '选择"跳江"→BE·很多人自发买吃的祭奠', n.type = '转折';
MERGE (n:Event {id: 'evt_007'}) SET n.title = '发现转账记录删温蔓青微信', n.time = 'Day 0 深夜', n.description = '发现转账记录（66666元给温蔓青）·删除温蔓青微信', n.type = '行动';
MERGE (n:Event {id: 'evt_008'}) SET n.title = '步行回出租屋发现身体损耗', n.time = 'Day 0 凌晨', n.description = '步行回八楼出租屋·发现身体严重损耗', n.type = '状态变化';
MERGE (n:Event {id: 'evt_009'}) SET n.title = '理发买衣吃重庆小面', n.time = 'Day 1', n.description = '理发·买平价新衣·吃重庆小面——身体在食物面前发抖', n.type = '行动';
MERGE (n:Event {id: 'evt_010'}) SET n.title = '重返代练林梦点单', n.time = 'Day 2', n.description = '重返代练·林梦点单·被实力折服变成小迷妹', n.type = '行动';
MERGE (n:Event {id: 'evt_011'}) SET n.title = '南滨路晨跑偶遇苏晓禾', n.time = 'Day 4', n.description = '南滨路晨跑偶遇苏晓禾·被指出跑步姿势不对可能会伤害膝盖', n.type = '行动';
MERGE (n:Event {id: 'evt_012'}) SET n.title = '林梦提议做直播首场峰值12000', n.time = 'Day 5', n.description = '林梦提议做直播·首场峰值12000', n.type = '行动';
MERGE (n:Event {id: 'evt_013'}) SET n.title = '收到沈暮雪私信', n.time = 'Day 5 深夜', n.description = '下播后收到沈暮雪私信', n.type = '交流';
MERGE (n:Event {id: 'evt_014'}) SET n.title = '星耀电竞试训与江烈冲突', n.time = 'Day 7', n.description = '星耀电竞试训·个人碾压但团队配合差·与江烈冲突', n.type = '行动';
MERGE (n:Event {id: 'evt_015'}) SET n.title = '沈暮雪咖啡店邀加入二队', n.time = 'Day 10', n.description = '沈暮雪在咖啡店约男主·邀请加入二队', n.type = '交流';
MERGE (n:Event {id: 'evt_016'}) SET n.title = '沈暮雪拉男主去西餐厅', n.time = 'Day 11', n.description = '沈暮雪加微信后看到签名"想吃肉"·拉男主去西餐厅吃牛排', n.type = '行动';
MERGE (n:Event {id: 'evt_017'}) SET n.title = '跑步下雨去出租屋避雨', n.time = 'Day 13 上午', n.description = '跑步突然下雨·苏晓禾和男主去陈默出租屋避雨', n.type = '行动';
MERGE (n:Event {id: 'evt_018'}) SET n.title = '苏晓禾拉男主去超市', n.time = 'Day 13 下午', n.description = '苏晓禾发现男主冰箱只有可乐和泡面·强行拉他去超市·她认真挑鸡蛋青菜牛奶·男主吐槽像老夫老妻·她耳朵红了但装没听见', n.type = '行动';
MERGE (n:Event {id: 'evt_019'}) SET n.title = '林梦作为房管对喷弹幕', n.time = 'Day 14', n.description = '林梦作为房管·和阴阳怪气的弹幕对喷', n.type = '交流';
MERGE (n:Event {id: 'evt_020'}) SET n.title = '爬山', n.time = 'Day 15 白天', n.description = '爬山·男主幻想苏晓禾穿瑜伽服·实际穿休闲服', n.type = '行动';
MERGE (n:Event {id: 'evt_021'}) SET n.title = '地铁返程苏晓禾靠过来', n.time = 'Day 15 傍晚', n.description = '地铁返程·苏晓禾太累睡着·头轻轻靠过来', n.type = '状态变化';
MERGE (n:Event {id: 'evt_022'}) SET n.title = '林梦拉男主去漫展', n.time = 'Day 16 白天', n.description = '林梦拉男主去漫展·提前准备情侣角色但不敢直说·男主刚好抽到对应角色·她高兴得偷偷拍照', n.type = '行动';
MERGE (n:Event {id: 'evt_023'}) SET n.title = '漫展后送林梦回家', n.time = 'Day 16 晚上', n.description = '漫展后送林梦回家——超级大平层但没人很安静像酒店·她一边拆零食一边说"我小时候发烧家里只有保姆"·发朋友圈"今天超幸运"', n.type = '行动';
MERGE (n:Event {id: 'evt_024'}) SET n.title = '生病发烧苏晓禾送吃的', n.time = 'Day 17', n.description = '生病发烧·苏晓禾送吃的', n.type = '状态变化';
MERGE (n:Event {id: 'evt_025'}) SET n.title = '男主拉沈暮雪去路边摊', n.time = 'Day 18', n.description = '男主拉沈暮雪去路边摊·被辣出眼泪', n.type = '行动';
MERGE (n:Event {id: 'evt_026'}) SET n.title = '偷偷看苏晓禾工作约晚餐', n.time = 'Day 19', n.description = '偷偷去苏晓禾工作的地方看她·约晚餐', n.type = '行动';
MERGE (n:Event {id: 'evt_027'}) SET n.title = '三个未接来电三选一', n.time = 'Day 22', n.description = '三个未接来电·陈默开启三选一·选择一个女主进行后续剧情', n.type = '转折';
MERGE (n:Event {id: 'evt_028'}) SET n.title = '苏晓禾结局', n.time = '后日谈', n.description = '从游戏代练回归正常生活·并肩跑过大桥·恍然与过去的自己擦肩', n.type = '状态变化';
MERGE (n:Event {id: 'evt_029'}) SET n.title = '林梦结局', n.time = '后日谈', n.description = '做主播·变成大主播人气很高', n.type = '状态变化';
MERGE (n:Event {id: 'evt_030'}) SET n.title = '沈暮雪结局', n.time = '后日谈', n.description = '加入战队·夺得世界冠军', n.type = '状态变化';

// ========== Info 节点 ==========
MERGE (n:Info {id: 'info_001'}) SET n.title = '灵魂穿越者获取宿主信息的能力', n.content = '灵魂穿越者能通过系统获取宿主近期10天内的信息·更久远的信息需要通过环境叙事获得', n.knowledge_level = 1;
MERGE (n:Info {id: 'info_002'}) SET n.title = '灵魂穿越者无法直接控制宿主', n.content = '灵魂穿越者无法直接控制宿主的行为·只能在关键选择节点进行干预', n.knowledge_level = 1;
MERGE (n:Info {id: 'info_003'}) SET n.title = '试炼规则', n.content = '六个试炼·每个30天·灵魂穿越拯救弱者', n.knowledge_level = 1;
MERGE (n:Info {id: 'info_004'}) SET n.title = '陈默转账66666元给温蔓青', n.content = '陈默曾转账66666元给前女友温蔓青', n.knowledge_level = 2;
MERGE (n:Info {id: 'info_005'}) SET n.title = '陈默身体严重损耗', n.content = '陈默身体严重损耗·长期营养不良·身体在食物面前发抖', n.knowledge_level = 2;
MERGE (n:Info {id: 'info_006'}) SET n.title = '苏晓禾是运动康复师', n.content = '苏晓禾是运动康复师·指出男主跑步姿势不对可能伤害膝盖', n.knowledge_level = 2;
MERGE (n:Info {id: 'info_007'}) SET n.title = '男主代练实力极强', n.content = '男主代练实力极强·林梦点单后被实力折服变成小迷妹', n.knowledge_level = 2;
MERGE (n:Info {id: 'info_008'}) SET n.title = '男主个人碾压但团队配合差', n.content = '星耀电竞试训中男主个人实力碾压但团队配合差', n.knowledge_level = 2;
MERGE (n:Info {id: 'info_009'}) SET n.title = '林梦家境富裕', n.content = '林梦家住超级大平层·家境富裕但家人不在身边', n.knowledge_level = 2;
MERGE (n:Info {id: 'info_010'}) SET n.title = '林梦童年孤独', n.content = '林梦小时候发烧时家里只有保姆陪伴·父母长期不在身边', n.knowledge_level = 3;
MERGE (n:Info {id: 'info_011'}) SET n.title = '苏晓禾对男主有好感', n.content = '男主吐槽像老夫老妻时苏晓禾耳朵红了但装没听见·暗示她对男主有好感', n.knowledge_level = 2;
MERGE (n:Info {id: 'info_012'}) SET n.title = '男主与江烈试训冲突', n.content = '星耀电竞试训时男主与队长江烈发生冲突', n.knowledge_level = 2;
