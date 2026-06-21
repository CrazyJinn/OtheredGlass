from ui.components import status_badge


def test_badge_text():
    assert status_badge.badge_text(0) == "待处理"
    assert status_badge.badge_text(10) == "待审"
    assert status_badge.badge_text(11) == "批准"


def test_badge_color():
    assert status_badge.badge_color(0) == "gray"
    assert status_badge.badge_color(10) == "orange"
    assert status_badge.badge_color(11) == "green"
