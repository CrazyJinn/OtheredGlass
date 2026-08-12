extends Node
## 集中式音频管理器。BGM 播放/停止/切轨、SFX 播放、音量设置。
# Demo 无真实音频文件，所有路径走 Manifest 取值；资源缺失时 push_warning 并静默跳过，不阻塞管线。

var _bgm: AudioStreamPlayer = null
var _sfx_player: AudioStreamPlayer = null
var _voice_player: AudioStreamPlayer = null
var _bgm_loop: bool = true

func _ready() -> void:
	_bgm = AudioStreamPlayer.new()
	_sfx_player = AudioStreamPlayer.new()
	_voice_player = AudioStreamPlayer.new()
	add_child(_bgm)
	add_child(_sfx_player)
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

func play_sfx(track: String) -> void:
	var path: String = _manifest().get_sfx(track) if _manifest() else ""
	if path == "" or not ResourceLoader.exists(path):
		push_warning("AudioManager: SFX 资源缺失 %s" % track)
		return
	_sfx_player.stream = load(path)
	_sfx_player.play()

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
		"bgm": _bgm.volume_db = value_db
		"sfx": _sfx_player.volume_db = value_db
		"voice": _voice_player.volume_db = value_db

func _manifest():
	return Engine.get_singleton("Manifest") if Engine.has_singleton("Manifest") else null
