import json
import os
import subprocess
import sys

from conftest import SCRIPTS, master_edit, needs_ffmpeg
import cutdown


def test_make_cut_30():
    e, est, warns = cutdown.make_cut(master_edit(), "30", {})
    assert [s["id"] for s in e["scenes"]] == ["hook", "logo", "brand", "b1", "offer", "end"]
    assert est == 29.5 and warns == []
    assert e["output"] == "out/ts-demo-9x16-30s.mp4" and e["version"] == "30"


def test_make_cut_15():
    e, est, warns = cutdown.make_cut(master_edit(), "15", {})
    assert est == 15.0 and warns == []
    assert e["output"] == "out/ts-demo-9x16-15s.mp4"


def test_make_cut_warns_when_off_target():
    m = master_edit()
    m["scenes"][3]["trim"]["15"]["out"] = 8
    _, est, warns = cutdown.make_cut(m, "15", {})
    assert est == 17.5 and warns and "±1.5" in warns[0]


def test_cli_writes_edits(tmp_path):
    p = tmp_path / "edit.json"
    p.write_text(json.dumps(master_edit(), ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "cutdown.py"), str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    e30 = json.loads((tmp_path / "edit_30.json").read_text(encoding="utf-8"))
    e15 = json.loads((tmp_path / "edit_15.json").read_text(encoding="utf-8"))
    assert e30["version"] == "30" and e15["version"] == "15"
    assert "HOOK → THƯƠNG HIỆU → LỢI ÍCH-1 → ƯU ĐÃI → CTA" in r.stdout


def test_cli_reports_error(tmp_path):
    m = master_edit()
    m["vo"][0] = {"file": "x.wav", "at": 1.0}
    p = tmp_path / "edit.json"
    p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "cutdown.py"), str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode != 0 and "'at'" in r.stderr


@needs_ffmpeg
def test_cli_probes_scene_without_out(media, tmp_path):
    edit = {"version": "60", "output": "out/x-60s.mp4", "cutdowns": {"15": ["HOOK"]},
            "scenes": [{"id": "h", "file": str(media / "clip_a.mp4"), "block": "HOOK"}]}
    p = tmp_path / "edit.json"
    p.write_text(json.dumps(edit), encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "cutdown.py"), str(p), "--to", "15"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    assert "4.00s" in r.stdout and "⚠" in r.stdout
