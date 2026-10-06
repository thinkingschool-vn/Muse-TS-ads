import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import BRAND, SCRIPTS, needs_ffmpeg
from adslib import load_brand


def items(out_dir):
    rep = json.loads((out_dir / "qc_report.json").read_text(encoding="utf-8"))
    return {(i["check"]): i["status"] for i in rep["items"]}


def run_qc(video, out_dir, *extra):
    env = dict(os.environ, QC_NO_WHISPER="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "qc.py"), "final", str(video),
                           "--out", str(out_dir), *extra],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


@pytest.fixture(scope="module")
def ad(media, tmp_path_factory):
    import brand_cards
    d = tmp_path_factory.mktemp("ad")
    card = brand_cards.render_card("end_card", "9:16", {"cta": "Đăng ký ngay", "link": "app.thinkingschool.vn"},
                                   load_brand(BRAND), str(d / "end.mp4"), duration=4.0)
    edit = {"aspect": "9:16", "version": "6", "brand": BRAND, "output": "ad-9x16-6s.mp4",
            "scenes": [{"id": "hook", "file": str(media / "clip_a.mp4"), "out": 2.5, "block": "HOOK"},
                       {"id": "end", "file": card, "block": "CTA"}],
            "vo": [{"file": str(media / "vo1.wav"), "scene": "hook", "offset": 0.3, "text": "Ra mắt 11/10"}],
            "music": {"file": str(media / "music.wav"), "gain_db": -14}}
    (d / "edit.json").write_text(json.dumps(edit, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "assemble.py"), str(d / "edit.json")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr + r.stdout
    return d, d / "ad-9x16-6s.mp4", card


def test_norm_text_is_number_aware():
    import qc
    assert qc.norm_text("Ra mắt 11/10!") == qc.norm_text("ra mắt mười một tháng mười")
    assert qc.norm_text("1.200.000đ") == qc.norm_text("một triệu hai trăm ngàn đồng")


def test_cut_into_flat_frame_is_not_jump_cut():
    import qc
    assert qc.classify_boundary(0.40, False)[0] == "FAIL"
    assert qc.classify_boundary(0.40, False, flat=True)[0] == "PASS"
    assert qc.classify_boundary(0.10, True, flat=True)[0] == "FAIL"  # định match-cut vẫn phải khớp


@needs_ffmpeg
def test_frame_spread_detects_flat_card_frame(tmp_path):
    import qc
    flat, busy = str(tmp_path / "flat.png"), str(tmp_path / "busy.png")
    for src, out in (("color=c=0x1E1B4B:s=360x640", flat), ("testsrc2=s=360x640", busy)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-frames:v", "1", out], check=True)
    assert qc.frame_spread(flat) < qc.FLAT_SPREAD <= qc.frame_spread(busy)


@needs_ffmpeg
def test_ad_checks_pass(ad, tmp_path):
    d, video, card = ad
    r = run_qc(video, tmp_path / "qc", "--duration", "6.5", "--ad", "--end-card", card,
               "--must-say", "mười một tháng mười", "--script", str(d / "ad-9x16-6s.vo.txt"))
    it = items(tmp_path / "qc")
    assert it["Thời lượng quảng cáo"] == "PASS", r.stdout
    assert it["End card cuối phim"] == "PASS"
    assert it["Mở đầu bằng HOOK"] == "PASS"
    assert it["End card khớp file thẻ"] == "PASS"
    assert it["Thông tin bắt buộc trong VO"] == "WARN"  # QC_NO_WHISPER
    assert "Kịch bản thiếu thông tin bắt buộc" not in it


@needs_ffmpeg
def test_wrong_duration_fails(ad, tmp_path):
    _, video, _ = ad
    run_qc(video, tmp_path / "qc", "--duration", "15", "--ad")
    assert items(tmp_path / "qc")["Thời lượng quảng cáo"] == "FAIL"


@needs_ffmpeg
def test_missing_end_card_fails(ad, tmp_path):
    d, video, _ = ad
    bad = tmp_path / "bad.mp4"
    shutil.copy(video, bad)
    tl = json.loads((d / "ad-9x16-6s.timeline.json").read_text(encoding="utf-8"))
    tl["scenes"][-1]["block"] = "LỢI ÍCH-1"
    (tmp_path / "bad.timeline.json").write_text(json.dumps(tl, ensure_ascii=False), encoding="utf-8")
    r = run_qc(bad, tmp_path / "qc", "--duration", "6.5", "--ad")
    assert items(tmp_path / "qc")["End card cuối phim"] == "FAIL"
    assert r.returncode == 1


@needs_ffmpeg
def test_script_missing_required_fact_fails(ad, tmp_path):
    d, video, _ = ad
    run_qc(video, tmp_path / "qc", "--must-say", "một triệu hai trăm nghìn đồng",
           "--script", str(d / "ad-9x16-6s.vo.txt"))
    assert items(tmp_path / "qc")["Kịch bản thiếu thông tin bắt buộc"] == "FAIL"
