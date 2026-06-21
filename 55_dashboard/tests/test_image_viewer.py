from ui.components import image_viewer


def test_resolve_path_none_when_missing():
    assert image_viewer.resolve_path("nonexistent.png") is None


def test_resolve_path_none_when_empty():
    assert image_viewer.resolve_path("") is None
    assert image_viewer.resolve_path(None) is None


def test_resolve_path_existing(tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    assert image_viewer.resolve_path(str(f)) == f
