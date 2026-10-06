#!/usr/bin/env python3
"""Dựng phim tự động từ edit.json — skill Muse animated/ads short film.

Chỉ cần Python 3.8+ và ffmpeg/ffprobe (có libass) trong PATH.

  assemble.py edit.json            # dựng phim
  assemble.py edit.json --plan     # chỉ in timeline (mốc bắt đầu từng cảnh), không render

Pipeline:
  1. Chuẩn hóa từng cảnh: cắt in/out, scale+crop về 720×1280 (9:16), 1280×720 (16:9) hoặc 720×720 (1:1), fps cố định.
  2. Nối cảnh: "cut" (cắt thẳng) hoặc chuyển cảnh xfade (fade, fadewhite, dissolve, slideup...).
     Tiếng gốc của clip (SFX) được crossfade theo đúng chuyển cảnh.
  3. Chữ overlay: sinh file ASS (font hỗ trợ tiếng Việt, viền, hiệu ứng fade/pop, vùng an toàn).
  4. Âm thanh 3 lớp: SFX gốc (nhỏ) + 1 bài nhạc liền mạch + track VO.
     Nhạc và SFX tự động hạ xuống khi có lời (sidechain ducking).
  5. Chuẩn hóa loudness 2 lượt (mặc định −14 LUFS, true peak −1 dBTP) → MP4 faststart.

Mốc thời gian của VO/overlay có thể ghi tuyệt đối ("at": 12.3) hoặc tương đối theo cảnh
("scene": "c3", "offset": 0.4) — script tự tính theo timeline sau khi trừ chuyển cảnh.
Xem templates/edit.example.json.

Mở rộng cho quảng cáo Thinking School (Muse-TS-ads):
  "brand": "../brand/brand.json"   → font + màu style lấy từ brand kit
  "version": "60"                  → lọc item có "versions", áp "trim" của bản; ghi vào timeline
  scene "block": "HOOK" …          → nhãn block (bắt buộc cho MỌI cảnh nếu có dùng)
  "logo_bug": {"logo": "on_dark", "corner": "tr"} → logo góc, ẩn ở block THƯƠNG HIỆU/ƯU ĐÃI/CTA
  vo "text": "…"                   → ghi <output>.vo.txt để qc.py --script
  "style": "cinematic-drama"       → phong cách (styles/*.json): chặn chuyển cảnh/thoại trái luật, ghi vào timeline
  scene "punch": 1.2               → phóng to 1.0–1.5 lần để tạo shot cận hơn từ cùng clip
  transition "whip" / "zoompunch" / "flash" → lia nhanh nhoè (0,2s) / zoom giật (0,15s) / chớp trắng (0,12s)
  scene "dialogue": {"speaker", "text"} → thoại do model tạo (≤ 15 từ); không VO đè; "dialogue_gain_db" (mặc định 0)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adslib import (ASPECTS, SAFE, AdsError, check_dialogue, check_style_use, dialogue_windows,  # noqa: E402
                    filter_version, load_brand, load_style, norm_block, resolve_transition,
                    timed_lines, vo_dialogue_clash)


# ASPECTS (9:16, 16:9, 1:1) và SAFE (vùng an toàn) định nghĩa ở adslib.py, dùng chung với brand_cards/qc.
LOGO_SKIP_DEFAULT = ["THƯƠNG HIỆU", "ƯU ĐÃI", "CTA"]  # thẻ thương hiệu đã có logo to → ẩn logo góc


# ----------------------------------------------------------------- helpers ---
def run(cmd, cwd=None, quiet=True):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                       encoding="utf-8", errors="replace", cwd=cwd)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg lỗi:\n{' '.join(cmd)}\n---\n{p.stderr[-3000:]}")
    return p


def probe(path):
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
             "-of", "json", path])
    d = json.loads(p.stdout)
    return {"duration": float(d["format"]["duration"]),
            "has_audio": any(s["codec_type"] == "audio" for s in d["streams"]),
            "has_video": any(s["codec_type"] == "video" for s in d["streams"])}


def db(x):
    return f"{float(x):.2f}dB"


def ass_time(t):
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def ass_color(hex_rgb, alpha=0):
    """'#RRGGBB' → '&HAABBGGRR' (ASS dùng BGR)."""
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_escape(text):
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


# --------------------------------------------------------------- timeline ---
def trans_of(scene):
    return resolve_transition(scene.get("transition", "cut"))


def build_timeline(edit, base):
    scenes = []
    start = 0.0
    for i, s in enumerate(edit["scenes"]):
        path = os.path.join(base, s["file"])
        if not os.path.exists(path):
            raise SystemExit(f"Không thấy file cảnh: {path}")
        info = probe(path)
        t_in = float(s.get("in", 0.0))
        t_out = float(s.get("out", info["duration"]))
        if t_out > info["duration"] + 0.05:
            raise SystemExit(f"Cảnh {s.get('id', i+1)}: out={t_out} vượt độ dài clip {info['duration']:.2f}s")
        dur = t_out - t_in
        if dur <= 0.3:
            raise SystemExit(f"Cảnh {s.get('id', i+1)}: in/out không hợp lệ")
        if i > 0:
            start -= scenes[-1]["trans"]["duration"]
        sc = {"id": s.get("id", f"s{i+1}"), "path": path, "in": t_in, "dur": dur,
              "start": round(start, 3), "end": round(start + dur, 3), "trans": trans_of(s),
              "has_audio": info["has_audio"], "block": norm_block(s["block"]) if s.get("block") else None,
              "punch": float(s.get("punch", 1.0)), "dialogue": s.get("dialogue")}
        if i < len(edit["scenes"]) - 1 and sc["trans"]["duration"] >= dur:
            raise SystemExit(f"Cảnh {sc['id']}: chuyển cảnh dài hơn cảnh")
        scenes.append(sc)
        start += dur
    tagged = [s["block"] for s in scenes]
    if any(tagged) and not all(tagged):
        raise SystemExit("Có cảnh gắn 'block', có cảnh không — quảng cáo cần gắn block cho MỌI cảnh")
    return scenes, round(start, 3)


def resolve_time(item, scenes_by_id, label):
    if "at" in item:
        return float(item["at"])
    if "scene" in item:
        sid = item["scene"]
        if sid not in scenes_by_id:
            raise SystemExit(f"{label}: không có cảnh id '{sid}'")
        return scenes_by_id[sid]["start"] + float(item.get("offset", 0.0))
    raise SystemExit(f"{label}: cần 'at' hoặc 'scene'+'offset'")


# ------------------------------------------------------------- step 1: seg ---
def scene_vf(W, H, fps, punch=1.0):
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
    if punch and punch > 1.0:  # phóng to rồi cắt giữa → shot cận hơn từ cùng clip
        vf += f"scale=trunc(iw*{punch:.3f}/2)*2:trunc(ih*{punch:.3f}/2)*2,crop={W}:{H},setsar=1,"
    return vf + f"fps={fps},format=yuv420p"


def normalize_scene(sc, idx, W, H, fps, work, gain_db=0.0):
    out = os.path.join(work, f"seg_{idx:02d}.mkv")
    vf = scene_vf(W, H, fps, sc.get("punch", 1.0))

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{sc['in']:.3f}", "-i", sc["path"]]
    if not sc["has_audio"]:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    af = ("aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
          + (f",volume={db(gain_db)}" if gain_db else ""))
    cmd += ["-t", f"{sc['dur']:.3f}", "-map", "0:v:0", "-map", "0:a:0" if sc["has_audio"] else "1:a:0",
            "-vf", vf, "-af", af,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-c:a", "pcm_s16le", out]
    run(cmd)
    return out


# --------------------------------------------------------- step 2+3: video ---
STYLE_DEFAULTS = {
    #          size  bold  color      outline shadow  align  anim
    "title":   (64,  True,  "#FFFFFF", 4,     2,      8,     "pop"),
    "caption": (46,  True,  "#FFFFFF", 3,     2,      2,     "fade"),
    "cta":     (78,  True,  "#FFD84D", 5,     3,      5,     "pop"),
    "brand":   (56,  True,  "#FFFFFF", 4,     2,      8,     "fade"),
    "small":   (38,  False, "#FFFFFF", 3,     1,      2,     "fade"),
}


def build_ass(edit, scenes_by_id, W, H, aspect, total, work, warnings):
    overlays = edit.get("overlays", [])
    if not overlays:
        return None
    font = edit.get("font", {})
    font_name = font.get("name", "Be Vietnam Pro")
    k = H / 1280 if aspect == "9:16" else (W / 720 if aspect == "1:1" else H / 720)
    safe = SAFE[aspect]
    mL, mR = int(W * safe["left"]), int(W * safe["right"])
    mTop, mBot = int(H * safe["top"]), int(H * safe["bottom"])
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
             "WrapStyle: 0", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
             "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
             "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"]
    custom = edit.get("styles", {})
    for name, (size, bold, color, outline, shadow, align, _) in STYLE_DEFAULTS.items():
        c = custom.get(name, {})
        size = int(c.get("size", size) * (k if "size" not in c else 1))
        color = c.get("color", color)
        mv = mTop if align in (7, 8, 9) else (mBot if align in (1, 2, 3) else 0)
        lines.append(
            f"Style: {name},{c.get('font', font_name)},{size},{ass_color(color)},&H000000FF,"
            f"{ass_color(c.get('outline_color', '#101018'))},{ass_color('#000000', 0x80)},"
            f"{-1 if c.get('bold', bold) else 0},0,0,0,100,100,0,0,1,{c.get('outline', outline)},"
            f"{c.get('shadow', shadow)},{align},{mL},{mR},{mv},1")
    lines += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for i, o in enumerate(overlays):
        t0 = resolve_time(o, scenes_by_id, f"overlay #{i+1}")
        t1 = t0 + float(o["duration"]) if "duration" in o else float(o["end"])
        if t1 > total + 0.01:
            warnings.append(f"Overlay '{o['text'][:30]}' kết thúc sau khi phim hết ({t1:.2f}s > {total:.2f}s)")
        words = len(o["text"].split())
        need = 0.8 + 0.3 * words
        if t1 - t0 < need:
            warnings.append(f"Overlay '{o['text'][:30]}' hiện {t1-t0:.1f}s — hơi ngắn để đọc (gợi ý ≥ {need:.1f}s)")
        style = o.get("style", "caption")
        anim = o.get("anim", STYLE_DEFAULTS.get(style, STYLE_DEFAULTS["caption"])[6])
        tags = ""
        if "y" in o:  # vị trí dọc theo tỷ lệ 0..1, tự kẹp trong vùng an toàn
            y = float(o["y"])
            lo, hi = safe["top"], 1 - safe["bottom"]
            if not lo <= y <= hi:
                warnings.append(f"Overlay '{o['text'][:30]}' y={y} nằm ngoài vùng an toàn → kẹp về [{lo:.2f}, {hi:.2f}]")
                y = min(max(y, lo), hi)
            x = (mL + (W - mR)) / 2
            tags += f"\\an5\\pos({x:.0f},{y * H:.0f})"
        if anim == "fade":
            tags += "\\fad(180,180)"
        elif anim == "pop":
            tags += "\\fad(120,180)\\fscx70\\fscy70\\t(0,220,\\fscx100\\fscy100)"
        text = ass_escape(o["text"])
        lines.append(f"Dialogue: 0,{ass_time(t0)},{ass_time(t1)},{style},,0,0,0,,{{{tags}}}{text}")
    path = os.path.join(work, "overlays.ass")
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines) + "\n")
    fdir = os.path.join(work, "fonts")
    os.makedirs(fdir, exist_ok=True)
    if font.get("file"):
        src = os.path.join(edit["_base"], font["file"])
        if not os.path.exists(src):
            raise SystemExit(f"Không thấy font: {src}")
        shutil.copy(src, fdir)
    else:
        warnings.append(f"Chưa khai báo font.file → dùng font hệ thống '{font_name}' (kiểm tra dấu tiếng Việt)")
    return "overlays.ass"


def logo_intervals(scenes, skip):
    """Khoảng thời gian hiện logo góc: mọi cảnh trừ block trong `skip`; gộp các khoảng liền nhau."""
    skip = {norm_block(b) for b in skip}
    out = []
    for s in scenes:
        if s.get("block") in skip:
            continue
        a, b = s["start"], s["end"]
        if out and a <= out[-1][1] + 1e-6:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return [(round(a, 3), round(b, 3)) for a, b in out]


def logo_spec(edit, scenes, W, H, aspect):
    lb = edit.get("logo_bug")
    if not lb:
        return None
    if lb.get("file"):
        path = os.path.join(edit["_base"], lb["file"])
    else:
        path = ((edit.get("_brand") or {}).get("logo") or {}).get(lb.get("logo", "on_dark"))
        if not path:
            raise SystemExit("logo_bug cần 'file' hoặc khai báo 'brand' trong edit.json")
    if not os.path.exists(path):
        raise SystemExit(f"Không thấy logo: {path}")
    corner = lb.get("corner", "tr")
    if corner not in ("tl", "tr", "bl", "br"):
        raise SystemExit("logo_bug.corner phải là tl / tr / bl / br")
    safe = SAFE[aspect]
    mL, mR = int(W * safe["left"]), int(W * safe["right"])
    mT, mB = int(H * safe["top"]), int(H * safe["bottom"])
    iv = logo_intervals(scenes, lb.get("skip_blocks", LOGO_SKIP_DEFAULT))
    if not iv:
        return None
    return {"path": path, "w": int(W * float(lb.get("width", 0.16))),
            "opacity": float(lb.get("opacity", 0.85)),
            "x": str(mL) if corner[1] == "l" else f"main_w-overlay_w-{mR}",
            "y": str(mT) if corner[0] == "t" else f"main_h-overlay_h-{mB}",
            "intervals": iv}


def render_video(segs, scenes, ass_file, total, work, logo=None):
    inputs, parts = [], []
    for i, s in enumerate(segs):
        inputs += ["-i", s]
        parts.append(f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")
    cur_v, cur_a, length = "v0", "a0", scenes[0]["dur"]
    for i in range(1, len(segs)):
        t = scenes[i - 1]["trans"]
        nv, na = f"xv{i}", f"xa{i}"
        if t["type"] == "cut":
            parts.append(f"[{cur_v}][v{i}]concat=n=2:v=1:a=0,settb=AVTB[{nv}]")
            parts.append(f"[{cur_a}][a{i}]concat=n=2:v=0:a=1[{na}]")
            length += scenes[i]["dur"]
        else:
            d = t["duration"]
            parts.append(f"[{cur_v}][v{i}]xfade=transition={t['xfade']}:duration={d:.3f}:"
                         f"offset={length - d:.3f},settb=AVTB[{nv}]")
            parts.append(f"[{cur_a}][a{i}]acrossfade=d={d:.3f}:c1=tri:c2=tri[{na}]")
            length += scenes[i]["dur"] - d
        cur_v, cur_a = nv, na
    if logo:
        n = len(segs)
        inputs += ["-loop", "1", "-i", logo["path"]]
        en = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in logo["intervals"])
        parts.append(f"[{n}:v]scale={logo['w']}:-1,format=rgba,colorchannelmixer=aa={logo['opacity']:.2f}[lg]")
        parts.append(f"[{cur_v}][lg]overlay=x={logo['x']}:y={logo['y']}:enable='{en}':shortest=1[vlg]")
        cur_v = "vlg"
    if ass_file:
        parts.append(f"[{cur_v}]ass={ass_file}:fontsdir=fonts[vout]")
        cur_v = "vout"
    out = os.path.join(work, "joined.mkv")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
         "-filter_complex", ";".join(parts), "-map", f"[{cur_v}]", "-map", f"[{cur_a}]",
         "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
         "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "joined.mkv"], cwd=work)
    return out


# ------------------------------------------------------------ step 4: mix ---
def render_mix(edit, scenes_by_id, joined, total, work, warnings, windows=()):
    base = edit["_base"]
    inputs, parts, bed = ["-i", joined], [], []
    sfx = edit.get("sfx", {"keep": True, "gain_db": -12})
    dlg = None
    if sfx.get("keep", True):
        parts.append(f"[0:a]volume={db(sfx.get('gain_db', -12))}[sfx_all]")
        if windows:
            # Tiếng gốc cảnh thoại tách riêng: không bị duck, và làm "chìa khoá" hạ nhạc như VO
            en = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b, _, _ in windows)
            parts.append("[sfx_all]asplit=2[sfx_a][dlg_a]")
            parts.append(f"[sfx_a]volume=0:enable='{en}'[sfx]")
            parts.append(f"[dlg_a]volume=0:enable='not({en})'[dlg]")
            dlg = "[dlg]"
        else:
            parts.append("[sfx_all]anull[sfx]")
        bed.append("[sfx]")
    n = 1
    music = edit.get("music")
    if music and music.get("file"):
        mpath = os.path.join(base, music["file"])
        if not os.path.exists(mpath):
            raise SystemExit(f"Không thấy file nhạc: {mpath}")
        mdur = probe(mpath)["duration"] - float(music.get("start_offset", 0))
        if mdur < total:
            warnings.append(f"Nhạc chỉ dài {mdur:.1f}s < phim {total:.1f}s → sẽ lặp lại (nên dùng bài đủ dài)")
            inputs += ["-stream_loop", "-1"]
        inputs += ["-i", mpath]
        fi, fo = float(music.get("fade_in", 0.3)), float(music.get("fade_out", 2.5))
        parts.append(
            f"[{n}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"atrim=start={float(music.get('start_offset', 0)):.3f},asetpts=PTS-STARTPTS,"
            f"atrim=0:{total:.3f},afade=t=in:d={fi:.2f},afade=t=out:st={max(0, total - fo):.3f}:d={fo:.2f},"
            f"volume={db(music.get('gain_db', -8))}[mus]")
        bed.append("[mus]")
        n += 1
    else:
        warnings.append("Không có nhạc nền (music.file) — phim chỉ có SFX + VO")

    vo_items = edit.get("vo", [])
    vo_labels, spans = [], []
    for i, v in enumerate(vo_items):
        vpath = os.path.join(base, v["file"])
        if not os.path.exists(vpath):
            raise SystemExit(f"Không thấy file VO: {vpath}")
        at = resolve_time(v, scenes_by_id, f"vo #{i+1}")
        vdur = probe(vpath)["duration"]
        spans.append((at, at + vdur, v["file"]))
        inputs += ["-i", vpath]
        ms = int(round(at * 1000))
        parts.append(f"[{n}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                     f"volume={db(v.get('gain_db', 0))},adelay={ms}:all=1[vo{i}]")
        vo_labels.append(f"[vo{i}]")
        n += 1
    spans.sort()
    for (a0, a1, fa), (b0, b1, fb) in zip(spans, spans[1:]):
        if b0 < a1 - 0.05:
            raise SystemExit(f"VO CHỒNG NHAU: {fa} ({a0:.2f}–{a1:.2f}s) và {fb} ({b0:.2f}–{b1:.2f}s). "
                             "Dời mốc hoặc rút gọn câu.")
    for f, sid in vo_dialogue_clash(spans, windows):
        raise SystemExit(f"VO TRÙNG THOẠI: {f} chồng lên cảnh thoại '{sid}' — dời VO sang cảnh khác "
                         "hoặc bỏ VO ở cảnh có thoại.")
    for a0, a1, f in spans:
        if a1 > total - 0.3:
            warnings.append(f"VO {f} kết thúc {a1:.2f}s, sát/vượt cuối phim {total:.2f}s")

    keys = vo_labels + ([dlg] if dlg else [])
    if not bed and not keys:
        raise SystemExit("Không có lớp âm thanh nào (sfx tắt, không nhạc, không VO)")
    if len(bed) > 1:
        parts.append(f"{''.join(bed)}amix=inputs={len(bed)}:normalize=0:duration=longest[bed]")
        bed_l = "[bed]"
    else:
        bed_l = bed[0] if bed else None

    duck = edit.get("duck", {})
    if keys:
        if len(keys) > 1:
            parts.append(f"{''.join(keys)}amix=inputs={len(keys)}:normalize=0:duration=longest[vo]")
        else:
            parts.append(f"{keys[0]}anull[vo]")
        if bed_l:
            parts.append("[vo]asplit=2[vo_sc][vo_mix]")
            parts.append(
                f"{bed_l}[vo_sc]sidechaincompress=threshold={duck.get('threshold', 0.015)}:"
                f"ratio={duck.get('ratio', 10)}:attack={duck.get('attack_ms', 15)}:"
                f"release={duck.get('release_ms', 450)}:makeup=1[ducked]")
            parts.append("[ducked][vo_mix]amix=inputs=2:normalize=0:duration=longest[pre]")
        else:
            parts.append("[vo]anull[pre]")
    else:
        parts.append(f"{bed_l}anull[pre]")
    parts.append(f"[pre]apad=whole_dur={total:.3f},atrim=0:{total:.3f}[mix]")
    out = os.path.join(work, "mix.wav")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
         "-filter_complex", ";".join(parts), "-map", "[mix]", "-c:a", "pcm_f32le", "-ar", "48000", out])
    return out, spans


def measure_loudness(wav, L):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", wav, "-af",
                        f"loudnorm=I={L['I']}:TP={L['TP']}:LRA={L['LRA']}:print_format=json",
                        "-f", "null", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    if not m:
        raise RuntimeError("Không đo được loudness:\n" + p.stderr[-1500:])
    return json.loads(m.group(0))


# ------------------------------------------------------------------- main ---
def load_edit(path):
    with open(path, encoding="utf-8-sig") as f:
        edit = json.load(f)
    base = os.path.dirname(os.path.abspath(path))
    edit["_base"] = base
    if edit.get("brand"):
        brand = load_brand(os.path.join(base, edit["brand"]))
        edit.setdefault("font", {"name": brand["font"]["name"], "file": brand["font"]["file"]})
        styles = {k: dict(v) for k, v in brand.get("styles", {}).items()}
        for k, v in edit.get("styles", {}).items():
            styles.setdefault(k, {}).update(v)
        edit["styles"] = styles  # "styles" = kiểu chữ overlay; "style" = phong cách video
        edit["_brand"] = brand
    return edit


def prepare(edit):
    """Áp bản (version) + kiểm tra luật phong cách → (edit, style). Lỗi dữ liệu → AdsError."""
    if edit.get("version") is not None:
        edit = filter_version(edit, edit["version"])
    style = load_style(edit.get("style"))
    check_style_use(edit, style, explicit=bool(edit.get("style")))
    check_dialogue(edit.get("scenes", []))
    if any(s.get("dialogue") for s in edit.get("scenes", [])) and not edit.get("sfx", {}).get("keep", True):
        raise AdsError("có cảnh thoại nhưng sfx.keep = false — thoại nằm trong tiếng gốc clip nên phải giữ sfx")
    return edit, style


def render_one(edit, style, a):
    """Dựng 1 file. Trả về đường dẫn output (None nếu --plan)."""
    base = edit["_base"]
    aspect = edit.get("aspect", "9:16")
    if aspect not in ASPECTS:
        raise AdsError(f"aspect phải là một trong {list(ASPECTS)}")
    W, H = ASPECTS[aspect]
    fps = int(edit.get("fps", 24))
    L = {"I": -14.0, "TP": -1.5, "LRA": 11.0, **edit.get("loudness", {})}
    scenes, total = build_timeline(edit, base)
    by_id = {s["id"]: s for s in scenes}
    out = os.path.normpath(os.path.join(base, edit.get("output", "final.mp4")))
    print(f"TIMELINE {os.path.basename(out)} ({aspect}, {W}×{H}, {fps}fps, phong cách {style['id']}) "
          f"— tổng {total:.2f}s")
    for s in scenes:
        tr = s["trans"]
        tr_s = "" if tr["type"] == "cut" else f"  → {tr['type']} {tr['duration']:.2f}s"
        blk = f"  [{s['block']}]" if s["block"] else ""
        print(f"  {s['id']:<8} {s['start']:7.2f} → {s['end']:7.2f}  ({s['dur']:.2f}s){tr_s}{blk}")
    if a.plan:
        return None

    warnings = []
    work = tempfile.mkdtemp(prefix="assemble_")
    try:
        print("1/5 Chuẩn hóa cảnh…")
        sfx_gain = float(edit.get("sfx", {}).get("gain_db", -12))
        boost = float(edit.get("dialogue_gain_db", 0)) - sfx_gain  # cảnh thoại về đúng dialogue_gain_db
        segs = [normalize_scene(s, i, W, H, fps, work, gain_db=boost if s.get("dialogue") else 0.0)
                for i, s in enumerate(scenes)]
        print("2/5 Overlay chữ…")
        ass = build_ass(edit, by_id, W, H, aspect, total, work, warnings)
        print("3/5 Nối cảnh + chuyển cảnh…")
        logo = logo_spec(edit, scenes, W, H, aspect)
        joined = render_video(segs, scenes, ass, total, work, logo)
        windows = dialogue_windows(scenes)
        print("4/5 Mix âm thanh 3 lớp + ducking…")
        mix, spans = render_mix(edit, by_id, joined, total, work, warnings, windows)
        print("5/5 Chuẩn hóa loudness + xuất file…")
        m = measure_loudness(mix, L)
        ln = (f"loudnorm=I={L['I']}:TP={L['TP']}:LRA={L['LRA']}:measured_I={m['input_i']}:"
              f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
              f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
              f"aresample=48000")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", joined, "-i", mix,
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", ln, "-c:a", "aac", "-b:a", "192k",
             "-ar", "48000", "-t", f"{total:.3f}", "-movflags", "+faststart", out])
        lines = timed_lines([(resolve_time(v, by_id, f"vo #{i+1}"), v.get("text"))
                             for i, v in enumerate(edit.get("vo", []))], windows)
        timeline = {"aspect": aspect, "fps": fps, "total": total, "version": edit.get("version"),
                    "style": style["id"], "hook_min_shots": style["hook_min_shots"],
                    "scenes": [dict({k: s[k] for k in ("id", "start", "end", "dur", "block")},
                                    dialogue=(s["dialogue"] or {}).get("text")) for s in scenes],
                    "vo": [{"file": f, "start": round(s0, 3), "end": round(s1, 3)} for s0, s1, f in spans],
                    "lines": [{"start": round(t, 3), "text": txt} for t, txt in lines],
                    "warnings": warnings}
        with open(os.path.splitext(out)[0] + ".timeline.json", "w", encoding="utf-8") as f:
            json.dump(timeline, f, ensure_ascii=False, indent=2)
        script_path = None
        if lines:
            script_path = os.path.splitext(out)[0] + ".vo.txt"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write("\n".join(txt for _, txt in lines) + "\n")
        print(f"\n✔ Xuất xong: {out}")
        for w in warnings:
            print(f"  ⚠ {w}")
        cmd = f"python scripts/qc.py final {os.path.basename(out)} --aspect {aspect}"
        if edit.get("version"):
            cmd += f" --duration {edit['version']} --ad"
        if script_path:
            cmd += f" --script {os.path.basename(script_path)}"
        print("→ Bước tiếp theo bắt buộc:", cmd)
        return out
    finally:
        if a.keep_work:
            print(f"(thư mục tạm: {work})")
        else:
            shutil.rmtree(work, ignore_errors=True)


def main():
    for t in ("ffmpeg", "ffprobe"):
        if not shutil.which(t):
            sys.exit(f"Thiếu {t} trong PATH.")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edit")
    ap.add_argument("--plan", action="store_true", help="chỉ in timeline, không render")
    ap.add_argument("--keep-work", action="store_true", help="giữ thư mục tạm để debug")
    a = ap.parse_args()
    try:
        edit = load_edit(a.edit)
        e, style = prepare(edit)
        render_one(e, style, a)
    except AdsError as ex:
        sys.exit(f"Lỗi edit.json: {ex}")


if __name__ == "__main__":
    main()
