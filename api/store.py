"""Process-level cache of the master table, area files, and model.

Loaded once per (path, mtime) fingerprint. A new snapshot or a retrain changes the
mtime and the next request loads again. Resident addresses are never written here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import pandas as pd

from lll import MODEL_DIR, PROCESSED_DIR
from lll.features import AREA_LEVELS, latest_master
from lll.geocode import normalize_address
from lll.train import FEATURES

LINE_COLUMNS: tuple[str, ...] = tuple(dict.fromkeys((
    "line_id", "address", "address_norm", "utility_side_material", "customer_side_material",
    "line_status", "verification_method", "replaced", "replacement_date", "snapshot_date",
    "block", "block_group", "tract", "ward", "community_area",
    *FEATURES,
)))


@dataclass
class Store:
    snapshot: str
    lines: pd.DataFrame
    areas: dict[str, pd.DataFrame] = field(default_factory=dict)
    model: dict | None = None

    def lookup(self, address: str) -> pd.DataFrame:
        """Rows whose normalized address matches; empty if none."""
        norm = normalize_address(address)
        if not norm or "address_norm" not in self.lines.columns:
            return self.lines.iloc[0:0]
        hit = self.lines["address_norm"].astype("string") == norm
        return self.lines.loc[hit]

    def area(self, level: str, area_id: str) -> pd.Series | None:
        table = self.areas.get(level)
        if table is None or level not in table.columns:
            return None
        key = str(area_id)
        rows = table[table[level].astype(str) == key]
        if rows.empty:
            return None
        return rows.iloc[0]


def _fingerprint() -> tuple[tuple[str, int], ...]:
    paths = list(sorted(PROCESSED_DIR.glob("master_chicago_*.parquet"))[-1:])
    paths += [MODEL_DIR / "lll_lightgbm_v1.pkl", MODEL_DIR / "calibrator_v1.pkl"]
    paths += sorted(PROCESSED_DIR.glob("equity_chicago_*/*.csv"))
    paths += sorted(PROCESSED_DIR.glob("areas_*_chicago_*.parquet"))
    out = []
    for p in paths:
        try:
            out.append((str(p), p.stat().st_mtime_ns))
        except FileNotFoundError:
            out.append((str(p), 0))
    return tuple(out)


def _read_areas(snap: str) -> dict[str, pd.DataFrame]:
    areas: dict[str, pd.DataFrame] = {}
    eq = PROCESSED_DIR / f"equity_chicago_{snap}"
    for level, name in (("ward", "ward.csv"), ("tract", "tract.csv")):
        p = eq / name
        if p.exists():
            areas[level] = pd.read_csv(p, dtype={level: str})
    for level in AREA_LEVELS:
        if level in areas:
            continue
        p = PROCESSED_DIR / f"areas_{level}_chicago_{snap}.parquet"
        if p.exists():
            areas[level] = pd.read_parquet(p)
            if level in areas[level].columns:
                areas[level][level] = areas[level][level].astype(str)
    return areas


@lru_cache(maxsize=2)
def _load(fp: tuple[tuple[str, int], ...]) -> Store:
    from lll.predict import load_model

    master, snap = latest_master()
    cols = [c for c in LINE_COLUMNS if c in master.columns]
    lines = master[cols].copy()
    if "address_norm" in lines.columns:
        lines["address_norm"] = lines["address_norm"].astype("string")
    model = None
    try:
        model = load_model()
    except FileNotFoundError:
        model = None
    return Store(snapshot=snap, lines=lines, areas=_read_areas(snap), model=model)


def get() -> Store:
    """Cached store for the current files on disk; raises FileNotFoundError if none."""
    return _load(_fingerprint())


def reset() -> None:
    _load.cache_clear()
    from lll.predict import _load_model_cached

    _load_model_cached.cache_clear()
