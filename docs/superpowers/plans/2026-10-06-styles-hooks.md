# Muse-TS-ads v2 — Styles + 3-second Hook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add selectable video styles (cinematic-drama, micro-drama, warm-3d, motion-graphics), a measurable 3-second hook system with 1–5 A/B hook variants per ad, model-generated character dialogue for drama styles, three edit-time transitions (whip, zoompunch, flash), and automated hook + dialogue QC.

**Architecture:** Styles are JSON configs in `styles/`, loaded and validated by `adslib.py`, exposed via a new `scripts/styles.py` CLI, and enforced by `assemble.py` (transitions, dialogue, punch). `adslib.apply_hook_variant` swaps the HOOK scenes per variant; `assemble.py` renders one file per variant. `assemble.py` writes richer `.timeline.json` (style, overlays, logo bug, spoken lines, dialogue) which `qc.py final` reads for the new "Hook:" and dialogue checks.

**Tech Stack:** Python 3.8+ stdlib, ffmpeg/ffprobe ≥ 6.1 with libass and xfade (`hblur`, `zoomin`, `fadewhite` verified in ffmpeg 8.1.1), optional faster-whisper, pytest.

**Spec:** `docs/superpowers/specs/2026-10-06-styles-hooks-design.md`

## Global Constraints

- Scripts use only Python stdlib + ffmpeg/ffprobe; faster-whisper optional; no new pip deps. Python 3.8 compatible (no `dict | dict`, no `match`).
- All user-facing messages, docs and comments in Vietnamese. Data errors raise `adslib.AdsError`; CLIs print `Lỗi edit.json: …` / `Lỗi: …` and exit non-zero.
- Styles v1 (exact ids): `cinematic-drama`, `micro-drama`, `warm-3d` (default), `motion-graphics`. `humans` must be `"stylized"`.
- Hook types (exact ids, 12): `in-medias-res, cold-open, pattern-interrupt, why-question, bold-claim, stop-doing, pov-pain, curiosity-gap, before-after, direct-address, callout, stat-shock`.
- Hook variants: 1–5 per edit; id matches `^[A-Za-z0-9]{1,8}$`; output suffix `_hook<id>` (e.g. `ts-x-9x16-60s_hookA.mp4`). Skill default = 3 variants.
- Dialogue: ≤ 15 words per scene, one speaker, only in styles with `dialogue: true`; no VO may overlap a dialogue scene; dialogue scene clip audio at `dialogue_gain_db` (default 0 dB); requires `sfx.keep` true.
- Punch: 1.0 ≤ punch ≤ 1.5.
- Transitions: `whip` = xfade `hblur` 0.2s · `zoompunch` = xfade `zoomin` 0.15s · `flash` = xfade `fadewhite` 0.12s. Other names pass through to xfade unchanged (default 0.4s). Style transition whitelist is enforced only when edit.json sets `"style"` explicitly.
- Hook QC thresholds: first cut ≤ 2.5s (FAIL) · shots in 0–5s ≥ style `hook_min_shots` (FAIL) · frame 0 YAVG > 20 and SSIM(frame 0, frame 0.5s) < 0.995 (FAIL) · overlay starting < 3.0s (FAIL) · audio onset ≤ 0.5s at −40 dB (FAIL) · brand (logo bug or brand name in a spoken line) starting < 5.0s (WARN).
- Dialogue QC: coverage < 0.8 → FAIL; heard words > 1.5 × script words → FAIL; no whisper → WARN.
- No AI-label overlay in video; `templates/AD_COPY.md` reminds to toggle platform AI labels (law 134/2025/QH15 label format ⚠ cần pháp chế xác nhận).
- Existing 82 tests must stay green. Do not modify `c:\Users\VietPC\MuseAI\Muse-ads-short-film`.
- Shell is Windows PowerShell 5: set `$env:PYTHONIOENCODING="utf-8"` before running scripts/tests. Git identity already set in repo.

## Review Focus

- A hook variant whose `vo`/`overlays` point at a master scene id (e.g. `"scene": "pain"`) → clear Vietnamese error naming the variant's own scene ids (test in Task 4).
- Variant id unsafe for file names (`"A/B"`, `"Bản 1"`) → rejected before rendering (test in Task 4).
- A dialogue scene while `sfx.keep` is false → the dialogue would silently vanish; must error instead (test in Task 3).
- Dialogue containing numbers/dates (`"Ra mắt 11/10 nhé"`) while the script spells them out → dialogue QC must still PASS (test in Task 5).
- Old edit.json with no `"style"` that uses a non-whitelisted xfade name (`"wipeleft"`) → still renders exactly as before (test in Task 2).

---

### Task 1: Style configs + `adslib` style API + `styles.py` CLI

**Files:**
- Create: `styles/cinematic-drama.json`, `styles/micro-drama.json`, `styles/warm-3d.json`, `styles/motion-graphics.json`
- Modify: `scripts/adslib.py` (append new section after `output_name`)
- Create: `scripts/styles.py`
- Test: `tests/test_styles.py`

**Interfaces:**
- Produces: `adslib.STYLES_DIR: str`, `adslib.DEFAULT_STYLE = "warm-3d"`, `adslib.HOOK_TYPES: list[str]`, `adslib.list_styles(styles_dir=None) -> list[str]`, `adslib.load_style(style_id=None, styles_dir=None) -> dict`, `adslib.style_prompt_block(style: dict) -> str`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_styles.py`:

```python
import json
import os
import subprocess
import sys

import pytest

from conftest import SCRIPTS
from adslib import AdsError, list_styles, load_style, style_prompt_block


def test_four_styles_load():
    assert list_styles() == ["cinematic-drama", "micro-drama", "motion-graphics", "warm-3d"]
    for sid in list_styles():
        s = load_style(sid)
        assert s["id"] == sid and s["humans"] == "stylized" and "cut" in s["transitions"]


def test_default_style_is_warm_3d():
    s = load_style(None)
    assert s["id"] == "warm-3d" and s["dialogue"] is False and s["hook_min_shots"] == 1


def test_drama_styles_allow_dialogue_and_need_two_hook_shots():
    for sid in ("cinematic-drama", "micro-drama"):
        s = load_style(sid)
        assert s["dialogue"] is True and s["hook_min_shots"] == 2
    assert load_style("motion-graphics")["hook_min_shots"] == 3


def test_unknown_style_lists_choices():
    with pytest.raises(AdsError, match="cinematic-drama"):
        load_style("cinematic_drama")


def _write(tmp_path, drop=None, **over):
    s = load_style("warm-3d")
    s.update(over)
    if drop:
        del s[drop]
    (tmp_path / "warm-3d.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    return str(tmp_path)


def test_photoreal_humans_rejected(tmp_path):
    with pytest.raises(AdsError, match="stylized"):
        load_style("warm-3d", styles_dir=_write(tmp_path, humans="photoreal"))


def test_missing_field_rejected(tmp_path):
    with pytest.raises(AdsError, match="look"):
        load_style("warm-3d", styles_dir=_write(tmp_path, drop="look"))


def test_unknown_hook_type_rejected(tmp_path):
    with pytest.raises(AdsError, match="clickbait"):
        load_style("warm-3d", styles_dir=_write(tmp_path, hook_types=["clickbait"]))


def test_bool_is_not_an_int(tmp_path):
    with pytest.raises(AdsError, match="hook_min_shots"):
        load_style("warm-3d", styles_dir=_write(tmp_path, hook_min_shots=True))


def test_bad_shot_len_rejected(tmp_path):
    with pytest.raises(AdsError, match="shot_len"):
        load_style("warm-3d", styles_dir=_write(tmp_path, shot_len=[4, 2]))


def test_prompt_block_has_look_and_camera_rules():
    b = style_prompt_block(load_style("cinematic-drama"))
    lines = b.splitlines()
    assert lines[0].startswith("STYLE: ") and "anamorphic" in lines[0]
    assert "whip pan" in b.split("CAMERA FORBIDDEN:")[1]
    assert lines[-1] == "HUMANS: stylized 3D characters, never photoreal humans."


def test_prompt_blocks_have_no_brand_words():
    # Khối này dán vào prompt AI → không được chứa chữ model có thể vẽ ra (TEXT BAN)
    for sid in list_styles():
        b = style_prompt_block(load_style(sid)).lower()
        for w in ("thinking", "disney", "pixar", "mba"):
            assert w not in b, (sid, w)


def run_cli(*args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "styles.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


def test_cli_list_show_prompt():
    r = run_cli("list")
    assert r.returncode == 0 and "warm-3d" in r.stdout and "(mặc định)" in r.stdout
    r = run_cli("show", "micro-drama")
    assert r.returncode == 0 and "Thoại nhân vật: có" in r.stdout
    r = run_cli("prompt", "motion-graphics")
    assert r.stdout.strip() == style_prompt_block(load_style("motion-graphics"))
    r = run_cli("show", "nope")
    assert r.returncode != 0 and "không có phong cách" in r.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_styles.py -q`
Expected: FAIL / ERROR with `ImportError: cannot import name 'list_styles'`.

- [ ] **Step 3: Create the four style files**

`styles/cinematic-drama.json`:
```json
{
  "id": "cinematic-drama",
  "name": "Drama điện ảnh",
  "use_when": "Mini MBA, chương trình chuyên sâu, hội thảo, câu chuyện chuyển mình của học viên — cần cảm xúc mạnh",
  "look": "Cinematic stylized 3D feature-animation characters in a photoreal environment, anamorphic 35mm lens feel, shallow depth of field, chiaroscuro key light with soft rim light, practical lights in frame, subtle film grain, teal-and-amber color grade",
  "camera_allowed": ["static locked-off shot with subject motion", "slow dolly-in (push-in)", "slow dolly-out", "slow lateral tracking", "slow orbit around the subject", "low-angle hero shot", "gentle handheld"],
  "camera_forbidden": ["whip pan", "crash zoom", "more than one camera move per clip", "close-up of hands typing", "readable screens", "crowds"],
  "shot_len": [1.5, 4.0],
  "hook_min_shots": 2,
  "hook_types": ["in-medias-res", "cold-open", "pattern-interrupt"],
  "transitions": ["cut", "fade", "whip", "flash", "zoompunch"],
  "grade_arc": "Trước: lạnh, xanh lam, tương phản gắt · Sau: ấm, vàng hổ phách, mềm",
  "music_brief": "Nhạc điện ảnh trầm, dồn dần; drone/nhịp tim ở hook; bùng lên ở khoảnh khắc lật ngược",
  "vo_brief": "Giọng trầm, chậm, có khoảng nghỉ; thoại nhân vật ngắn, đời thường",
  "dialogue": true,
  "humans": "stylized"
}
```

`styles/micro-drama.json`:
```json
{
  "id": "micro-drama",
  "name": "Micro-drama / sitcom văn phòng",
  "use_when": "Khoá kỹ năng ngắn (microlearning), kỹ năng văn phòng, giao tiếp — tình huống đời thường, lật kèo",
  "look": "Stylized 3D feature-animation characters with expressive faces in a bright photoreal modern office or apartment, natural soft daylight, clean contemporary set dressing, slightly saturated sitcom color palette, medium depth of field",
  "camera_allowed": ["static locked-off shot with subject motion", "slow push-in on a reaction", "over-the-shoulder medium shot", "medium two-shot", "gentle handheld"],
  "camera_forbidden": ["whip pan", "crash zoom", "more than one camera move per clip", "close-up of hands typing", "readable screens", "crowds"],
  "shot_len": [1.0, 3.0],
  "hook_min_shots": 2,
  "hook_types": ["in-medias-res", "pov-pain", "why-question"],
  "transitions": ["cut", "fade", "whip", "zoompunch", "flash"],
  "grade_arc": "Trước: hơi xám, ánh đèn huỳnh quang · Sau: sáng, ấm, tươi",
  "music_brief": "Nhạc sitcom nhẹ, nhịp nhanh; stinger khựng/hài ở điểm lật kèo",
  "vo_brief": "Ít VO; ưu tiên thoại nhân vật tự nhiên, câu ngắn, giọng đời thường",
  "dialogue": true,
  "humans": "stylized"
}
```

`styles/warm-3d.json`:
```json
{
  "id": "warm-3d",
  "name": "Hoạt hình 3D ấm",
  "use_when": "Mặc định; chương trình cộng đồng, Thinking Uni, khoá cho người mới — thân thiện, truyền cảm hứng",
  "look": "Stylized 3D feature-animation look, soft rounded shapes, gentle subsurface skin, warm cinematic lighting, rich painterly backgrounds",
  "camera_allowed": ["static locked-off shot with subject motion", "slow push-in", "gentle orbit", "slow pan"],
  "camera_forbidden": ["whip pan", "crash zoom", "more than one camera move per clip", "readable screens"],
  "shot_len": [3.0, 10.0],
  "hook_min_shots": 1,
  "hook_types": ["pattern-interrupt", "curiosity-gap", "why-question"],
  "transitions": ["cut", "fade", "fadewhite", "fadeblack", "dissolve", "slideup", "slideleft"],
  "grade_arc": "Ấm xuyên suốt, sáng dần về cuối",
  "music_brief": "Nhạc ấm, truyền cảm hứng, 1 bài liền mạch",
  "vo_brief": "Giọng ấm, rõ, tốc độ vừa",
  "dialogue": false,
  "humans": "stylized"
}
```

`styles/motion-graphics.json`:
```json
{
  "id": "motion-graphics",
  "name": "Motion-graphics nhịp nhanh",
  "use_when": "Ưu đãi, flash sale, seminar, khoá nhiều lợi ích cần liệt kê — nhịp nhanh, thông tin dày",
  "look": "Clean stylized 3D motion-design look, simple geometric shapes and props, bold flat blue and violet color fields, soft studio lighting, crisp shadows, playful bouncy motion",
  "camera_allowed": ["static locked-off shot with object motion", "slow push-in", "slow orbit around an object"],
  "camera_forbidden": ["whip pan", "crash zoom", "more than one camera move per clip", "readable screens", "text or numbers on objects"],
  "shot_len": [0.8, 2.5],
  "hook_min_shots": 3,
  "hook_types": ["pattern-interrupt", "stat-shock", "stop-doing"],
  "transitions": ["cut", "fade", "whip", "zoompunch", "flash", "slideup"],
  "grade_arc": "Sáng, bão hoà, màu thương hiệu xuyên suốt",
  "music_brief": "Điện tử/pop 110–128 BPM, có hit trùng điểm cắt",
  "vo_brief": "Giọng nhanh, năng lượng, câu cực ngắn",
  "dialogue": false,
  "humans": "stylized"
}
```

- [ ] **Step 4: Append the style API to `scripts/adslib.py`** (after `output_name`; also add `- load_style() / style_prompt_block(): phong cách video (styles/*.json)` as a line in the module docstring):

```python


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
```

- [ ] **Step 5: Create `scripts/styles.py`**

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_styles.py -q` → Expected: all PASS.
Run: `python -m pytest -q` → Expected: all PASS (82 old + new).

- [ ] **Step 7: Commit**

```powershell
git add styles scripts/adslib.py scripts/styles.py tests/test_styles.py
git commit -m "feat: style presets (styles/*.json), adslib style API, styles.py CLI"
```

---

### Task 2: `assemble.py` — style enforcement, punch, whip/zoompunch/flash, `render_one` refactor

**Files:**
- Modify: `scripts/adslib.py` (`trans_duration` → uses new `resolve_transition`; add `TRANSITION_ALIASES`, `check_style_use`)
- Modify: `scripts/assemble.py` (imports, `trans_of`, `build_timeline`, `normalize_scene`, new `scene_vf`, `render_video`, replace `main` with `load_edit` / `prepare` / `render_one` / `main`)
- Modify: `tests/conftest.py` (add `run_assemble` helper)
- Test: `tests/test_assemble_styles.py`

**Interfaces:**
- Consumes: `load_style`, `DEFAULT_STYLE` (Task 1).
- Produces: `adslib.TRANSITION_ALIASES: dict[str, tuple[str, float]]`, `adslib.resolve_transition(t) -> {"type": str, "xfade": str|None, "duration": float}`, `adslib.check_style_use(edit, style, explicit=True) -> None`, `assemble.scene_vf(W, H, fps, punch=1.0) -> str`, `assemble.load_edit(path) -> dict`, `assemble.prepare(edit) -> (edit, style)`, `assemble.render_one(edit, style, a) -> str|None`. Timeline JSON gains `"style"` and `"hook_min_shots"`. Timeline scene dicts (in memory) gain `"punch"` and `"dialogue"` (raw dict or None).

- [ ] **Step 1: Add the helper to `tests/conftest.py`** (append at end):

```python


def run_assemble(edit, d, *extra):
    """Ghi edit.json vào thư mục d rồi chạy assemble.py; trả về CompletedProcess."""
    p = d / "edit.json"
    p.write_text(json.dumps(edit, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "assemble.py"), str(p), *extra],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
```

- [ ] **Step 2: Write the failing tests** — create `tests/test_assemble_styles.py`:

```python
import json
import os

import pytest

from conftest import needs_ffmpeg, probe, run_assemble
import adslib
import assemble
from adslib import AdsError, check_style_use, load_style, resolve_transition


def test_resolve_transition_aliases_and_passthrough():
    assert resolve_transition("whip") == {"type": "whip", "xfade": "hblur", "duration": 0.2}
    assert resolve_transition({"type": "zoompunch"}) == {"type": "zoompunch", "xfade": "zoomin", "duration": 0.15}
    assert resolve_transition("flash") == {"type": "flash", "xfade": "fadewhite", "duration": 0.12}
    assert resolve_transition({"type": "whip", "duration": 0.3})["duration"] == 0.3
    assert resolve_transition("wipeleft") == {"type": "wipeleft", "xfade": "wipeleft", "duration": 0.4}
    assert resolve_transition("cut") == {"type": "cut", "xfade": None, "duration": 0.0}
    assert resolve_transition(None)["type"] == "cut"


def test_trans_duration_uses_alias_default():
    assert adslib.trans_duration({"transition": "flash"}) == 0.12
    assert adslib.trans_duration({"transition": {"type": "fade", "duration": 0.4}}) == 0.4


def test_style_transition_whitelist_only_when_style_explicit():
    e = {"scenes": [{"id": "a", "transition": "whip"}]}
    with pytest.raises(AdsError, match="whip"):
        check_style_use(e, load_style("warm-3d"), explicit=True)
    check_style_use(e, load_style("warm-3d"), explicit=False)
    check_style_use(e, load_style("cinematic-drama"), explicit=True)


def test_dialogue_needs_a_dialogue_style():
    e = {"scenes": [{"id": "a", "dialogue": {"speaker": "Linh", "text": "Chào"}}]}
    with pytest.raises(AdsError, match="không cho thoại"):
        check_style_use(e, load_style("warm-3d"), explicit=False)
    check_style_use(e, load_style("micro-drama"), explicit=True)


@pytest.mark.parametrize("p", [0.9, 1.6, "1.2", True])
def test_punch_out_of_range_rejected(p):
    with pytest.raises(AdsError, match="punch"):
        check_style_use({"scenes": [{"id": "a", "punch": p}]}, load_style("warm-3d"), explicit=False)


def test_scene_vf_punch():
    assert "trunc(iw*1.200/2)*2" in assemble.scene_vf(720, 1280, 24, 1.2)
    assert "trunc" not in assemble.scene_vf(720, 1280, 24, 1.0)


@needs_ffmpeg
def test_new_transitions_and_punch_render(media, tmp_path):
    edit = {"aspect": "9:16", "style": "cinematic-drama", "output": "out/x.mp4", "scenes": [
        {"id": "a", "file": str(media / "clip_a.mp4"), "out": 1.5, "transition": "whip"},
        {"id": "b", "file": str(media / "clip_a.mp4"), "in": 1.5, "out": 3, "punch": 1.3, "transition": "zoompunch"},
        {"id": "c", "file": str(media / "clip_b.mp4"), "out": 2, "transition": "flash"},
        {"id": "d", "file": str(media / "clip_c.mp4"), "out": 2}],
        "music": {"file": str(media / "music.wav"), "gain_db": -14}}
    r = run_assemble(edit, tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    info = probe(tmp_path / "out" / "x.mp4")
    assert (info["width"], info["height"]) == (720, 1280)
    assert abs(info["duration"] - (7.0 - 0.2 - 0.15 - 0.12)) < 0.15
    tl = json.loads((tmp_path / "out" / "x.timeline.json").read_text(encoding="utf-8"))
    assert tl["style"] == "cinematic-drama" and tl["hook_min_shots"] == 2


@needs_ffmpeg
def test_style_violation_stops_before_render(media, tmp_path):
    edit = {"aspect": "9:16", "style": "warm-3d", "scenes": [
        {"id": "a", "file": str(media / "clip_a.mp4"), "out": 2, "transition": "whip"},
        {"id": "b", "file": str(media / "clip_b.mp4"), "out": 2}]}
    r = run_assemble(edit, tmp_path, "--plan")
    assert r.returncode != 0 and "whip" in r.stderr and "warm-3d" in r.stderr


@needs_ffmpeg
def test_old_edit_without_style_keeps_any_xfade(media, tmp_path):
    edit = {"aspect": "9:16", "output": "old.mp4", "scenes": [
        {"id": "a", "file": str(media / "clip_a.mp4"), "out": 2, "transition": {"type": "wipeleft", "duration": 0.4}},
        {"id": "b", "file": str(media / "clip_b.mp4"), "out": 2}],
        "music": {"file": str(media / "music.wav"), "gain_db": -14}}
    r = run_assemble(edit, tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    assert abs(probe(tmp_path / "old.mp4")["duration"] - 3.6) < 0.15
    tl = json.loads((tmp_path / "old.timeline.json").read_text(encoding="utf-8"))
    assert tl["style"] == "warm-3d" and tl["hook_min_shots"] == 1


@needs_ffmpeg
def test_punch_changes_the_picture(media, tmp_path):
    import qc
    imgs = []
    for p in (1.0, 1.5):
        sc = {"path": str(media / "clip_a.mp4"), "in": 0.0, "dur": 1.0, "has_audio": True, "punch": p}
        d = tmp_path / f"p{p}"
        d.mkdir()
        seg = assemble.normalize_scene(sc, 0, 720, 1280, 24, str(d))
        imgs.append(qc.extract_frame(seg, 0.5, str(d / "f.jpg")))
    assert qc.ssim(*imgs) < 0.9
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_assemble_styles.py -q`
Expected: ERROR `ImportError: cannot import name 'check_style_use'`.

- [ ] **Step 4: Implement in `scripts/adslib.py`** — replace the existing `trans_duration` function with:

```python
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
```

and append after `style_prompt_block`:

```python


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
```

- [ ] **Step 5: Implement in `scripts/assemble.py`**

5a. Docstring: after the line `  "logo_bug": …` block add:
```
  "style": "cinematic-drama"       → phong cách (styles/*.json): chặn chuyển cảnh/thoại trái luật, ghi vào timeline
  scene "punch": 1.2               → phóng to 1.0–1.5 lần để tạo shot cận hơn từ cùng clip
  transition "whip" / "zoompunch" / "flash" → lia nhanh nhoè (0,2s) / zoom giật (0,15s) / chớp trắng (0,12s)
```

5b. Import line becomes:
```python
from adslib import (ASPECTS, SAFE, AdsError, check_style_use, filter_version, load_brand,  # noqa: E402
                    load_style, norm_block, resolve_transition)
```

5c. Replace `trans_of`:
```python
def trans_of(scene):
    return resolve_transition(scene.get("transition", "cut"))
```

5d. In `build_timeline`, replace the `sc = {...}` statement with:
```python
        sc = {"id": s.get("id", f"s{i+1}"), "path": path, "in": t_in, "dur": dur,
              "start": round(start, 3), "end": round(start + dur, 3), "trans": trans_of(s),
              "has_audio": info["has_audio"], "block": norm_block(s["block"]) if s.get("block") else None,
              "punch": float(s.get("punch", 1.0)), "dialogue": s.get("dialogue")}
```

5e. Add `scene_vf` above `normalize_scene` and use it:
```python
def scene_vf(W, H, fps, punch=1.0):
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
    if punch and punch > 1.0:  # phóng to rồi cắt giữa → shot cận hơn từ cùng clip
        vf += f"scale=trunc(iw*{punch:.3f}/2)*2:trunc(ih*{punch:.3f}/2)*2,crop={W}:{H},setsar=1,"
    return vf + f"fps={fps},format=yuv420p"
```
In `normalize_scene` replace the two-line `vf = (...)` assignment with `vf = scene_vf(W, H, fps, sc.get("punch", 1.0))`.

5f. In `render_video`, change `xfade=transition={t['type']}` to `xfade=transition={t['xfade']}`.

5g. Replace the whole `main()` function (from `def main():` to the end of its `finally:` block) with:

```python
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
        segs = [normalize_scene(s, i, W, H, fps, work) for i, s in enumerate(scenes)]
        print("2/5 Overlay chữ…")
        ass = build_ass(edit, by_id, W, H, aspect, total, work, warnings)
        print("3/5 Nối cảnh + chuyển cảnh…")
        logo = logo_spec(edit, scenes, W, H, aspect)
        joined = render_video(segs, scenes, ass, total, work, logo)
        print("4/5 Mix âm thanh 3 lớp + ducking…")
        mix, spans = render_mix(edit, by_id, joined, total, work, warnings)
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
        timeline = {"aspect": aspect, "fps": fps, "total": total, "version": edit.get("version"),
                    "style": style["id"], "hook_min_shots": style["hook_min_shots"],
                    "scenes": [{k: s[k] for k in ("id", "start", "end", "dur", "block")} for s in scenes],
                    "vo": [{"file": f, "start": round(s0, 3), "end": round(s1, 3)} for s0, s1, f in spans],
                    "warnings": warnings}
        with open(os.path.splitext(out)[0] + ".timeline.json", "w", encoding="utf-8") as f:
            json.dump(timeline, f, ensure_ascii=False, indent=2)
        vo_texts = [v["text"] for v in edit.get("vo", []) if v.get("text")]
        script_path = None
        if vo_texts:
            script_path = os.path.splitext(out)[0] + ".vo.txt"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write("\n".join(vo_texts) + "\n")
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
```

- [ ] **Step 6: Run tests**

Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_assemble_styles.py -q` → all PASS.
Run: `python -m pytest -q` → all PASS (incl. `test_assemble_plan_runs`, which checks `TIMELINE` and `4.00s`).

- [ ] **Step 7: Commit**

```powershell
git add scripts/adslib.py scripts/assemble.py tests/conftest.py tests/test_assemble_styles.py
git commit -m "feat(assemble): style enforcement, punch-in shots, whip/zoompunch/flash transitions"
```

---

### Task 3: Dialogue scenes — validation, mixing, script output

**Files:**
- Modify: `scripts/adslib.py` (append `DIALOGUE_MAX_WORDS`, `check_dialogue`, `dialogue_windows`, `vo_dialogue_clash`, `timed_lines`)
- Modify: `scripts/assemble.py` (`normalize_scene` gain, `render_mix` dialogue routing + clash check, `prepare`, `render_one` vo.txt + timeline)
- Test: `tests/test_dialogue.py`

**Interfaces:**
- Consumes: `prepare`, `render_one`, timeline scene `"dialogue"` (Task 2).
- Produces: `adslib.check_dialogue(scenes) -> None`, `adslib.dialogue_windows(timeline_scenes) -> list[(start, end, scene_id, text)]`, `adslib.vo_dialogue_clash(spans, windows, tol=0.05) -> list[(file, scene_id)]`, `adslib.timed_lines(vo_timed, windows) -> list[(t, text)]` sorted by time. `render_mix(edit, scenes_by_id, joined, total, work, warnings, windows=())`. `normalize_scene(sc, idx, W, H, fps, work, gain_db=0.0)`. Timeline JSON: scenes gain `"dialogue": text|None`; new top-level `"lines": [{"start", "text"}]` (VO + dialogue, time order). `.vo.txt` = VO + dialogue texts in time order.

- [ ] **Step 1: Write the failing tests** — create `tests/test_dialogue.py`:

```python
import json
import subprocess

import pytest

from conftest import needs_ffmpeg, run_assemble
from adslib import AdsError, check_dialogue, dialogue_windows, timed_lines, vo_dialogue_clash


def test_check_dialogue_limits():
    check_dialogue([{"id": "a", "dialogue": {"speaker": "Linh", "text": " ".join(["từ"] * 15)}}])
    with pytest.raises(AdsError, match="16 từ"):
        check_dialogue([{"id": "a", "dialogue": {"speaker": "Linh", "text": " ".join(["từ"] * 16)}}])
    with pytest.raises(AdsError, match="speaker"):
        check_dialogue([{"id": "a", "dialogue": {"text": "Chào"}}])
    with pytest.raises(AdsError, match="speaker"):
        check_dialogue([{"id": "a", "dialogue": "Chào"}])


def test_windows_and_clash():
    scenes = [{"id": "a", "start": 0, "end": 2}, {"id": "t", "start": 2, "end": 5,
                                                   "dialogue": {"speaker": "Linh", "text": "Lại trễ hạn"}}]
    w = dialogue_windows(scenes)
    assert w == [(2, 5, "t", "Lại trễ hạn")]
    assert vo_dialogue_clash([(0.3, 1.5, "vo1.wav")], w) == []
    assert vo_dialogue_clash([(0.3, 2.0, "vo1.wav")], w) == []          # chạm mép, không chồng
    assert vo_dialogue_clash([(1.0, 2.6, "vo1.wav")], w) == [("vo1.wav", "t")]


def test_timed_lines_in_time_order():
    w = [(2.0, 5.0, "t", "Lại trễ hạn")]
    assert timed_lines([(0.3, "Học trước quên sau?"), (5.2, "Đăng ký ngay"), (6.0, None)], w) == [
        (0.3, "Học trước quên sau?"), (2.0, "Lại trễ hạn"), (5.2, "Đăng ký ngay")]


def _edit(media, **over):
    e = {"aspect": "9:16", "style": "micro-drama", "output": "out/d.mp4", "scenes": [
        {"id": "hook", "file": str(media / "clip_a.mp4"), "out": 2},
        {"id": "talk", "file": str(media / "clip_b.mp4"), "out": 3,
         "dialogue": {"speaker": "Linh", "text": "Lại trượt phỏng vấn nữa rồi"}},
        {"id": "end", "file": str(media / "clip_c.mp4"), "out": 2}],
        "vo": [{"file": str(media / "vo1.wav"), "scene": "hook", "offset": 0.3, "text": "Học trước quên sau?"}],
        "music": {"file": str(media / "music.wav"), "gain_db": -14}}
    e.update(over)
    return e


def mean_db(path, t0, dur):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-ss", str(t0), "-t", str(dur), "-i", str(path),
                        "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return float(p.stderr.split("mean_volume:")[1].split("dB")[0])


@needs_ffmpeg
def test_dialogue_render_boosts_scene_and_writes_script(media, tmp_path):
    r = run_assemble(_edit(media), tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    out = tmp_path / "out"
    assert (out / "d.vo.txt").read_text(encoding="utf-8").splitlines() == [
        "Học trước quên sau?", "Lại trượt phỏng vấn nữa rồi"]
    tl = json.loads((out / "d.timeline.json").read_text(encoding="utf-8"))
    assert tl["scenes"][1]["dialogue"] == "Lại trượt phỏng vấn nữa rồi"
    assert [x["text"] for x in tl["lines"]] == ["Học trước quên sau?", "Lại trượt phỏng vấn nữa rồi"]
    # tiếng gốc cảnh thoại ở 0 dB, cảnh khác ở sfx −12 dB mặc định → cảnh thoại to hơn rõ rệt
    assert mean_db(out / "d.mp4", 2.3, 2.4) > mean_db(out / "d.mp4", 5.2, 1.6) + 6


@needs_ffmpeg
def test_vo_over_dialogue_is_rejected(media, tmp_path):
    e = _edit(media)
    e["vo"].append({"file": str(media / "vo2.wav"), "scene": "talk", "offset": 0.5, "text": "đè"})
    r = run_assemble(e, tmp_path)
    assert r.returncode != 0 and "VO TRÙNG THOẠI" in r.stderr


@needs_ffmpeg
def test_dialogue_with_sfx_off_is_rejected(media, tmp_path):
    r = run_assemble(_edit(media, sfx={"keep": False}), tmp_path, "--plan")
    assert r.returncode != 0 and "sfx.keep" in r.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_dialogue.py -q`
Expected: ERROR `ImportError: cannot import name 'check_dialogue'`.

- [ ] **Step 3: Append to `scripts/adslib.py`**

```python


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
```

- [ ] **Step 4: Modify `scripts/assemble.py`**

4a. Import line: add `check_dialogue, dialogue_windows, timed_lines, vo_dialogue_clash` to the `from adslib import (...)` list.

4b. `normalize_scene` signature and audio filter:
```python
def normalize_scene(sc, idx, W, H, fps, work, gain_db=0.0):
```
and replace the `-af` value `"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"` with
`"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo" + (f",volume={db(gain_db)}" if gain_db else "")`.

4c. `render_mix`: change signature to `def render_mix(edit, scenes_by_id, joined, total, work, warnings, windows=()):` and replace

```python
    sfx = edit.get("sfx", {"keep": True, "gain_db": -12})
    if sfx.get("keep", True):
        parts.append(f"[0:a]volume={db(sfx.get('gain_db', -12))}[sfx]")
        bed.append("[sfx]")
```
with
```python
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
```
After the existing `VO CHỒNG NHAU` loop add:
```python
    for f, sid in vo_dialogue_clash(spans, windows):
        raise SystemExit(f"VO TRÙNG THOẠI: {f} chồng lên cảnh thoại '{sid}' — dời VO sang cảnh khác "
                         "hoặc bỏ VO ở cảnh có thoại.")
```
Then replace the block from `if not bed and not vo_labels:` through the end of the `if vo_labels: … else: …` ducking block with:
```python
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
```

4d. `prepare`: after `check_style_use(...)` add:
```python
    check_dialogue(edit.get("scenes", []))
    if any(s.get("dialogue") for s in edit.get("scenes", [])) and not edit.get("sfx", {}).get("keep", True):
        raise AdsError("có cảnh thoại nhưng sfx.keep = false — thoại nằm trong tiếng gốc clip nên phải giữ sfx")
```

4e. `render_one`:
- Replace the `segs = [...]` line with:
```python
        sfx_gain = float(edit.get("sfx", {}).get("gain_db", -12))
        boost = float(edit.get("dialogue_gain_db", 0)) - sfx_gain  # cảnh thoại về đúng dialogue_gain_db
        segs = [normalize_scene(s, i, W, H, fps, work, gain_db=boost if s.get("dialogue") else 0.0)
                for i, s in enumerate(scenes)]
```
- Before `print("4/5 …")`-step call, compute `windows = dialogue_windows(scenes)`; change the mix call to `render_mix(edit, by_id, joined, total, work, warnings, windows)`.
- Replace the `timeline = {...}` scenes entry and add `lines`; replace the `vo_texts` block:
```python
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
```
- Docstring: add `  scene "dialogue": {"speaker", "text"} → thoại do model tạo (≤ 15 từ); không VO đè; "dialogue_gain_db" (mặc định 0)`.

- [ ] **Step 5: Run tests**

Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_dialogue.py -q` → all PASS.
Run: `python -m pytest -q` → all PASS (incl. `test_square_ad_with_brand_logo_and_versions`: `.vo.txt` still has the hook line and not the filtered one).

- [ ] **Step 6: Commit**

```powershell
git add scripts/adslib.py scripts/assemble.py tests/test_dialogue.py
git commit -m "feat(assemble): dialogue scenes - limits, unducked dialogue audio, VO clash guard, script lines"
```

---

### Task 4: Hook variants (A/B) — `adslib`, `assemble.py --hook`, `cutdown.py`

**Files:**
- Modify: `scripts/adslib.py` (append `HOOK_VARIANTS_MAX`, `validate_hook_variants`, `apply_hook_variant`, `variant_output`)
- Modify: `scripts/assemble.py` (`main` loop, `--hook`, timeline `hook_variant`)
- Modify: `scripts/cutdown.py` (`make_cut` validates variants; docstring)
- Test: `tests/test_hook_variants.py`

**Interfaces:**
- Consumes: `load_edit`, `prepare`, `render_one` (Tasks 2–3), `HOOK_TYPES` (Task 1).
- Produces: `adslib.validate_hook_variants(edit) -> list[dict]` (`[]` when absent), `adslib.apply_hook_variant(edit, variant) -> dict` (sets `e["hook_variant"] = {"id", "type"}`, removes `hook_variants`), `adslib.variant_output(output, vid) -> str`. Timeline JSON gains `"hook_variant": {"id", "type"} | null`. CLI: `assemble.py edit.json [--hook <id>]`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_hook_variants.py`:

```python
import copy
import json

import pytest

from conftest import master_edit, needs_ffmpeg, probe, run_assemble
import cutdown
from adslib import AdsError, apply_hook_variant, filter_version, validate_hook_variants, variant_output

VAR_A = {"id": "A", "type": "in-medias-res",
         "scenes": [{"id": "hA1", "file": "a.mp4", "out": 2, "block": "HOOK"},
                    {"id": "hA2", "file": "a.mp4", "in": 2, "out": 4.5, "block": "HOOK", "punch": 1.2,
                     "trim": {"15": {"out": 4}}}],
         "vo": [{"file": "vo_a.wav", "scene": "hA1", "offset": 0.3, "text": "Lại trễ deadline?"}],
         "overlays": [{"text": "LẠI TRỄ DEADLINE?", "scene": "hA1", "offset": 0.1, "duration": 2}]}


def with_variants(*vs):
    m = master_edit()
    m["hook_variants"] = [copy.deepcopy(v) for v in vs]
    return m


def test_apply_replaces_hook_scenes_and_their_vo():
    e = apply_hook_variant(master_edit(), VAR_A)
    assert [s["id"] for s in e["scenes"]][:3] == ["hA1", "hA2", "pain"]
    assert "hook" not in [s["id"] for s in e["scenes"]]
    assert e["vo"][0]["text"] == "Lại trễ deadline?"
    assert not any(v.get("scene") == "hook" for v in e["vo"])
    assert e["overlays"][0]["scene"] == "hA1" and len(e["overlays"]) == 2
    assert e["hook_variant"] == {"id": "A", "type": "in-medias-res"} and "hook_variants" not in e


def test_variant_output_name():
    assert variant_output("out/ts-x-9x16-60s.mp4", "B") == "out/ts-x-9x16-60s_hookB.mp4"


@pytest.mark.parametrize("bad, msg", [
    ([], "1–5"),
    ([dict(VAR_A, id=str(i)) for i in range(6)], "1–5"),
    ([dict(VAR_A, id="A/B")], "chữ/số"),
    ([dict(VAR_A, id="Bản 1")], "chữ/số"),
    ([VAR_A, VAR_A], "trùng id"),
    ([dict(VAR_A, type="clickbait")], "type"),
    ([dict(VAR_A, scenes=[])], "ít nhất 1 cảnh"),
    ([dict(VAR_A, scenes=[{"id": "x", "file": "a.mp4", "block": "VẤN ĐỀ"}], vo=[], overlays=[])], "HOOK"),
    ([dict(VAR_A, vo=[{"file": "v.wav", "scene": "pain", "offset": 0}])], "hA1, hA2"),
])
def test_validate_rejects(bad, msg):
    m = master_edit()
    m["hook_variants"] = bad
    with pytest.raises(AdsError, match=msg):
        validate_hook_variants(m)


def test_apply_needs_master_hook_and_scene_relative_times():
    m = master_edit()
    m["scenes"] = m["scenes"][1:]
    with pytest.raises(AdsError, match="HOOK"):
        apply_hook_variant(m, VAR_A)
    m = master_edit()
    m["vo"][1] = {"file": "x.wav", "at": 6.0}
    with pytest.raises(AdsError, match="'at'"):
        apply_hook_variant(m, VAR_A)


def test_cutdown_keeps_variants_and_variant_trim_applies():
    m = with_variants(VAR_A)
    e, _, _ = cutdown.make_cut(m, "15", {})
    assert e["hook_variants"] == m["hook_variants"]
    v = filter_version(apply_hook_variant(e, e["hook_variants"][0]), "15")
    assert [s["id"] for s in v["scenes"]][:2] == ["hA1", "hA2"] and v["scenes"][1]["out"] == 4


def test_cutdown_rejects_bad_variants():
    m = with_variants(dict(VAR_A, id="A/B"))
    with pytest.raises(AdsError):
        cutdown.make_cut(m, "15", {})


def _media_edit(media):
    def var(vid, typ, clip):
        return {"id": vid, "type": typ,
                "scenes": [{"id": f"h{vid}1", "file": str(media / clip), "out": 1.2, "block": "HOOK"},
                           {"id": f"h{vid}2", "file": str(media / clip), "in": 1.2, "out": 2.5,
                            "punch": 1.3, "block": "HOOK"}],
                "overlays": [{"text": f"HOOK {vid}", "scene": f"h{vid}1", "offset": 0.1, "duration": 2.0}]}
    return {"aspect": "9:16", "style": "cinematic-drama", "version": "5", "output": "out/ad-5s.mp4",
            "scenes": [{"id": "hook", "file": str(media / "clip_a.mp4"), "out": 2, "block": "HOOK"},
                       {"id": "end", "file": str(media / "clip_c.mp4"), "out": 2.5, "block": "CTA"}],
            "hook_variants": [var("A", "in-medias-res", "clip_a.mp4"), var("B", "cold-open", "clip_b.mp4")],
            "music": {"file": str(media / "music.wav"), "gain_db": -14}}


@needs_ffmpeg
def test_assemble_renders_one_file_per_variant(media, tmp_path):
    r = run_assemble(_media_edit(media), tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    for vid in ("A", "B"):
        out = tmp_path / "out" / f"ad-5s_hook{vid}.mp4"
        assert abs(probe(out)["duration"] - 5.0) < 0.15
        tl = json.loads((tmp_path / "out" / f"ad-5s_hook{vid}.timeline.json").read_text(encoding="utf-8"))
        assert tl["hook_variant"]["id"] == vid and tl["scenes"][0]["id"] == f"h{vid}1"
    assert not (tmp_path / "out" / "ad-5s.mp4").exists()


@needs_ffmpeg
def test_assemble_hook_flag_renders_only_that_variant(media, tmp_path):
    r = run_assemble(_media_edit(media), tmp_path, "--hook", "B")
    assert r.returncode == 0, r.stderr + r.stdout
    assert (tmp_path / "out" / "ad-5s_hookB.mp4").exists()
    assert not (tmp_path / "out" / "ad-5s_hookA.mp4").exists()
    r = run_assemble(_media_edit(media), tmp_path, "--hook", "Z", "--plan")
    assert r.returncode != 0 and "không có hook 'Z'" in r.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_hook_variants.py -q`
Expected: ERROR `ImportError: cannot import name 'apply_hook_variant'`.

- [ ] **Step 3: Append to `scripts/adslib.py`**

```python


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
```

- [ ] **Step 4: Modify `scripts/assemble.py`**

4a. Import: add `apply_hook_variant, validate_hook_variants, variant_output` to the `from adslib import (...)` list.

4b. Docstring: add
```
  "hook_variants": [{"id": "A", "type": "in-medias-res", "scenes": […HOOK…], "vo": […], "overlays": […]}, …]
                                   → dựng 1 file/bản hook: <output>_hookA.mp4, _hookB… (1–5 bản)
  assemble.py edit.json --hook B   → chỉ dựng bản hook B
```

4c. In `render_one` timeline dict add `"hook_variant": edit.get("hook_variant"),` after `"hook_min_shots"`.

4d. Replace the body of `main()` after `ap.add_argument("--keep-work", …)` with:
```python
    ap.add_argument("--hook", help="chỉ dựng 1 bản hook (id trong hook_variants)")
    a = ap.parse_args()
    try:
        edit = load_edit(a.edit)
        variants = validate_hook_variants(edit)
        if a.hook:
            variants = [v for v in variants if str(v["id"]) == a.hook]
            if not variants:
                raise AdsError(f"không có hook '{a.hook}' trong hook_variants")
        jobs = [apply_hook_variant(edit, v) for v in variants] or [edit]
        for job in jobs:
            if job.get("hook_variant"):
                job["output"] = variant_output(edit.get("output", "final.mp4"), job["hook_variant"]["id"])
            e, style = prepare(job)
            render_one(e, style, a)
    except AdsError as ex:
        sys.exit(f"Lỗi edit.json: {ex}")
```

- [ ] **Step 5: Modify `scripts/cutdown.py`**

- Import: add `validate_hook_variants` to the `from adslib import (...)` list.
- First line of `make_cut` body: `validate_hook_variants(edit)`.
- Docstring: add `Có "hook_variants" → giữ nguyên trong edit_30/edit_15; assemble.py dựng đủ các bản hook cho từng bản cắt.`

- [ ] **Step 6: Run tests**

Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_hook_variants.py -q` → all PASS.
Run: `python -m pytest -q` → all PASS.

- [ ] **Step 7: Commit**

```powershell
git add scripts/adslib.py scripts/assemble.py scripts/cutdown.py tests/test_hook_variants.py
git commit -m "feat: hook_variants - 1-5 A/B hooks per ad, --hook flag, cutdown passthrough"
```

---

### Task 5: Timeline facts + QC "Hook:" checks + dialogue QC

**Files:**
- Modify: `scripts/assemble.py` (new `overlay_spans`; timeline `brand_name`, `overlays`, `logo_bug`)
- Modify: `scripts/qc.py` (constants, `frame_yavg`, `shot_starts`, `audio_onset`, `hook_checks`, `dialogue_verdict`, `extract_audio`, `dialogue_checks`; wire into `cmd_final`; docstring)
- Test: `tests/test_qc_hook.py`

**Interfaces:**
- Consumes: timeline fields `style`, `hook_min_shots`, `scenes[].dialogue`, `lines` (Tasks 2–3); `script_coverage`, `norm_text`, `transcribe`, `extract_frame`, `ssim`, `detect_cuts` (existing qc).
- Produces: `assemble.overlay_spans(edit, by_id) -> list[{"start","end","text"}]`; timeline `"brand_name": str|None`, `"overlays": [...]`, `"logo_bug": [[a, b], …]`; `qc.shot_starts(tl, cuts, tol=0.2) -> list[float]`, `qc.audio_onset(src, noise_db=-40, window=3.0) -> float`, `qc.frame_yavg(img) -> float|None`, `qc.dialogue_verdict(text, segments) -> (status, detail)`, `qc.hook_checks(rep, tl, cuts, video, out_dir)`, `qc.dialogue_checks(rep, tl, video, out_dir)`. Report items named `Hook: cắt cảnh đầu`, `Hook: số shot 0–5s`, `Hook: khung hình đầu`, `Hook: chữ 0–3s`, `Hook: âm thanh mở đầu`, `Hook: thương hiệu 5s`, `Thoại cảnh <id>`, `Thoại nhân vật`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_qc_hook.py`:

```python
import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import BRAND, SCRIPTS, ff, needs_ffmpeg, run_assemble
from adslib import load_brand
import qc


def items(out_dir):
    rep = json.loads((out_dir / "qc_report.json").read_text(encoding="utf-8"))
    return {i["check"]: i["status"] for i in rep["items"]}


def run_qc(video, out_dir, *extra):
    env = dict(os.environ, QC_NO_WHISPER="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "qc.py"), "final", str(video),
                           "--out", str(out_dir), *extra],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)


def test_shot_starts_merges_timeline_and_detected_cuts():
    tl = {"scenes": [{"start": 0}, {"start": 1.2}, {"start": 3.0}]}
    assert qc.shot_starts(tl, [1.25, 4.0]) == [1.2, 3.0, 4.0]
    assert qc.shot_starts({"scenes": [{"start": 0}]}, []) == []


def seg(text):
    return [(0.0, 1.0, text)]


def test_dialogue_verdict():
    assert qc.dialogue_verdict("Lại trượt phỏng vấn nữa rồi", seg("lại trượt phỏng vấn nữa rồi"))[0] == "PASS"
    assert qc.dialogue_verdict("Ra mắt mười một tháng mười nhé", seg("Ra mắt 11/10 nhé"))[0] == "PASS"
    assert qc.dialogue_verdict("Lại trượt phỏng vấn nữa rồi", seg("hôm nay trời đẹp"))[0] == "FAIL"
    st, why = qc.dialogue_verdict("Lại trễ hạn", seg("lại trễ hạn rồi sếp ơi em xin lỗi mà"))
    assert st == "FAIL" and "thừa lời" in why


@needs_ffmpeg
def test_audio_onset(tmp_path):
    late, early = tmp_path / "late.wav", tmp_path / "early.wav"
    ff("-f", "lavfi", "-i", "aevalsrc='if(gte(t,1),0.5*sin(2*PI*440*t),0)':s=48000:d=3", late)
    ff("-f", "lavfi", "-i", "sine=f=440:d=3:sample_rate=48000", early)
    assert abs(qc.audio_onset(str(late)) - 1.0) < 0.1
    assert qc.audio_onset(str(early)) == 0.0


@pytest.fixture(scope="module")
def card(tmp_path_factory):
    import brand_cards
    d = tmp_path_factory.mktemp("hookcard")
    return brand_cards.render_card("end_card", "9:16", {"cta": "Đăng ký ngay", "link": "app.thinkingschool.vn"},
                                   load_brand(BRAND), str(d / "end.mp4"), duration=4.0)


@pytest.fixture(scope="module")
def good_ad(media, card, tmp_path_factory):
    d = tmp_path_factory.mktemp("hook_good")
    edit = {"aspect": "9:16", "version": "6", "brand": BRAND, "style": "cinematic-drama", "output": "good-6s.mp4",
            "logo_bug": {"logo": "on_dark", "corner": "tr"},
            "scenes": [{"id": "h1", "file": str(media / "clip_a.mp4"), "out": 1.2, "block": "HOOK"},
                       {"id": "h2", "file": str(media / "clip_a.mp4"), "in": 1.2, "out": 2.5, "punch": 1.3,
                        "block": "HOOK"},
                       {"id": "end", "file": card, "block": "CTA"}],
            "vo": [{"file": str(media / "vo1.wav"), "scene": "h1", "offset": 0.3, "text": "Học trước quên sau?"}],
            "overlays": [{"text": "HỌC TRƯỚC QUÊN SAU?", "style": "title", "scene": "h1", "offset": 0.1,
                          "duration": 2.2}],
            "music": {"file": str(media / "music.wav"), "gain_db": -14}}
    r = run_assemble(edit, d)
    assert r.returncode == 0, r.stderr + r.stdout
    return d, d / "good-6s.mp4"


@needs_ffmpeg
def test_timeline_has_hook_facts(good_ad):
    d, _ = good_ad
    tl = json.loads((d / "good-6s.timeline.json").read_text(encoding="utf-8"))
    assert tl["brand_name"] == load_brand(BRAND)["name"]
    assert tl["overlays"] == [{"start": 0.1, "end": 2.3, "text": "HỌC TRƯỚC QUÊN SAU?"}]
    assert tl["logo_bug"] and tl["logo_bug"][0][0] == 0.0


@needs_ffmpeg
def test_good_hook_passes(good_ad, tmp_path):
    _, video = good_ad
    r = run_qc(video, tmp_path / "qc", "--ad")
    it = items(tmp_path / "qc")
    for k in ("Hook: cắt cảnh đầu", "Hook: số shot 0–5s", "Hook: khung hình đầu", "Hook: chữ 0–3s",
              "Hook: âm thanh mở đầu", "Hook: thương hiệu 5s"):
        assert it[k] == "PASS", (k, r.stdout)


@needs_ffmpeg
def test_weak_hook_fails(media, card, tmp_path):
    static = tmp_path / "static.mp4"
    ff("-f", "lavfi", "-i", "color=c=0x335577:s=720x1280:r=24:d=5", "-f", "lavfi", "-i",
       "anullsrc=r=48000:cl=stereo", "-t", "5", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-shortest", static)
    edit = {"aspect": "9:16", "version": "8", "brand": BRAND, "style": "motion-graphics", "output": "weak.mp4",
            "scenes": [{"id": "h", "file": str(static), "out": 4, "block": "HOOK"},
                       {"id": "end", "file": card, "block": "CTA"}],
            "sfx": {"keep": False},
            "vo": [{"file": str(media / "vo1.wav"), "scene": "h", "offset": 1.0, "text": "Học trước quên sau?"}]}
    r = run_assemble(edit, tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    r = run_qc(tmp_path / "weak.mp4", tmp_path / "qc", "--ad")
    it = items(tmp_path / "qc")
    for k in ("Hook: cắt cảnh đầu", "Hook: số shot 0–5s", "Hook: khung hình đầu", "Hook: chữ 0–3s",
              "Hook: âm thanh mở đầu"):
        assert it[k] == "FAIL", (k, r.stdout)
    assert it["Hook: thương hiệu 5s"] == "WARN"
    assert r.returncode == 1


@needs_ffmpeg
def test_dialogue_qc_without_whisper_warns(good_ad, tmp_path):
    d, video = good_ad
    shutil.copy(video, tmp_path / "talk.mp4")
    tl = json.loads((d / "good-6s.timeline.json").read_text(encoding="utf-8"))
    tl["scenes"][1]["dialogue"] = "Lại trượt phỏng vấn nữa rồi"
    (tmp_path / "talk.timeline.json").write_text(json.dumps(tl, ensure_ascii=False), encoding="utf-8")
    run_qc(tmp_path / "talk.mp4", tmp_path / "qc")
    assert items(tmp_path / "qc")["Thoại nhân vật"] == "WARN"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_qc_hook.py -q`
Expected: FAIL with `AttributeError: module 'qc' has no attribute 'shot_starts'` (and KeyErrors for timeline fields).

- [ ] **Step 3: Modify `scripts/assemble.py`**

Add after `resolve_time`:
```python
def overlay_spans(edit, by_id):
    """[{start, end, text}] của overlay chữ — ghi vào timeline cho QC hook."""
    out = []
    for i, o in enumerate(edit.get("overlays", [])):
        t0 = resolve_time(o, by_id, f"overlay #{i+1}")
        t1 = t0 + float(o["duration"]) if "duration" in o else float(o["end"])
        out.append({"start": round(t0, 3), "end": round(t1, 3), "text": o["text"]})
    return out
```
In `render_one` timeline dict add (after `"lines"`):
```python
                    "brand_name": (edit.get("_brand") or {}).get("name"),
                    "overlays": overlay_spans(edit, by_id),
                    "logo_bug": [list(iv) for iv in (logo or {}).get("intervals", [])],
```

- [ ] **Step 4: Modify `scripts/qc.py`**

4a. Docstring: after the `--must-say` line add:
```
      --ad còn kiểm tra HOOK 3 GIÂY (đọc timeline): cắt cảnh đầu ≤ 2,5s, đủ số shot trong 0–5s theo phong cách,
      khung hình 0 có hình + chuyển động, có chữ trong 0–3s, có tiếng trong 0,5s, thương hiệu trong 5s (WARN).
      Cảnh có "dialogue" trong timeline: whisper nghe từng cảnh, so với câu thoại (độ khớp ≥ 0,8, không thừa lời).
```

4b. Constants after `FLAT_SPREAD = 24`:
```python
# Hook 3 giây (spec 2026-10-06-styles-hooks-design.md §6)
HOOK_FIRST_CUT_MAX = 2.5
HOOK_SHOT_WINDOW = 5.0
HOOK_TEXT_BY = 3.0
HOOK_AUDIO_BY = 0.5
HOOK_BRAND_BY = 5.0
BLACK_YAVG = 20       # khung 0 tối hơn mức này = mở bằng màn đen
STATIC_SSIM = 0.995   # khung 0 và 0,5s gần như y hệt = hình đứng yên
DIALOGUE_MIN_COVER = 0.8
DIALOGUE_MAX_RATIO = 1.5
```

4c. Add after `frame_spread`:
```python
def frame_yavg(img):
    p = run(["ffmpeg", "-hide_banner", "-i", img, "-vf", "scale=360:-2,signalstats,metadata=print",
             "-f", "null", "-"], check=False)
    m = re.search(r"YAVG=([\d.]+)", p.stderr)
    return float(m.group(1)) if m else None
```

4d. Add after `silences`:
```python
def audio_onset(src, noise_db=-40, window=3.0):
    """Giây đầu tiên có tiếng (> noise_db) trong `window` giây đầu; = window nếu im lặng suốt."""
    p = run(["ffmpeg", "-hide_banner", "-t", f"{window}", "-i", src, "-vn", "-af",
             f"silencedetect=n={noise_db}dB:d=0.05", "-f", "null", "-"], check=False)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    if not starts or starts[0] > 0.01:
        return 0.0
    return ends[0] if ends else window


def shot_starts(tl, cuts, tol=0.2):
    """Mốc bắt đầu shot (bỏ 0): ranh giới cảnh trong timeline ∪ cut phát hiện được; gộp mốc gần nhau < tol."""
    pts = sorted([float(s["start"]) for s in tl.get("scenes", [])[1:]] + [float(c) for c in cuts])
    out = []
    for p in pts:
        if p > tol and (not out or p - out[-1] >= tol):
            out.append(p)
    return out
```

4e. Add after `script_coverage`:
```python
def dialogue_verdict(text, segments):
    """(status, chi tiết) khi so thoại nghe được với câu thoại trong kịch bản."""
    target = norm_text(text).split()
    heard = norm_text(" ".join(t for _, _, t in segments)).split()
    cover = script_coverage([text], segments)[0][1] if target else 0.0
    if cover < DIALOGUE_MIN_COVER:
        return FAIL, f"{cover:.2f} — thoại sai/thiếu: nghe “{' '.join(heard)[:80]}”"
    if len(heard) > DIALOGUE_MAX_RATIO * len(target):
        return FAIL, f"thừa lời / giọng lạ: nghe {len(heard)} từ, kịch bản {len(target)} từ"
    return PASS, f"{cover:.2f} — “{text[:60]}”"


def extract_audio(src, t0, t1, out):
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
         "-i", src, "-vn", "-ac", "1", "-ar", "16000", out])
    return out
```

4f. Add after `check_format`:
```python
def _num(x, fmt):
    return format(x, fmt) if x is not None else "?"


def hook_checks(rep, tl, cuts, video, out_dir):
    starts = shot_starts(tl, cuts)
    first = starts[0] if starts else None
    rep.add(PASS if first is not None and first <= HOOK_FIRST_CUT_MAX else FAIL, "Hook: cắt cảnh đầu",
            f"cắt đầu tiên @ {first:.2f}s (cần ≤ {HOOK_FIRST_CUT_MAX}s)" if first is not None
            else "không có cắt cảnh nào")
    need = int(tl.get("hook_min_shots", 1))
    shots = 1 + sum(1 for t in starts if t < HOOK_SHOT_WINDOW)
    rep.add(PASS if shots >= need else FAIL, "Hook: số shot 0–5s",
            f"{shots} shot (phong cách {tl.get('style', 'warm-3d')} cần ≥ {need})")
    fdir = os.path.join(out_dir, "frames")
    os.makedirs(fdir, exist_ok=True)
    f0 = extract_frame(video, 0, os.path.join(fdir, "hook_0.jpg"))
    f1 = extract_frame(video, 0.5, os.path.join(fdir, "hook_05.jpg"))
    y, sc = frame_yavg(f0), ssim(f0, f1)
    ok = y is not None and y > BLACK_YAVG and sc is not None and sc < STATIC_SSIM
    rep.add(PASS if ok else FAIL, "Hook: khung hình đầu",
            f"độ sáng {_num(y, '.0f')}, SSIM 0→0,5s {_num(sc, '.3f')} "
            f"(cần sáng > {BLACK_YAVG} và có chuyển động: SSIM < {STATIC_SSIM})")
    ov = [o for o in tl.get("overlays", []) if o["start"] < HOOK_TEXT_BY]
    rep.add(PASS if ov else FAIL, "Hook: chữ 0–3s",
            f"“{ov[0]['text'][:40]}” @ {ov[0]['start']:.2f}s" if ov else "không có overlay chữ trong 3s đầu")
    on = audio_onset(video)
    rep.add(PASS if on <= HOOK_AUDIO_BY else FAIL, "Hook: âm thanh mở đầu",
            f"tiếng bắt đầu @ {on:.2f}s (cần ≤ {HOOK_AUDIO_BY}s)")
    brand = (tl.get("brand_name") or "").strip()
    logo = any(iv[0] < HOOK_BRAND_BY for iv in tl.get("logo_bug") or [])
    said = bool(brand) and any(norm_text(brand) in norm_text(x.get("text") or "")
                               for x in tl.get("lines", []) if x["start"] < HOOK_BRAND_BY)
    rep.add(PASS if logo or said else WARN, "Hook: thương hiệu 5s",
            "logo góc hiện trước 5s" if logo else (f"nhắc “{brand}” trước 5s" if said else
                                                   "chưa thấy logo/tên thương hiệu trong 5s đầu — bật logo_bug "
                                                   "hoặc nhắc tên trong VO/thoại"))


def dialogue_checks(rep, tl, video, out_dir):
    scenes = [s for s in tl.get("scenes", []) if s.get("dialogue")]
    if not scenes:
        return
    if os.environ.get("QC_NO_WHISPER"):
        rep.add(WARN, "Thoại nhân vật", "QC_NO_WHISPER → nghe thủ công từng cảnh thoại")
        return
    for s in scenes:
        wav = extract_audio(video, s["start"], s["end"], os.path.join(out_dir, f"dlg_{s['id']}.wav"))
        segs = transcribe(wav)
        if segs is None:
            rep.add(WARN, "Thoại nhân vật", "chưa cài faster-whisper → nghe thủ công từng cảnh thoại")
            return
        st, why = dialogue_verdict(s["dialogue"], segs)
        rep.add(st, f"Thoại cảnh {s['id']}", why + ("" if st == PASS else " → render lại clip này"))
```

4g. Wire into `cmd_final`:
- Before `tl_path = …` add `tl = None`.
- After the existing `if not cuts: rep.add(PASS, "Mối nối", …)` block add:
```python
    if tl is not None:
        if a.ad:
            hook_checks(rep, tl, cuts, a.video, a.out)
        dialogue_checks(rep, tl, a.video, a.out)
```

- [ ] **Step 5: Run tests**

Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_qc_hook.py -q` → all PASS.
Run: `python -m pytest -q` → all PASS (existing `test_ad_checks_pass` only asserts its own items).

- [ ] **Step 6: Commit**

```powershell
git add scripts/assemble.py scripts/qc.py tests/test_qc_hook.py
git commit -m "feat(qc): 3-second hook checks and dialogue QC from richer timeline"
```

---

### Task 6: Docs — reference 11, SKILL.md, references, templates, README

**Files:**
- Create: `references/11-styles-and-hooks.md`
- Modify: `SKILL.md`, `references/00-brief.md`, `references/01-ad-strategy.md`, `references/05-mega-prompts.md`, `references/08-assembly-and-cutdown.md`, `references/09-qc.md`, `templates/BRIEF.md`, `templates/AD_COPY.md`, `templates/edit.example.json`, `README.md`
- Modify test: `tests/test_docs.py`

**Interfaces:**
- Consumes: CLI flags `styles.py list|show|prompt`, `assemble.py --hook`, edit.json keys `style`, `punch`, `dialogue`, `dialogue_gain_db`, `hook_variants`; report item names from Task 5.

- [ ] **Step 1: Write the failing doc tests** — in `tests/test_docs.py`:
replace `test_references_numbered_00_to_10` with:
```python
def test_references_numbered_00_to_11():
    names = sorted(n for n in os.listdir(os.path.join(ROOT, "references")) if n.endswith(".md"))
    assert [n[:2] for n in names] == [f"{i:02d}" for i in range(12)]
```
and append:
```python
def test_hook_library_documents_every_hook_type():
    from adslib import HOOK_TYPES
    doc = read("references/11-styles-and-hooks.md")
    assert [h for h in HOOK_TYPES if f"`{h}`" not in doc] == []


def test_docs_mention_new_tools():
    s = read("SKILL.md")
    for needle in ("scripts/styles.py", "references/11-styles-and-hooks.md", "--hook", "hook_variants"):
        assert needle in s, needle


def test_edit_example_uses_style_variants_and_dialogue():
    from adslib import apply_hook_variant, check_dialogue, check_style_use, load_style, validate_hook_variants
    with open(os.path.join(ROOT, "templates", "edit.example.json"), encoding="utf-8-sig") as f:
        e = json.load(f)
    style = load_style(e["style"])
    variants = validate_hook_variants(e)
    assert len(variants) == 3
    for v in variants:
        job = filter_version(apply_hook_variant(e, v), e["version"])
        check_style_use(job, style)
        check_dialogue(job["scenes"])
    assert any(s.get("dialogue") for s in e["scenes"])
```
Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_docs.py -q` → Expected: FAIL (no reference 11, SKILL.md lacks needles, example lacks `style`).

- [ ] **Step 2: Create `references/11-styles-and-hooks.md`**

````markdown
# Phong cách video + Hook 3 giây

Đọc ở Giai đoạn 0 (chọn phong cách) và Giai đoạn 1 (viết 3 bản hook). Nguồn: Meta/Nielsen (47% giá trị quảng cáo video nằm ở 3s đầu), Google ABCD (Attention · Branding · Connection · Direction), TikTok Creative Center.

## 1. Chọn phong cách
```powershell
python scripts/styles.py list
python scripts/styles.py show cinematic-drama
```
| Phong cách | Khi dùng | Hook ≥ shot (0–5s) | Thoại |
|---|---|---|---|
| `warm-3d` (mặc định) | Thinking Uni, cộng đồng, người mới | 1 | không |
| `cinematic-drama` | Mini MBA, chuyên sâu, hội thảo, câu chuyện chuyển mình | 2 | có |
| `micro-drama` | Microlearning, kỹ năng văn phòng, giao tiếp | 2 | có |
| `motion-graphics` | Ưu đãi, flash sale, seminar, nhiều lợi ích | 3 | không |

Ghi `"style": "<id>"` vào `edit.json`. `assemble.py` chặn chuyển cảnh không thuộc phong cách và chặn thoại ở phong cách không cho thoại.
Người **luôn** vẽ cách điệu (stylized 3D); bối cảnh/ánh sáng có thể như thật. Không dựng học viên/giảng viên giả, không lời chứng thực giả.

## 2. Tám luật hook 3 giây
1. **Khung hình 0** có chủ thể + chuyển động. Không fade-in, không logo mở đầu, không màn đen.
2. **Cắt cảnh đầu ≤ 2,5s**; số shot trong 0–5s ≥ `hook_min_shots` của phong cách (dùng `in/out` + `"punch": 1.2–1.4` để có shot cận từ cùng clip).
3. **Ba lớp trong 0–3s:** hình mạnh + chữ hook 5–8 từ + âm thanh mở trong 0,5s (SFX hit / thoại / VO vào lúc 0,3–0,5s).
4. **Thương hiệu trong 5s:** logo góc (`logo_bug`) hoặc nhắc tên trong lời. Logo sting vẫn ở ~giây 10.
5. **Mặt người** (nhân vật) càng sớm càng tốt; nhìn vào máy hoặc phản ứng mạnh.
6. **Chữ khớp lời:** chữ hook là phiên bản ngắn của câu VO/thoại đầu.
7. **CTA vừa nói vừa hiện** (end card + câu VO CTA).
8. **Hook là module:** mặc định viết **3 bản hook** (`hook_variants`) khác loại, cùng thân quảng cáo → chạy A/B.

Đo trên nền tảng: **hook rate = lượt xem 3s ÷ lượt hiển thị** — < 20% yếu · 25–35% ổn · > 35% mạnh. Giữ bản thắng, thay bản thua bằng loại hook khác.

## 3. Thư viện 12 loại hook
| id | Khung hình đầu | Câu mở mẫu | Chữ mẫu | Rủi ro | Hợp hoạt hình |
|---|---|---|---|---|---|
| `in-medias-res` | Giữa xung đột: sếp đập tập hồ sơ xuống bàn | "Lại sai số liệu nữa à?" | LẠI SAI NỮA À? | Cần giải quyết nhanh ở block sau | ✔ |
| `cold-open` | Khoảnh khắc cao trào cuối phim (lên chức, vỗ tay) rồi cắt ngược | "Ba tháng trước, tôi suýt bỏ việc." | 3 THÁNG TRƯỚC… | Lộ kết, phải giữ tò mò "bằng cách nào" | ✔ |
| `pattern-interrupt` | Hình bất ngờ: chồng sách đổ sập, đèn vỡ thành pháo hoa | (SFX mạnh, VO 0,4s) "Khoan đã!" | KHOAN ĐÃ! | Lạc đề nếu không nối về nỗi đau | ✔ (tốt nhất cho AI) |
| `why-question` | Nhân vật nhíu mày trước vấn đề | "Vì sao học mãi vẫn quên?" | VÌ SAO HỌC MÃI VẪN QUÊN? | Tránh câu hỏi có/không | ✔ |
| `bold-claim` | Nhân vật tự tin, ánh sáng hero | "5 phút mỗi ngày là đủ." | 5 PHÚT/NGÀY | Phải có bằng chứng trong BRIEF | ✔ |
| `stop-doing` | Tay gạt bỏ thói quen sai (giấy note bay đi) | "Đừng học kiểu nhồi nhét nữa." | ĐỪNG NHỒI NHÉT | Giọng chê bai → giữ tích cực | ✔ |
| `pov-pain` | Góc nhìn thứ nhất: hộp thư 99+ email, đồng hồ 23h | "POV: 11 giờ đêm vẫn chưa xong việc." | POV: 23H VẪN CHƯA XONG | Màn hình không được có chữ đọc được | ✔ |
| `curiosity-gap` | Vật bí ẩn phát sáng trong tay nhân vật | "Thứ này thay đổi cách tôi học." | THỨ NÀY LÀ GÌ? | Phải trả lời trong block THƯƠNG HIỆU | ✔ |
| `before-after` | Chia đôi/chuyển nhanh: rối → gọn | "Trước và sau 30 ngày." | TRƯỚC → SAU | Không hứa kết quả không có nguồn | ✔ |
| `direct-address` | Người nói thẳng vào máy | "Nếu bạn là quản lý mới, nghe này." | QUẢN LÝ MỚI? | Cần người thật; AI dễ "creepy" | ✘ (chỉ quay thật) |
| `callout` | Nhân vật đúng persona trong bối cảnh nhận diện | "Dành cho ai vừa lên trưởng nhóm." | VỪA LÊN TRƯỞNG NHÓM? | Thu hẹp tệp — chỉ dùng khi target rõ | ✔ |
| `stat-shock` | Con số lớn bằng overlay (KHÔNG do AI vẽ) | "70% kiến thức quên sau 24 giờ." | 70% QUÊN SAU 24H | Bắt buộc nguồn trong BRIEF | ✔ |

## 4. Khung micro-drama (1 beat ≈ 1 clip)
| Beat | 60s | 30s | 15s |
|---|---|---|---|
| Xung đột (hook, < 3s đã thấy mâu thuẫn) | 0–5 | 0–4 | 0–4 |
| Leo thang / đáy | 5–15 | 4–9 | — |
| Phát hiện (bài học hiện tự nhiên trên điện thoại/laptop — màn hình không chữ) | 15–25 | 9–14 | 4–8 |
| Lật ngược / thắng | 25–45 | 14–22 | 8–10 |
| Ưu đãi + CTA | 45–60 | 22–30 | 10–15 |
Lật kèo phải đến từ **kỹ năng học được**, không từ may mắn. Tránh cringe: thoại đời thường, không thuyết giảng, không bôi nhọ người khác.

## 5. Ngôn ngữ máy cho AI video
- Công thức prompt: **[máy quay] + [chủ thể] + [hành động] + [bối cảnh] + [phong cách & không khí]**, đặt khối `styles.py prompt <id>` lên đầu.
- Ổn định: máy tĩnh + chủ thể chuyển động, dolly-in/out chậm, pan chậm, orbit chậm, handheld nhẹ, low-angle hero.
- Hay hỏng: whip pan / crash zoom trong clip, nhiều chuyển động chồng nhau, cận tay gõ phím, màn hình đọc được, đám đông.
- Whip / zoom giật / chớp trắng làm **lúc dựng**: `"transition": "whip" | "zoompunch" | "flash"`.
- Màu kể chuyện: trước lạnh → sau ấm (`grade_arc` của phong cách).

## 6. Nhãn AI
Video không gắn nhãn AI. Khi đăng: bật nhãn "nội dung AI" trên TikTok/Meta. Luật Trí tuệ nhân tạo 134/2025/QH15 (hiệu lực 1/3/2026) yêu cầu gắn nhãn — mẫu nhãn ⚠ cần pháp chế xác nhận.
````

- [ ] **Step 3: Edit `SKILL.md`**

- `description`: append before the final sentence: `Có nhiều phong cách (drama điện ảnh, micro-drama, hoạt hình 3D ấm, motion-graphics), hook 3 giây đo được với 3 bản hook A/B, thoại nhân vật cho phong cách drama.`
- Rule 2 becomes: `2. **Âm thanh 3 lớp:** clip video chỉ mang SFX; 1 bài nhạc cho mọi bản; 1 track VO. Prompt video không chứa MUSIC / VO / lời thoại. **Ngoại lệ duy nhất:** phong cách có thoại (\`cinematic-drama\`, \`micro-drama\`) — clip thoại theo khối DIALOGUE ở \`references/05-mega-prompts.md\` (≤ 15 từ, 1 người nói, không VO đè).`
- Giai đoạn 0: add item `5. **Phong cách:** chạy \`python scripts/styles.py list\`, gợi ý 1 phong cách theo loại sản phẩm (\`references/11-styles-and-hooks.md\`), user chọn. Mặc định \`warm-3d\`.`
- Workflow table: row 1 output → `` `SCRIPT.md` + 3 bản HOOK A/B/C + ước tính thời lượng 60/30/15 ``; row 5 output → `` `MEGA_PROMPTS.md`: khối `styles.py prompt` ở đầu, chỉ SFX (trừ clip thoại), TEXT BAN ``.
- "Đọc trước khi bắt đầu": add `references/11-styles-and-hooks.md`.
- Scripts block: add lines
```
python scripts/styles.py list
python scripts/styles.py prompt cinematic-drama
python scripts/assemble.py edit.json --hook B
```
  and in "Script chi tiết" add `scripts/styles.py`.
- Output contract: change the out line to `` `out/ts-<slug>-<9x16|16x9|1x1>-{60,30,15}s_hook{A,B,C}.mp4` (mỗi bản hook 1 file) + `.timeline.json` + `.vo.txt` `` and qc line to `` `qc_60_A/`, `qc_60_B/`… (`qc_report.md`, `boundaries.jpg`) ``.
- Operating rules: add
```
11. Hook 3 giây theo `references/11-styles-and-hooks.md`; mặc định 3 bản hook trong `hook_variants`; mục "Hook:" trong QC phải PASS.
12. Người luôn vẽ cách điệu; không học viên/giảng viên/lời chứng thực giả; nhắc user bật nhãn AI trên nền tảng khi đăng.
```

- [ ] **Step 4: Edit the other references**

`references/00-brief.md` §1 item 1 → `1. Hỏi user: link + tỷ lệ + độ dài master + nền tảng + **phong cách** (SKILL.md, Giai đoạn 0; bảng chọn ở \`references/11-styles-and-hooks.md\`).`

`references/01-ad-strategy.md`: replace the line starting `Luật hook:` with:
```
Luật hook: theo 8 luật ở `references/11-styles-and-hooks.md` (khung 0 có chuyển động, cắt cảnh đầu ≤ 2,5s, chữ + tiếng trong 3s, thương hiệu trong 5s).
**Viết 3 bản HOOK (A/B/C)** khác loại — lấy từ `hook_types` của phong cách (`python scripts/styles.py show <id>`). Ghi trong SCRIPT.md là các dòng `1A`, `1B`, `1C`; phần thân dùng chung. Phong cách drama: dựng theo khung micro-drama (mục 4 của reference 11).
```
and in §4 replace `- Shot 2–5s;` with `- Độ dài shot theo \`shot_len\` của phong cách (drama 1–4s, motion 0,8–2,5s, 3D ấm 3–10s);`.

`references/05-mega-prompts.md`: append section:
````markdown

## Bổ sung: phong cách + thoại (v2)
**Khối phong cách** — dán ngay sau GLOBAL LOCKS của mọi prompt:
```powershell
python scripts/styles.py prompt <id>
```
Style lock trong GLOBAL LOCKS thay bằng dòng `STYLE:` này (không dùng 2 mô tả look khác nhau). CAMERA của từng cảnh chọn **1** chuyển động trong `CAMERA ALLOWED`.

**Clip có thoại** (chỉ `cinematic-drama`, `micro-drama`) — thay AUDIO RULES bằng:
```
DIALOGUE: <mô tả ngoại hình ngắn, cảm xúc> says in Vietnamese, spoken aloud only: "<câu nguyên văn ≤ 15 từ>"
AUDIO RULES: only this character speaks; no other voices; no music; no narration; room tone + SFX only.
No subtitles, no captions, no on-screen text of the spoken line.
```
- 1 người nói/clip; trung cảnh hoặc cận vừa; máy tĩnh hoặc dolly-in chậm (khẩu hình rõ).
- Tên nhân vật **không** đưa vào DIALOGUE (model có thể vẽ thành chữ) — tả ngoại hình.
- Câu thoại chép y hệt vào `edit.json` → scene `"dialogue": {"speaker": "...", "text": "..."}` để QC nghe lại.
- Clip không thoại vẫn dùng AUDIO RULES cũ (No dialogue).
````

`references/08-assembly-and-cutdown.md`: append rows to the "Trường edit.json mới" table:
```
| `"style": "cinematic-drama"` | phong cách (`styles/*.json`): chặn chuyển cảnh/thoại trái luật; QC hook đọc số shot tối thiểu |
| scene `"punch": 1.3` | phóng to 1.0–1.5 lần → shot cận hơn từ cùng clip (tạo nhịp hook mà không generate thêm) |
| `"transition": "whip"` / `"zoompunch"` / `"flash"` | lia nhoè 0,2s / zoom giật 0,15s / chớp trắng 0,12s (làm lúc dựng, không bắt AI làm) |
| scene `"dialogue": {"speaker", "text"}` | cảnh thoại do model tạo (≤ 15 từ); không VO đè (`VO TRÙNG THOẠI`); `"dialogue_gain_db"` mặc định 0 |
| `"hook_variants": [...]` | 1–5 bản hook; mỗi bản `id` (chữ/số), `type`, `scenes` (block HOOK), `vo`, `overlays` gắn cảnh của chính bản đó |
```
and under "Quy trình" add:
```powershell
python scripts/assemble.py edit.json --hook B   # chỉ dựng bản hook B
```
plus a line: `Có \`hook_variants\` → mỗi bản ra 1 file \`…-60s_hookA.mp4\`, \`_hookB\`…; cutdown giữ nguyên hook_variants nên bản 30/15 cũng đủ các bản hook.` And add row to "Lỗi thường gặp": `| \`VO TRÙNG THOẠI\` | Bỏ/dời VO khỏi cảnh có thoại |`.

`references/09-qc.md`: append rows to the `--ad` table:
```
| Hook: cắt cảnh đầu | cắt cảnh đầu tiên ≤ 2,5s |
| Hook: số shot 0–5s | ≥ `hook_min_shots` của phong cách (3D ấm 1 · drama 2 · motion 3) |
| Hook: khung hình đầu | độ sáng > 20 và SSIM khung 0 ↔ 0,5s < 0,995 (có chuyển động) |
| Hook: chữ 0–3s | có overlay bắt đầu trước 3s |
| Hook: âm thanh mở đầu | có tiếng (> −40 dB) trong 0,5s |
| Hook: thương hiệu 5s | logo góc hoặc tên thương hiệu trong lời trước 5s (WARN nếu thiếu) |
| Thoại cảnh `<id>` | (không cần `--ad`) whisper khớp câu thoại ≥ 0,8 và không thừa > 1,5× số từ; FAIL → render lại clip |
```
and in "Giao hàng": `Có nhiều bản hook → QC từng file (\`--out qc_60_A\`, \`qc_60_B\`…).`

- [ ] **Step 5: Edit templates and README**

`templates/BRIEF.md` "Thông số video" table: add row `| Phong cách | warm-3d / cinematic-drama / micro-drama / motion-graphics (\`python scripts/styles.py list\`) |` and row `| Số bản hook A/B | 3 (1–5) |`.

`templates/AD_COPY.md`: "File giao" header row becomes `| Bản | Hook | File | QC |` with rows `| 60s | A/B/C | \`out/ts-<slug>-<aspect>-60s_hook{A,B,C}.mp4\` | \`qc_60_{A,B,C}/qc_report.md\` |` (same pattern for 30s, 15s); checklist add:
```
- [ ] Bật nhãn "nội dung AI" trên TikTok / Meta khi đăng (Luật AI 134/2025/QH15 — mẫu nhãn ⚠ cần pháp chế xác nhận)
- [ ] Chạy cả 3 bản hook cùng ngân sách; sau 48–72h giữ bản có hook rate (3s ÷ hiển thị) cao nhất
```

`templates/edit.example.json` — replace whole file with:
```json
{
  "_help": "Mẫu edit.json MASTER. Mọi cảnh có id + block; VO/overlay gắn scene+offset (không dùng 'at'). 'style' = phong cách (styles/*.json). 'hook_variants' = 3 bản hook A/B/C thay cho cảnh HOOK → 3 file _hookA/_hookB/_hookC. Cảnh 'pain' có thoại do model tạo nên KHÔNG có VO. Xem references/08-assembly-and-cutdown.md và references/11-styles-and-hooks.md.",
  "aspect": "9:16",
  "fps": 24,
  "version": "60",
  "style": "cinematic-drama",
  "brand": "../Muse-TS-ads/brand/brand.json",
  "output": "out/ts-mini-mba-9x16-60s.mp4",
  "logo_bug": {"logo": "on_dark", "corner": "tr", "width": 0.16, "opacity": 0.85},
  "scenes": [
    {"id": "hook", "file": "videos/c1.mp4", "in": 0, "out": 5, "block": "HOOK", "trim": {"15": {"out": 4}}},
    {"id": "pain", "file": "videos/c2.mp4", "out": 5, "block": "VẤN ĐỀ",
     "dialogue": {"speaker": "Minh", "text": "Lại bị sếp trả báo cáo nữa rồi."}},
    {"id": "logo", "file": "cards/logo.mp4", "block": "THƯƠNG HIỆU", "transition": {"type": "fade", "duration": 0.4}},
    {"id": "brand", "file": "videos/c3.mp4", "out": 8, "block": "THƯƠNG HIỆU", "trim": {"30": {"out": 6}, "15": {"out": 5}}},
    {"id": "b1", "file": "videos/c4.mp4", "out": 10, "block": "LỢI ÍCH-1", "transition": "whip"},
    {"id": "b2", "file": "videos/c5.mp4", "out": 10, "block": "LỢI ÍCH-2"},
    {"id": "b3", "file": "videos/c6.mp4", "out": 8, "block": "LỢI ÍCH-3"},
    {"id": "proof", "file": "videos/c7.mp4", "out": 5, "block": "BẰNG CHỨNG", "transition": "flash"},
    {"id": "offer", "file": "cards/price.mp4", "block": "ƯU ĐÃI"},
    {"id": "end", "file": "cards/end.mp4", "block": "CTA"}
  ],
  "hook_variants": [
    {"id": "A", "type": "in-medias-res",
     "scenes": [{"id": "hA1", "file": "videos/hA.mp4", "out": 2.2, "block": "HOOK"},
                {"id": "hA2", "file": "videos/hA.mp4", "in": 2.2, "out": 5, "punch": 1.3, "block": "HOOK", "trim": {"15": {"out": 4}}}],
     "vo": [{"file": "audio/vo_hookA.wav", "scene": "hA1", "offset": 0.4, "text": "Báo cáo thứ ba bị trả về trong tuần."}],
     "overlays": [{"text": "LẠI BỊ TRẢ BÁO CÁO?", "style": "title", "scene": "hA1", "offset": 0.1, "duration": 2.4, "y": 0.2}]},
    {"id": "B", "type": "why-question",
     "scenes": [{"id": "hB1", "file": "videos/hB.mp4", "out": 2.0, "block": "HOOK"},
                {"id": "hB2", "file": "videos/hB.mp4", "in": 2.0, "out": 5, "punch": 1.25, "block": "HOOK", "trim": {"15": {"out": 4}}}],
     "vo": [{"file": "audio/vo_hookB.wav", "scene": "hB1", "offset": 0.3, "text": "Vì sao làm chăm mà vẫn không được ghi nhận?"}],
     "overlays": [{"text": "VÌ SAO CHĂM MÀ KHÔNG ĐƯỢC GHI NHẬN?", "style": "title", "scene": "hB1", "offset": 0.1, "duration": 2.8, "y": 0.2}]},
    {"id": "C", "type": "cold-open",
     "scenes": [{"id": "hC1", "file": "videos/hC.mp4", "out": 2.0, "block": "HOOK"},
                {"id": "hC2", "file": "videos/c2.mp4", "in": 5, "out": 8, "block": "HOOK", "transition": "whip", "trim": {"15": {"out": 7}}}],
     "vo": [{"file": "audio/vo_hookC.wav", "scene": "hC1", "offset": 0.3, "text": "Ba tháng trước, tôi suýt bỏ việc."}],
     "overlays": [{"text": "3 THÁNG TRƯỚC…", "style": "title", "scene": "hC1", "offset": 0.1, "duration": 2.0, "y": 0.2}]}
  ],
  "music": {"file": "audio/music.wav", "gain_db": -8, "fade_out": 2.0},
  "sfx": {"keep": true, "gain_db": -14},
  "dialogue_gain_db": 0,
  "vo": [
    {"file": "audio/vo_hook.wav", "scene": "hook", "offset": 0.3, "text": "Làm chăm mà vẫn giậm chân tại chỗ?"},
    {"file": "audio/vo_brand.wav", "scene": "brand", "offset": 0.2, "text": "Mini MBA của Thinking School — tư duy quản trị cho người đi làm."},
    {"file": "audio/vo_b1.wav", "scene": "b1", "offset": 0.3, "text": "Học quản trị theo tình huống thật, mỗi bài năm phút."},
    {"file": "audio/vo_b2.wav", "scene": "b2", "offset": 0.2, "text": "Áp dụng ngay vào báo cáo và cuộc họp."},
    {"file": "audio/vo_b3.wav", "scene": "b3", "offset": 0.2, "text": "Có mentor đồng hành suốt lộ trình."},
    {"file": "audio/vo_offer.wav", "scene": "offer", "offset": 0.1, "text": "Ưu đãi có hạn."},
    {"file": "audio/vo_cta.wav", "scene": "end", "offset": 0.2, "versions": ["60", "30"], "text": "Đăng ký ngay hôm nay."},
    {"file": "audio/vo_cta_15.wav", "scene": "end", "offset": 0.2, "versions": ["15"], "text": "Mini MBA Thinking School, đăng ký ngay."}
  ],
  "overlays": [
    {"text": "GIẬM CHÂN TẠI CHỖ?", "style": "title", "scene": "hook", "offset": 0.1, "duration": 2.5, "y": 0.2},
    {"text": "Tình huống thật · 5 phút/bài", "style": "title", "scene": "b1", "offset": 0.6, "duration": 3, "y": 0.2},
    {"text": "Áp dụng ngay", "style": "title", "scene": "b2", "offset": 0.5, "duration": 3, "y": 0.2},
    {"text": "Mentor đồng hành", "style": "title", "scene": "b3", "offset": 0.5, "duration": 3, "y": 0.2}
  ]
}
```
(The example's facts are placeholders for format only; a real ad takes every claim from BRIEF.md.) Add that sentence to the `_help` string's end: ` Nội dung chỉ minh hoạ định dạng — quảng cáo thật lấy mọi thông tin từ BRIEF.md.`

`README.md`: add a section:
```markdown
## Phong cách + hook 3 giây (v2)
- `python scripts/styles.py list` — 4 phong cách: `warm-3d` (mặc định), `cinematic-drama`, `micro-drama`, `motion-graphics`.
- `edit.json`: `"style"`, `"hook_variants"` (3 bản A/B/C → 3 file `_hookA/B/C`), cảnh `"punch"`, `"dialogue"`, chuyển cảnh `whip` / `zoompunch` / `flash`.
- `qc.py final --ad` có thêm mục **Hook:** (cắt cảnh đầu, số shot, khung hình 0, chữ, âm thanh, thương hiệu) và kiểm tra thoại.
- Chi tiết: `references/11-styles-and-hooks.md`.
```

- [ ] **Step 6: Run doc + flag checks**

Run: `$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_docs.py -q` → all PASS.
Run: `python C:\Users\VietPC\.gemini\antigravity\brain\afc6818e-f402-4db1-b4f0-ef6f076fe4dd\scratch\check_doc_flags.py` (verifies every `--flag` in docs exists in the script CLIs) → Expected: no missing flags. If the helper does not know `styles.py`/`--hook`, run `python scripts/assemble.py -h` and `python scripts/styles.py -h` and confirm by eye.
Run: `python -m pytest -q` → all PASS.

- [ ] **Step 7: Commit**

```powershell
git add references SKILL.md templates README.md tests/test_docs.py
git commit -m "docs: styles + 3s hook reference, dialogue prompts, hook variants, QC tables"
```

---

### Task 7: End-to-end verification on real clips (no commit of media)

**Files:**
- Create (scratch, not in repo): `C:\Users\VietPC\.gemini\antigravity\brain\afc6818e-f402-4db1-b4f0-ef6f076fe4dd\scratch\e2e_v2\edit.json`

**Interfaces:**
- Consumes: everything above; media in `c:\Users\VietPC\MuseAI\Muse-TS-ads\examples\thinking-uni-launch\media\` (gitignored; `videos/c1..c6.mp4`, `audio/*.wav`, `cards/*.mp4` — list the folder first and use the real names).

- [ ] **Step 1: List media** — `Get-ChildItem -Recurse c:\Users\VietPC\MuseAI\Muse-TS-ads\examples\thinking-uni-launch\media | Select-Object FullName, Length`.

- [ ] **Step 2: Write the scratch edit** — copy `examples/thinking-uni-launch/edit.json`, then: set `"style": "cinematic-drama"`, make all file paths absolute to the media folder, set `"output"` to `out/e2e-9x16-60s.mp4`, and add `hook_variants` with 3 variants built only from existing clips (e.g. A = c1 0–2.2 + c1 2.2–5 punch 1.3; B = c3 0–2 + c1 0–3 punch 1.2; C = c6 0–2 + c1 2–5 with `"transition": "whip"`), each with one overlay at offset 0.1 and the master hook VO moved to the variant's first scene. Use only transitions in the cinematic-drama whitelist.

- [ ] **Step 3: Render** — `$env:PYTHONIOENCODING="utf-8"; python scripts/assemble.py <scratch>\edit.json` → Expected: 3 files `e2e-9x16-60s_hookA.mp4`, `_hookB`, `_hookC`, exit 0.

- [ ] **Step 4: QC each** — `python scripts/qc.py final <out>\e2e-9x16-60s_hookA.mp4 --aspect 9:16 --ad --duration 60 --script <out>\e2e-9x16-60s_hookA.vo.txt --out <scratch>\qc_A` (same for B, C). Read every `qc_report.md`. Expected: all six "Hook:" items PASS (brand may be PASS via logo bug). Any FAIL in other items must be explained (fixture clips carry burned-in v1 text; that is known) — do not claim PASS without the report.

- [ ] **Step 5: Cutdown with variants** — `python scripts/cutdown.py <scratch>\edit.json --to 15 --render` → Expected: `e2e-9x16-15s_hookA/B/C.mp4`. QC one of them with `--duration 15 --ad`.

- [ ] **Step 6: Report** measured numbers (durations, hook items, LUFS) to the user. Nothing to commit unless a defect was found; defects go back to the owning task with a failing test first.

---

## Self-Review Notes (author)

- Spec coverage: §3 styles → Tasks 1–2; §4 hook rules/library → Tasks 5–6, variants → Task 4; §5 dialogue → Tasks 3, 5, 6; §6 transitions → Task 2, timeline + QC hook → Task 5; §7 docs → Task 6; §8 tests → each task; AD_COPY AI-label → Task 6.
- Spec says dialogue QC "SKIP" without whisper; the report model has only PASS/WARN/FAIL, so it is WARN (not a failure), matching the existing VO-check behaviour.
- Spec timeline `hook_variant` "id or null" → stored as `{"id", "type"}` or null (superset, QC does not read it).
- `estimate_duration` in cutdown uses the master HOOK scenes, not each variant; variants of different length shift the estimate. Accepted: the QC duration window catches real misses.
