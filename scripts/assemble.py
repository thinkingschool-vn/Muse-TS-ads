#!/usr/bin/env python3
"""Dựng phim tự động từ edit.json — skill Muse animated/ads short film.

Chỉ cần Python 3.8+ và ffmpeg/ffprobe (có libass) trong PATH.

  assemble.py edit.json            # dựng phim
  assemble.py edit.json --plan     # chỉ in timeline (mốc bắt đầu từng cảnh), không render

Pipeline:
  1. Chuẩn hóa từng cảnh: cắt in/out, scale+crop về 720×1280 (9:16) hoặc 1280×720 (16:9), fps cố định.
  2. Nối cảnh: "cut" (cắt thẳng) hoặc chuyển cảnh xfade (fade, fadewhite, dissolve, slideup...).
     Tiếng gốc của clip (SFX) được crossfade theo đúng chuyển cảnh.
  3. Chữ overlay: sinh file ASS (font hỗ trợ tiếng Việt, viền, hiệu ứng fade/pop, vùng an toàn).
  4. Âm thanh 3 lớp: SFX gốc (nhỏ) + 1 bài nhạc liền mạch + track VO.
     Nhạc và SFX tự động hạ xuống khi có lời (sidechain ducking).
  5. Chuẩn hóa loudness 2 lượt (mặc định −14 LUFS, true peak −1 dBTP) → MP4 faststart.

Mốc thời gian của VO/overlay có thể ghi tuyệt đối ("at": 12.3) hoặc tương đối theo cảnh
("scene": "c3", "offset": 0.4) — script tự tính theo timeline sau khi trừ chuyển cảnh.
Xem templates/edit.example.json.
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

ASPECTS = {"9:16": (720, 1280), "16:9": (1280, 720)}

# Vùng an toàn (tỷ lệ theo chiều cao/chiều rộng) — tránh UI TikTok/Reels/Shorts che chữ.
SAFE = {
    "9:16": {"top": 0.14, "bottom": 0.24, "left": 0.08, "right": 0.14},
    "16:9": {"top": 0.08, "bottom": 0.12, "left": 0.06, "right": 0.06},
}


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
    t = scene.get("transition", "cut")
    if isinstance(t, str):
        t = {"type": t}
    t = dict(t)
    t.setdefault("type", "cut")
    t["duration"] = 0.0 if t["type"] == "cut" else float(t.get("duration", 0.4))
    return t


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
              "has_audio": info["has_audio"]}
        if i < len(edit["scenes"]) - 1 and sc["trans"]["duration"] >= dur:
            raise SystemExit(f"Cảnh {sc['id']}: chuyển cảnh dài hơn cảnh")
        scenes.append(sc)
        start += dur
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
def normalize_scene(sc, idx, W, H, fps, work):
    out = os.path.join(work, f"seg_{idx:02d}.mkv")
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
          f"fps={fps},format=yuv420p")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{sc['in']:.3f}", "-i", sc["path"]]
    if not sc["has_audio"]:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    cmd += ["-t", f"{sc['dur']:.3f}", "-map", "0:v:0", "-map", "0:a:0" if sc["has_audio"] else "1:a:0",
            "-vf", vf, "-af", "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo",
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
    k = H / 1280 if aspect == "9:16" else H / 720
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


def render_video(segs, scenes, ass_file, total, work):
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
            parts.append(f"[{cur_v}][v{i}]xfade=transition={t['type']}:duration={d:.3f}:"
                         f"offset={length - d:.3f},settb=AVTB[{nv}]")
            parts.append(f"[{cur_a}][a{i}]acrossfade=d={d:.3f}:c1=tri:c2=tri[{na}]")
            length += scenes[i]["dur"] - d
        cur_v, cur_a = nv, na
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
def render_mix(edit, scenes_by_id, joined, total, work, warnings):
    base = edit["_base"]
    inputs, parts, bed = ["-i", joined], [], []
    sfx = edit.get("sfx", {"keep": True, "gain_db": -12})
    if sfx.get("keep", True):
        parts.append(f"[0:a]volume={db(sfx.get('gain_db', -12))}[sfx]")
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
    for a0, a1, f in spans:
        if a1 > total - 0.3:
            warnings.append(f"VO {f} kết thúc {a1:.2f}s, sát/vượt cuối phim {total:.2f}s")

    if not bed and not vo_labels:
        raise SystemExit("Không có lớp âm thanh nào (sfx tắt, không nhạc, không VO)")
    if len(bed) > 1:
        parts.append(f"{''.join(bed)}amix=inputs={len(bed)}:normalize=0:duration=longest[bed]")
        bed_l = "[bed]"
    else:
        bed_l = bed[0] if bed else None

    duck = edit.get("duck", {})
    if vo_labels:
        if len(vo_labels) > 1:
            parts.append(f"{''.join(vo_labels)}amix=inputs={len(vo_labels)}:normalize=0:duration=longest[vo]")
        else:
            parts.append(f"{vo_labels[0]}anull[vo]")
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
def main():
    for t in ("ffmpeg", "ffprobe"):
        if not shutil.which(t):
            sys.exit(f"Thiếu {t} trong PATH.")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edit")
    ap.add_argument("--plan", action="store_true", help="chỉ in timeline, không render")
    ap.add_argument("--keep-work", action="store_true", help="giữ thư mục tạm để debug")
    a = ap.parse_args()

    with open(a.edit, encoding="utf-8-sig") as f:
        edit = json.load(f)
    base = os.path.dirname(os.path.abspath(a.edit))
    edit["_base"] = base
    aspect = edit.get("aspect", "9:16")
    if aspect not in ASPECTS:
        sys.exit(f"aspect phải là một trong {list(ASPECTS)}")
    W, H = ASPECTS[aspect]
    fps = int(edit.get("fps", 24))
    L = {"I": -14.0, "TP": -1.5, "LRA": 11.0, **edit.get("loudness", {})}

    scenes, total = build_timeline(edit, base)
    by_id = {s["id"]: s for s in scenes}
    print(f"TIMELINE ({aspect}, {W}×{H}, {fps}fps) — tổng {total:.2f}s")
    for s in scenes:
        tr = s["trans"]
        tr_s = "" if tr["type"] == "cut" else f"  → {tr['type']} {tr['duration']:.2f}s"
        print(f"  {s['id']:<8} {s['start']:7.2f} → {s['end']:7.2f}  ({s['dur']:.2f}s){tr_s}")
    if a.plan:
        return

    warnings = []
    work = tempfile.mkdtemp(prefix="assemble_")
    try:
        print("1/5 Chuẩn hóa cảnh…")
        segs = [normalize_scene(s, i, W, H, fps, work) for i, s in enumerate(scenes)]
        print("2/5 Overlay chữ…")
        ass = build_ass(edit, by_id, W, H, aspect, total, work, warnings)
        print("3/5 Nối cảnh + chuyển cảnh…")
        joined = render_video(segs, scenes, ass, total, work)
        print("4/5 Mix âm thanh 3 lớp + ducking…")
        mix, spans = render_mix(edit, by_id, joined, total, work, warnings)
        print("5/5 Chuẩn hóa loudness + xuất file…")
        m = measure_loudness(mix, L)
        ln = (f"loudnorm=I={L['I']}:TP={L['TP']}:LRA={L['LRA']}:measured_I={m['input_i']}:"
              f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
              f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
              f"aresample=48000")
        out = os.path.normpath(os.path.join(base, edit.get("output", "final.mp4")))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", joined, "-i", mix,
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", ln, "-c:a", "aac", "-b:a", "192k",
             "-ar", "48000", "-t", f"{total:.3f}", "-movflags", "+faststart", out])
        timeline = {"aspect": aspect, "fps": fps, "total": total,
                    "scenes": [{k: s[k] for k in ("id", "start", "end", "dur")} for s in scenes],
                    "vo": [{"file": f, "start": round(s0, 3), "end": round(s1, 3)} for s0, s1, f in spans],
                    "warnings": warnings}
        with open(os.path.splitext(out)[0] + ".timeline.json", "w", encoding="utf-8") as f:
            json.dump(timeline, f, ensure_ascii=False, indent=2)
        print(f"\n✔ Xuất xong: {out}")
        for w in warnings:
            print(f"  ⚠ {w}")
        print("→ Bước tiếp theo bắt buộc: python scripts/qc.py final", os.path.basename(out),
              f"--aspect {aspect} --script vo_lines.txt")
    finally:
        if a.keep_work:
            print(f"(thư mục tạm: {work})")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
