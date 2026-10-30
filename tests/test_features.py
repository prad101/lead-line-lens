from lll.features import AREA_LEVELS


def test_area_levels():
    assert {"block", "tract", "ward", "community_area"} <= set(AREA_LEVELS)
