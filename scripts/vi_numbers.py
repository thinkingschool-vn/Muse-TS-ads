"""Đọc số kiểu tiếng Việt — để so khớp lời VO với kịch bản (whisper hay ghi số bằng chữ số)."""
from __future__ import annotations

import re

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
UNITS = ["", "nghìn", "triệu", "tỷ"]


def _read3(n, full):
    """Đọc nhóm 3 chữ số; full=True khi đứng sau nhóm lớn hơn (đọc cả 'không trăm', 'linh')."""
    tr, ch, dv = n // 100, (n // 10) % 10, n % 10
    out = []
    if tr or full:
        out += [DIGITS[tr], "trăm"]
    if ch == 0:
        if dv and (tr or full):
            out.append("linh")
    elif ch == 1:
        out.append("mười")
    else:
        out += [DIGITS[ch], "mươi"]
    if dv:
        if dv == 1 and ch >= 2:
            out.append("mốt")
        elif dv == 5 and ch >= 1:
            out.append("lăm")
        else:
            out.append(DIGITS[dv])
    return out


def num_to_vi(n):
    if n < 0:
        return "âm " + num_to_vi(-n)
    if n == 0:
        return "không"
    if n >= 10 ** 12:
        return " ".join(DIGITS[int(c)] for c in str(n))
    groups = []
    while n:
        groups.append(n % 1000)
        n //= 1000
    words = []
    for i in range(len(groups) - 1, -1, -1):
        if groups[i] == 0:
            continue
        words += _read3(groups[i], full=i < len(groups) - 1)
        if UNITS[i]:
            words.append(UNITS[i])
    return " ".join(words)


_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b")
_NUM = re.compile(r"\d{1,3}(?:[.,]\d{3})+(?!\d)|\d+")


def _num_words(m):
    s = re.sub(r"[.,]", "", m.group(0))
    if len(s) > 1 and s[0] == "0":
        return " ".join(DIGITS[int(c)] for c in s)
    return num_to_vi(int(s))


def normalize_numbers(text):
    t = _DATE.sub(lambda m: f"{m.group(1)} tháng {m.group(2)}" + (f" năm {m.group(3)}" if m.group(3) else ""), text)
    t = re.sub(r"(\d)\s*%", r"\1 phần trăm", t)
    t = re.sub(r"(\d)\s*(?:vnđ|vnd|đ)(?!\w)", r"\1 đồng", t, flags=re.IGNORECASE)
    return _NUM.sub(_num_words, t)
