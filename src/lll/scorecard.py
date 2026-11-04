"""One-page ward scorecards rendered with Jinja2 and WeasyPrint.

Scorecards rank need for verification and replacement, never the reverse: rank 1 is
the ward with the largest share of lines that are lead, galvanized, or unknown.

    python -m lll.scorecard              # all 50 wards
    python -m lll.scorecard --ward 12    # one ward

Output goes to data/processed/scorecards_chicago_<snapshot>/.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import io
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from lll import METHODOLOGY_URL, PROCESSED_DIR, TEMPLATE_DIR
from lll.equity import NEEDS_ACTION, SUPPRESSION_MIN

MASTER_COLUMNS = ["ward", "line_status", "address_norm", "latitude", "longitude", "replaced",
                  "snapshot_date"]
TOP_BLOCKS = 8
MODEL_PENDING = "Pending model v1"

SOURCES = {
    "inventory": "Chicago Department of Water Management service line inventory submitted to "
                 "Illinois EPA (copy obtained by FOIA and published by Inside Climate News, "
                 "Grist, and WBEZ)",
    "acs": "U.S. Census Bureau, American Community Survey 2020-2024 5-year estimates",
}
LINKS = {
    "test_kit": "https://www.chicagowaterquality.org/",
    "city_lookup": "https://sli.chicagowaterquality.org/",
    "equity_program": "https://www.leadsafechicago.org/equity-lead-service-line-replacement-program",
    "epa_lead": "https://www.epa.gov/ground-water-and-drinking-water/"
                "basic-information-about-lead-drinking-water",
}


def _street_title(street: str) -> str:
    return " ".join(t.lower() if t[:1].isdigit() else t.capitalize() for t in street.split())


def hundred_blocks(lines: pd.DataFrame, top: int = TOP_BLOCKS) -> list[dict]:
    """Hundred-blocks with the most lines to act on; blocks under 5 lines are left out."""
    parts = lines["address_norm"].astype("string").str.extract(r"^(\d+) (.+)$")
    df = pd.DataFrame({
        "num": pd.to_numeric(parts[0], errors="coerce"),
        "street": parts[1],
        "status": lines["line_status"].astype(str),
    }).dropna(subset=["num", "street"])
    df["block"] = (df["num"] // 100 * 100).astype(int).astype(str) + " " + df["street"]
    g = df.groupby("block")
    t = pd.DataFrame({
        "lines": g.size(),
        "needs": df["status"].isin(NEEDS_ACTION).groupby(df["block"]).sum(),
        "lead": df["status"].isin(("Lead", "GRR")).groupby(df["block"]).sum(),
        "unknown": df["status"].eq("Unknown").groupby(df["block"]).sum(),
    })
    t = t[t["lines"] >= SUPPRESSION_MIN].sort_values(["needs", "lines"], ascending=False).head(top)
    out = []
    for block, r in t.iterrows():
        num, street = block.split(" ", 1)
        out.append({"label": f"{num} block of {_street_title(street)}", "lines": int(r.lines),
                    "needs": int(r.needs), "lead": int(r.lead), "unknown": int(r.unknown)})
    return out


def ward_map_png(lines: pd.DataFrame, ward_geom) -> str:
    """Hexbin map of the share of lines needing action; hexes under 5 lines stay blank."""
    import geopandas as gpd
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from lll.features import METRIC_CRS

    pts = lines.dropna(subset=["latitude", "longitude"])
    g = gpd.GeoSeries(gpd.points_from_xy(pts["longitude"], pts["latitude"]), crs="EPSG:4326")
    g = g.to_crs(METRIC_CRS)
    boundary = gpd.GeoSeries([ward_geom], crs="EPSG:4326").to_crs(METRIC_CRS)
    needs = pts["line_status"].isin(NEEDS_ACTION).astype(float).to_numpy()
    fig, ax = plt.subplots(figsize=(3.6, 3.6), dpi=150)
    minx, miny, maxx, maxy = boundary.total_bounds
    span = max(maxx - minx, maxy - miny)
    hb = ax.hexbin(g.x, g.y, C=needs, reduce_C_function=np.mean, mincnt=SUPPRESSION_MIN,
                   gridsize=max(8, int(span / 150)), cmap="YlOrRd", vmin=0, vmax=1,
                   linewidths=0.1, extent=(minx, maxx, miny, maxy))
    boundary.boundary.plot(ax=ax, color="#333333", linewidth=0.8)
    ax.set_axis_off()
    ax.set_aspect("equal")
    cb = fig.colorbar(hb, ax=ax, shrink=0.7, pad=0.02)
    cb.ax.tick_params(labelsize=6)
    cb.set_ticks([0, 0.5, 1])
    cb.set_ticklabels(["0%", "50%", "100%"])
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _fmt_int(v) -> str:
    return "n/a" if v is None or pd.isna(v) else f"{int(v):,}"


def _fmt_pct(v) -> str:
    return "n/a" if v is None or pd.isna(v) else f"{v:.0%}"


def ward_context(
    ward: int,
    ward_table: pd.DataFrame,
    master: pd.DataFrame,
    wards_geo,
    snapshot: str,
) -> dict:
    """Template context for one ward. ward_table is the disparity report's ward table."""
    w = str(int(ward))
    row = ward_table.assign(ward=ward_table["ward"].astype(str)).set_index("ward").loc[w]
    lines = master[master["ward"].astype(str) == w]
    city = master[master["ward"].notna()]
    city_share = city["line_status"].isin(NEEDS_ACTION).mean()
    suppressed = bool(row.get("suppressed", False))
    geom = wards_geo.assign(ward=wards_geo["ward"].astype(str)).set_index("ward").loc[w, "geometry"]
    pred = row.get("pred_lead_share_unknown")
    snap = pd.Timestamp(snapshot)
    statuses = [
        ("Lead", "n_lead", "share_lead", "Confirmed lead"),
        ("GRR", "n_grr", "share_grr", "Galvanized, must be replaced"),
        ("Unknown", "n_unknown", "share_unknown", "Unknown: possibly lead until checked"),
        ("Non-Lead", "n_nonlead", "share_nonlead", "Not lead"),
    ]
    return {
        "ward": w,
        "snapshot": f"{snap:%B} {snap.day}, {snap.year}",
        "generated": dt.date.today().isoformat(),
        "suppressed": suppressed,
        "total_lines": _fmt_int(row.get("total_lines")),
        "statuses": [{"key": k, "label": label, "n": _fmt_int(row.get(n)),
                      "share": _fmt_pct(row.get(s))} for k, n, s, label in statuses],
        "needs_n": _fmt_int(row.get("n_needs_action")),
        "needs_share": _fmt_pct(row.get("share_needs_action")),
        "needs_in_ten": (None if pd.isna(row.get("share_needs_action"))
                         else round(float(row["share_needs_action"]) * 10)),
        "city_share": _fmt_pct(city_share),
        "rank": _fmt_int(row.get("rank_needs_action")),
        "wards": int(ward_table["ward"].nunique()),
        "replaced": _fmt_int(row.get("n_replaced")),
        "prediction": MODEL_PENDING if pred is None or pd.isna(pred) else _fmt_pct(pred),
        "income": (None if pd.isna(row.get("median_income", np.nan))
                   else f"${row['median_income']:,.0f}"),
        "kids_under6": (None if pd.isna(row.get("kids_under6", np.nan))
                        else _fmt_int(row["kids_under6"])),
        "pre1950": (None if pd.isna(row.get("pct_housing_pre1950", np.nan))
                    else _fmt_pct(row["pct_housing_pre1950"])),
        "blocks": [] if suppressed else hundred_blocks(lines),
        "map_png": None if suppressed or lines.empty else ward_map_png(lines, geom),
        "sources": SOURCES,
        "links": LINKS,
        "methodology_url": METHODOLOGY_URL,
        "suppression_min": SUPPRESSION_MIN,
    }


def render_html(context: dict) -> str:
    """Render templates/scorecard.html."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)),
                      autoescape=select_autoescape(["html"]))
    return env.get_template("scorecard.html").render(**context)


def render_pdf(context: dict) -> bytes:
    """Render one scorecard to PDF bytes."""
    from weasyprint import HTML

    return HTML(string=render_html(context), base_url=str(TEMPLATE_DIR)).write_pdf()


@lru_cache(maxsize=1)
def load_inputs(processed_dir: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, object, str]:
    """(ward table, master subset, ward polygons, snapshot) for scorecards."""
    from lll import sources
    from lll.features import latest_master

    pdir = Path(processed_dir) if processed_dir else PROCESSED_DIR
    master, snap = latest_master(pdir, columns=MASTER_COLUMNS)
    ward_csv = pdir / f"equity_chicago_{snap}" / "ward.csv"
    if not ward_csv.exists():
        raise FileNotFoundError(f"{ward_csv} missing; run scripts/build_equity.py first.")
    ward_table = pd.read_csv(ward_csv, dtype={"ward": str})
    snapshot = str(pd.to_datetime(master["snapshot_date"]).max().date())
    return ward_table, master, sources.wards(), snapshot


def ward_pdf(ward: int) -> bytes:
    ward_table, master, wards_geo, snapshot = load_inputs()
    return render_pdf(ward_context(ward, ward_table, master, wards_geo, snapshot))


def generate_all(out_dir: str | Path | None = None) -> list[Path]:
    """Write all ward scorecard PDFs; returns their paths."""
    ward_table, master, wards_geo, snapshot = load_inputs()
    out = Path(out_dir) if out_dir else (
        PROCESSED_DIR / f"scorecards_chicago_{snapshot.replace('-', '')}")
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for w in sorted(ward_table["ward"].astype(int)):
        p = out / f"ward_{w:02d}.pdf"
        p.write_bytes(render_pdf(ward_context(w, ward_table, master, wards_geo, snapshot)))
        paths.append(p)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description="Render ward scorecard PDFs.")
    ap.add_argument("--ward", type=int, help="render one ward only")
    ap.add_argument("--out", type=Path, help="output directory")
    args = ap.parse_args()
    if args.ward:
        out = args.out or Path(".")
        out.mkdir(parents=True, exist_ok=True)
        p = out / f"ward_{args.ward:02d}.pdf"
        p.write_bytes(ward_pdf(args.ward))
        print(p)
        return
    paths = generate_all(args.out)
    print(f"{len(paths)} scorecards -> {paths[0].parent}")


if __name__ == "__main__":
    main()
