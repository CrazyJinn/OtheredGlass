import urllib.parse
from ui.components import launch_button


def test_deeplink_uses_vscode_handler():
    url = launch_button.build_deeplink("NvCkQmFPFu")
    assert url.startswith("vscode://anthropic.claude-code/open?prompt=")


def test_deeplink_embeds_char_id_and_agent():
    url = launch_button.build_deeplink("NvCkQmFPFu")
    prompt = urllib.parse.unquote(url.split("prompt=", 1)[1])
    assert "char-design" in prompt
    assert "NvCkQmFPFu" in prompt


def test_deeplink_is_url_encoded():
    url = launch_button.build_deeplink("NvCkQmFPFu")
    # 含中文时必须被 encode
    assert "%20" in url or urllib.parse.quote(" ") in url


def _prompt_of(url):
    assert url.startswith(launch_button.VSCODE_HANDLER + "?prompt=")
    return urllib.parse.unquote(url.split("prompt=", 1)[1])


def test_add_costume_deeplink_encodes_desc_and_targets_skill():
    url = launch_button.build_add_costume_deeplink("abc123", "陆择", "冬季深色大衣；军装风")
    prompt = _prompt_of(url)
    assert "陆择" in prompt
    assert "abc123" in prompt
    assert "冬季深色大衣；军装风" in prompt
    assert "char-costume-designer" in prompt
    assert "has_costume" in prompt
    assert "status=1" in prompt


def test_add_costume_deeplink_empty_desc_uses_fallback():
    url = launch_button.build_add_costume_deeplink("abc123", "陆择", "")
    prompt = _prompt_of(url)
    assert "无具体描述" in prompt
    assert "char-costume-designer" in prompt


def test_add_costume_deeplink_name_falls_back_to_id():
    url = launch_button.build_add_costume_deeplink("abc123", "", "x")
    prompt = _prompt_of(url)
    assert "abc123" in prompt


def test_add_scene_deeplink_encodes_desc_and_targets_skill():
    url = launch_button.build_add_scene_deeplink("loc1", "咖啡店", "点餐台，午后暖光")
    prompt = _prompt_of(url)
    assert "咖啡店" in prompt
    assert "loc1" in prompt
    assert "点餐台，午后暖光" in prompt
    assert "scene-designer" in prompt
    assert "has_scene" in prompt
    assert "status=1" in prompt


def test_add_scene_deeplink_whitespace_desc_uses_fallback():
    url = launch_button.build_add_scene_deeplink("loc1", "咖啡店", "   ")
    prompt = _prompt_of(url)
    assert "无具体描述" in prompt
    assert "scene-designer" in prompt
