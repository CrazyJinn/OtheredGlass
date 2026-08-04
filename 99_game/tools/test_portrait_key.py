"""portrait_key 单测：guid 整键生成（搬运层立绘去冲突）。

整键 <char>-<costume_short>-<variant>-<stand_id>，stand_id 全局唯一 → 同角色换装两套图各得各键。
"""
from portrait_key import costume_short, make_key


def test_costume_short_strips_char_prefix():
    assert costume_short("陆择", "陆择-赤裸上身") == "赤裸上身"
    assert costume_short("陆择", "陆择-商务休闲着装") == "商务休闲着装"


def test_costume_short_keeps_name_without_prefix():
    assert costume_short("陈默", "工作服") == "工作服"


def test_costume_short_none_or_empty():
    assert costume_short("陆择", None) == ""
    assert costume_short("陆择", "") == ""


def test_costume_short_sanitize_illegal_chars():
    # Windows 文件名非法字符 → _
    assert costume_short("陆择", "陆择-a/b:c") == "a_b_c"


def test_make_key_with_costume():
    assert make_key("陆择", "慵懒", "PHSE4iftNQ", "陆择-赤裸上身") == "陆择-赤裸上身-慵懒-PHSE4iftNQ"


def test_make_key_without_costume_orphan():
    assert make_key("陆择", "慵懒", "PHSE4iftNQ", None) == "陆择-慵懒-PHSE4iftNQ"


def test_make_key_disambiguates_same_char_variant_across_costumes():
    """同角色同变体、不同着装 → 不同键（去冲突的核心）。"""
    k1 = make_key("陆择", "慵懒", "PHSE4iftNQ", "陆择-赤裸上身")
    k2 = make_key("陆择", "慵懒", "PJajqyM6s4", "陆择-商务休闲着装")
    assert k1 != k2
    assert "赤裸上身" in k1 and "商务休闲着装" in k2


def test_make_key_sanitize_illegal_chars_in_segments():
    key = make_key("a", "v:x", "id1", "a-c*d")
    for ch in ":*":
        assert ch not in key
    assert "_" in key
