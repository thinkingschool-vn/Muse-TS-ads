import pytest

from conftest import BRAND, needs_ffmpeg, probe
import brand_cards as bc
from adslib import ASPECTS, AdsError, load_brand

SAMPLE = {
    "logo_sting": {},
    "price_card": {"original": "1.600.000đ", "price": "1.200.000đ", "deadline": "Ưu đãi đến hết 15/10"},
    "end_card": {"cta": "Đăng ký ngay", "sub": "Ra mắt 11/10",
                 "link": "app.thinkingschool.vn/thinking-uni"},
}


@pytest.fixture(scope="module")
def brand():
    return load_brand(BRAND)


def test_fit_size():
    assert bc.fit_size("Ngắn", 68, 562) == 68
    assert bc.fit_size("A" * 40, 68, 562) < 68
    assert bc.fit_size("A" * 500, 68, 562) == 20


def test_discount_requires_deadline(brand):
    with pytest.raises(AdsError, match="hạn"):
        bc.card_fields("price_card", {"original": "1.600.000đ", "price": "1.200.000đ"}, brand)


def test_free_price_needs_no_deadline(brand):
    f = bc.card_fields("price_card", {"price": "100% MIỄN PHÍ", "label": "Học bổng"}, brand)
    assert f["label"] == "Học bổng" and "deadline" not in f


def test_end_card_requires_cta_and_link(brand):
    with pytest.raises(AdsError, match="--link"):
        bc.card_fields("end_card", {"cta": "Đăng ký"}, brand)


def test_end_card_defaults_hotline_and_qr(brand):
    f = bc.card_fields("end_card", {"cta": "Đăng ký", "link": "x.vn"}, brand)
    assert f["hotline"] == "Hotline 0909 00 64 09" and f["qr"] == brand["qr"]
    assert bc.card_fields("end_card", {"cta": "Đăng ký", "link": "x.vn", "no_qr": True}, brand)["qr"] is None


@needs_ffmpeg
@pytest.mark.parametrize("kind", list(SAMPLE))
@pytest.mark.parametrize("aspect", list(ASPECTS))
def test_layout_inside_safe_zone(brand, kind, aspect):
    plan = bc.card_plan(kind, aspect, SAMPLE[kind], brand)
    assert any(el["field"] == "logo" for el in plan["elements"])
    assert bc.check_safe(plan) == []


@needs_ffmpeg
def test_ass_strikes_only_original_price(brand):
    ass = bc.build_ass(bc.card_plan("price_card", "9:16", SAMPLE["price_card"], brand), "Be Vietnam Pro", 3.0)
    orig = next(l for l in ass.splitlines() if l.endswith("1.600.000đ"))
    price = next(l for l in ass.splitlines() if l.endswith("1.200.000đ"))
    assert "\\s1" in orig and "\\s1" not in price


@needs_ffmpeg
def test_absurdly_long_link_errors(brand, tmp_path):
    with pytest.raises(AdsError, match="vùng an toàn"):
        bc.render_card("end_card", "9:16", {"cta": "Đăng ký", "link": "x" * 120}, brand, str(tmp_path / "x.mp4"))


@needs_ffmpeg
@pytest.mark.parametrize("kind", list(SAMPLE))
@pytest.mark.parametrize("aspect", list(ASPECTS))
def test_render_card(brand, tmp_path, kind, aspect):
    out = bc.render_card(kind, aspect, SAMPLE[kind], brand, str(tmp_path / f"{kind}.mp4"))
    info = probe(out)
    assert (info["width"], info["height"]) == ASPECTS[aspect]
    assert abs(info["duration"] - bc.DEFAULT_DUR[kind]) < 0.15
    assert info["has_audio"]
