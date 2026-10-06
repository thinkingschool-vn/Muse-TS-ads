"""Thư viện dùng chung cho skill Muse-TS-ads.

- ASPECTS / SAFE: khung hình + vùng an toàn (assemble.py, brand_cards.py, qc.py dùng chung)
- BLOCKS / CUT_PLANS: nhãn block kịch bản quảng cáo + kế hoạch cắt bản 30s/15s
- load_brand(): đọc brand/brand.json, đổi đường dẫn thành tuyệt đối, kiểm tra file tồn tại
- load_style() / style_prompt_block(): phong cách video (styles/*.json)
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


# Chuyển cảnh: tên trong edit.json → (tên xfade của ffmpeg, độ dài mặc định giây).
# Tên khác "cut" và không có ở đây được chuyển thẳng cho xfade (fade, dissolve, wipeleft…), mặc định 0,4s.
TRANSITION_ALIASES = {"whip": ("hblur", 0.2), "zoompunch": ("zoomin", 0.15), "flash": ("fadewhite", 0.12)}


def resolve_transition(t):
    """'whip' | {"type": "whip", "duration": 0.3} | None → {"type", "xfade", "duration"}."""
    if t is None or isinstance(t, str):
        t = {"type": t or "cut"}
    t = dict(t)
    name = t.get("type", "cut")
    if name == "cut":
        return {"type": "cut", "xfade": None, "duration": 0.0}
    xf, d = TRANSITION_ALIASES.get(name, (name, 0.4))
    return {"type": name, "xfade": xf, "duration": float(t.get("duration", d))}


def trans_duration(scene):
    return resolve_transition(scene.get("transition", "cut"))["duration"]


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


# ------------------------------------------------------------------ styles ---
STYLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "styles")
DEFAULT_STYLE = "warm-3d"
HOOK_TYPES = ["in-medias-res", "cold-open", "pattern-interrupt", "why-question", "bold-claim", "stop-doing",
              "pov-pain", "curiosity-gap", "before-after", "direct-address", "callout", "stat-shock"]
STYLE_FIELDS = {"id": str, "name": str, "use_when": str, "look": str, "camera_allowed": list,
                "camera_forbidden": list, "shot_len": list, "hook_min_shots": int, "hook_types": list,
                "transitions": list, "grade_arc": str, "music_brief": str, "vo_brief": str,
                "dialogue": bool, "humans": str}


def list_styles(styles_dir=None):
    d = styles_dir or STYLES_DIR
    return sorted(os.path.splitext(n)[0] for n in os.listdir(d) if n.endswith(".json"))


def load_style(style_id=None, styles_dir=None):
    """Đọc + kiểm tra styles/<id>.json. style_id None → phong cách mặc định (warm-3d)."""
    sid = style_id or DEFAULT_STYLE
    d = styles_dir or STYLES_DIR
    path = os.path.join(d, f"{sid}.json")
    if not os.path.exists(path):
        raise AdsError(f"không có phong cách '{sid}' — dùng một trong: {', '.join(list_styles(d))}")
    with open(path, encoding="utf-8-sig") as f:
        s = json.load(f)
    for k, typ in STYLE_FIELDS.items():
        if k not in s:
            raise AdsError(f"phong cách {sid}: thiếu trường '{k}'")
        v = s[k]
        if (typ is int and isinstance(v, bool)) or not isinstance(v, typ):
            raise AdsError(f"phong cách {sid}: trường '{k}' sai kiểu (cần {typ.__name__})")
    if s["id"] != sid:
        raise AdsError(f"phong cách {sid}: 'id' trong file là '{s['id']}' — phải trùng tên file")
    if s["humans"] != "stylized":
        raise AdsError(f"phong cách {sid}: 'humans' phải là \"stylized\" (không dùng người photoreal)")
    if s["hook_min_shots"] < 1:
        raise AdsError(f"phong cách {sid}: 'hook_min_shots' phải ≥ 1")
    lo_hi = s["shot_len"]
    if len(lo_hi) != 2 or not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in lo_hi) \
            or not 0 < lo_hi[0] <= lo_hi[1]:
        raise AdsError(f"phong cách {sid}: 'shot_len' phải là [min, max] giây, 0 < min ≤ max")
    bad = [h for h in s["hook_types"] if h not in HOOK_TYPES]
    if bad:
        raise AdsError(f"phong cách {sid}: loại hook không có trong thư viện: {', '.join(map(str, bad))}")
    if "cut" not in s["transitions"]:
        raise AdsError(f"phong cách {sid}: 'transitions' phải có 'cut'")
    return s


def style_prompt_block(style):
    """Khối tiếng Anh dán vào ĐẦU mỗi prompt clip (sau GLOBAL LOCKS)."""
    return "\n".join([
        f"STYLE: {style['look']}.",
        "CAMERA ALLOWED (pick exactly one per clip): " + "; ".join(style["camera_allowed"]) + ".",
        "CAMERA FORBIDDEN: " + "; ".join(style["camera_forbidden"]) + ".",
        "HUMANS: stylized 3D characters, never photoreal humans.",
    ])


def check_style_use(edit, style, explicit=True):
    """Lỗi nếu edit.json dùng chuyển cảnh/thoại/punch trái luật phong cách.

    explicit=False (edit.json không ghi "style"): không chặn tên chuyển cảnh — giữ tương thích bản cũ.
    """
    for s in edit.get("scenes", []):
        sid = s.get("id", "?")
        if explicit:
            name = resolve_transition(s.get("transition", "cut"))["type"]
            if name not in style["transitions"]:
                raise AdsError(f"cảnh {sid}: chuyển cảnh '{name}' không thuộc phong cách {style['id']} — "
                               f"dùng: {', '.join(style['transitions'])}")
        if s.get("dialogue") and not style["dialogue"]:
            raise AdsError(f"cảnh {sid} có thoại nhưng phong cách {style['id']} không cho thoại — "
                           "đổi sang cinematic-drama / micro-drama hoặc bỏ 'dialogue'")
        p = s.get("punch")
        if p is not None and (isinstance(p, bool) or not isinstance(p, (int, float)) or not 1.0 <= p <= 1.5):
            raise AdsError(f"cảnh {sid}: 'punch' phải là số trong khoảng 1.0–1.5 (đang là {p!r})")


# ---------------------------------------------------------------- dialogue ---
DIALOGUE_MAX_WORDS = 15


def check_dialogue(scenes):
    """Lỗi nếu 'dialogue' của cảnh thiếu speaker/text hoặc quá DIALOGUE_MAX_WORDS từ."""
    for s in scenes:
        d = s.get("dialogue")
        if d is None:
            continue
        sid = s.get("id", "?")
        if not isinstance(d, dict) or not str(d.get("speaker", "")).strip() or not str(d.get("text", "")).strip():
            raise AdsError(f"cảnh {sid}: 'dialogue' cần dạng {{\"speaker\": \"…\", \"text\": \"…\"}}")
        n = len(str(d["text"]).split())
        if n > DIALOGUE_MAX_WORDS:
            raise AdsError(f"cảnh {sid}: thoại {n} từ — tối đa {DIALOGUE_MAX_WORDS} từ/clip (~4–5s); "
                           "rút gọn hoặc tách cảnh")


def dialogue_windows(scenes):
    """[(start, end, scene_id, text)] của cảnh có thoại; scenes = timeline đã có start/end."""
    return [(s["start"], s["end"], s["id"], s["dialogue"]["text"]) for s in scenes if s.get("dialogue")]


def vo_dialogue_clash(spans, windows, tol=0.05):
    """spans: [(start, end, file)] của VO → [(file, scene_id)] các VO chồng lên cảnh thoại."""
    return [(f, sid) for a0, a1, f in spans for b0, b1, sid, _ in windows
            if a0 < b1 - tol and b0 < a1 - tol]


def timed_lines(vo_timed, windows):
    """Câu VO [(t, text|None)] + thoại → [(t, text)] theo thời gian (nội dung .vo.txt / timeline 'lines')."""
    items = [(t, txt) for t, txt in vo_timed if txt] + [(b0, txt) for b0, _, _, txt in windows]
    return sorted(items, key=lambda x: x[0])


# ----------------------------------------------------------- hook variants ---
HOOK_VARIANTS_MAX = 5
_VARIANT_ID = re.compile(r"^[A-Za-z0-9]{1,8}$")


def validate_hook_variants(edit):
    """Kiểm tra edit['hook_variants'] (nếu có). Trả về danh sách bản hook ([] nếu không khai báo)."""
    hv = edit.get("hook_variants")
    if hv is None:
        return []
    if not isinstance(hv, list) or not 1 <= len(hv) <= HOOK_VARIANTS_MAX:
        raise AdsError(f"hook_variants cần 1–{HOOK_VARIANTS_MAX} bản")
    seen = set()
    for i, v in enumerate(hv, 1):
        vid = str(v.get("id", ""))
        if not _VARIANT_ID.match(vid):
            raise AdsError(f"hook_variants #{i}: 'id' chỉ gồm chữ/số không dấu, 1–8 ký tự (vd A, B, C) — "
                           f"đang là '{vid}'")
        if vid in seen:
            raise AdsError(f"hook_variants: trùng id '{vid}'")
        seen.add(vid)
        if v.get("type") not in HOOK_TYPES:
            raise AdsError(f"hook {vid}: 'type' phải thuộc thư viện hook: {', '.join(HOOK_TYPES)}")
        scenes = v.get("scenes") or []
        if not scenes:
            raise AdsError(f"hook {vid}: cần ít nhất 1 cảnh")
        for s in scenes:
            if "id" not in s:
                raise AdsError(f"hook {vid}: mọi cảnh cần 'id'")
            if not s.get("block") or norm_block(s["block"]) != "HOOK":
                raise AdsError(f"hook {vid}: cảnh {s['id']} phải có \"block\": \"HOOK\"")
        own = sorted(s["id"] for s in scenes)
        for key in ("vo", "overlays"):
            for j, it in enumerate(v.get(key, []), 1):
                if it.get("scene") not in own:
                    raise AdsError(f"hook {vid}: {key} #{j} phải gắn 'scene' vào cảnh của chính bản hook "
                                   f"({', '.join(own)})")
    return hv


def apply_hook_variant(edit, variant):
    """Edit mới: các cảnh HOOK ở đầu master (và VO/overlay gắn vào chúng) được thay bằng bản hook."""
    e = copy.deepcopy(edit)
    e.pop("hook_variants", None)
    scenes = e.get("scenes", [])
    hook_ids = {s.get("id") for s in scenes if s.get("block") and norm_block(s["block"]) == "HOOK"}
    if not hook_ids:
        raise AdsError("hook_variants cần master có cảnh block HOOK để thay")
    n = 0
    while n < len(scenes) and scenes[n].get("id") in hook_ids:
        n += 1
    if n != len(hook_ids):
        raise AdsError("các cảnh HOOK của master phải nằm liền nhau ở đầu phim")
    for key in ("vo", "overlays"):
        for j, it in enumerate(e.get(key, []), 1):
            if "scene" not in it:
                raise AdsError(f"{key} #{j} dùng mốc 'at' tuyệt đối — khi có hook_variants phải dùng "
                               "'scene' + 'offset'")
    v = copy.deepcopy(variant)
    clash = {s.get("id") for s in scenes[n:]} & {s["id"] for s in v["scenes"]}
    if clash:
        raise AdsError(f"hook {v['id']}: id cảnh trùng với master: {', '.join(sorted(clash))}")
    e["scenes"] = v["scenes"] + scenes[n:]
    for key in ("vo", "overlays"):
        kept = [it for it in e.get(key, []) if it["scene"] not in hook_ids]
        e[key] = v.get(key, []) + kept
    e["hook_variant"] = {"id": str(v["id"]), "type": v["type"]}
    return e


def variant_output(output, vid):
    root, ext = os.path.splitext(output)
    return f"{root}_hook{vid}{ext or '.mp4'}"




