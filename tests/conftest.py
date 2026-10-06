"""Fixture dùng chung: đường dẫn repo, media tổng hợp bằng ffmpeg, edit master mẫu."""
import copy
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
BRAND = os.path.join(ROOT, "brand", "brand.json")

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg trong PATH")


def ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], check=True)


def probe(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,width,height", "-of", "json", str(path)],
                       stdout=subprocess.PIPE, text=True, check=True)
    d = json.loads(p.stdout)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    return {"width": v["width"], "height": v["height"], "duration": float(d["format"]["duration"]),
            "has_audio": any(s["codec_type"] == "audio" for s in d["streams"])}


@pytest.fixture(scope="session")
def media(tmp_path_factory):
    """Clip/âm thanh tổng hợp nhỏ để test dựng phim (không cần clip AI thật)."""
    if not shutil.which("ffmpeg"):
        pytest.skip("cần ffmpeg")
    d = tmp_path_factory.mktemp("media")
    for name, src in {"a": "testsrc2", "b": "smptebars", "c": "rgbtestsrc"}.items():
        ff("-f", "lavfi", "-i", f"{src}=s=720x1280:r=24:d=4",
           "-f", "lavfi", "-i", "sine=f=330:d=4:sample_rate=48000",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", d / f"clip_{name}.mp4")
    ff("-f", "lavfi", "-i", "sine=f=660:d=1.2:sample_rate=48000", "-ac", "2", d / "vo1.wav")
    ff("-f", "lavfi", "-i", "sine=f=550:d=1.0:sample_rate=48000", "-ac", "2", d / "vo2.wav")
    ff("-f", "lavfi", "-i", "sine=f=220:d=40:sample_rate=48000", "-ac", "2", d / "music.wav")
    return d


_MASTER = {
    "version": "60",
    "output": "out/ts-demo-9x16-60s.mp4",
    "scenes": [
        {"id": "hook", "file": "a.mp4", "out": 5, "block": "HOOK", "trim": {"15": {"out": 4}}},
        {"id": "pain", "file": "a.mp4", "in": 5, "out": 10, "block": "VẤN ĐỀ"},
        {"id": "logo", "file": "logo.mp4", "out": 1.4, "block": "THƯƠNG HIỆU",
         "transition": {"type": "fade", "duration": 0.4}},
        {"id": "brand", "file": "b.mp4", "out": 8, "block": "THƯƠNG HIỆU",
         "trim": {"30": {"out": 6}, "15": {"out": 5.5}}},
        {"id": "b1", "file": "c.mp4", "out": 10, "block": "LỢI ÍCH-1"},
        {"id": "b2", "file": "d.mp4", "out": 10, "block": "LỢI ÍCH-2"},
        {"id": "b3", "file": "e.mp4", "out": 8, "block": "LỢI ÍCH-3"},
        {"id": "proof", "file": "f.mp4", "out": 5.5, "block": "BẰNG CHỨNG"},
        {"id": "offer", "file": "price.mp4", "out": 3, "block": "ƯU ĐÃI"},
        {"id": "end", "file": "end.mp4", "out": 4.5, "block": "CTA"},
    ],
    "vo": [
        {"file": "vo_hook.wav", "scene": "hook", "offset": 0.3, "text": "Học trước quên sau?"},
        {"file": "vo_pain.wav", "scene": "pain", "offset": 0.2},
        {"file": "vo_brand.wav", "scene": "brand", "offset": 0.2},
        {"file": "vo_b1.wav", "scene": "b1", "offset": 0.2},
        {"file": "vo_end_15.wav", "scene": "end", "offset": 0.2, "versions": ["15"]},
        {"file": "vo_end.wav", "scene": "end", "offset": 0.2, "versions": ["60", "30"]},
    ],
    "overlays": [{"text": "HỌC 5 PHÚT", "scene": "b1", "offset": 0.5, "duration": 2}],
}


def master_edit():
    """Edit master 60s mẫu (60.0s sau khi trừ fade 0.4s); bản 30 = 29.5s, bản 15 = 15.0s."""
    return copy.deepcopy(_MASTER)
