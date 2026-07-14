import json
from pathlib import Path
from validate_chapter import validate_chapter

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = str(ROOT / "data" / "剧本.schema.json")
CHAPTER = str(ROOT / "data" / "chapters" / "chapter01_新皮肤.json")


def test_valid_chapter_passes():
    ok, errors = validate_chapter(CHAPTER, SCHEMA)
    assert ok, errors


def test_missing_op_field_fails(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"meta": {"chapter": 1, "title": "x"},
                    "scenes": [{"id": "s", "scene": "x", "lines": [{"text": "hi"}]}]},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    ok, errors = validate_chapter(str(bad), SCHEMA)
    assert not ok
    assert any("op" in e or "required" in e for e in errors)


def test_bad_ending_kind_fails(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"meta": {"chapter": 1, "title": "x"},
                    "scenes": [{"id": "s", "scene": "x",
                                "lines": [{"op": "ending", "kind": "XXX"}]}]},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    ok, _ = validate_chapter(str(bad), SCHEMA)
    assert not ok
