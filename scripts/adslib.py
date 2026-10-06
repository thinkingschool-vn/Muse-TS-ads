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


# ------------------------------------------------------------ block & cut ---
BLOCKS = ["HOOK", "VẤN ĐỀ", "THƯƠNG HIỆU", "LỢI ÍCH-1", "LỢI ÍCH-2", "LỢI ÍCH-3",
          "BẰNG CHỨNG", "ƯU ĐÃI", "CTA"]

# Bản cắt ngắn giữ các block này theo thứ tự trong master. Ghi đè bằng "cutdowns" trong edit.json.
CUT_PLANS = {
    "30": ["HOOK", "THƯƠNG HIỆU", "LỢI ÍCH-1", "ƯU ĐÃI", "CTA"],
    "15": ["HOOK", "THƯƠNG HIỆU", "CTA"],
}
TOLERANCE = 1.5  # giây — bản cắt lệch hơn mức này so với đích thì cảnh báo


def norm_block(name):
    b = unicodedata.normalize("NFC", str(name)).strip().upper()
    if b not in BLOCKS:
        raise AdsError(f"block '{name}' không hợp lệ — dùng một trong: {', '.join(BLOCKS)}")
    return b


def in_version(item, version):
    """Item không ghi 'versions' thì có mặt ở mọi bản."""
    vs = item.get("versions")
    return vs is None or str(version) in [str(v) for v in vs]


def _drop_orphans(e):
    ids = {s.get("id") for s in e.get("scenes", [])}
    for key in ("vo", "overlays"):
        if key in e:
            e[key] = [it for it in e[key] if "scene" not in it or it["scene"] in ids]
    return e


def filter_version(edit, version):
    """Bản `version`: bỏ scene/VO/overlay không thuộc bản này, áp 'trim' riêng của bản."""
    v = str(version)
    e = copy.deepcopy(edit)
    scenes = []
    for s in e.get("scenes", []):
        trim = (s.pop("trim", None) or {}).get(v)
        if not in_version(s, v):
            continue
        s.pop("versions", None)
        if trim:
            s.update({k: trim[k] for k in ("in", "out") if k in trim})
        scenes.append(s)
    e["scenes"] = scenes
    for key in ("vo", "overlays"):
        if key in e:
            kept = []
            for it in e[key]:
                if in_version(it, v):
                    it.pop("versions", None)
                    kept.append(it)
            e[key] = kept
    e["version"] = v
    return _drop_orphans(e)


def select_blocks(edit, version, plan=None):
    """Edit của bản cắt ngắn: giữ cảnh thuộc block trong kế hoạch, theo thứ tự master."""
    v = str(version)
    plan = plan or (edit.get("cutdowns") or {}).get(v) or CUT_PLANS.get(v)
    if not plan:
        raise AdsError(f"chưa có kế hoạch cắt cho bản {v}s — thêm \"cutdowns\": {{\"{v}\": [...]}} vào edit.json")
    keep = [norm_block(b) for b in plan]
    for i, s in enumerate(edit.get("scenes", [])):
        if "id" not in s:
            raise AdsError(f"cảnh #{i + 1} thiếu 'id' — bản cắt cần id cố định để gắn VO/overlay")
        if not s.get("block"):
            raise AdsError(f"cảnh {s['id']} thiếu nhãn \"block\"")
    for key in ("vo", "overlays"):
        for i, it in enumerate(edit.get(key, [])):
            if "scene" not in it:
                raise AdsError(f"{key} #{i + 1} dùng mốc 'at' tuyệt đối — bản cắt cần 'scene' + 'offset'")
    e = filter_version(edit, v)
    e["scenes"] = [s for s in e["scenes"] if norm_block(s["block"]) in keep]
    present = {norm_block(s["block"]) for s in e["scenes"]}
    missing = [b for b in keep if b not in present]
    if missing:
        raise AdsError(f"master không có cảnh nào cho block: {', '.join(missing)}")
    e.pop("cutdowns", None)
    return _drop_orphans(e)


def trans_duration(scene):
    t = scene.get("transition", "cut")
    if isinstance(t, str):
        t = {"type": t}
    return 0.0 if t.get("type", "cut") == "cut" else float(t.get("duration", 0.4))


def estimate_duration(scenes, durations):
    """Tổng thời lượng sau khi trừ chuyển cảnh. durations: {file: giây} cho cảnh không ghi 'out'."""
    total = 0.0
    for i, s in enumerate(scenes):
        t_in = float(s.get("in", 0.0))
        t_out = float(s["out"]) if "out" in s else float(durations[s["file"]])
        total += t_out - t_in
        if i < len(scenes) - 1:
            total -= trans_duration(s)
    return round(total, 3)


def output_name(master_output, version):
    root, ext = os.path.splitext(master_output)
    root = re.sub(r"-\d+s$", "", root)
    return f"{root}-{version}s{ext or '.mp4'}"
