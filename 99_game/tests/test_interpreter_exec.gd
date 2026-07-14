extends GutTest

func before_each():
	# Manifest autoload 需先加载，解释器依赖它（占位图路径解析在 PortraitLayer，这里不触发）
	if not Engine.has_singleton("Manifest"):
		var m = preload("res://scripts/data/Manifest.gd").new()
		m.load_from_path("res://data/manifest.json")
		Engine.register_singleton("Manifest", m)

func test_narrate_then_say_emits_lines():
	var interp = preload("res://scripts/autoload/ScriptInterpreter.gd").new()
	var got := []
	interp.line_ready.connect(func(kind, payload): got.append([kind, payload]))
	interp.start("chapter01_新皮肤", "桥上")
	# 第一条是 say（阻塞），advance 前 line_ready 已发出 say
	assert_eq(got[0][0], "say")
	assert_eq(got[0][1]["text"], "就到这里吧。")

func test_advance_moves_past_blocking():
	var interp = preload("res://scripts/autoload/ScriptInterpreter.gd").new()
	var got := []
	interp.line_ready.connect(func(kind, payload):
		got.append([kind, payload]))
	interp.start("chapter01_新皮肤", "桥上")
	got.clear()
	interp.advance()  # 离开 say，下一条是 narrate（阻塞）→ 发 narrate 后停
	assert_eq(got[-1][0], "narrate")
	assert_eq(got[-1][1]["text"], "江风很大。他翻过栏杆。")

func test_scene_block_bg_emitted_on_enter():
	var interp = preload("res://scripts/autoload/ScriptInterpreter.gd").new()
	var bg := ""
	interp.bg_changed.connect(func(scene_name, time): bg = scene_name)
	interp.start("chapter01_新皮肤", "桥上")
	assert_eq(bg, "长江大桥-栏杆")
