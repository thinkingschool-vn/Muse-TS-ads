import json
import subprocess

import pytest

from conftest import needs_ffmpeg, run_assemble
from adslib import AdsError, check_dialogue, dialogue_windows, timed_lines, vo_dialogue_clash


def test_check_dialogue_limits():
    check_dialogue([{"id": "a", "dialogue": {"speaker": "Linh", "text": " ".join(["từ"] * 15)}}])
    with pytest.raises(AdsError, match="16 từ"):
        check_dialogue([{"id": "a", "dialogue": {"speaker": "Linh", "text": " ".join(["từ"] * 16)}}])
    with pytest.raises(AdsError, match="speaker"):
        check_dialogue([{"id": "a", "dialogue": {"text": "Chào"}}])
    with pytest.raises(AdsError, match="speaker"):
        check_dialogue([{"id": "a", "dialogue": "Chào"}])


def test_windows_and_clash():
    scenes = [{"id": "a", "start": 0, "end": 2}, {"id": "t", "start": 2, "end": 5,
                                                   "dialogue": {"speaker": "Linh", "text": "Lại trễ hạn"}}]
    w = dialogue_windows(scenes)
    assert w == [(2, 5, "t", "Lại trễ hạn")]
    assert vo_dialogue_clash([(0.3, 1.5, "vo1.wav")], w) == []
    assert vo_dialogue_clash([(0.3, 2.0, "vo1.wav")], w) == []          # chạm mép, không chồng
    assert vo_dialogue_clash([(1.0, 2.6, "vo1.wav")], w) == [("vo1.wav", "t")]


def test_timed_lines_in_time_order():
    w = [(2.0, 5.0, "t", "Lại trễ hạn")]
    assert timed_lines([(0.3, "Học trước quên sau?"), (5.2, "Đăng ký ngay"), (6.0, None)], w) == [
        (0.3, "Học trước quên sau?"), (2.0, "Lại trễ hạn"), (5.2, "Đăng ký ngay")]


def _edit(media, **over):
    e = {"aspect": "9:16", "style": "micro-drama", "output": "out/d.mp4", "scenes": [
        {"id": "hook", "file": str(media / "clip_a.mp4"), "out": 2},
        {"id": "talk", "file": str(media / "clip_b.mp4"), "out": 3,
         "dialogue": {"speaker": "Linh", "text": "Lại trượt phỏng vấn nữa rồi"}},
        {"id": "end", "file": str(media / "clip_c.mp4"), "out": 2}],
        "vo": [{"file": str(media / "vo1.wav"), "scene": "hook", "offset": 0.3, "text": "Học trước quên sau?"}],
        "music": {"file": str(media / "music.wav"), "gain_db": -14}}
    e.update(over)
    return e


def mean_db(path, t0, dur):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-ss", str(t0), "-t", str(dur), "-i", str(path),
                        "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return float(p.stderr.split("mean_volume:")[1].split("dB")[0])


@needs_ffmpeg
def test_dialogue_render_boosts_scene_and_writes_script(media, tmp_path):
    r = run_assemble(_edit(media), tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    out = tmp_path / "out"
    assert (out / "d.vo.txt").read_text(encoding="utf-8").splitlines() == [
        "Học trước quên sau?", "Lại trượt phỏng vấn nữa rồi"]
    tl = json.loads((out / "d.timeline.json").read_text(encoding="utf-8"))
    assert tl["scenes"][1]["dialogue"] == "Lại trượt phỏng vấn nữa rồi"
    assert [x["text"] for x in tl["lines"]] == ["Học trước quên sau?", "Lại trượt phỏng vấn nữa rồi"]
    # tiếng gốc cảnh thoại ở 0 dB, cảnh khác ở sfx −12 dB mặc định → cảnh thoại to hơn rõ rệt
    assert mean_db(out / "d.mp4", 2.3, 2.4) > mean_db(out / "d.mp4", 5.2, 1.6) + 6


@needs_ffmpeg
def test_vo_over_dialogue_is_rejected(media, tmp_path):
    e = _edit(media)
    e["vo"].append({"file": str(media / "vo2.wav"), "scene": "talk", "offset": 0.5, "text": "đè"})
    r = run_assemble(e, tmp_path)
    assert r.returncode != 0 and "VO TRÙNG THOẠI" in r.stderr


@needs_ffmpeg
def test_dialogue_with_sfx_off_is_rejected(media, tmp_path):
    r = run_assemble(_edit(media, sfx={"keep": False}), tmp_path, "--plan")
    assert r.returncode != 0 and "sfx.keep" in r.stderr
