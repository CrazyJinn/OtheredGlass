// === 角色 (Character) ===
MERGE (n:Character {id: 'char_001'}) SET n.name = '陆择', n.gender = '男', n.description = '男主角，灵魂穿越者', n.character_tags = '渣男';
MERGE (n:Character {id: 'char_002'}) SET n.name = '伊芙', n.gender = '女', n.description = '天使，灵魂引路人', n.character_tags = '天使,天然呆';
MERGE (n:Character {id: 'char_003'}) SET n.name = '陈默', n.gender = '男', n.description = '代练高手', n.character_tags = '舔狗,游戏高手,宅男';
MERGE (n:Character {id: 'char_004'}) SET n.name = '温蔓青', n.gender = '女', n.description = '陈默前女友', n.character_tags = '绿茶婊';
MERGE (n:Character {id: 'char_005'}) SET n.name = '苏晓禾', n.gender = '女', n.description = '运动康复者', n.character_tags = '运动,阳光,心思细腻';
MERGE (n:Character {id: 'char_006'}) SET n.name = '林梦', n.gender = '女', n.description = '代练客户，网名梦回峡谷', n.character_tags = '黏人,富家千金,话痨';
MERGE (n:Character {id: 'char_007'}) SET n.name = '沈暮雪', n.gender = '女', n.description = '星耀电竞战队经理', n.character_tags = '御姐,小资,外冷内热';
MERGE (n:Character {id: 'char_008'}) SET n.name = '顾盈', n.gender = '女', n.description = '陆择的一夜情对象', n.character_tags = '性感';
MERGE (n:Character {id: 'char_009'}) SET n.name = '江烈', n.gender = '男', n.description = '星耀电竞战队队长', n.character_tags = '';

// === 场景 (Scene) ===
MERGE (n:Scene {id: 'scene_001'}) SET n.name = '酒店', n.description = '陆择和顾盈过夜的酒店';
MERGE (n:Scene {id: 'scene_002'}) SET n.name = '马路/街道', n.description = '陆择逃离酒店后过马路遭遇车祸的地点';
MERGE (n:Scene {id: 'scene_003'}) SET n.name = '长江大桥', n.description = '陈默跳江的地点，后日谈苏晓禾并肩跑过此处';
MERGE (n:Scene {id: 'scene_004'}) SET n.name = '陈默出租屋', n.description = '八楼出租屋陈默和陆择的住所';
MERGE (n:Scene {id: 'scene_005'}) SET n.name = '南滨路', n.description = '晨跑地点偶遇苏晓禾';
MERGE (n:Scene {id: 'scene_006'}) SET n.name = '咖啡店', n.description = '沈暮雪约男主谈加入二队';
MERGE (n:Scene {id: 'scene_007'}) SET n.name = '西餐厅', n.description = 'Day 11 沈暮雪带男主吃牛排';
MERGE (n:Scene {id: 'scene_008'}) SET n.name = '山', n.description = 'Day 15 爬山';
MERGE (n:Scene {id: 'scene_009'}) SET n.name = '地铁', n.description = 'Day 15 傍晚返程';
MERGE (n:Scene {id: 'scene_010'}) SET n.name = '漫展', n.description = 'Day 16 漫展';
MERGE (n:Scene {id: 'scene_011'}) SET n.name = '林梦家', n.description = '超级大平层没人很安静像酒店';
MERGE (n:Scene {id: 'scene_012'}) SET n.name = '路边摊', n.description = 'Day 18 沈暮雪被辣出眼泪';
MERGE (n:Scene {id: 'scene_013'}) SET n.name = '苏晓禾工作地点', n.description = '苏晓禾工作的地方';
MERGE (n:Scene {id: 'scene_014'}) SET n.name = '超市', n.description = 'Day 13 苏晓禾拉男主去买菜';
MERGE (n:Scene {id: 'scene_015'}) SET n.name = '星耀电竞', n.description = '星耀电竞战队基地';

// === 事件 (Event) ===
MERGE (n:Event {id: 'evt_001'}) SET n.title = '陆择酒店醒来/顾盈离开', n.time = '开场', n.description = '陆择酒店醒来，顾盈穿男主白衬衫洗漱准备离开，陆择用手机没电逃离', n.type = '行动';
MERGE (n:Event {id: 'evt_002'}) SET n.title = '陆择车祸死亡', n.time = '开场', n.description = '过马路遭遇车祸死亡', n.type = '转折';
MERGE (n:Event {id: 'evt_003'}) SET n.title = '伊芙告知试炼规则', n.time = '开场', n.description = '伊芙告知试炼规则：六个试炼，每个30天，灵魂穿越拯救弱者', n.type = '交流';
MERGE (n:Event {id: 'evt_004'}) SET n.title = '陈默跳江/陆择灵魂挤入', n.time = 'Day 0 深夜', n.description = '陈默长江大桥跳江，陆择灵魂挤入身体，翻回栏杆', n.type = '转折';
MERGE (n:Event {id: 'evt_005'}) SET n.title = '分支A-姐姐电话', n.time = 'Day 0', n.description = '选择再想想，姐姐的电话打了过来，主线继续', n.type = '转折';
MERGE (n:Event {id: 'evt_006'}) SET n.title = '分支B-BE跳江', n.time = 'Day 0', n.description = '选择跳江BE，很多人自发买吃的祭奠', n.type = '转折';
MERGE (n:Event {id: 'evt_007'}) SET n.title = '发现转账记录/删除微信', n.time = 'Day 0 深夜', n.description = '发现转账记录66666元给温蔓青，删除温蔓青微信', n.type = '行动';
MERGE (n:Event {id: 'evt_008'}) SET n.title = '步行回出租屋', n.time = 'Day 0 凌晨', n.description = '步行回八楼出租屋发现身体严重损耗', n.type = '行动';
MERGE (n:Event {id: 'evt_009'}) SET n.title = '理发买衣吃面', n.time = 'Day 1', n.description = '理发、买平价新衣、吃重庆小面，身体在食物面前发抖', n.type = '行动';
MERGE (n:Event {id: 'evt_010'}) SET n.title = '重返代练/林梦点单', n.time = 'Day 2', n.description = '重返代练林梦点单被实力折服变成小迷妹', n.type = '行动';
MERGE (n:Event {id: 'evt_011'}) SET n.title = '南滨路晨跑偶遇苏晓禾', n.time = 'Day 4', n.description = '南滨路晨跑偶遇苏晓禾被指出跑步姿势不对可能伤膝盖', n.type = '行动';
MERGE (n:Event {id: 'evt_012'}) SET n.title = '林梦提议直播', n.time = 'Day 5', n.description = '林梦提议做直播首场峰值12000', n.type = '行动';
MERGE (n:Event {id: 'evt_013'}) SET n.title = '收到沈暮雪私信', n.time = 'Day 5 深夜', n.description = '下播后收到沈暮雪私信', n.type = '交流';
MERGE (n:Event {id: 'evt_014'}) SET n.title = '星耀电竞试训', n.time = 'Day 7', n.description = '星耀电竞试训个人碾压但团队配合差，与江烈冲突', n.type = '行动';
MERGE (n:Event {id: 'evt_015'}) SET n.title = '沈暮雪邀请加入二队', n.time = 'Day 10', n.description = '沈暮雪在咖啡店约男主邀请加入二队', n.type = '交流';
MERGE (n:Event {id: 'evt_016'}) SET n.title = '沈暮雪拉去西餐厅', n.time = 'Day 11', n.description = '沈暮雪加微信后看到签名想吃肉，拉男主去西餐厅吃牛排', n.type = '行动';
MERGE (n:Event {id: 'evt_017'}) SET n.title = '跑步下雨避雨出租屋', n.time = 'Day 13 上午', n.description = '跑步突然下雨两人去陈默出租屋避雨', n.type = '行动';
MERGE (n:Event {id: 'evt_018'}) SET n.title = '苏晓禾拉去超市', n.time = 'Day 13 下午', n.description = '苏晓禾发现冰箱只有可乐和泡面强行拉去超市买菜', n.type = '行动';
MERGE (n:Event {id: 'evt_019'}) SET n.title = '林梦房管对喷弹幕', n.time = 'Day 14', n.description = '林梦作为房管和阴阳怪气的弹幕对喷', n.type = '行动';
MERGE (n:Event {id: 'evt_020'}) SET n.title = '爬山', n.time = 'Day 15 白天', n.description = '爬山，幻想苏晓禾穿瑜伽服，实际休闲服', n.type = '行动';
MERGE (n:Event {id: 'evt_021'}) SET n.title = '地铁返程', n.time = 'Day 15 傍晚', n.description = '地铁返程苏晓禾太累睡着头轻轻靠过来', n.type = '行动';
MERGE (n:Event {id: 'evt_022'}) SET n.title = '林梦拉去漫展', n.time = 'Day 16 白天', n.description = '林梦拉男主去漫展准备情侣角色不敢直说男主刚好抽到对应角色', n.type = '行动';
MERGE (n:Event {id: 'evt_023'}) SET n.title = '送林梦回家', n.time = 'Day 16 晚上', n.description = '送林梦回家，超级大平层但没人很安静像酒店她说小时候发烧家里只有保姆', n.type = '行动';
MERGE (n:Event {id: 'evt_024'}) SET n.title = '生病发烧/苏晓禾送吃的', n.time = 'Day 17', n.description = '生病发烧苏晓禾送吃的', n.type = '行动';
MERGE (n:Event {id: 'evt_025'}) SET n.title = '拉沈暮雪去路边摊', n.time = 'Day 18', n.description = '男主拉沈暮雪去路边摊被辣出眼泪', n.type = '行动';
MERGE (n:Event {id: 'evt_026'}) SET n.title = '偷偷看苏晓禾工作', n.time = 'Day 19', n.description = '偷偷去苏晓禾工作的地方看她约晚餐', n.type = '行动';
MERGE (n:Event {id: 'evt_027'}) SET n.title = '三个未接来电/三选一', n.time = 'Day 22', n.description = '三个未接来电陈默开启三选一选择一个女主进行后续剧情', n.type = '转折';

// === 信息 (Info) ===
MERGE (n:Info {id: 'info_001'}) SET n.title = '灵魂穿越者能获取宿主近期信息', n.content = '灵魂穿越者能通过系统获取宿主近期的信息（暂定10天内），再久远的信息要通过环境叙事告诉玩家', n.knowledge_level = 1;
MERGE (n:Info {id: 'info_002'}) SET n.title = '灵魂穿越者只能在关键节点干预', n.content = '灵魂穿越者无法直接控制宿主的行为，只能在关键选择节点进行干预，关键选择节点实际上也就是玩家的选择项', n.knowledge_level = 1;
MERGE (n:Info {id: 'info_003'}) SET n.title = '试炼规则六个试炼每个30天', n.content = '伊芙告知：六个试炼，每个30天，灵魂穿越拯救弱者', n.knowledge_level = 1;
MERGE (n:Info {id: 'info_004'}) SET n.title = '陈默给温蔓青转账66666元', n.content = '陈默给前女友温蔓青转账66666元，被发现后删除了温蔓青的微信', n.knowledge_level = 2;
MERGE (n:Info {id: 'info_005'}) SET n.title = '陈默身体严重损耗', n.content = '陈默的身体严重损耗，步行回八楼出租屋时发现，吃东西时身体在食物面前发抖', n.knowledge_level = 1;
MERGE (n:Info {id: 'info_006'}) SET n.title = '林梦家境富裕但家庭冷漠', n.content = '林梦住超级大平层但家里没人很安静像酒店，暗示家境富裕但家庭关系冷漠', n.knowledge_level = 2;
MERGE (n:Info {id: 'info_007'}) SET n.title = '林梦从小缺乏父母陪伴', n.content = '林梦一边拆零食一边说：我小时候发烧，家里只有保姆，说明从小缺乏父母陪伴', n.knowledge_level = 3;
MERGE (n:Info {id: 'info_008'}) SET n.title = '星耀电竞试训个人碾压团队差', n.content = '陈默在星耀电竞试训中个人实力碾压但团队配合差，与队长江烈发生冲突', n.knowledge_level = 1;
MERGE (n:Info {id: 'info_009'}) SET n.title = '林梦直播首场峰值12000', n.content = '林梦提议做直播，首场峰值12000', n.knowledge_level = 1;
MERGE (n:Info {id: 'info_010'}) SET n.title = '沈暮雪邀请加入二队', n.content = '沈暮雪在咖啡店约男主，邀请陈默加入星耀电竞二队', n.knowledge_level = 1;
