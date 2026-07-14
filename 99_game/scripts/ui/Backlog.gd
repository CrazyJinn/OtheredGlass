extends Control
## 对话历史 Log。

var _panel := Panel.new()
var _label := RichTextLabel.new()
var _entries: Array = []

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	_panel.offset_left = 100
	_panel.offset_right = -100
	_panel.offset_top = 80
	_panel.offset_bottom = -80
	add_child(_panel)
	_label.set_anchors_preset(Control.PRESET_FULL_RECT)
	_label.offset_left = 20
	_label.offset_right = -20
	_label.offset_top = 20
	_label.offset_bottom = -20
	_label.bbcode_enabled = true
	_label.scroll_following = true
	_panel.add_child(_label)
	hide()

func append(who: String, text: String) -> void:
	var line := ("[b]%s[/b]：%s" % [who, text]) if who != "" else text
	_entries.append(line)
	_label.text = "\n".join(_entries)

func toggle() -> void:
	visible = not visible  # 切自身可见性，子 _panel 跟随父
