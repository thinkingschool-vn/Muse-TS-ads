#!/usr/bin/env python3
"""Phong cách video quảng cáo — skill Muse-TS-ads.

  styles.py list                    # liệt kê phong cách
  styles.py show cinematic-drama    # in luật của phong cách (đọc trước khi viết kịch bản)
  styles.py prompt cinematic-drama  # in khối STYLE/CAMERA dán vào ĐẦU mỗi prompt clip

Phong cách nằm ở styles/<id>.json. Ghi "style": "<id>" vào edit.json để assemble.py/qc.py áp luật.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adslib import DEFAULT_STYLE, AdsError, list_styles, load_style, style_prompt_block  # noqa: E402


def describe(s):
    lo, hi = s["shot_len"]
    talk = "có (model tự tạo, ≤ 15 từ/clip, 1 người nói)" if s["dialogue"] else "không — chỉ VO"
    return "\n".join([
        f"# {s['name']} ({s['id']})",
        f"Dùng khi: {s['use_when']}",
        "",
        f"Shot dài {lo:g}–{hi:g}s · hook cần ≥ {s['hook_min_shots']} shot trong 0–5s",
        f"Loại hook gợi ý: {', '.join(s['hook_types'])}",
        f"Chuyển cảnh: {', '.join(s['transitions'])}",
        f"Thoại nhân vật: {talk}",
        f"Màu: {s['grade_arc']}",
        f"Nhạc: {s['music_brief']}",
        f"Giọng: {s['vo_brief']}",
        "",
        "Máy được phép: " + "; ".join(s["camera_allowed"]),
        "Máy bị cấm: " + "; ".join(s["camera_forbidden"]),
    ])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for c in ("show", "prompt"):
        sub.add_parser(c).add_argument("style")
    a = ap.parse_args()
    try:
        if a.cmd == "list":
            for sid in list_styles():
                s = load_style(sid)
                mark = " (mặc định)" if sid == DEFAULT_STYLE else ""
                print(f"{sid:<16} {s['name']}{mark} — {s['use_when']}")
        elif a.cmd == "show":
            print(describe(load_style(a.style)))
        else:
            print(style_prompt_block(load_style(a.style)))
    except AdsError as e:
        sys.exit(f"Lỗi: {e}")


if __name__ == "__main__":
    main()
