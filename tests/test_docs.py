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


def test_references_numbered_00_to_11():
    names = sorted(n for n in os.listdir(os.path.join(ROOT, "references")) if n.endswith(".md"))
    assert [n[:2] for n in names] == [f"{i:02d}" for i in range(12)]


def test_edit_example_cuts_cleanly():
    with open(os.path.join(ROOT, "templates", "edit.example.json"), encoding="utf-8-sig") as f:
        e = json.load(f)
    assert filter_version(e, e["version"])["scenes"]
    for v in ("30", "15"):
        assert select_blocks(e, v)["scenes"]


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

