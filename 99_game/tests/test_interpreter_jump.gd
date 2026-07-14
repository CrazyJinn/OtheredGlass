extends GutTest

func _new_interp():
	var interp = preload("res://scripts/autoload/ScriptInterpreter.gd").new()
	return interp

func test_jump_to_scene_block():
	var interp = _new_interp()
	var last_bg := ""
	interp.bg_changed.connect(func(s, t): last_bg = s)
	interp.start("chapter01_新皮肤", "桥上")
	interp._do_jump({"op": "jump", "scene": "回出租屋"})
	assert_eq(last_bg, "出租屋", "jump 到段应套用其 scene")

func test_resolve_label_within_block():
	var interp = _new_interp()
	interp.start("chapter01_新皮肤", "桥上")
	# 推进到 choice 后选「再想想」→ to=keepgoing
	var ok := interp.resolve_target("keepgoing", "", "")
	assert_true(ok)
	# 下一行应是 label 后的 say（释然）
	var got := []
	interp.line_ready.connect(func(k, p): got.append(p))
	interp._run_from_current()
	assert_eq(got[0].get("portrait"), "释然")

func test_choose_drives_jump_to_ending_scene():
	var interp = _new_interp()
	var ended_kind := ""
	interp.ended.connect(func(k, t, c): ended_kind = k)
	interp.start("chapter01_新皮肤", "桥上")
	interp.advance()  # 过 say
	interp.advance()  # 过 narrate → 撞 choice 停住（choice_presented 已发）
	interp.choose({"label": "跳下去", "scene": "结局_BE", "leads_to_ending": true})
	# 结局段：narrate（阻塞，停在 advance 前）→ 需 advance 过 narrate 到 ending
	interp.advance()
	assert_eq(ended_kind, "BE")

func test_missing_target_returns_false():
	var interp = _new_interp()
	interp.start("chapter01_新皮肤", "桥上")
	var ok := interp.resolve_target("不存在的label", "", "")
	assert_false(ok)
