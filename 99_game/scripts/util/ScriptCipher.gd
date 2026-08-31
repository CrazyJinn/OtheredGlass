extends RefCounted
## 剧本对称加解密（AES-256-CBC + PKCS7）。仅用于 Web 发布时给剧本 JSON 套壳，挡自动扒包。
##
## ⚠️ 密钥硬编码、非安全密钥。目的是让扒包者不能直接用解包工具拿到明文剧本 JSON；
## 挡不住逆向（密钥在 GDScript 里可见）。对 Galgame 剧本这是合理的防御层级。
##
## 加密在发布侧（Python: tools/encrypt_chapter.py），解密在运行时（本类）。
## 两端共享 KEY/IV/padding/magic，务必一致——改一处要同步另一处。
##
## 密文文件格式（文本）：
##   OGCRYPT1\n
##   <base64(AES-256-CBC(json_utf8))>\n

const MAGIC := "OGCRYPT1"

# 32 字节 AES-256 密钥（两端一致；tools/encrypt_chapter.py 同值）
const KEY := "ProxyLove_2024_ScriptKey_v1!!"
# 16 字节 CBC IV（两端一致）
const IV := "ProxyLoveIV01"


## 解密一段原始文件文本。明文（无 magic 头）原样返回（桌面/开发期兼容）。
func decrypt_text(raw: String) -> String:
	if not raw.begins_with(MAGIC):
		return raw  # 明文，原样返回
	# 截掉 magic 行，strip 首尾空白（Python 端密文首尾带换行，base64 解码需纯净输入）
	var after := raw.substr(MAGIC.length()).strip_edges()
	var cipher := Marshalls.base64_to_raw(after)
	if cipher.is_empty():
		push_error("ScriptCipher: base64 解码失败")
		return ""
	var ctx := AESContext.new()
	ctx.start(AESContext.MODE_CBC_DECRYPT, KEY.to_utf8_buffer(), IV.to_utf8_buffer())
	var padded := ctx.update(cipher)
	ctx.finish()
	var unpadded := _unpad_pkcs7(padded)
	return unpadded.get_string_from_utf8()


# 去 PKCS7 填充：最后一字节 = 填充长度
func _unpad_pkcs7(data: PackedByteArray) -> PackedByteArray:
	if data.is_empty():
		return data
	var pad := int(data[data.size() - 1])
	if pad <= 0 or pad > 16 or pad > data.size():
		push_error("ScriptCipher: PKCS7 填充非法 pad=%d" % pad)
		return data
	return data.slice(0, data.size() - pad)
