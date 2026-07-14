extends Node
## 逻辑名 → 资源路径 映射加载器。

var _data: Dictionary = {
	"portraits": {}, "scenes": {}, "bgm": {}, "sfx": {}, "cg": {}
}

func load_from_path(path: String) -> void:
	if not FileAccess.file_exists(path):
		push_error("Manifest: 文件不存在 %s" % path)
		return
	var text := FileAccess.get_file_as_string(path)
	var parsed = JSON.parse_string(text)
	if parsed == null:
		push_error("Manifest: JSON 解析失败 %s" % path)
		return
	for key in _data.keys():
		if parsed.has(key) and parsed[key] is Dictionary:
			_data[key] = parsed[key]

func get_portrait(name: String) -> String:
	return _data["portraits"].get(name, "")

func get_scene(name: String) -> String:
	return _data["scenes"].get(name, "")

func get_bgm(track: String) -> String:
	return _data["bgm"].get(track, "")

func get_sfx(track: String) -> String:
	return _data["sfx"].get(track, "")

func get_cg(name: String) -> String:
	return _data["cg"].get(name, "")
