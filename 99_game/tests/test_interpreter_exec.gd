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

func test_mid_scene_block_auto_advances_to_next():
	"""中段 lines 执行完应顺序进下一段（套用其 bg），而非 chapter_finished。

	序章 sec00（酒店）结尾无 jump，靠 scenes[] 顺序推进到 sec01（咖啡店）。
	"""
	var interp = preload("res://scripts/autoload/ScriptInterpreter.gd").new()
	var bgs := []
	var finished := false
	interp.bg_changed.connect(func(s, t): bgs.append(s))
	interp.chapter_finished.connect(func(): finished = true)
	interp.start("chapter00_序章", "酒店")
	assert_eq(bgs[-1], "酒店-客房", "首段 bg")
	var safety := 200
	while not finished and bgs.count("街角咖啡店-点餐台") == 0 and safety > 0:
		interp.advance()
		safety -= 1
	assert_true("街角咖啡店-点餐台" in bgs, "酒店段完应自动推进到咖啡店段")
	assert_false(finished, "中段段完不应触发 chapter_finished")
