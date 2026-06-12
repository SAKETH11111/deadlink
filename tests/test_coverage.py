from __future__ import annotations

from deadlink.core.contract import GridSpec, Point, ZoneSpec
from deadlink.core.coverage import cell_bounds, cell_center, cell_order


def test_boustrophedon_order_is_serpentine_and_deterministic() -> None:
    zone = ZoneSpec(
        id="zone-a",
        display_name="Zone A",
        origin=Point(x=10.0, y=20.0),
        cell_size=2.0,
        grid=GridSpec(cols=3, rows=2),
        cells=["a1", "a2", "a3", "a4", "a5", "a6"],
    )

    assert cell_order(zone) == ("a1", "a2", "a3", "a6", "a5", "a4")


def test_cell_centers_land_inside_half_open_bounds() -> None:
    zone = ZoneSpec(
        id="zone-a",
        display_name="Zone A",
        origin=Point(x=0.0, y=0.0),
        cell_size=1.0,
        grid=GridSpec(cols=3, rows=2),
        cells=["a1", "a2", "a3", "a4", "a5", "a6"],
    )

    for cell_id in zone.cells:
        center = cell_center(zone, cell_id)
        min_x, min_y, max_x, max_y = cell_bounds(zone, cell_id)

        assert min_x <= center.x < max_x
        assert min_y <= center.y < max_y
