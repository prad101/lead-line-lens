import pandas as pd
import pandera.errors
import pytest

from lll.ingest import (
    IEPA_TEMPLATE_COLUMNS,
    map_columns,
    parse_diameter,
    read_iepa_template,
    read_il_epa_summary,
    suggest_mapping,
)
from lll.schema import (
    CANONICAL_COLUMNS,
    MATERIALS,
    REQUIRED_COLUMNS,
    normalize_material,
    unrecognized_materials,
    validate_inventory,
)


def test_material_vocabulary():
    assert MATERIALS == ("Lead", "GRR", "Non-Lead", "Unknown")


def test_required_columns_are_canonical():
    assert set(REQUIRED_COLUMNS) <= set(CANONICAL_COLUMNS)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Lead", "Lead"),
        ("LEAD", "Lead"),
        ("L", "Lead"),
        ("Galvanized Requiring Replacement", "GRR"),
        ("GRR", "GRR"),
        ("Galvanized", "GRR"),
        ("Non-Lead", "Non-Lead"),
        ("Non Lead", "Non-Lead"),
        ("Copper", "Non-Lead"),
        ("PVC", "Non-Lead"),
        ("Cast Iron", "Non-Lead"),
        ("Ductile Iron", "Non-Lead"),
        ("Copper with lead solder", "Non-Lead"),
        ("Unknown - Not Lead", "Non-Lead"),
        ("G", "GRR"),
        ("C", "Non-Lead"),
        ("UNL", "Non-Lead"),
        ("U", "Unknown"),
        ("Lead Status Unknown", "Unknown"),
        ("Unknown", "Unknown"),
        ("", "Unknown"),
        (None, "Unknown"),
        (float("nan"), "Unknown"),
    ],
)
def test_normalize_material(raw, expected):
    assert normalize_material(raw) == expected


def test_unrecognized_is_unknown_unless_strict():
    assert normalize_material("wood") == "Unknown"
    with pytest.raises(ValueError):
        normalize_material("wood", strict=True)
    assert unrecognized_materials(pd.Series(["Lead", "wood", "Copper"])) == ["wood"]


@pytest.mark.parametrize(
    "raw,expected",
    [("1", 1.0), ("0.75", 0.75), ("3/4", 0.75), ("1-1/2", 1.5), ('1"', 1.0), ("2 inch", 2.0)],
)
def test_parse_diameter(raw, expected):
    assert parse_diameter(raw) == pytest.approx(expected)


def _raw_inventory():
    return pd.DataFrame(
        {
            "Service Address": ["123 N MAIN ST", "456 W ELM AVE", "789 S OAK BLVD"],
            "Public Side Material": ["Lead", "Copper", "Unknown"],
            "Private Side Material": ["Galvanized", "Non-Lead", ""],
            "Year Built": ["1924", "1990", None],
            "Pipe Size": ["3/4", "1", None],
        }
    )


def test_suggest_mapping_and_map_columns_validate():
    raw = _raw_inventory()
    mapping = suggest_mapping(list(raw.columns))
    assert mapping == {
        "Service Address": "address",
        "Public Side Material": "utility_side_material",
        "Private Side Material": "customer_side_material",
        "Year Built": "year_built",
        "Pipe Size": "diameter_in",
    }
    out = validate_inventory(map_columns(raw, mapping, snapshot_date="2025-04-15"))
    assert list(out["customer_side_material"]) == ["GRR", "Non-Lead", "Unknown"]
    assert out["line_id"].is_unique
    assert out["year_built"].iloc[0] == 1924
    assert out["diameter_in"].iloc[0] == pytest.approx(0.75)


def test_validation_rejects_bad_material_and_year():
    raw = _raw_inventory()
    out = map_columns(raw, suggest_mapping(list(raw.columns)), snapshot_date="2025-04-15")
    out.loc[0, "customer_side_material"] = "Wood"
    out.loc[1, "year_built"] = 1700
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_inventory(out)


def test_validation_requires_key_columns():
    with pytest.raises(ValueError):
        validate_inventory(pd.DataFrame({"line_id": ["a"]}))


def test_read_il_epa_summary(tmp_path):
    p = tmp_path / "il.csv"
    p.write_text(
        '\ufeff"FacilityId","County","FacilityName","ReportedDate","ReportingYear",'
        '"TotalServiceConnections","WholesaleConnections","RetailConnections","ServicesLead",'
        '"ServicesUnknownMaterial","ServicesCopperLeadSolder","ServicesGalvanized",'
        '"ServicesUnknownNotLead","ServicesCopperNonLeadSolder",'
        '"ServicesCastDuctileIronTransite","ServicesPlastic"\n'
        '"IL0000001","Cook","Test (PWS)","4/21/2025 3:56:39 PM","2024","200","0","200",'
        '"50","100","0","0","0","50","0","0"\n',
        encoding="utf-8",
    )
    df = read_il_epa_summary(p)
    assert df.loc[0, "FacilityId"] == "IL0000001"
    assert df.loc[0, "unknown_share"] == pytest.approx(0.5)
    assert df.loc[0, "lead_share"] == pytest.approx(0.25)
    assert df.loc[0, "ReportedDate"].year == 2025


def test_read_iepa_template(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Water System Name", "TEST CITY"])
    ws.append(["System ID", "IL0000001"])
    ws.append(["Inventory Date", "2025-04-14"])
    ws.append(["Total Service lines", 2])
    ws.append(["Service Address", *["x"] * (len(IEPA_TEMPLATE_COLUMNS) - 1)])
    ws.append(["FullAddress", *["example"] * (len(IEPA_TEMPLATE_COLUMNS) - 1)])
    blank = [None] * len(IEPA_TEMPLATE_COLUMNS)
    cols = list(IEPA_TEMPLATE_COLUMNS)
    for addr, pws, cust, overall, replaced in (
        ("1 N MAIN ST", "L", "U", "L", "N"),
        ("2 N MAIN ST", "C", "C", "NL", "Y"),
    ):
        row = blank.copy()
        row[0] = addr
        row[cols.index("pws_material")] = pws
        row[cols.index("customer_material")] = cust
        row[cols.index("overall_class")] = overall
        row[cols.index("prev_lead_replaced")] = replaced
        ws.append(row)
    path = tmp_path / "inv.xlsx"
    wb.save(path)

    df, meta = read_iepa_template(path)
    assert meta["system_id"] == "IL0000001"
    assert meta["snapshot_date"] == pd.Timestamp("2025-04-14")
    assert list(df["line_id"]) == ["IL0000001-000001", "IL0000001-000002"]
    assert list(df["utility_side_material"]) == ["Lead", "Non-Lead"]
    assert list(df["customer_side_material"]) == ["Unknown", "Non-Lead"]
    assert list(df["reported_line_class"]) == ["Lead", "Non-Lead"]
    assert list(df["prev_lead_replaced"]) == [False, True]
    validate_inventory(df)
