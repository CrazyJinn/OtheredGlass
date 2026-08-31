extends Node
## 章节文件加载/缓存/结构校验。file_name 不带扩展名。
## 透明支持加密剧本：文件若有 OGCRYPT1 magic 头则先用 ScriptCipher 解密，否则按明文处理。

const DIR := "res://data/chapters/"
var _cache: Dictionary = {}
var _cipher = null

func load_chapter(file_name: String) -> Dictionary:
	if _cache.has(file_name):
		return _cache[file_name]
	var path := DIR + file_name + ".json"
	if not FileAccess.file_exists(path):
		push_error("ChapterLoader: 文件不存在 %s" % path)
		return {}
	if _cipher == null:
		_cipher = preload("res://scripts/util/ScriptCipher.gd").new()
	# decrypt_text 对明文原样返回（桌面/开发期兼容），对加密文件解密
	# 显式标注 String：_cipher 无静态类型，:= 无法从其方法返回推断
	var text: String = _cipher.decrypt_text(FileAccess.get_file_as_string(path))
	var parsed = JSON.parse_string(text)
	if parsed == null or not (parsed is Dictionary):
		push_error("ChapterLoader: JSON 解析失败 %s" % path)
		return {}
	if not _validate(parsed):
		push_error("ChapterLoader: 结构校验失败 %s" % path)
		return {}
	_cache[file_name] = parsed
	return parsed

func _validate(ch: Dictionary) -> bool:
	if not ch.has("meta") or not ch.has("scenes"):
		return false
	if not (ch["scenes"] is Array) or ch["scenes"].is_empty():
		return false
	for blk in ch["scenes"]:
		if not (blk is Dictionary):
			return false
		if not blk.has("id") or not blk.has("scene") or not blk.has("lines"):
			return false
		if not (blk["lines"] is Array):
			return false
		for line in blk["lines"]:
			if not (line is Dictionary) or not line.has("op"):
				return false
	return true
