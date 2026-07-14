extends Node
## 存档：JSON 序列化到 user://saves/。V1 无变量无 flag，快照即指针+槽+bg+bgm。

const SAVE_DIR := "user://saves/"
const QUICK := "quick"
const AUTO := "auto"
const EXT := ".json"

func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(SAVE_DIR)

func save_slot(slot_name: String, snapshot: Dictionary) -> void:
	# 幂等：GUT .new() 不触发 _ready()，确保父目录存在再写
	DirAccess.make_dir_recursive_absolute(SAVE_DIR)
	var path := SAVE_DIR + slot_name + EXT
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		push_error("SaveManager: 无法写入 %s" % path)
		return
	f.store_string(JSON.stringify(snapshot, "  "))
	f.close()

func load_slot(slot_name: String) -> Dictionary:
	var path := SAVE_DIR + slot_name + EXT
	if not FileAccess.file_exists(path):
		return {}
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}

func list_slots() -> Array:
	var names: Array = []
	var dir := DirAccess.open(SAVE_DIR)
	if dir == null:
		return names
	dir.list_dir_begin()
	var fn := dir.get_next()
	while fn != "":
		if fn.ends_with(EXT):
			names.append(fn.get_basename())
		fn = dir.get_next()
	return names
