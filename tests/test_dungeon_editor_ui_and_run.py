from __future__ import annotations

import sqlite3
from pathlib import Path

import dungeon_editor

from conftest import FakeStdScr, make_grid


def test_editor_load_floors_legacy_and_default_fallbacks(tmp_path: Path):
    legacy_db = tmp_path / "legacy.db"
    with sqlite3.connect(legacy_db) as conn:
        conn.execute("CREATE TABLE map_rows (row_index INTEGER PRIMARY KEY, row_text TEXT)")
        conn.executemany(
            "INSERT INTO map_rows (row_index, row_text) VALUES (?, ?)",
            [(0, "#####"), (1, "#..>#"), (2, "#####")],
        )
        conn.commit()

    legacy_floors = dungeon_editor.load_floors(legacy_db)
    assert "".join(legacy_floors[0][1]) == "#..>#"
    assert len(legacy_floors) == 3

    empty_db = tmp_path / "empty.db"
    sqlite3.connect(empty_db).close()
    default_floors = dungeon_editor.load_floors(empty_db)
    assert len(default_floors) == 3
    assert "G" in "".join(default_floors[0][15])


def test_editor_setup_colors_and_draw_helpers(monkeypatch):
    calls = []
    monkeypatch.setattr(dungeon_editor.curses, "start_color", lambda: calls.append(("start",)))
    monkeypatch.setattr(dungeon_editor.curses, "use_default_colors", lambda: calls.append(("default",)))
    monkeypatch.setattr(dungeon_editor.curses, "init_pair", lambda pair, fg, bg: calls.append((pair, fg, bg)))
    monkeypatch.setattr(dungeon_editor.curses, "color_pair", lambda value: value * 10)
    monkeypatch.setattr(dungeon_editor.curses, "A_BOLD", 1000)
    monkeypatch.setattr(dungeon_editor.curses, "A_NORMAL", 0)

    dungeon_editor.setup_colors()
    assert calls[-1] == (9, 16, 159)

    stdscr = FakeStdScr(height=60, width=120)
    grid = make_grid(
        "#####",
        "# A #",
        "#R>.#",
        "#####",
    )
    dungeon_editor.draw_grid(stdscr, grid, 1, 1, 0, 0)
    grid_calls = [args for name, args in stdscr.calls if name == "addch"]
    assert any(call[2] == "." for call in grid_calls)  # spaces render as dots
    assert any(call[2] == "A" for call in grid_calls)

    stdscr.calls.clear()
    floors = [grid, make_grid("#####", "#...#", "#####")]
    dungeon_editor.draw_sidebar(
        stdscr,
        floors,
        floor_index=0,
        selected_tile="G",
        cursor_x=1,
        cursor_y=2,
        message="placed",
        verify_messages=["Issue 1", "Issue 2"],
        saved=False,
    )
    sidebar_text = [args[2] for name, args in stdscr.calls if name == "addstr"]
    assert "Dungeon Editor" in sidebar_text
    assert any("Tile: G (holy grail)" in text for text in sidebar_text)
    assert any("placed" in text for text in sidebar_text)
    assert "Issue 1" in sidebar_text


def test_editor_verify_floor_and_totals_additional_cases():
    no_start = [list("###"), list("###")]
    assert dungeon_editor.verify_floor(no_start, 0, 1) == [
        "Floor 1: map has no walkable floor.",
        "Floor 1: no reachable starting floor tile.",
    ]

    first_floor = make_grid("#####", "#.<.#", "#####")
    last_floor = make_grid("#####", "#.>.#", "#####")
    issues_first = dungeon_editor.verify_floor(first_floor, 0, 2)
    issues_last = dungeon_editor.verify_floor(last_floor, 1, 2)
    assert "Floor 1: should not contain upstairs '<'." in issues_first
    assert "Floor 2: should not contain downstairs '>'." in issues_last

    totals = dungeon_editor.verify_floors(
        [
            make_grid("#####", "#G.G#", "#####"),
            make_grid("#####", "#A.A#", "#####"),
        ]
    )
    assert "Dungeon has 2 Holy Grails; expected 1." in totals
    assert "Dungeon has 2 altars; expected 1." in totals


def test_editor_run_and_main(monkeypatch):
    floors = [
        make_grid(
            "#####",
            "#...#",
            "#...#",
            "#####",
        ),
        make_grid(
            "#####",
            "#...#",
            "#...#",
            "#####",
        ),
    ]
    events = []
    monkeypatch.setattr(dungeon_editor, "load_floors", lambda: floors)
    monkeypatch.setattr(dungeon_editor, "setup_colors", lambda: events.append("setup"))
    monkeypatch.setattr(dungeon_editor, "draw_grid", lambda *args: None)
    monkeypatch.setattr(dungeon_editor, "draw_sidebar", lambda *args: None)
    monkeypatch.setattr(dungeon_editor, "verify_floors", lambda current: [f"floors:{len(current)}"])
    monkeypatch.setattr(dungeon_editor, "save_floors", lambda current: events.append(("save", current[0][1][1])))
    monkeypatch.setattr(dungeon_editor.curses, "curs_set", lambda _value: None)

    stdscr = FakeStdScr(
        keys=[
            dungeon_editor.curses.KEY_RIGHT,
            dungeon_editor.curses.KEY_DOWN,
            ord("4"),
            ord(" "),
            ord("."),
            ord(","),
            ord("v"),
            ord("s"),
            ord("q"),
        ]
    )

    assert dungeon_editor.run(stdscr) == 0
    assert stdscr.keypad_enabled is True
    assert floors[0][1][1] == "G"
    assert ("save", "G") in events

    wrapper_calls = []
    monkeypatch.setattr(dungeon_editor.curses, "wrapper", lambda fn: wrapper_calls.append(fn) or 9)
    assert dungeon_editor.main() == 9
    assert len(wrapper_calls) == 1
