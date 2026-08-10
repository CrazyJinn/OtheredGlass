extends GutTest

func _new_interp():
	return preload("res://scripts/autoload/ScriptInterpreter.gd").new()

func test_say_sets_slot():
	var interp = _new_interp()
	var snap: Dictionary = {}
	interp.portrait_changed.connect(func(s): snap = s)
	interp.start("chapter01_新皮肤", "桥上")  # 首条 say: 陈默.沉重 center
	assert_eq(snap["center"]["who"], "陈默")
	assert_eq(snap["center"]["portrait"], "沉重")
	assert_is_null(snap["left"])

func test_show_hide_updates_slots():
	var interp = _new_interp()
	var snap: Dictionary = {}
	interp.portrait_changed.connect(func(s): snap = s.duplicate(true))
	interp._apply_portrait({"op": "show", "who": "陈默", "portrait": "疲惫", "pos": "left"})
	assert_eq(snap["left"]["portrait"], "疲惫")
	interp._apply_portrait({"op": "hide", "who": "陈默"})
	assert_is_null(snap["left"])

# 注：brief 原版依赖信号快照，但 narrate 不发 portrait_changed（connect 在 start 之后），
# snap 永远为空、断言 key 不存在必败。改为直接读 interp.slots 公开成员验证 narrate 未改槽。
func test_narrate_keeps_slots():
	var interp = _new_interp()
	interp.start("chapter01_新皮肤", "桥上")  # 首条 say 设 center=陈默.沉重
	interp.advance()  # 离开 say 到 narrate；narrate 不改槽
	# 直接读 slots：center 仍是沉重，证明 narrate 维持画面
	assert_eq(interp.slots["center"]["portrait"], "沉重")

# 回归：跨 scene-block 时 _enter_scene_block 必须清空立绘槽，避免上一段残留（序章 sec00→sec01 顾盈残留 bug）
func test_scene_block_change_clears_slots():
	var interp = _new_interp()
	# 手动构造两段，不依赖具体章文件
	interp._scenes = [
		{"id": "a", "lines": [{"op": "narrate", "text": "段A"}]},
		{"id": "b", "lines": [{"op": "narrate", "text": "段B"}]}
	]
	interp._scene_idx = 0
	interp._line_idx = 0
	# 段 A 模拟有人在场（left + right 各占槽）
	interp.slots = {"left": {"who": "陆择", "portrait": "x"}, "center": null, "right": {"who": "顾盈", "portrait": "y"}}
	# 推进跨到段 B：advance 越过段 A 末尾触发 _enter_scene_block 清场
	var start := interp.current_scene_idx()
	var guard := 0
	while interp.current_scene_idx() == start and guard < 100:
		interp.advance()
		guard += 1
	assert_eq(interp.current_scene_idx(), 1, "应已跨到段 B")
	assert_is_null(interp.slots["left"], "跨段后 left 清空")
	assert_is_null(interp.slots["right"], "跨段后 right 清空")
	assert_is_null(interp.slots["center"], "跨段后 center 清空")
