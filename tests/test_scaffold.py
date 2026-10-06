import json
import os
import py_compile
import subprocess
import sys

from conftest import SCRIPTS, needs_ffmpeg


def test_scripts_compile():
    for name in os.listdir(SCRIPTS):
        if name.endswith(".py"):
            py_compile.compile(os.path.join(SCRIPTS, name), doraise=True)


@needs_ffmpeg
def test_assemble_plan_runs(media, tmp_path):
    edit = {"aspect": "9:16", "scenes": [
        {"id": "a", "file": str(media / "clip_a.mp4"), "out": 2},
        {"id": "b", "file": str(media / "clip_b.mp4"), "out": 2}]}
    p = tmp_path / "edit.json"
    p.write_text(json.dumps(edit), encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "assemble.py"), str(p), "--plan"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    assert "TIMELINE" in r.stdout and "4.00s" in r.stdout
