import copy
import json

import pytest

from conftest import master_edit, needs_ffmpeg, probe, run_assemble
import cutdown
from adslib import AdsError, apply_hook_variant, filter_version, validate_hook_variants, variant_output

VAR_A = {"id": "A", "type": "in-medias-res",
         "scenes": [{"id": "hA1", "file": "a.mp4", "out": 2, "block": "HOOK"},
                    {"id": "hA2", "file": "a.mp4", "in": 2, "out": 4.5, "block": "HOOK", "punch": 1.2,
                     "trim": {"15": {"out": 4}}}],
         "vo": [{"file": "vo_a.wav", "scene": "hA1", "offset": 0.3, "text": "Lại trễ deadline?"}],
         "overlays": [{"text": "LẠI TRỄ DEADLINE?", "scene": "hA1", "offset": 0.1, "duration": 2}]}


def with_variants(*vs):
    m = master_edit()
    m["hook_variants"] = [copy.deepcopy(v) for v in vs]
    return m


def test_apply_replaces_hook_scenes_and_their_vo():
    e = apply_hook_variant(master_edit(), VAR_A)
    assert [s["id"] for s in e["scenes"]][:3] == ["hA1", "hA2", "pain"]
    assert "hook" not in [s["id"] for s in e["scenes"]]
    assert e["vo"][0]["text"] == "Lại trễ deadline?"
    assert not any(v.get("scene") == "hook" for v in e["vo"])
    assert e["overlays"][0]["scene"] == "hA1" and len(e["overlays"]) == 2
    assert e["hook_variant"] == {"id": "A", "type": "in-medias-res"} and "hook_variants" not in e


def test_variant_output_name():
    assert variant_output("out/ts-x-9x16-60s.mp4", "B") == "out/ts-x-9x16-60s_hookB.mp4"


@pytest.mark.parametrize("bad, msg", [
    ([], "1–5"),
    ([dict(VAR_A, id=str(i)) for i in range(6)], "1–5"),
    ([dict(VAR_A, id="A/B")], "chữ/số"),
    ([dict(VAR_A, id="Bản 1")], "chữ/số"),
    ([VAR_A, VAR_A], "trùng id"),
    ([dict(VAR_A, type="clickbait")], "type"),
    ([dict(VAR_A, scenes=[])], "ít nhất 1 cảnh"),
    ([dict(VAR_A, scenes=[{"id": "x", "file": "a.mp4", "block": "VẤN ĐỀ"}], vo=[], overlays=[])], "HOOK"),
    ([dict(VAR_A, vo=[{"file": "v.wav", "scene": "pain", "offset": 0}])], "hA1, hA2"),
])
def test_validate_rejects(bad, msg):
    m = master_edit()
    m["hook_variants"] = bad
    with pytest.raises(AdsError, match=msg):
        validate_hook_variants(m)


def test_apply_needs_master_hook_and_scene_relative_times():
    m = master_edit()
    m["scenes"] = m["scenes"][1:]
    with pytest.raises(AdsError, match="HOOK"):
        apply_hook_variant(m, VAR_A)
    m = master_edit()
    m["vo"][1] = {"file": "x.wav", "at": 6.0}
    with pytest.raises(AdsError, match="'at'"):
        apply_hook_variant(m, VAR_A)


def test_cutdown_keeps_variants_and_variant_trim_applies():
    m = with_variants(VAR_A)
    e, _, _ = cutdown.make_cut(m, "15", {})
    assert e["hook_variants"] == m["hook_variants"]
    v = filter_version(apply_hook_variant(e, e["hook_variants"][0]), "15")
    assert [s["id"] for s in v["scenes"]][:2] == ["hA1", "hA2"] and v["scenes"][1]["out"] == 4


def test_cutdown_rejects_bad_variants():
    m = with_variants(dict(VAR_A, id="A/B"))
    with pytest.raises(AdsError):
        cutdown.make_cut(m, "15", {})


def _media_edit(media):
    def var(vid, typ, clip):
        return {"id": vid, "type": typ,
                "scenes": [{"id": f"h{vid}1", "file": str(media / clip), "out": 1.2, "block": "HOOK"},
                           {"id": f"h{vid}2", "file": str(media / clip), "in": 1.2, "out": 2.5,
                            "punch": 1.3, "block": "HOOK"}],
                "overlays": [{"text": f"HOOK {vid}", "scene": f"h{vid}1", "offset": 0.1, "duration": 2.0}]}
    return {"aspect": "9:16", "style": "cinematic-drama", "version": "5", "output": "out/ad-5s.mp4",
            "scenes": [{"id": "hook", "file": str(media / "clip_a.mp4"), "out": 2, "block": "HOOK"},
                       {"id": "end", "file": str(media / "clip_c.mp4"), "out": 2.5, "block": "CTA"}],
            "hook_variants": [var("A", "in-medias-res", "clip_a.mp4"), var("B", "cold-open", "clip_b.mp4")],
            "music": {"file": str(media / "music.wav"), "gain_db": -14}}


@needs_ffmpeg
def test_assemble_renders_one_file_per_variant(media, tmp_path):
    r = run_assemble(_media_edit(media), tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    for vid in ("A", "B"):
        out = tmp_path / "out" / f"ad-5s_hook{vid}.mp4"
        assert abs(probe(out)["duration"] - 5.0) < 0.15
        tl = json.loads((tmp_path / "out" / f"ad-5s_hook{vid}.timeline.json").read_text(encoding="utf-8"))
        assert tl["hook_variant"]["id"] == vid and tl["scenes"][0]["id"] == f"h{vid}1"
    assert not (tmp_path / "out" / "ad-5s.mp4").exists()


@needs_ffmpeg
def test_assemble_hook_flag_renders_only_that_variant(media, tmp_path):
    r = run_assemble(_media_edit(media), tmp_path, "--hook", "B")
    assert r.returncode == 0, r.stderr + r.stdout
    assert (tmp_path / "out" / "ad-5s_hookB.mp4").exists()
    assert not (tmp_path / "out" / "ad-5s_hookA.mp4").exists()
    r = run_assemble(_media_edit(media), tmp_path, "--hook", "Z", "--plan")
    assert r.returncode != 0 and "không có hook 'Z'" in r.stderr
