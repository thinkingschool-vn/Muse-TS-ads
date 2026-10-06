#!/usr/bin/env python3
"""Thẻ thương hiệu Thinking School render bằng ffmpeg — chữ, giá, logo, QR luôn chính xác.

  brand_cards.py logo_sting --aspect 9:16 --out cards/logo.mp4
  brand_cards.py price_card --aspect 9:16 --price "1.200.000đ" --original "1.600.000đ" \\
                 --deadline "Ưu đãi đến hết 15/10" --out cards/price.mp4
  brand_cards.py end_card   --aspect 9:16 --cta "Đăng ký ngay" --sub "Ra mắt 11/10" \\
                 --link "app.thinkingschool.vn/thinking-uni" --out cards/end.mp4

Mỗi thẻ là MP4 H.264 đúng khung (720×1280 / 1280×720 / 720×720), 24fps, có track âm thanh câm
để assemble.py nối/crossfade như cảnh thường. Gắn vào edit.json như một scene:
logo_sting → block THƯƠNG HIỆU · price_card → ƯU ĐÃI · end_card → CTA.
Cần ffmpeg ≥ 6.1 (filter gradients + libass).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from adslib import ASPECTS, SAFE, AdsError, configure_utf8_console, load_brand  # noqa: E402

DEFAULT_BRAND = os.path.normpath(os.path.join(HERE, "..", "brand", "brand.json"))
DEFAULT_DUR = {"logo_sting": 1.4, "price_card": 3.0, "end_card": 4.5}
GLYPH_W = 0.58  # bề rộng trung bình 1 ký tự ≈ 0,58 × cỡ chữ (Be Vietnam Pro Bold)
MIN_SIZE = 20
TEXT_FIELDS = ("tagline", "label", "original", "price", "deadline", "cta", "sub", "link", "hotline")

# (loại, trường, x, y, tùy chọn) — x, y: tâm phần tử theo tỷ lệ khung; x = .5 nghĩa là giữa VÙNG AN TOÀN.
# image: w = bề rộng theo tỷ lệ chiều rộng khung. text: size = cỡ chữ px (cạnh ngắn của cả 3 khung = 720px).
# maxw: bề rộng tối đa của dòng chữ theo tỷ lệ chiều rộng khung (mặc định = bề rộng vùng an toàn).
LAYOUTS = {
    "logo_sting": {
        "9:16": [("image", "logo", .5, .46, {"w": .62}),
                 ("text", "tagline", .5, .555, {"size": 34, "color": "muted", "delay": 250})],
        "16:9": [("image", "logo", .5, .44, {"w": .34}),
                 ("text", "tagline", .5, .62, {"size": 34, "color": "muted", "delay": 250})],
        "1:1": [("image", "logo", .5, .44, {"w": .56}),
                ("text", "tagline", .5, .62, {"size": 32, "color": "muted", "delay": 250})],
    },
    "price_card": {
        "9:16": [("image", "logo", .5, .22, {"w": .36}),
                 ("text", "label", .5, .36, {"size": 44, "color": "text"}),
                 ("text", "original", .5, .45, {"size": 56, "color": "muted", "strike": True, "delay": 150}),
                 ("text", "price", .5, .55, {"size": 104, "color": "accent", "pop": True, "delay": 350}),
                 ("text", "deadline", .5, .66, {"size": 40, "color": "text", "delay": 600})],
        "16:9": [("image", "logo", .5, .18, {"w": .20}),
                 ("text", "label", .5, .34, {"size": 40, "color": "text"}),
                 ("text", "original", .5, .46, {"size": 52, "color": "muted", "strike": True, "delay": 150}),
                 ("text", "price", .5, .62, {"size": 100, "color": "accent", "pop": True, "delay": 350}),
                 ("text", "deadline", .5, .78, {"size": 38, "color": "text", "delay": 600})],
        "1:1": [("image", "logo", .5, .14, {"w": .34}),
                ("text", "label", .5, .30, {"size": 40, "color": "text"}),
                ("text", "original", .5, .42, {"size": 52, "color": "muted", "strike": True, "delay": 150}),
                ("text", "price", .5, .57, {"size": 100, "color": "accent", "pop": True, "delay": 350}),
                ("text", "deadline", .5, .74, {"size": 38, "color": "text", "delay": 600})],
    },
    "end_card": {
        "9:16": [("image", "logo", .5, .21, {"w": .56}),
                 ("text", "cta", .5, .33, {"size": 68, "color": "accent", "pop": True, "delay": 200}),
                 ("text", "sub", .5, .395, {"size": 40, "color": "text", "delay": 300}),
                 ("text", "link", .5, .45, {"size": 32, "color": "text", "delay": 400}),
                 ("image", "qr", .5, .59, {"w": .30, "delay": 500}),
                 ("text", "hotline", .5, .725, {"size": 36, "color": "text", "delay": 600})],
        "16:9": [("image", "logo", .34, .22, {"w": .30}),
                 ("text", "cta", .34, .42, {"size": 64, "color": "accent", "pop": True, "delay": 200, "maxw": .52}),
                 ("text", "sub", .34, .54, {"size": 38, "color": "text", "delay": 300, "maxw": .52}),
                 ("text", "link", .34, .64, {"size": 30, "color": "text", "delay": 400, "maxw": .52}),
                 ("text", "hotline", .34, .75, {"size": 32, "color": "text", "delay": 600, "maxw": .52}),
                 ("image", "qr", .76, .48, {"w": .20, "delay": 500})],
        "1:1": [("image", "logo", .5, .13, {"w": .38}),
                ("text", "cta", .5, .28, {"size": 58, "color": "accent", "pop": True, "delay": 200}),
                ("text", "sub", .5, .365, {"size": 34, "color": "text", "delay": 300}),
                ("text", "link", .5, .44, {"size": 28, "color": "text", "delay": 400}),
                ("image", "qr", .5, .64, {"w": .28, "delay": 500}),
                ("text", "hotline", .5, .86, {"size": 30, "color": "text", "delay": 600})],
    },
}


def fit_size(text, size, max_w):
    """Thu nhỏ cỡ chữ để dòng chữ (ước tính) vừa bề rộng max_w px; tối thiểu MIN_SIZE."""
    n = max(1, len(text))
    return max(MIN_SIZE, min(size, int(max_w / (GLYPH_W * n))))


def image_size(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height", "-of", "csv=p=0:s=x", path],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        w, h = (int(v) for v in p.stdout.strip().split("x")[:2])
    except ValueError:
        raise AdsError(f"không đọc được kích thước ảnh: {path}")
    return w, h


def card_fields(kind, fields, brand):
    """Chuẩn hóa trường chữ theo loại thẻ + áp luật thương hiệu (BRAND_GUIDE)."""
    f = {k: (v.strip() if isinstance(v, str) else v) for k, v in fields.items() if v not in (None, "")}
    if kind == "logo_sting":
        if f.pop("no_tagline", False):
            f.pop("tagline", None)
        else:
            f.setdefault("tagline", brand.get("tagline", ""))
    elif kind == "price_card":
        if not f.get("price"):
            raise AdsError("price_card cần --price")
        if f.get("original") and not f.get("deadline"):
            raise AdsError("Giá ưu đãi (có --original) bắt buộc kèm hạn --deadline (BRAND_GUIDE)")
        f.setdefault("label", "Học phí ưu đãi" if f.get("original") else "Học phí")
    elif kind == "end_card":
        for k in ("cta", "link"):
            if not f.get(k):
                raise AdsError(f"end_card cần --{k}")
        f.setdefault("hotline", "Hotline " + brand["contact"]["hotline"])
        f["qr"] = None if (f.pop("no_qr", False) or not brand.get("qr")) else brand["qr"]
    else:
        raise AdsError(f"loại thẻ phải là: {', '.join(LAYOUTS)}")
    f["logo"] = brand["logo"]["on_dark"]
    return f


def card_plan(kind, aspect, fields, brand):
    if kind not in LAYOUTS:
        raise AdsError(f"loại thẻ phải là: {', '.join(LAYOUTS)}")
    if aspect not in ASPECTS:
        raise AdsError(f"aspect phải là: {', '.join(ASPECTS)}")
    W, H = ASPECTS[aspect]
    s = SAFE[aspect]
    f = card_fields(kind, fields, brand)
    els = []
    for typ, field, x, y, o in LAYOUTS[kind][aspect]:
        val = f.get(field)
        if not val:
            continue
        cx = ((s["left"] + 1 - s["right"]) / 2 if x == .5 else x) * W
        cy = y * H
        if typ == "image":
            iw, ih = image_size(val)
            w = int(o["w"] * W)
            h = round(w * ih / iw)
            els.append({"type": "image", "field": field, "path": val, "w": w, "cx": cx, "cy": cy,
                        "delay": o.get("delay", 0), "box": (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)})
        else:
            maxw = o.get("maxw", 1 - s["left"] - s["right"]) * W
            size = fit_size(val, o["size"], maxw)
            tw, th = GLYPH_W * size * len(val), 1.2 * size
            els.append({"type": "text", "field": field, "text": val, "size": size,
                        "color": brand["colors"][o["color"]], "strike": o.get("strike", False),
                        "pop": o.get("pop", False), "delay": o.get("delay", 0), "cx": cx, "cy": cy,
                        "box": (cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2)})
    return {"kind": kind, "aspect": aspect, "W": W, "H": H, "elements": els}


def check_safe(plan):
    """Danh sách phần tử tràn vùng an toàn (rỗng = đạt)."""
    W, H = plan["W"], plan["H"]
    s = SAFE[plan["aspect"]]
    lo_x, hi_x = W * s["left"] - 1, W * (1 - s["right"]) + 1
    lo_y, hi_y = H * s["top"] - 1, H * (1 - s["bottom"]) + 1
    bad = []
    for el in plan["elements"]:
        x0, y0, x1, y1 = el["box"]
        if x0 < lo_x or x1 > hi_x or y0 < lo_y or y1 > hi_y:
            bad.append(f"{el['field']} ({x0:.0f},{y0:.0f})–({x1:.0f},{y1:.0f})")
    return bad


def ass_bgr(hex_rgb):
    h = hex_rgb.lstrip("#")
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def _esc(t):
    return t.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def build_ass(plan, font_name, duration):
    W, H = plan["W"], plan["H"]
    end = f"0:00:{duration:05.2f}"
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2",
             "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
             "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
             "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             f"Style: Card,{font_name},40,&H00FFFFFF,&H000000FF,&H00101018,&H96000000,"
             "-1,0,0,0,100,100,0,0,1,0,2,5,0,0,0,1",
             "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for el in plan["elements"]:
        if el["type"] != "text":
            continue
        d = int(el["delay"])
        tags = f"\\an5\\pos({el['cx']:.0f},{el['cy']:.0f})\\fs{el['size']}\\c{ass_bgr(el['color'])}"
        if el["strike"]:
            tags += "\\s1"
        tags += f"\\alpha&HFF&\\t({d},{d + 250},\\alpha&H00&)"
        if el["pop"]:
            tags += f"\\fscx70\\fscy70\\t({d},{d + 220},\\fscx100\\fscy100)"
        lines.append(f"Dialogue: 0,0:00:00.00,{end},Card,,0,0,0,,{{{tags}}}{_esc(el['text'])}")
    return "\n".join(lines) + "\n"


def render_card(kind, aspect, fields, brand, out, duration=None, fps=24):
    plan = card_plan(kind, aspect, fields, brand)
    bad = check_safe(plan)
    if bad:
        raise AdsError("chữ/ảnh tràn vùng an toàn — rút gọn nội dung: " + "; ".join(bad))
    dur = float(duration or DEFAULT_DUR[kind])
    W, H = plan["W"], plan["H"]
    c0 = brand["colors"].get("bg_dark", "#0B1020").lstrip("#")
    c1 = brand["colors"].get("bg_dark2", "#1E1B4B").lstrip("#")
    work = tempfile.mkdtemp(prefix="card_")
    try:
        os.makedirs(os.path.join(work, "fonts"))
        shutil.copy(brand["font"]["file"], os.path.join(work, "fonts"))
        with open(os.path.join(work, "card.ass"), "w", encoding="utf-8-sig") as fh:
            fh.write(build_ass(plan, brand["font"]["name"], dur))
        inputs = ["-f", "lavfi", "-i",
                  f"gradients=s={W}x{H}:r={fps}:d={dur:.3f}:c0=0x{c0}:c1=0x{c1}:"
                  f"x0=0:y0=0:x1={W}:y1={H}:nb_colors=2:speed=0.012",
                  "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        parts, cur, n = [], "0:v", 2
        for el in plan["elements"]:
            if el["type"] != "image":
                continue
            inputs += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", el["path"]]
            parts.append(f"[{n}:v]scale={el['w']}:-1,format=rgba,"
                         f"fade=t=in:st={el['delay'] / 1000:.2f}:d=0.3:alpha=1[im{n}]")
            parts.append(f"[{cur}][im{n}]overlay=x={el['cx']:.0f}-overlay_w/2:"
                         f"y={el['cy']:.0f}-overlay_h/2:format=auto[b{n}]")
            cur, n = f"b{n}", n + 1
        parts.append(f"[{cur}]ass=card.ass:fontsdir=fonts,format=yuv420p[vout]")
        out_abs = os.path.abspath(out)
        os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
               "-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "1:a",
               "-t", f"{dur:.3f}", "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "16",
               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out_abs]
        p = subprocess.run(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            raise RuntimeError("ffmpeg lỗi khi render thẻ:\n" + p.stderr[-2000:])
        return out_abs
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    configure_utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=list(LAYOUTS))
    ap.add_argument("--aspect", choices=list(ASPECTS), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--brand", default=DEFAULT_BRAND)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--fps", type=int, default=24)
    for k in TEXT_FIELDS:
        ap.add_argument(f"--{k}")
    ap.add_argument("--no-tagline", action="store_true")
    ap.add_argument("--no-qr", action="store_true")
    a = ap.parse_args()
    for t in ("ffmpeg", "ffprobe"):
        if not shutil.which(t):
            sys.exit(f"Thiếu {t} trong PATH.")
    fields = {k: getattr(a, k) for k in TEXT_FIELDS}
    fields.update(no_tagline=a.no_tagline, no_qr=a.no_qr)
    try:
        brand = load_brand(a.brand)
        out = render_card(a.kind, a.aspect, fields, brand, a.out, a.duration, a.fps)
    except AdsError as e:
        sys.exit(f"Lỗi: {e}")
    print(f"✔ {a.kind} {a.aspect} → {out}")


if __name__ == "__main__":
    main()
