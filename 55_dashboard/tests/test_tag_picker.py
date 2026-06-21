from ui.components import tag_picker


def test_merge_options_appends_gender():
    tagdef = {"label": "体态", "multi": False, "options": ["修长", "匀称"], "female": ["曼妙", "娇小"]}
    merged = tag_picker.merge_options(tagdef, "女")
    assert "曼妙" in merged and "修长" in merged


def test_merge_options_no_gender():
    tagdef = {"label": "体态", "multi": False, "options": ["修长"]}
    assert tag_picker.merge_options(tagdef, None) == ["修长"]


def test_grp_options_appends_gender():
    group = {"key": "style", "options": ["直发"], "female": ["大波浪"]}
    opts = tag_picker._grp_options(group, "女")
    assert "大波浪" in opts and "直发" in opts


def test_grp_options_no_gender():
    group = {"key": "color", "options": ["深棕"]}
    assert tag_picker._grp_options(group, None) == ["深棕"]
