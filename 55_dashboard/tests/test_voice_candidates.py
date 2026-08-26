import json

import pytest

from core import voice_candidates

EMOTIONS = ("平静", "高兴", "愤怒")


@pytest.fixture
def setup(tmp_path):
    """造假项目根：14_声音设计/<char>/candidates/ 下 3 候选 ref + 9 试听 + manifest。"""
    cand_dir = tmp_path / "14_声音设计" / "陆择" / "candidates"
    cand_dir.mkdir(parents=True)
    manifest = {
        "char": "陆择",
        "instruct": "青年男性，中低音，语速中速，尾音短促下收。",
        "ref_text": "上午我把书桌上的三份文件整理好……",
        "audition_texts": {e: f"{e}试听句" for e in EMOTIONS},
        "candidates": [
            {
                "key": f"c{i}",
                "ref": f"14_声音设计/陆择/candidates/陆择_c{i}_ref.wav",
                "auditions": {
                    e: f"14_声音设计/陆择/candidates/陆择_c{i}_{e}.wav" for e in EMOTIONS
                },
            }
            for i in (1, 2, 3)
        ],
    }
    for i in (1, 2, 3):
        (cand_dir / f"陆择_c{i}_ref.wav").write_bytes(f"REF-{i}".encode())
        for e in EMOTIONS:
            (cand_dir / f"陆择_c{i}_{e}.wav").write_bytes(f"EMO-{i}-{e}".encode())
    (cand_dir / "candidates.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return tmp_path, manifest


class TestLoadManifest:
    def test_ok(self, setup):
        root, _ = setup
        m = voice_candidates.load_manifest(
            "14_声音设计/陆择/candidates/candidates.json", root
        )
        assert m is not None and m["char"] == "陆择"
        assert len(m["candidates"]) == 3

    def test_empty_path_returns_none(self, setup):
        root, _ = setup
        assert voice_candidates.load_manifest(None, root) is None
        assert voice_candidates.load_manifest("", root) is None

    def test_missing_file_returns_none(self, setup):
        root, _ = setup
        assert voice_candidates.load_manifest(
            "14_声音设计/陆择/candidates/不存在.json", root
        ) is None

    def test_invalid_json_returns_none(self, setup):
        root, _ = setup
        p = root / "14_声音设计" / "陆择" / "candidates" / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert voice_candidates.load_manifest(p, root) is None

    def test_no_candidates_key_returns_none(self, setup):
        root, _ = setup
        p = root / "14_声音设计" / "陆择" / "candidates" / "empty.json"
        p.write_text(json.dumps({"char": "陆择"}), encoding="utf-8")
        assert voice_candidates.load_manifest(p, root) is None


class TestPromote:
    def test_moves_selected_to_canonical_ref(self, setup):
        root, manifest = setup
        props = voice_candidates.promote_candidate(manifest, "c2", root)
        official = root / "14_声音设计" / "陆择" / "陆择_ref.wav"
        assert official.read_bytes() == b"REF-2"  # 内容 = 选中候选
        assert not (root / "14_声音设计" / "陆择" / "candidates" / "陆择_c2_ref.wav").exists()
        assert props == {
            "ref_audio_path": "14_声音设计/陆择/陆择_ref.wav",
            "candidates_path": None,  # update_node 传 None → Neo4j 删属性
        }

    def test_overwrites_existing_official_ref(self, setup):
        root, manifest = setup
        official = root / "14_声音设计" / "陆择" / "陆择_ref.wav"
        official.write_bytes(b"OLD")  # 旧正式 ref 遗留
        voice_candidates.promote_candidate(manifest, "c3", root)
        assert official.read_bytes() == b"REF-3"

    def test_unknown_key_raises(self, setup):
        root, manifest = setup
        with pytest.raises(KeyError):
            voice_candidates.promote_candidate(manifest, "c9", root)

    def test_missing_candidate_file_raises(self, setup):
        root, manifest = setup
        (root / "14_声音设计" / "陆择" / "candidates" / "陆择_c1_ref.wav").unlink()
        with pytest.raises(FileNotFoundError):
            voice_candidates.promote_candidate(manifest, "c1", root)


class TestCleanup:
    def test_removes_candidates_dir_keeps_official(self, setup):
        root, manifest = setup
        voice_candidates.promote_candidate(manifest, "c1", root)
        voice_candidates.cleanup_candidates_dir(manifest, root)
        assert not (root / "14_声音设计" / "陆择" / "candidates").exists()
        assert (root / "14_声音设计" / "陆择" / "陆择_ref.wav").exists()

    def test_missing_dir_tolerated(self, setup):
        root, manifest = setup
        voice_candidates.cleanup_candidates_dir(manifest, root)  # 不抛
        voice_candidates.cleanup_candidates_dir(manifest, root)  # 幂等


def test_absolute_manifest_path_resolved(tmp_path):
    """manifest 传绝对路径时 load_manifest 也能读（_resolve 直通）。"""
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"char": "x", "candidates": [{"key": "c1"}]}), encoding="utf-8")
    assert voice_candidates.load_manifest(p, tmp_path) is not None
