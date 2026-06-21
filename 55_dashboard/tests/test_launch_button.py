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
