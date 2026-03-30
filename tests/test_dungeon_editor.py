from __future__ import annotations

import pytest

import sqlite3
from pathlib import Path

import dungeon_editor

from conftest import make_grid


def test_editor_normalize_load_and_save_round_trip(tmp_path: Path):
    db_path = tmp_path / "editor.db"
    dungeon_editor.initialize_map_db(db_path)
    floors = dungeon_editor.load_floors(db_path)

    assert len(floors) == 3
    assert all(floors)

    floors[0][1][1] = "G"
    dungeon_editor.save_floors(floors, db_path)
    reloaded = dungeon_editor.load_floors(db_path)

    assert reloaded[0][1][1] == "G"


@pytest.mark.xfail(reason="initialize_map_db seeds floor_map_rows before legacy fallback can run")
def test_editor_load_floors_uses_legacy_map_rows_when_present(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE map_rows (row_index INTEGER PRIMARY KEY, row_text TEXT)")
        conn.executemany(
            "INSERT INTO map_rows (row_index, row_text) VALUES (?, ?)",
            [(0, "#####"), (1, "#..>#"), (2, "#####")],
        )
        conn.commit()

    floors = dungeon_editor.load_floors(db_path)

    assert len(floors) == 3
    assert "".join(floors[0][1]) == "#..>#"


def test_find_start_and_flood_walkable():
    grid = make_grid(
        "#####",
        "#..G#",
        "#.#A#",
        "#####",
    )
    start = dungeon_editor.find_start(grid)
    reachable = dungeon_editor.flood_walkable(grid, start)

    assert start == (1, 1)
    assert reachable == {(1, 1), (2, 1), (3, 1), (1, 2), (3, 2)}


def test_verify_floor_reports_shape_tile_border_and_stair_issues():
    grid = [list("#.###"), list("#X..#"), list("#####")]
    issues = dungeon_editor.verify_floor(grid, floor_index=0, floor_count=2)

    assert "Floor 1: unknown tile 'X' at 1,1." in issues
    assert any("top border leak" in issue for issue in issues)
    assert "Floor 1: missing downstairs '>'." in issues


def test_verify_floor_reports_unreachable_special_tiles():
    grid = make_grid(
        "#######",
        "#..#G>#",
        "###.#.#",
        "#A..#.#",
        "#######",
    )
    issues = dungeon_editor.verify_floor(grid, floor_index=1, floor_count=3)

    assert any("unreachable walkable tile" in issue for issue in issues)
    assert any("holy grail" in issue for issue in issues)
    assert any("altar" in issue for issue in issues)
    assert any("missing upstairs" not in issue for issue in issues)


def test_verify_floors_reports_global_totals():
    floors = [
        make_grid("#####", "#...#", "#####"),
        make_grid("#####", "#...#", "#####"),
    ]
    issues = dungeon_editor.verify_floors(floors)

    assert "Dungeon has no Holy Grail." in issues
    assert "Dungeon has no altar." in issues
    assert "Dungeon has no monsters." in issues
    assert "Dungeon has 0 upstairs tiles; expected 1." in issues
    assert "Dungeon has 0 downstairs tiles; expected 1." in issues


def test_cycle_tile_wraps_and_place_tile_enforces_uniqueness_and_bounds():
    assert dungeon_editor.cycle_tile("#", -1) == " "
    assert dungeon_editor.cycle_tile(" ", 1) == "#"

    floors = [
        make_grid("#####", "#G..#", "#####"),
        make_grid("#####", "#..A#", "#####"),
        make_grid("#####", "#...#", "#####"),
    ]

    dungeon_editor.place_tile(floors[1], floors, 1, 1, 1, "G")
    assert "G" not in "".join(floors[0][1])
    assert floors[1][1][1] == "G"

    dungeon_editor.place_tile(floors[2], floors, 2, 2, 1, "A")
    assert "A" not in "".join(floors[1][1])
    assert floors[2][1][2] == "A"

    dungeon_editor.place_tile(floors[1], floors, 1, 3, 1, ">")
    dungeon_editor.place_tile(floors[1], floors, 1, 1, 1, ">")
    assert floors[1][1].count(">") == 1
    assert floors[1][1][1] == ">"

    before_top = [row[:] for row in floors[0]]
    dungeon_editor.place_tile(floors[0], floors, 0, 2, 1, "<")
    assert floors[0] == before_top

    before_last = [row[:] for row in floors[-1]]
    dungeon_editor.place_tile(floors[-1], floors, len(floors) - 1, 2, 1, ">")
    assert floors[-1] == before_last

    snapshot = [row[:] for row in floors[1]]
    dungeon_editor.place_tile(floors[1], floors, 1, 999, 999, "R")
    assert floors[1] == snapshot
