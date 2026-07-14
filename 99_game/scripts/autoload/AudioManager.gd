extends Node
## 集中式音频管理器。BGM 播放/停止/切轨、SFX 播放、音量设置。
# Demo 无真实音频文件，所有路径走 Manifest 取值；资源缺失时 push_warning 并静默跳过，不阻塞管线。

var _bgm: AudioStreamPlayer = null
var _sfx_player: AudioStreamPlayer = null
var _bgm_loop: bool = true

func _ready() -> void:
	_bgm = AudioStreamPlayer.new()
	_sfx_player = AudioStreamPlayer.new()
	add_child(_bgm)
	add_child(_sfx_player)

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

func set_volume(channel: String, value_db: float) -> void:
	match channel:
		"bgm": _bgm.volume_db = value_db
		"sfx": _sfx_player.volume_db = value_db

func _manifest():
	return Engine.get_singleton("Manifest") if Engine.has_singleton("Manifest") else null
