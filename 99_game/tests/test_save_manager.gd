extends GutTest

var SaveManager = preload("res://scripts/autoload/SaveManager.gd")

func test_save_and_load_roundtrip():
	var sm = SaveManager.new()
	var snap := {"file": "chapter01_新皮肤", "scene_id": "桥上", "line_idx": 2,
		"slots": {"left": null, "center": {"who": "陈默", "portrait": "沉重"}, "right": null},
		"bg": "长江大桥-栏杆", "bgm": "夜风"}
	sm.save_slot("test_slot", snap)
	var loaded = sm.load_slot("test_slot")
	assert_eq(loaded["scene_id"], "桥上")
	assert_eq(loaded["line_idx"], 2)
	assert_eq(loaded["slots"]["center"]["portrait"], "沉重")

func test_list_slots_includes_saved():
	var sm = SaveManager.new()
	sm.save_slot("test_list", {"file": "x", "scene_id": "s", "line_idx": 0, "slots": {}, "bg": "", "bgm": ""})
	var slots = sm.list_slots()
	assert_true("test_list" in slots)
