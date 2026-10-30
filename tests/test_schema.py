from lll.schema import CANONICAL_COLUMNS, MATERIALS, REQUIRED_COLUMNS


def test_material_vocabulary():
    assert MATERIALS == ("Lead", "GRR", "Non-Lead", "Unknown")


def test_required_columns_are_canonical():
    assert set(REQUIRED_COLUMNS) <= set(CANONICAL_COLUMNS)
