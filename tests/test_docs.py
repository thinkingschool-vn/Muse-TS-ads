import json
import os
import re

from conftest import ROOT
from adslib import filter_version, select_blocks


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def test_skill_frontmatter():
    s = read("SKILL.md")
    assert s.startswith("---\nname:")
    assert "description:" in s.split("---")[1]


def test_skill_paths_exist():
    s = read("SKILL.md")
    paths = set(re.findall(r"`((?:references|templates|scripts|brand)/[^`\s]+)`", s))
    assert len(paths) >= 15
    assert [p for p in paths if not os.path.exists(os.path.join(ROOT, p))] == []


def test_references_numbered_00_to_10():
    names = sorted(n for n in os.listdir(os.path.join(ROOT, "references")) if n.endswith(".md"))
    assert [n[:2] for n in names] == [f"{i:02d}" for i in range(11)]


def test_edit_example_cuts_cleanly():
    with open(os.path.join(ROOT, "templates", "edit.example.json"), encoding="utf-8-sig") as f:
        e = json.load(f)
    assert filter_version(e, e["version"])["scenes"]
    for v in ("30", "15"):
        assert select_blocks(e, v)["scenes"]
