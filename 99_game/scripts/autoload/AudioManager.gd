extends Node
## 集中式音频管理器。BGM 播放/停止/切轨、转场音效（transition）、氛围声景（ambience）、
## 语音播放、音量设置。
# Demo 无真实音频文件，所有路径走 Manifest 取值；资源缺失时 push_warning 并静默跳过，不阻塞管线。

var _bgm: AudioStreamPlayer = null
var _transition_player: AudioStreamPlayer = null
var _ambience_player: AudioStreamPlayer = null
var _voice_player: AudioStreamPlayer = null
var _bgm_loop: bool = true
var _bgm_user_db: float = 0.0  # 用户设置的 BGM 音量（SettingsPanel 加载时写入）

# BGM 通道基础衰减（默认混音：BGM 相对听感减半，语音/音效优先）。用户音量设置叠加其上。
const BGM_BASE_GAIN_DB := -10.0

func _ready() -> void:
	_bgm = AudioStreamPlayer.new()
	_bgm.volume_db = BGM_BASE_GAIN_DB
	_transition_player = AudioStreamPlayer.new()
	_ambience_player = AudioStreamPlayer.new()
	_voice_player = AudioStreamPlayer.new()
	add_child(_bgm)
	add_child(_transition_player)
	add_child(_ambience_player)
	add_child(_voice_player)

func play_bgm(track: String, loop: bool = true) -> void:
	var path: String = _manifest().get_bgm(track) if _manifest() else ""
	if path == "" or not ResourceLoader.exists(path):
		push_warning("AudioManager: BGM 资源缺失 %s" % track)
		return
	_bgm.stream = load(path)
	_bgm_loop = loop
	_bgm.play()

func stop_bgm() -> void:
	_bgm.stop()

func fade_bgm(track: String, loop: bool = true) -> void:
	# V1：简化为切换播放目标轨道（无真实淡入淡出）
	play_bgm(track, loop)

## 转场音效（一次性短事件，1~2s 实录）。返回流时长（秒）；0 = 资源缺失/失败。
## 调用方（ScriptInterpreter）据此 await 播完再推进下一行——音效与台词不叠播。
func play_transition(track: String) -> float:
	var path: String = _manifest().get_sfx(track) if _manifest() else ""
	if path == "" or not ResourceLoader.exists(path):
		push_warning("AudioManager: 转场音效资源缺失 %s" % track)
		return 0.0
	var stream: AudioStream = load(path)
	_transition_player.stream = stream
	_transition_player.play()
	return stream.get_length() if stream else 0.0

## 氛围声景（挂 narrate 行，随旁白同出）。产物为 ~5s 带淡出的一次性片段——**播放一次
## 自然结束，不循环、不阻塞台词**（区别于 transition 转场音效的「等播完再推进」）。
## 同 track 已在播则不重启（防同段短间隔重复触发）；换 track 原地替换。
## 场景块切换由调用方 stop_ambience（打断残留长声景）。
func play_ambience(track: String) -> void:
	if _ambience_player.playing and track == _ambience_player.get_meta("track", ""):
		return  # 同声景在播：不重启（避免句间反复起播）
	var path: String = _manifest().get_sfx(track) if _manifest() else ""
	if path == "" or not ResourceLoader.exists(path):
		push_warning("AudioManager: 氛围声景资源缺失 %s" % track)
		return
	_ambience_player.stream = load(path)
	_ambience_player.set_meta("track", track)
	_ambience_player.play()

func stop_ambience() -> void:
	_ambience_player.stop()

func play_voice(key: String) -> void:
	# 首行无条件 stop：任一新 say 都自动停上一句，覆盖点击/Auto/Skip/Ctrl 所有推进路径
	_voice_player.stop()
	if key == "":
		return  # narrate / 无 voice 字段：仅停旧音不播放
	var path: String = _manifest().get_voice(key) if _manifest() else ""
	if path == "" or not ResourceLoader.exists(path):
		push_warning("AudioManager: VOICE 资源缺失 %s" % key)
		return
	_voice_player.stream = load(path)
	_voice_player.play()

func stop_voice() -> void:
	_voice_player.stop()

func set_volume(channel: String, value_db: float) -> void:
	match channel:
		"bgm":
			_bgm_user_db = value_db
			_bgm.volume_db = BGM_BASE_GAIN_DB + value_db  # 用户值叠加通道基础衰减
		"sfx":
			_transition_player.volume_db = value_db
			_ambience_player.volume_db = value_db
		"voice": _voice_player.volume_db = value_db

func _manifest():
	return Engine.get_singleton("Manifest") if Engine.has_singleton("Manifest") else null
