import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import BRAND, SCRIPTS, ff, needs_ffmpeg, run_assemble
from adslib import load_brand
import qc


def items(out_dir):
    rep = json.loads((out_dir / "qc_report.json").read_text(encoding="utf-8"))
    return {i["check"]: i["status"] for i in rep["items"]}


def run_qc(video, out_dir, *extra):
    env = dict(os.environ, QC_NO_WHISPER="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "qc.py"), "final", str(video),
                           "--out", str(out_dir), *extra],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


def test_shot_starts_merges_timeline_and_detected_cuts():
    tl = {"scenes": [{"start": 0}, {"start": 1.2}, {"start": 3.0}]}
    assert qc.shot_starts(tl, [1.25, 4.0]) == [1.2, 3.0, 4.0]
    assert qc.shot_starts({"scenes": [{"start": 0}]}, []) == []


def seg(text):
    return [(0.0, 1.0, text)]


def test_dialogue_verdict():
    assert qc.dialogue_verdict("Lại trượt phỏng vấn nữa rồi", seg("lại trượt phỏng vấn nữa rồi"))[0] == "PASS"
    assert qc.dialogue_verdict("Ra mắt mười một tháng mười nhé", seg("Ra mắt 11/10 nhé"))[0] == "PASS"
    assert qc.dialogue_verdict("Lại trượt phỏng vấn nữa rồi", seg("hôm nay trời đẹp"))[0] == "FAIL"
    st, why = qc.dialogue_verdict("Lại trễ hạn", seg("lại trễ hạn rồi sếp ơi em xin lỗi mà"))
    assert st == "FAIL" and "thừa lời" in why


@needs_ffmpeg
def test_audio_onset(tmp_path):
    late, early = tmp_path / "late.wav", tmp_path / "early.wav"
    ff("-f", "lavfi", "-i", "aevalsrc='if(gte(t,1),0.5*sin(2*PI*440*t),0)':s=48000:d=3", late)
    ff("-f", "lavfi", "-i", "sine=f=440:d=3:sample_rate=48000", early)
    assert abs(qc.audio_onset(str(late)) - 1.0) < 0.1
    assert qc.audio_onset(str(early)) == 0.0


@pytest.fixture(scope="module")
def card(tmp_path_factory):
    import brand_cards
    d = tmp_path_factory.mktemp("hookcard")
    return brand_cards.render_card("end_card", "9:16", {"cta": "Đăng ký ngay", "link": "app.thinkingschool.vn"},
                                   load_brand(BRAND), str(d / "end.mp4"), duration=4.0)


@pytest.fixture(scope="module")
def good_ad(media, card, tmp_path_factory):
    d = tmp_path_factory.mktemp("hook_good")
    edit = {"aspect": "9:16", "version": "6", "brand": BRAND, "style": "cinematic-drama", "output": "good-6s.mp4",
            "logo_bug": {"logo": "on_dark", "corner": "tr"},
            "scenes": [{"id": "h1", "file": str(media / "clip_a.mp4"), "out": 1.2, "block": "HOOK"},
                       {"id": "h2", "file": str(media / "clip_a.mp4"), "in": 1.2, "out": 2.5, "punch": 1.3,
                        "block": "HOOK"},
                       {"id": "end", "file": card, "block": "CTA"}],
            "vo": [{"file": str(media / "vo1.wav"), "scene": "h1", "offset": 0.3, "text": "Học trước quên sau?"}],
            "overlays": [{"text": "HỌC TRƯỚC QUÊN SAU?", "style": "title", "scene": "h1", "offset": 0.1,
                          "duration": 2.2}],
            "music": {"file": str(media / "music.wav"), "gain_db": -14}}
    r = run_assemble(edit, d)
    assert r.returncode == 0, r.stderr + r.stdout
    return d, d / "good-6s.mp4"


@needs_ffmpeg
def test_timeline_has_hook_facts(good_ad):
    d, _ = good_ad
    tl = json.loads((d / "good-6s.timeline.json").read_text(encoding="utf-8"))
    assert tl["brand_name"] == load_brand(BRAND)["name"]
    assert tl["overlays"] == [{"start": 0.1, "end": 2.3, "text": "HỌC TRƯỚC QUÊN SAU?"}]
    assert tl["logo_bug"] and tl["logo_bug"][0][0] == 0.0


@needs_ffmpeg
def test_good_hook_passes(good_ad, tmp_path):
    _, video = good_ad
    r = run_qc(video, tmp_path / "qc", "--ad")
    it = items(tmp_path / "qc")
    for k in ("Hook: cắt cảnh đầu", "Hook: số shot 0–5s", "Hook: khung hình đầu", "Hook: chữ 0–3s",
              "Hook: âm thanh mở đầu", "Hook: thương hiệu 5s"):
        assert it[k] == "PASS", (k, r.stdout)


@needs_ffmpeg
def test_weak_hook_fails(media, card, tmp_path):
    static = tmp_path / "static.mp4"
    ff("-f", "lavfi", "-i", "color=c=0x335577:s=720x1280:r=24:d=5", "-f", "lavfi", "-i",
       "anullsrc=r=48000:cl=stereo", "-t", "5", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-shortest", static)
    edit = {"aspect": "9:16", "version": "8", "brand": BRAND, "style": "motion-graphics", "output": "weak.mp4",
            "scenes": [{"id": "h", "file": str(static), "out": 4, "block": "HOOK"},
                       {"id": "end", "file": card, "block": "CTA"}],
            "sfx": {"keep": False},
            "vo": [{"file": str(media / "vo1.wav"), "scene": "h", "offset": 1.0, "text": "Học trước quên sau?"}]}
    r = run_assemble(edit, tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    r = run_qc(tmp_path / "weak.mp4", tmp_path / "qc", "--ad")
    it = items(tmp_path / "qc")
    for k in ("Hook: cắt cảnh đầu", "Hook: số shot 0–5s", "Hook: khung hình đầu", "Hook: chữ 0–3s",
              "Hook: âm thanh mở đầu"):
        assert it[k] == "FAIL", (k, r.stdout)
    assert it["Hook: thương hiệu 5s"] == "WARN"
    assert r.returncode == 1


@needs_ffmpeg
def test_dialogue_qc_without_whisper_warns(good_ad, tmp_path):
    d, video = good_ad
    shutil.copy(video, tmp_path / "talk.mp4")
    tl = json.loads((d / "good-6s.timeline.json").read_text(encoding="utf-8"))
    tl["scenes"][1]["dialogue"] = "Lại trượt phỏng vấn nữa rồi"
    (tmp_path / "talk.timeline.json").write_text(json.dumps(tl, ensure_ascii=False), encoding="utf-8")
    run_qc(tmp_path / "talk.mp4", tmp_path / "qc")
    assert items(tmp_path / "qc")["Thoại nhân vật"] == "WARN"
