#!/usr/bin/env python3
"""QC tự động cho skill Muse animated/ads short film.

Chỉ cần Python 3.8+ và ffmpeg/ffprobe trong PATH. faster-whisper là tùy chọn
(dùng để phát hiện lời nói lạ trong clip và kiểm tra VO nghe có rõ không).

Lệnh:
  qc.py lastframe <clip.mp4> <out.png>
      Trích frame CUỐI THẬT của clip (dùng làm first frame cho clip kế tiếp).

  qc.py clips <c1.mp4> <c2.mp4> ... [--aspect 9:16] [--out qc_clips]
      Kiểm tra từng clip vừa generate + độ khớp mối nối giữa các clip liền kề
      (frame cuối clip N so với frame đầu clip N+1).

  qc.py final <final.mp4> [--aspect 9:16] [--script vo.txt] [--target-lufs -14]
             [--expect-match-cuts] [--out qc_final]
             [--ad --duration 30] [--end-card cards/end.mp4] [--must-say "mười một tháng mười"]...
      Kiểm tra file phim cuối: định dạng, loudness, khoảng lặng, flash/khung đen,
      mối nối (SSIM), và (tùy chọn) đối chiếu lời đọc với kịch bản VO.
      --ad: thời lượng phải nằm trong [đích − 1,5 ; đích + 0,5]s, cảnh cuối phải là block CTA
      ≥ 3,5s, cảnh đầu nên là HOOK (đọc <video>.timeline.json do assemble.py ghi).
      --must-say: cụm thông tin bắt buộc (giá, ngày…) phải nghe được trong VO và có trong --script.
      QC_NO_WHISPER=1: tắt nhận dạng giọng nói.

Mã thoát: 0 = PASS, 1 = có lỗi FAIL, 2 = lỗi sử dụng.
Báo cáo được ghi ra <out>/qc_report.md + qc_report.json + ảnh ghép mối nối.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adslib import ASPECTS  # noqa: E402  (9:16, 16:9, 1:1)
from vi_numbers import normalize_numbers  # noqa: E402

SYNONYMS = {"ngàn": "nghìn", "lẻ": "linh", "tỉ": "tỷ"}
AD_END_MIN = 3.5  # end card (block CTA) cuối phim tối thiểu bao nhiêu giây

# Ngưỡng SSIM ở mối nối (ảnh xám 360px; hiệu chỉnh trên clip Thinking Uni):
#   >= MATCH_OK   : match-cut đạt (gần như trùng khung)
#   <  CUT_CLEAN  : cắt sang cảnh khác hẳn (đo được 0.10–0.18) — ổn nếu là CUT có chủ đích
#   ở giữa        : "jump cut" — gần giống nhưng lệch (đo được 0.33), mắt người thấy giật
# Đây là heuristic: luôn mở ảnh ghép boundaries.jpg để nhìn tận mắt.
MATCH_OK = 0.75
CUT_CLEAN = 0.25

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


# ----------------------------------------------------------------- helpers ---
def run(cmd, check=True, cwd=None):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, encoding="utf-8", errors="replace", cwd=cwd)
    if check and p.returncode != 0:
        raise RuntimeError(f"Lệnh lỗi: {' '.join(cmd)}\n{p.stderr[-2000:]}")
    return p


def need_tools():
    for t in ("ffmpeg", "ffprobe"):
        if not shutil.which(t):
            sys.exit(f"Thiếu {t} trong PATH.")


def probe(path):
    p = run(["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=index,codec_type,width,height,r_frame_rate,sample_rate,channels",
             "-of", "json", path])
    data = json.loads(p.stdout)
    v = next((s for s in data.get("streams", []) if s["codec_type"] == "video"), None)
    a = next((s for s in data.get("streams", []) if s["codec_type"] == "audio"), None)
    fps = None
    if v and v.get("r_frame_rate"):
        n, d = v["r_frame_rate"].split("/")
        fps = float(n) / float(d) if float(d) else None
    return {
        "duration": float(data["format"].get("duration", 0) or 0),
        "width": v and v.get("width"), "height": v and v.get("height"), "fps": fps,
        "has_audio": a is not None,
        "sample_rate": a and a.get("sample_rate"), "channels": a and a.get("channels"),
    }


def extract_frame(src, t, out, from_end=False):
    if from_end:
        # -update 1 ghi đè liên tục → ảnh cuối cùng còn lại chính là frame cuối thật
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-sseof", "-0.5",
               "-i", src, "-update", "1", "-q:v", "2", out]
    else:
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}",
               "-i", src, "-frames:v", "1", "-q:v", "2", out]
    run(cmd)
    if not os.path.exists(out):
        raise RuntimeError(f"Không trích được frame từ {src} @ {t}")
    return out


def ssim(img_a, img_b):
    p = run(["ffmpeg", "-hide_banner", "-i", img_a, "-i", img_b, "-lavfi",
             "[0:v]scale=360:-2,format=gray[a];[1:v]scale=360:-2,format=gray[b];[a][b]ssim",
             "-f", "null", "-"], check=False)
    m = re.search(r"All:([\d.]+)", p.stderr)
    return float(m.group(1)) if m else None


def classify_boundary(score, expect_match):
    if score is None:
        return WARN, "không đo được"
    if score >= MATCH_OK:
        return PASS, "match-cut khớp"
    if score < CUT_CLEAN:
        if expect_match:
            return FAIL, "đã định match-cut nhưng 2 khung khác hẳn"
        return PASS, "cắt sang cảnh khác (CUT) — ổn nếu có chủ đích"
    return FAIL, "JUMP CUT: gần giống nhưng lệch → mắt thấy giật"


def boundary_sheet(pairs, out_path, label_w=320):
    """pairs: list of (img_before, img_after). Ghép mỗi cặp thành 1 hàng."""
    if not pairs:
        return None
    tmpdir = tempfile.mkdtemp(prefix="qc_sheet_")
    rows = []
    for i, (a, b) in enumerate(pairs):
        row = os.path.join(tmpdir, f"row_{i}.png")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", a, "-i", b,
             "-filter_complex",
             f"[0:v]scale={label_w}:-2,pad=iw+8:ih:0:0:red[l];[1:v]scale={label_w}:-2[r];[l][r]hstack",
             row])
        rows.append(row)
    if len(rows) == 1:
        shutil.copy(rows[0], out_path)
    else:
        inputs = []
        for r in rows:
            inputs += ["-i", r]
        cols = min(3, len(rows))
        layout = []
        for i in range(len(rows)):
            c, r = i % cols, i // cols
            x = "+".join(["w0"] * c) or "0"
            y = "+".join(["h0"] * r) or "0"
            layout.append(f"{x}_{y}")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex",
             f"xstack=inputs={len(rows)}:layout={'|'.join(layout)}:fill=black", out_path])
    shutil.rmtree(tmpdir, ignore_errors=True)
    return out_path


def detect_cuts(src, threshold=0.3):
    p = run(["ffmpeg", "-hide_banner", "-i", src, "-vf",
             f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"], check=False)
    return [float(m) for m in re.findall(r"pts_time:([\d.]+)", p.stderr)]


def loudness(src):
    p = run(["ffmpeg", "-hide_banner", "-i", src, "-vn", "-af", "ebur128=peak=true",
             "-f", "null", "-"], check=False)
    tail = p.stderr[p.stderr.rfind("Summary:"):]
    def grab(key):
        m = re.search(key + r":\s+(-?[\d.]+)", tail)
        return float(m.group(1)) if m else None
    return {"I": grab("I"), "LRA": grab("LRA"), "TP": grab("Peak")}


def silences(src, noise_db=-45, min_dur=0.5):
    p = run(["ffmpeg", "-hide_banner", "-i", src, "-vn", "-af",
             f"silencedetect=n={noise_db}dB:d={min_dur}", "-f", "null", "-"], check=False)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    return [(s, ends[i] if i < len(ends) else None) for i, s in enumerate(starts)]


def luma_events(src, fps_sample=12, cuts=()):
    """Trả về (flash_ranges, black_ranges).

    Flash/cháy sáng = khung mất tương phản (cả vùng tối nhất YLOW cũng sáng ≥ 110)
    hoặc độ sáng trung bình nhảy vọt ≥ 55 giữa 2 mẫu liền nhau (không trùng điểm cắt).
    Hiệu chỉnh trên clip thật: flash 40,1–41,5s có YAVG 95→210, YLOW 28→165.
    """
    p = run(["ffmpeg", "-hide_banner", "-i", src, "-vf",
             f"fps={fps_sample},scale=160:-2,signalstats,metadata=print",
             "-an", "-f", "null", "-"], check=False)
    samples, t = [], None
    vals = {}
    for line in p.stderr.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            if t is not None and "YAVG" in vals:
                samples.append((t, vals.get("YAVG", 0), vals.get("YLOW", 0)))
            t, vals = float(m.group(1)), {}
            continue
        m = re.search(r"signalstats\.(YAVG|YLOW)=([\d.]+)", line)
        if m:
            vals[m.group(1)] = float(m.group(2))
    if t is not None and "YAVG" in vals:
        samples.append((t, vals.get("YAVG", 0), vals.get("YLOW", 0)))

    def ranges(pred, min_len):
        out, start, last = [], None, None
        for tt, ya, yl in samples:
            if pred(ya, yl):
                start = tt if start is None else start
                last = tt
            elif start is not None:
                if tt - start >= min_len:
                    out.append((start, tt))
                start = None
        if start is not None and last - start + 1.0 / fps_sample >= min_len:
            out.append((start, last))
        return out

    flashes = ranges(lambda ya, yl: yl >= 110 or ya >= 215, 0.15)
    for (t0, a0, _), (t1, a1, _) in zip(samples, samples[1:]):
        if a1 - a0 >= 55 and not any(abs(t1 - c) < 0.2 for c in cuts):
            if not any(s - 0.3 <= t1 <= e + 0.3 for s, e in flashes):
                flashes.append((t0, t1))
    flashes.sort()
    return flashes, ranges(lambda ya, yl: ya <= 16, 0.25)


def transcribe(src):
    """Trả về list (start, end, text) hoặc None nếu chưa cài faster-whisper."""
    if os.environ.get("QC_NO_WHISPER"):
        return None
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return None
    model_size = os.environ.get("QC_WHISPER_MODEL", "small")
    lang = os.environ.get("QC_LANG", "vi")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segs, _ = model.transcribe(src, language=lang, vad_filter=True,
                               condition_on_previous_text=False)
    return [(s.start, s.end, s.text.strip()) for s in segs]


def norm_text(s):
    s = unicodedata.normalize("NFC", s.lower())
    s = normalize_numbers(s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return " ".join(SYNONYMS.get(w, w) for w in s.split())


def script_coverage(script_lines, segments):
    """Với mỗi câu VO trong kịch bản, tìm đoạn nghe được giống nhất (theo từ)."""
    heard = norm_text(" ".join(t for _, _, t in segments))
    heard_words = heard.split()
    results = []
    for line in script_lines:
        target = norm_text(line).split()
        if not target:
            continue
        best = 0.0
        n = len(target)
        for i in range(0, max(1, len(heard_words) - n + 1)):
            window = heard_words[i:i + n + 2]
            r = difflib.SequenceMatcher(None, target, window).ratio()
            best = max(best, r)
        results.append((line, round(best, 2)))
    return results


# -------------------------------------------------------------- reporting ---
class Report:
    def __init__(self, title):
        self.title = title
        self.items = []   # (status, check, detail)
        self.images = []

    def add(self, status, check, detail):
        self.items.append((status, check, detail))

    @property
    def verdict(self):
        st = [s for s, _, _ in self.items]
        return FAIL if FAIL in st else (WARN if WARN in st else PASS)

    def write(self, out_dir, extra=None):
        os.makedirs(out_dir, exist_ok=True)
        icon = {PASS: "✅", WARN: "⚠️", FAIL: "❌"}
        lines = [f"# {self.title}", "", f"**Kết luận: {icon[self.verdict]} {self.verdict}**", "",
                 "| | Hạng mục | Chi tiết |", "|---|---|---|"]
        for s, c, d in self.items:
            lines.append(f"| {icon[s]} | {c} | {d} |")
        for cap, img in self.images:
            lines += ["", f"### {cap}", f"![{cap}]({os.path.basename(img)})"]
        md = os.path.join(out_dir, "qc_report.md")
        with open(md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        with open(os.path.join(out_dir, "qc_report.json"), "w", encoding="utf-8") as f:
            json.dump({"verdict": self.verdict,
                       "items": [{"status": s, "check": c, "detail": d} for s, c, d in self.items],
                       **(extra or {})}, f, ensure_ascii=False, indent=2)
        print("\n".join(lines))
        print(f"\n→ Báo cáo: {md}")
        return md


def check_format(rep, info, aspect, label=""):
    w, h = ASPECTS[aspect]
    ok_ratio = info["width"] and info["height"] and abs(info["width"] / info["height"] - w / h) < 0.01
    rep.add(PASS if ok_ratio else FAIL, f"{label}Tỷ lệ khung hình",
            f"{info['width']}×{info['height']} (yêu cầu {aspect})")
    return ok_ratio


# --------------------------------------------------------------- commands ---
def cmd_lastframe(a):
    extract_frame(a.clip, 0, a.out, from_end=True)
    print(f"Đã trích frame cuối thật: {a.out}")


def cmd_clips(a):
    rep = Report("QC clip vừa generate")
    tmp = os.path.join(a.out, "frames")
    os.makedirs(tmp, exist_ok=True)
    whisper_ok = True
    for i, c in enumerate(a.clips, 1):
        info = probe(c)
        tag = f"C{i} "
        check_format(rep, info, a.aspect, tag)
        rep.add(PASS if 4 <= info["duration"] <= 12 else WARN, f"{tag}Thời lượng", f"{info['duration']:.2f}s")
        if info["has_audio"] and whisper_ok:
            segs = transcribe(c)
            if segs is None:
                whisper_ok = False
                rep.add(WARN, "Lời nói lạ trong clip",
                        "chưa cài faster-whisper → không kiểm tra được; hãy nghe thử hoặc đặt sfx.keep=false khi dựng")
            elif segs:
                said = " / ".join(t for _, _, t in segs)[:160]
                rep.add(FAIL, f"{tag}Lời nói lạ trong clip",
                        f"model tự sinh lời: “{said}” → render lại (prompt cấm lời) hoặc tắt tiếng gốc khi dựng")
            else:
                rep.add(PASS, f"{tag}Lời nói lạ trong clip", "không phát hiện lời nói")
        flashes, blacks = luma_events(c)
        if flashes:
            rep.add(WARN, f"{tag}Cháy sáng/flash", ", ".join(f"{s:.1f}–{e:.1f}s" for s, e in flashes))
    pairs = []
    for i in range(len(a.clips) - 1):
        fa = extract_frame(a.clips[i], 0, os.path.join(tmp, f"c{i+1}_last.jpg"), from_end=True)
        fb = extract_frame(a.clips[i + 1], 0, os.path.join(tmp, f"c{i+2}_first.jpg"))
        sc = ssim(fa, fb)
        st, why = classify_boundary(sc, a.expect_match_cuts)
        rep.add(st, f"Mối nối C{i+1}→C{i+2}", f"SSIM {sc:.2f} — {why}" if sc is not None else why)
        pairs.append((fa, fb))
    if pairs:
        img = boundary_sheet(pairs, os.path.join(a.out, "boundaries.jpg"))
        rep.images.append(("Mối nối (trái = cuối clip N, phải = đầu clip N+1)", img))
    rep.write(a.out)
    return 1 if rep.verdict == FAIL else 0


def cmd_final(a):
    rep = Report("QC phim cuối")
    info = probe(a.video)
    check_format(rep, info, a.aspect)
    w, h = ASPECTS[a.aspect]
    rep.add(PASS if (info["width"], info["height"]) == (w, h) else WARN, "Độ phân giải chuẩn",
            f"{info['width']}×{info['height']} (chuẩn {w}×{h})")
    rep.add(PASS if info["fps"] and abs(info["fps"] - a.fps) < 0.01 else WARN, "FPS", f"{info['fps']}")
    rep.add(PASS if info["has_audio"] else FAIL, "Có audio", str(info["has_audio"]))
    if a.duration and a.ad:
        d = info["duration"]
        ok = a.duration - 1.5 <= d <= a.duration + 0.5
        rep.add(PASS if ok else FAIL, "Thời lượng quảng cáo",
                f"{d:.2f}s (bản {a.duration:g}s cho phép {a.duration - 1.5:.1f}–{a.duration + 0.5:.1f}s)")
    elif a.duration:
        diff = abs(info["duration"] - a.duration)
        rep.add(PASS if diff <= 2 else WARN, "Thời lượng", f"{info['duration']:.2f}s (mục tiêu {a.duration}s)")
    else:
        rep.add(PASS, "Thời lượng", f"{info['duration']:.2f}s")

    tl_path = os.path.splitext(a.video)[0] + ".timeline.json"
    if os.path.exists(tl_path):
        with open(tl_path, encoding="utf-8") as f:
            tl = json.load(f)
        for w_ in tl.get("warnings", []):
            rep.add(WARN, "Cảnh báo lúc dựng", w_)
        if a.ad:
            sc = tl.get("scenes", [])
            last, first = (sc[-1] if sc else {}), (sc[0] if sc else {})
            ok = last.get("block") == "CTA" and last.get("dur", 0) >= AD_END_MIN
            rep.add(PASS if ok else FAIL, "End card cuối phim",
                    f"cảnh cuối {last.get('id')} [{last.get('block')}] {last.get('dur', 0):.2f}s "
                    f"(cần block CTA ≥ {AD_END_MIN}s)")
            rep.add(PASS if first.get("block") == "HOOK" else WARN, "Mở đầu bằng HOOK",
                    f"cảnh đầu {first.get('id')} [{first.get('block')}]")
    elif a.ad:
        rep.add(WARN, "Timeline", f"không thấy {os.path.basename(tl_path)} → không kiểm tra được block/end card")
    if a.end_card:
        fdir = os.path.join(a.out, "frames")
        os.makedirs(fdir, exist_ok=True)
        fa = extract_frame(a.video, 0, os.path.join(fdir, "final_last.jpg"), from_end=True)
        fb = extract_frame(a.end_card, 0, os.path.join(fdir, "endcard_last.jpg"), from_end=True)
        sc_ = ssim(fa, fb)
        rep.add(PASS if sc_ is not None and sc_ >= MATCH_OK else FAIL, "End card khớp file thẻ",
                f"SSIM {sc_:.2f}" if sc_ is not None else "không đo được")
    extra = {}
    if info["has_audio"]:
        L = loudness(a.video)
        extra["loudness"] = L
        okI = L["I"] is not None and abs(L["I"] - a.target_lufs) <= 1.5
        rep.add(PASS if okI else FAIL, "Loudness (LUFS)", f"{L['I']} (mục tiêu {a.target_lufs} ±1.5)")
        okTP = L["TP"] is not None and L["TP"] <= -0.9
        rep.add(PASS if okTP else WARN, "True peak", f"{L['TP']} dBFS (≤ −1)")
        gaps = [(s, e) for s, e in silences(a.video) if s > 0.3 and (e or info["duration"]) < info["duration"] - 0.5]
        rep.add(PASS if not gaps else FAIL, "Khoảng lặng/hụt tiếng giữa phim",
                ", ".join(f"{s:.1f}–{e:.1f}s" for s, e in gaps) if gaps else "không có")

    cuts = detect_cuts(a.video)
    extra["cuts"] = cuts
    flashes, blacks = luma_events(a.video, cuts=cuts)
    rep.add(PASS if not flashes else WARN, "Cháy sáng/flash trắng",
            (", ".join(f"{s:.1f}–{e:.1f}s" for s, e in flashes) +
             " → đừng đặt chữ/thông điệp chính ở đoạn này; cân nhắc cắt bỏ") if flashes else "không có")
    blacks_mid = [(s, e) for s, e in blacks if s > 0.5 and e < info["duration"] - 0.5]
    rep.add(PASS if not blacks_mid else WARN, "Khung đen giữa phim",
            ", ".join(f"{s:.1f}–{e:.1f}s" for s, e in blacks_mid) or "không có")

    tmp = os.path.join(a.out, "frames")
    os.makedirs(tmp, exist_ok=True)
    pairs = []
    frame = 1.0 / (info["fps"] or 24)
    for i, t in enumerate(cuts, 1):
        fa = extract_frame(a.video, max(0, t - 2 * frame), os.path.join(tmp, f"cut{i}_a.jpg"))
        fb = extract_frame(a.video, t + frame, os.path.join(tmp, f"cut{i}_b.jpg"))
        sc = ssim(fa, fb)
        st, why = classify_boundary(sc, a.expect_match_cuts)
        rep.add(st, f"Mối nối @ {t:.2f}s", f"SSIM {sc:.2f} — {why}" if sc is not None else why)
        pairs.append((fa, fb))
    if pairs:
        img = boundary_sheet(pairs, os.path.join(a.out, "boundaries.jpg"))
        rep.images.append(("Mối nối (trái = trước cut, phải = sau cut)", img))
    if not cuts:
        rep.add(PASS, "Mối nối", "không phát hiện cut cứng (dùng chuyển cảnh mềm)")

    lines = []
    if a.script:
        with open(a.script, encoding="utf-8-sig") as f:
            lines = [l.strip() for l in f if l.strip() and not l.lstrip().startswith("#")]
    segs = transcribe(a.video) if (a.script or a.must_say) else None
    if a.script:
        if segs is None:
            rep.add(WARN, "Độ rõ lời VO", "chưa có faster-whisper (hoặc QC_NO_WHISPER) → nghe thủ công")
        else:
            extra["transcript"] = [{"start": s, "end": e, "text": t} for s, e, t in segs]
            for line, score in script_coverage(lines, segs):
                st = PASS if score >= 0.6 else (WARN if score >= 0.4 else FAIL)
                rep.add(st, "Độ rõ lời VO", f"{score:.2f} — “{line[:70]}”")
            script_words = set(norm_text(" ".join(lines)).split())
            for s, e, t in segs:
                words = norm_text(t).split()
                if len(words) >= 4:
                    unknown = sum(1 for w_ in words if w_ not in script_words) / len(words)
                    if unknown > 0.6:
                        rep.add(FAIL, "Lời lạ ngoài kịch bản",
                                f"{s:.1f}–{e:.1f}s: “{t[:80]}” → có thể do tiếng gốc của clip; tắt/hạ sfx")
    script_norm = norm_text(" ".join(lines)) if a.script else None
    for phrase in a.must_say:
        if script_norm is not None and norm_text(phrase) not in script_norm:
            rep.add(FAIL, "Kịch bản thiếu thông tin bắt buộc",
                    f"“{phrase}” không có trong {os.path.basename(a.script)}")
        if segs is None:
            rep.add(WARN, "Thông tin bắt buộc trong VO", f"“{phrase}” — chưa có whisper → nghe thủ công")
        else:
            res = script_coverage([phrase], segs)
            score = res[0][1] if res else 0.0
            rep.add(PASS if score >= 0.6 else FAIL, "Thông tin bắt buộc trong VO", f"{score:.2f} — “{phrase}”")
    rep.write(a.out, extra)
    return 1 if rep.verdict == FAIL else 0


def main():
    need_tools()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("lastframe")
    p.add_argument("clip")
    p.add_argument("out")
    p.set_defaults(fn=cmd_lastframe)

    p = sub.add_parser("clips")
    p.add_argument("clips", nargs="+")
    p.add_argument("--aspect", choices=ASPECTS, default="9:16")
    p.add_argument("--expect-match-cuts", action="store_true")
    p.add_argument("--out", default="qc_clips")
    p.set_defaults(fn=cmd_clips)

    p = sub.add_parser("final")
    p.add_argument("video")
    p.add_argument("--aspect", choices=ASPECTS, default="9:16")
    p.add_argument("--fps", type=float, default=24)
    p.add_argument("--duration", type=float, help="thời lượng mục tiêu (giây)")
    p.add_argument("--target-lufs", type=float, default=-14.0)
    p.add_argument("--script", help="file text: mỗi dòng 1 câu VO đúng như kịch bản")
    p.add_argument("--expect-match-cuts", action="store_true")
    p.add_argument("--ad", action="store_true", help="kiểm tra luật quảng cáo (thời lượng chặt, end card, HOOK)")
    p.add_argument("--end-card", help="file thẻ end card để so khớp frame cuối")
    p.add_argument("--must-say", action="append", default=[], help="cụm thông tin bắt buộc trong VO (lặp lại được)")
    p.add_argument("--out", default="qc_final")
    p.set_defaults(fn=cmd_final)

    a = ap.parse_args()
    if a.cmd != "lastframe":
        os.makedirs(a.out, exist_ok=True)
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
