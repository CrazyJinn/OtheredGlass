extends SceneTree
## 【测试】挂载章包并抽查各类资源可加载（build_chapter_packs 的验收对端）。
## 用法：godot --headless -s tools/test_chapter_pack_mount.gd -- <pck绝对路径>

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		push_error("用法: test_chapter_pack_mount.gd -- <pck绝对路径>")
		quit(1)
		return
	var pck: String = args[0]
	var ok := ProjectSettings.load_resource_pack(pck, false)
	print("mount %s: %s" % [pck.get_file(), ok])
	var fail := 0
	# 每类资源抽 1（res:// 路径 = ChapterPackLoader 挂载后的全局命中路径）
	for p in [
		"data/chapters/chapter00_序章.json",
		"assets/portraits/陆择-赤裸上身-慵懒-PHSE4iftNQ.png",
		"assets/scenes/酒店-客房.png",
		"assets/bgm/晨离.wav",
		"assets/voices/陆择-chapter00_序章-s00_酒店-PxH5yKwcum.wav",
		"assets/sfx/amb-chapter00_序章-s00_酒店-PxH5yKwcuh.wav",
	]:
		var res: String = "res://" + p
		if not ResourceLoader.exists(res):
			print("MISS  " + res)
			fail += 1
			continue
		var loaded: Variant = null
		if p.ends_with(".json"):
			loaded = FileAccess.get_file_as_string(res) != ""
		else:
			loaded = load(res) != null
		print("%s %s loaded=%s" % ["OK   " if loaded else "FAIL ", res, loaded])
		if not loaded:
			fail += 1
	quit(1 if fail > 0 else 0)
