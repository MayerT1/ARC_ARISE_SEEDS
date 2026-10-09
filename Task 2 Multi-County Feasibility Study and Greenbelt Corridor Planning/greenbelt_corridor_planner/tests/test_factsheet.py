"""FACT_SHEET.md must stay in step with the code (see section 20 of the fact sheet)."""
import re
from pathlib import Path

import yaml

import seeds_cds
from seeds_cds.network import CLASSES

ROOT = Path(__file__).resolve().parents[1]
FS = (ROOT / "FACT_SHEET.md").read_text(encoding="utf-8")
CFG = yaml.safe_load((ROOT / "config" / "seeds.yaml").read_text())
SRC = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())


def test_version_matches():
    m = re.search(r"\*\*Version (\d+\.\d+\.\d+)\*\*", FS)
    assert m, "fact sheet must state **Version x.y.z**"
    assert m.group(1) == seeds_cds.__version__ == CFG["project"]["version"]
    assert f"| {seeds_cds.__version__} |" in FS, "add a change-log row for this version"


def test_every_criterion_documented():
    missing = [k for k in CFG["criteria"] if f"`{k}`" not in FS]
    assert not missing, f"criteria missing from FACT_SHEET.md: {missing}"


def test_every_source_documented():
    ids = [s["id"] for g in ("network", "parcels") for s in SRC.get(g, [])]
    missing = [i for i in ids if f"`{i}`" not in FS]
    assert not missing, f"sources missing from FACT_SHEET.md: {missing}"


def test_classes_costs_commands_documented():
    for c in CLASSES:
        assert f"`{c}`" in FS, c
    for k in CFG["corridor"]["cost"]:
        assert k in FS, k
    main = (ROOT / "seeds_cds" / "__main__.py").read_text()
    for cmd in re.findall(r'sub\.add_parser\("(\w+)"', main):
        assert f"seeds_cds {cmd}" in FS, f"command {cmd} missing from FACT_SHEET.md"


def test_scenarios_documented():
    for s in CFG["scenarios"]:
        assert f"`{s}`" in FS, s


def test_web_assets_versioned():
    """Asset URLs carry ?v=<version> so browsers load each release without a hard refresh."""
    html = (ROOT / "docs" / "tool" / "index.html").read_text()
    for a in ("app.css", "engine.js", "app.js"):
        assert f"{a}?v={seeds_cds.__version__}" in html, a
