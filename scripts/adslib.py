"""Thư viện dùng chung cho skill Muse-TS-ads.

- ASPECTS / SAFE: khung hình + vùng an toàn (assemble.py, brand_cards.py, qc.py dùng chung)
- BLOCKS / CUT_PLANS: nhãn block kịch bản quảng cáo + kế hoạch cắt bản 30s/15s
- load_brand(): đọc brand/brand.json, đổi đường dẫn thành tuyệt đối, kiểm tra file tồn tại
"""
from __future__ import annotations

import copy
import json
import os
import re
import unicodedata

ASPECTS = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (720, 720)}

# Vùng an toàn (tỷ lệ theo chiều cao/chiều rộng) — tránh UI TikTok/Reels/Shorts/Facebook che chữ.
SAFE = {
    "9:16": {"top": 0.14, "bottom": 0.24, "left": 0.08, "right": 0.14},
    "16:9": {"top": 0.08, "bottom": 0.12, "left": 0.06, "right": 0.06},
    "1:1": {"top": 0.06, "bottom": 0.10, "left": 0.06, "right": 0.06},
}

REQUIRED_BRAND = ("name", "colors", "font", "logo", "contact")


class AdsError(Exception):
    """Lỗi dữ liệu đầu vào (edit.json, brand.json, thông số thẻ) — thông báo cho người dùng."""


def load_brand(path):
    with open(path, encoding="utf-8-sig") as f:
        b = json.load(f)
    missing = [k for k in REQUIRED_BRAND if k not in b]
    if missing:
        raise AdsError(f"brand.json thiếu trường: {', '.join(missing)}")
    base = os.path.dirname(os.path.abspath(path))

    def absf(p):
        q = os.path.normpath(os.path.join(base, p))
        if not os.path.exists(q):
            raise AdsError(f"brand.json: không thấy file {q}")
        return q

    b["font"]["file"] = absf(b["font"]["file"])
    b["logo"] = {k: absf(v) for k, v in b["logo"].items()}
    if b.get("qr"):
        b["qr"] = absf(b["qr"])
    b["_dir"] = base
    return b
