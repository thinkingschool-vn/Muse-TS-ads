import json
import os
import subprocess
import sys

from conftest import BRAND, SCRIPTS, needs_ffmpeg, probe
import assemble


def run_assemble(edit, d, *extra):
    p = d / "edit.json"
    p.write_text(json.dumps(edit, ensure_ascii=False), encoding="utf-8")
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "assemble.py"), str(p), *extra],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_logo_intervals_skips_brand_blocks_and_merges():
    scenes = [{"start": 0, "end": 5, "block": "HOOK"}, {"start": 5, "end": 10, "block": "VẤN ĐỀ"},
              {"start": 10, "end": 11.4, "block": "THƯƠNG HIỆU"}, {"start": 11.4, "end": 20, "block": "LỢI ÍCH-1"},
              {"start": 20, "end": 24.5, "block": "CTA"}]
    assert assemble.logo_intervals(scenes, assemble.LOGO_SKIP_DEFAULT) == [(0, 10), (11.4, 20)]


@needs_ffmpeg
def test_mixed_block_tags_rejected(media, tmp_path):
    edit = {"aspect": "9:16", "scenes": [
        {"id": "a", "file": str(media / "clip_a.mp4"), "block": "HOOK"},
        {"id": "b", "file": str(media / "clip_b.mp4")}]}
    r = run_assemble(edit, tmp_path, "--plan")
    assert r.returncode != 0 and "block" in (r.stderr + r.stdout)


@needs_ffmpeg
def test_invalid_block_rejected(media, tmp_path):
    edit = {"aspect": "9:16", "scenes": [{"id": "a", "file": str(media / "clip_a.mp4"), "block": "OUTRO"}]}
    r = run_assemble(edit, tmp_path, "--plan")
    assert r.returncode != 0 and "không hợp lệ" in (r.stderr + r.stdout)


@needs_ffmpeg
def test_square_ad_with_brand_logo_and_versions(media, tmp_path):
    edit = {
        "aspect": "1:1", "version": "5", "brand": BRAND, "output": "out/ad-1x1-5s.mp4",
        "logo_bug": {"logo": "on_dark", "corner": "tr"},
        "scenes": [
            {"id": "hook", "file": str(media / "clip_a.mp4"), "out": 2.5, "block": "HOOK"},
            {"id": "extra", "file": str(media / "clip_c.mp4"), "out": 2.0, "block": "LỢI ÍCH-1", "versions": ["60"]},
            {"id": "end", "file": str(media / "clip_b.mp4"), "out": 2.0, "block": "CTA"}],
        "vo": [
            {"file": str(media / "vo1.wav"), "scene": "hook", "offset": 0.3, "text": "Học trước quên sau?"},
            {"file": str(media / "vo2.wav"), "scene": "extra", "offset": 0.2, "text": "không được có"}],
        "overlays": [{"text": "HỌC 5 PHÚT", "style": "title", "scene": "hook", "offset": 0.2, "duration": 2.0}],
        "music": {"file": str(media / "music.wav"), "gain_db": -14},
    }
    r = run_assemble(edit, tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    out = tmp_path / "out" / "ad-1x1-5s.mp4"
    info = probe(out)
    assert (info["width"], info["height"]) == (720, 720)
    assert abs(info["duration"] - 4.5) < 0.15
    tl = json.loads((tmp_path / "out" / "ad-1x1-5s.timeline.json").read_text(encoding="utf-8"))
    assert [s["block"] for s in tl["scenes"]] == ["HOOK", "CTA"]
    assert tl["version"] == "5"
    vo_txt = (tmp_path / "out" / "ad-1x1-5s.vo.txt").read_text(encoding="utf-8")
    assert "Học trước quên sau?" in vo_txt and "không được có" not in vo_txt
    assert "--ad" in r.stdout and "--duration 5" in r.stdout
