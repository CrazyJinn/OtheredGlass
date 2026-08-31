"""立绘运行时整键生成（搬运层共享逻辑）。

被 generate_portrait_map.py 与 manifest_builder.py 共用，保证
「运行时拼接键 / manifest 键 / PNG 文件名」三处对齐。

键格式：<char>-<costume_short>-<variant>-<stand_id>
  - stand_id 即 guid（图 StandingIllustration.id，雪花全局唯一）→ 天然唯一，无需冲突检测。
  - costume_short = CostumeStyle.name 安全去「<char>-」前缀 + sanitize 非法字符。
  - 孤儿立绘（无 CostumeStyle 绑定）→ <char>-<variant>-<stand_id>（去 costume 段）。

Godot 侧 PortraitLayer._resolve 直接用 portrait 字段整键查 manifest；
旧章（二维键 <char>.<variant>）走「拼 who」fallback 兼容。

纯函数、无 I/O、无 neo4j 依赖，可独立单测。
"""
import re

# 键进入 PNG 文件名（assets/portraits/<key>.png），需清洗 Windows 非法字符
_ILLEGAL = re.compile(r'[\\/:*?"<>|]')


def _sanitize(s: str) -> str:
    """替换 Windows 文件名非法字符为 _，折叠首尾空白。"""
    if not s:
        return ""
    return _ILLEGAL.sub("_", s.strip())


def costume_short(char_name: str, costume_name: str | None) -> str:
    """CostumeStyle.name → 着装短名：去掉「<char>-」前缀（仅当 startswith）+ sanitize。

    「陆择-赤裸上身」→「赤裸上身」；「工作服」（无前缀）→「工作服」；None/空 → ""。
    """
    if not costume_name:
        return ""
    prefix = f"{char_name}-"
    name = costume_name[len(prefix):] if costume_name.startswith(prefix) else costume_name
    return _sanitize(name)


def make_key(char_name: str, variant: str, stand_id: str, costume_name: str | None = None) -> str:
    """生成运行时整键。

    有着装：<char>-<costume_short>-<variant>-<stand_id>  如 陆择-赤裸上身-慵懒-PHSE4iftNQ
    无着装：<char>-<variant>-<stand_id>                  如 陆择-慵懒-PHSE4iftNQ
    """
    parts = [_sanitize(char_name)]
    cs = costume_short(char_name, costume_name)  # 已 sanitize
    if cs:
        parts.append(cs)
    parts.append(_sanitize(variant))
    parts.append(_sanitize(stand_id))
    return "-".join(parts)
