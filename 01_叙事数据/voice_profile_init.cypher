// 角色基线声音档案（VoiceProfile）实例初始化
// instruct / ref_text 从 15_声音/luze_voice_build.py、guying_voice_build.py 提取
// ref_audio_path / clone_prompt_path 指向派生产物（首次配音时由 voice_clone_runner 按需固化）

// 陆择声音档案
MERGE (v:VoiceProfile {id:'PWognMSnxI'})
SET v.name='陆择声音档案',
    v.instruct='青年男性，20余岁，中低音略带沙哑；玩世不恭的调侃腔调，嘴角噙笑、语气松弛慵懒，像用渣男口头话把真实情绪裹起来；语速不快，尾音常带一丝玩味的上扬；表面从容，底下偶有一沉。',
    v.ref_text='嗯……这床是真不行，我都怕它散架。',
    v.ref_audio_path='15_声音/output/陆择_ref.wav',
    v.clone_prompt_path='15_声音/output/陆择_clone_prompt.pt',
    v.description='玩世不恭的调侃腔，中低音略沙哑（依据 06_角色美术 立绘变体 轻佻/沉吟）',
    v.status=1
WITH v
MATCH (c:Character {id:'NvCkQmFPFo'})
MERGE (c)-[r:has_voice_profile]->(v) SET r.sync=true;

// 顾盈声音档案
MERGE (v:VoiceProfile {id:'PWognMSnxJ'})
SET v.name='顾盈声音档案',
    v.instruct='成熟女性，约28岁，中音略偏低、嗓音圆润；气定神闲、似笑非笑的玩味腔调，从容笃定中暗藏锐利；是被撩也能反撩的对手，松弛慵懒却始终掌控节奏；语速不疾不徐，尾音常带一丝戏谑的上扬；表面温和随性，底子自信而漫不经心。',
    v.ref_text='哟，这才醒啊——咖啡都凉了，我可没等你。',
    v.ref_audio_path='15_声音/output/顾盈_ref.wav',
    v.clone_prompt_path='15_声音/output/顾盈_clone_prompt.pt',
    v.description='成熟从容的玩味反撩，中音略偏低（依据 06_角色美术 立绘变体 挑眉/玩味/慵懒）',
    v.status=1
WITH v
MATCH (c:Character {id:'NvCkQmFPFv'})
MERGE (c)-[r:has_voice_profile]->(v) SET r.sync=true;
