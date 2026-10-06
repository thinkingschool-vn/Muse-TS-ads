import json
import os

import pytest

from conftest import needs_ffmpeg, probe, run_assemble
import adslib
import assemble
from adslib import AdsError, check_style_use, load_style, resolve_transition


def test_resolve_transition_aliases_and_passthrough():
    assert resolve_transition("whip") == {"type": "whip", "xfade": "hblur", "duration": 0.2}
    assert resolve_transition({"type": "zoompunch"}) == {"type": "zoompunch", "xfade": "zoomin", "duration": 0.15}
    assert resolve_transition("flash") == {"type": "flash", "xfade": "fadewhite", "duration": 0.12}
    assert resolve_transition({"type": "whip", "duration": 0.3})["duration"] == 0.3
    assert resolve_transition("wipeleft") == {"type": "wipeleft", "xfade": "wipeleft", "duration": 0.4}
    assert resolve_transition("cut") == {"type": "cut", "xfade": None, "duration": 0.0}
    assert resolve_transition(None)["type"] == "cut"


def test_trans_duration_uses_alias_default():
    assert adslib.trans_duration({"transition": "flash"}) == 0.12
    assert adslib.trans_duration({"transition": {"type": "fade", "duration": 0.4}}) == 0.4


def test_style_transition_whitelist_only_when_style_explicit():
    e = {"scenes": [{"id": "a", "transition": "whip"}]}
    with pytest.raises(AdsError, match="whip"):
        check_style_use(e, load_style("warm-3d"), explicit=True)
    check_style_use(e, load_style("warm-3d"), explicit=False)
    check_style_use(e, load_style("cinematic-drama"), explicit=True)


def test_dialogue_needs_a_dialogue_style():
    e = {"scenes": [{"id": "a", "dialogue": {"speaker": "Linh", "text": "Chào"}}]}
    with pytest.raises(AdsError, match="không cho thoại"):
        check_style_use(e, load_style("warm-3d"), explicit=False)
    check_style_use(e, load_style("micro-drama"), explicit=True)


@pytest.mark.parametrize("p", [0.9, 1.6, "1.2", True])
def test_punch_out_of_range_rejected(p):
    with pytest.raises(AdsError, match="punch"):
        check_style_use({"scenes": [{"id": "a", "punch": p}]}, load_style("warm-3d"), explicit=False)


def test_scene_vf_punch():
    assert "trunc(iw*1.200/2)*2" in assemble.scene_vf(720, 1280, 24, 1.2)
    assert "trunc" not in assemble.scene_vf(720, 1280, 24, 1.0)


@needs_ffmpeg
def test_new_transitions_and_punch_render(media, tmp_path):
    edit = {"aspect": "9:16", "style": "cinematic-drama", "output": "out/x.mp4", "scenes": [
        {"id": "a", "file": str(media / "clip_a.mp4"), "out": 1.5, "transition": "whip"},
        {"id": "b", "file": str(media / "clip_a.mp4"), "in": 1.5, "out": 3, "punch": 1.3, "transition": "zoompunch"},
        {"id": "c", "file": str(media / "clip_b.mp4"), "out": 2, "transition": "flash"},
        {"id": "d", "file": str(media / "clip_c.mp4"), "out": 2}],
        "music": {"file": str(media / "music.wav"), "gain_db": -14}}
    r = run_assemble(edit, tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    info = probe(tmp_path / "out" / "x.mp4")
    assert (info["width"], info["height"]) == (720, 1280)
    assert abs(info["duration"] - (7.0 - 0.2 - 0.15 - 0.12)) < 0.15
    tl = json.loads((tmp_path / "out" / "x.timeline.json").read_text(encoding="utf-8"))
    assert tl["style"] == "cinematic-drama" and tl["hook_min_shots"] == 2


@needs_ffmpeg
def test_style_violation_stops_before_render(media, tmp_path):
    edit = {"aspect": "9:16", "style": "warm-3d", "scenes": [
        {"id": "a", "file": str(media / "clip_a.mp4"), "out": 2, "transition": "whip"},
        {"id": "b", "file": str(media / "clip_b.mp4"), "out": 2}]}
    r = run_assemble(edit, tmp_path, "--plan")
    assert r.returncode != 0 and "whip" in r.stderr and "warm-3d" in r.stderr


@needs_ffmpeg
def test_old_edit_without_style_keeps_any_xfade(media, tmp_path):
    edit = {"aspect": "9:16", "output": "old.mp4", "scenes": [
        {"id": "a", "file": str(media / "clip_a.mp4"), "out": 2, "transition": {"type": "wipeleft", "duration": 0.4}},
        {"id": "b", "file": str(media / "clip_b.mp4"), "out": 2}],
        "music": {"file": str(media / "music.wav"), "gain_db": -14}}
    r = run_assemble(edit, tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    assert abs(probe(tmp_path / "old.mp4")["duration"] - 3.6) < 0.15
    tl = json.loads((tmp_path / "old.timeline.json").read_text(encoding="utf-8"))
    assert tl["style"] == "warm-3d" and tl["hook_min_shots"] == 1


@needs_ffmpeg
def test_punch_changes_the_picture(media, tmp_path):
    import qc
    imgs = []
    for p in (1.0, 1.5):
        sc = {"path": str(media / "clip_a.mp4"), "in": 0.0, "dur": 1.0, "has_audio": True, "punch": p}
        d = tmp_path / f"p{p}"
        d.mkdir()
        seg = assemble.normalize_scene(sc, 0, 720, 1280, 24, str(d))
        imgs.append(qc.extract_frame(seg, 0.5, str(d / "f.jpg")))
    assert qc.ssim(*imgs) < 0.9
