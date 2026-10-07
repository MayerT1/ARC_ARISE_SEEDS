from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "seeds.yaml"
DEFAULT_HUBS = ROOT / "config" / "hubs.csv"


@dataclass
class Hub:
    id: str
    name: str
    type: str  # park | gateway
    state: str
    lat: float
    lon: float
    note: str = ""


@dataclass
class Config:
    raw: dict
    hubs: list[Hub] = field(default_factory=list)
    path: Path = DEFAULT_CONFIG

    # convenience accessors -------------------------------------------------
    @property
    def counties(self) -> dict[str, tuple[str, str, str]]:
        return {k: tuple(v) for k, v in self.raw["counties"].items()}

    @property
    def criteria(self) -> dict[str, dict]:
        return self.raw["criteria"]

    @property
    def scenarios(self) -> dict[str, dict]:
        return self.raw["scenarios"]

    @property
    def gee(self) -> dict:
        return self.raw["gee"]

    @property
    def grid(self) -> dict:
        return self.raw["grid"]

    @property
    def corridor(self) -> dict:
        return self.raw["corridor"]

    @property
    def ai(self) -> dict:
        return self.raw["ai"]

    def arc_need(self, status: str) -> float:
        return float(self.raw["arc_need_score"].get(status, 0.0))

    def hubs_of(self, kind: str) -> list[Hub]:
        return [h for h in self.hubs if h.type == kind]


def load_hubs(path: str | Path = DEFAULT_HUBS) -> list[Hub]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [
            Hub(r["id"], r["name"], r["type"], r["state"], float(r["lat"]), float(r["lon"]), r.get("note", ""))
            for r in csv.DictReader(fh)
        ]


def load_config(path: str | Path = DEFAULT_CONFIG, hubs: str | Path = DEFAULT_HUBS) -> Config:
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Config(raw=raw, hubs=load_hubs(hubs), path=path)
