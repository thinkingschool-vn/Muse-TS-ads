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
