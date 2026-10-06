#!/usr/bin/env python3
"""Cắt bản 30s/15s từ edit.json master theo nhãn block — skill Muse-TS-ads.

  cutdown.py edit.json                 # tạo edit_30.json + edit_15.json cạnh file master
  cutdown.py edit.json --to 15         # chỉ bản 15s
  cutdown.py edit.json --render        # tạo xong gọi luôn assemble.py cho từng bản

Bản cắt giữ các cảnh có block nằm trong kế hoạch (adslib.CUT_PLANS hoặc "cutdowns" trong
edit.json), theo thứ tự master; giữ VO/overlay gắn với các cảnh đó; áp "versions" và "trim".
Cảnh báo nếu thời lượng ước tính lệch quá ±1.5s so với đích.
Có "hook_variants" → giữ nguyên trong edit_30/edit_15; assemble.py dựng đủ các bản hook cho từng bản cắt.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from adslib import (TOLERANCE, AdsError, estimate_duration, norm_block, output_name,  # noqa: E402
                    select_blocks, validate_hook_variants)


def probe_duration(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0 or not p.stdout.strip():
        raise AdsError(f"không đọc được độ dài: {path}")
    return float(p.stdout.strip())


def make_cut(edit, version, durations):
    """(edit bản cắt, thời lượng ước tính, cảnh báo). durations: {file: giây} cho cảnh thiếu 'out'."""
    validate_hook_variants(edit)
    e = select_blocks(edit, version)
    est = estimate_duration(e["scenes"], durations)
    warnings = []
    if abs(est - int(version)) > TOLERANCE:
        warnings.append(f"bản {version}s ước tính {est:.2f}s — lệch quá ±{TOLERANCE}s; "
                        "chỉnh 'trim' của cảnh hoặc 'cutdowns' trong edit.json")
    e["output"] = output_name(edit.get("output", "final.mp4"), version)
    return e, est, warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edit")
    ap.add_argument("--to", nargs="+", default=["30", "15"], help="các bản cần cắt (giây)")
    ap.add_argument("--render", action="store_true", help="gọi assemble.py cho từng bản sau khi tạo")
    a = ap.parse_args()
    with open(a.edit, encoding="utf-8-sig") as f:
        edit = json.load(f)
    base = os.path.dirname(os.path.abspath(a.edit))
    if edit.get("version") is None:
        print('⚠ edit.json master chưa có "version" (vd "60") — nên khai báo')
    written = []
    try:
        durations = {}
        for s in edit.get("scenes", []):
            if "out" not in s and s["file"] not in durations:
                durations[s["file"]] = probe_duration(os.path.join(base, s["file"]))
        for v in a.to:
            e, est, warns = make_cut(edit, v, durations)
            path = os.path.join(base, f"edit_{v}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(e, f, ensure_ascii=False, indent=2)
            blocks = " → ".join(dict.fromkeys(norm_block(s["block"]) for s in e["scenes"]))
            print(f"✔ {os.path.basename(path)}: {blocks} — ước tính {est:.2f}s → {e['output']}")
            for w in warns:
                print(f"  ⚠ {w}")
            written.append(path)
    except AdsError as ex:
        sys.exit(f"Lỗi: {ex}")
    if a.render:
        for p in written:
            r = subprocess.run([sys.executable, os.path.join(HERE, "assemble.py"), p])
            if r.returncode:
                sys.exit(r.returncode)


if __name__ == "__main__":
    main()
