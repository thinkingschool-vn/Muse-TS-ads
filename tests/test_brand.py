import json
import os

import pytest

from conftest import BRAND, needs_ffmpeg, probe
from adslib import ASPECTS, SAFE, AdsError, load_brand


def test_load_brand_resolves_absolute_paths():
    b = load_brand(BRAND)
    for p in (b["font"]["file"], b["logo"]["on_dark"], b["logo"]["on_light"], b["qr"]):
        assert os.path.isabs(p) and os.path.exists(p)
    assert b["colors"]["primary"] == "#0064FF"
    assert b["contact"]["hotline"] == "0909 00 64 09"


def test_load_brand_missing_key(tmp_path):
    p = tmp_path / "brand.json"
    p.write_text(json.dumps({"name": "X"}), encoding="utf-8")
    with pytest.raises(AdsError, match="thiếu"):
        load_brand(str(p))


def test_load_brand_missing_file(tmp_path):
    data = json.load(open(BRAND, encoding="utf-8-sig"))
    data["logo"]["on_dark"] = "khong-co.png"
    data["font"]["file"] = os.path.join(os.path.dirname(BRAND), "fonts", "BeVietnamPro-Bold.ttf")
    data["logo"]["on_light"] = os.path.join(os.path.dirname(BRAND), "logo-on-light.png")
    data["qr"] = os.path.join(os.path.dirname(BRAND), "zalo-qr.png")
    p = tmp_path / "brand.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AdsError, match="khong-co.png"):
        load_brand(str(p))


def test_aspects_and_safe_zones():
    assert ASPECTS == {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (720, 720)}
    assert set(SAFE) == set(ASPECTS)


@needs_ffmpeg
def test_logo_resolution_is_usable():
    b = load_brand(BRAND)
    assert probe(b["logo"]["on_dark"])["width"] >= 1000
    assert probe(b["qr"])["width"] >= 300
