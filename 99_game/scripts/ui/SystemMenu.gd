extends Control
## 系统菜单：存档/读档/设置/返回标题/关闭。

signal save_requested()
signal load_requested()
signal settings_requested()
signal title_requested()
signal closed()

var _panel := Panel.new()

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_panel.set_anchors_preset(Control.PRESET_CENTER_RIGHT)
	_panel.custom_minimum_size = Vector2(360, 420)
	_panel.position = Vector2(-380, -210)
	add_child(_panel)
	var vbox := VBoxContainer.new()
	vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	vbox.offset_left = 20
	vbox.offset_right = -20
	vbox.offset_top = 20
	vbox.offset_bottom = -20
	_panel.add_child(vbox)
	for data in [["存档", save_requested], ["读档", load_requested],
				["设置", settings_requested], ["返回标题", title_requested],
				["关闭", closed]]:
		var b := Button.new()
		b.text = data[0]
		b.custom_minimum_size = Vector2(320, 56)
		var sig = data[1]  # 局部解耦，避免 lambda 捕获循环变量
		b.pressed.connect(func(): sig.emit())
		vbox.add_child(b)
	hide()

func open() -> void:
	show()

func close() -> void:
	hide()
