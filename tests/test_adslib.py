import unicodedata

import pytest

from conftest import master_edit
from adslib import (BLOCKS, CUT_PLANS, AdsError, estimate_duration, filter_version, norm_block,
                    output_name, select_blocks)


def ids(e):
    return [s["id"] for s in e["scenes"]]


def vos(e):
    return [v["file"] for v in e["vo"]]


def test_constants():
    assert BLOCKS == ["HOOK", "VẤN ĐỀ", "THƯƠNG HIỆU", "LỢI ÍCH-1", "LỢI ÍCH-2", "LỢI ÍCH-3",
                      "BẰNG CHỨNG", "ƯU ĐÃI", "CTA"]
    assert CUT_PLANS["30"] == ["HOOK", "THƯƠNG HIỆU", "LỢI ÍCH-1", "ƯU ĐÃI", "CTA"]
    assert CUT_PLANS["15"] == ["HOOK", "THƯƠNG HIỆU", "CTA"]


def test_norm_block_accepts_nfd_and_lowercase():
    assert norm_block(unicodedata.normalize("NFD", "vấn đề")) == "VẤN ĐỀ"
    assert norm_block(" cta ") == "CTA"


def test_norm_block_rejects_unknown():
    with pytest.raises(AdsError, match="không hợp lệ"):
        norm_block("OUTRO")


def test_filter_version_master():
    e = filter_version(master_edit(), "60")
    assert e["version"] == "60"
    assert "vo_end_15.wav" not in vos(e) and "vo_end.wav" in vos(e)
    assert all("trim" not in s and "versions" not in s for s in e["scenes"])
    assert estimate_duration(e["scenes"], {}) == 60.0


def test_select_30():
    e = select_blocks(master_edit(), "30")
    assert ids(e) == ["hook", "logo", "brand", "b1", "offer", "end"]
    assert next(s for s in e["scenes"] if s["id"] == "brand")["out"] == 6
    assert vos(e) == ["vo_hook.wav", "vo_brand.wav", "vo_b1.wav", "vo_end.wav"]
    assert len(e["overlays"]) == 1
    assert estimate_duration(e["scenes"], {}) == 29.5


def test_select_15():
    e = select_blocks(master_edit(), 15)
    assert ids(e) == ["hook", "logo", "brand", "end"]
    assert e["scenes"][0]["out"] == 4
    assert vos(e) == ["vo_hook.wav", "vo_brand.wav", "vo_end_15.wav"]
    assert e["overlays"] == []
    assert estimate_duration(e["scenes"], {}) == 15.0


def test_custom_cutdowns_override():
    m = master_edit()
    m["cutdowns"] = {"15": ["HOOK", "ƯU ĐÃI", "CTA"]}
    e = select_blocks(m, "15")
    assert ids(e) == ["hook", "offer", "end"]
    assert "cutdowns" not in e


def test_missing_block_label_raises():
    m = master_edit()
    del m["scenes"][1]["block"]
    with pytest.raises(AdsError, match="pain"):
        select_blocks(m, "30")


def test_scene_without_id_raises():
    m = master_edit()
    del m["scenes"][0]["id"]
    with pytest.raises(AdsError, match="id"):
        select_blocks(m, "30")


def test_absolute_at_raises():
    m = master_edit()
    m["vo"][0] = {"file": "x.wav", "at": 1.0}
    with pytest.raises(AdsError, match="'at'"):
        select_blocks(m, "30")


def test_missing_planned_block_raises():
    m = master_edit()
    m["scenes"] = [s for s in m["scenes"] if s["id"] != "offer"]
    with pytest.raises(AdsError, match="ƯU ĐÃI"):
        select_blocks(m, "30")


def test_unknown_version_raises():
    with pytest.raises(AdsError, match="20s"):
        select_blocks(master_edit(), "20")


def test_estimate_uses_probed_duration():
    assert estimate_duration([{"file": "x.mp4", "in": 1}], {"x.mp4": 4.0}) == 3.0


def test_output_name():
    assert output_name("out/ts-demo-9x16-60s.mp4", "30") == "out/ts-demo-9x16-30s.mp4"
    assert output_name("final.mp4", 15) == "final-15s.mp4"
