extends Control
## 设置：文字速度/自动间隔/三通道音量/全屏，存 user://settings.cfg。

const PATH := "user://settings.cfg"
var _config := ConfigFile.new()
var _panel := Panel.new()

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_panel.set_anchors_preset(Control.PRESET_CENTER)
	_panel.custom_minimum_size = Vector2(520, 520)
	_panel.position = Vector2(-260, -260)
	add_child(_panel)
	_load()
	hide()

func _load() -> void:
	_config.load(PATH)
	# 默认值：fullscreen=false，其余=0.5
	for k in ["text_speed", "auto_interval", "vol_bgm", "vol_sfx", "vol_voice", "fullscreen"]:
		if not _config.has_section_key("ui", k):
			_config.set_value("ui", k, false if k == "fullscreen" else 0.5)

func get_value(key: String) -> Variant:
	return _config.get_value("ui", key, 0.5)

func set_value(key: String, v: Variant) -> void:
	_config.set_value("ui", key, v)
	_config.save(PATH)
	_apply(key, v)

func _apply(key: String, v: Variant) -> void:
	if key == "fullscreen":
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN if v else DisplayServer.WINDOW_MODE_WINDOWED)
	elif key == "vol_bgm" and Engine.has_singleton("AudioManager"):
		Engine.get_singleton("AudioManager").set_volume("bgm", linear_to_db(float(v)))
	elif key == "vol_sfx" and Engine.has_singleton("AudioManager"):
		Engine.get_singleton("AudioManager").set_volume("sfx", linear_to_db(float(v)))
	elif key == "vol_voice" and Engine.has_singleton("AudioManager"):
		Engine.get_singleton("AudioManager").set_volume("voice", linear_to_db(float(v)))
