from __future__ import annotations

from deadlink.core.contract import Point, ZoneSpec


def cell_order(zone: ZoneSpec) -> tuple[str, ...]:
    ordered: list[str] = []
    for row in range(zone.grid.rows):
        cols = range(zone.grid.cols)
        if row % 2 == 1:
            cols = range(zone.grid.cols - 1, -1, -1)
        for col in cols:
            ordered.append(zone.cells[_cell_index(zone, row=row, col=col)])
    return tuple(ordered)


def cell_center(zone: ZoneSpec, cell_id: str) -> Point:
    row, col = _cell_row_col(zone, cell_id)
    return Point(
        x=zone.origin.x + (col + 0.5) * zone.cell_size,
        y=zone.origin.y + (row + 0.5) * zone.cell_size,
    )


def cell_bounds(zone: ZoneSpec, cell_id: str) -> tuple[float, float, float, float]:
    row, col = _cell_row_col(zone, cell_id)
    min_x = zone.origin.x + col * zone.cell_size
    min_y = zone.origin.y + row * zone.cell_size
    return min_x, min_y, min_x + zone.cell_size, min_y + zone.cell_size


def cell_at_position(zone: ZoneSpec, position: Point) -> str | None:
    if position.x < zone.origin.x or position.y < zone.origin.y:
        return None

    col = int((position.x - zone.origin.x) / zone.cell_size)
    row = int((position.y - zone.origin.y) / zone.cell_size)
    if row < 0 or row >= zone.grid.rows or col < 0 or col >= zone.grid.cols:
        return None

    return zone.cells[_cell_index(zone, row=row, col=col)]


def _cell_row_col(zone: ZoneSpec, cell_id: str) -> tuple[int, int]:
    index = zone.cells.index(cell_id)
    return index // zone.grid.cols, index % zone.grid.cols


def _cell_index(zone: ZoneSpec, *, row: int, col: int) -> int:
    return row * zone.grid.cols + col
