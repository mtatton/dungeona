#!/usr/bin/env python3
import os
import curses
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

def _get_user_db_path() -> Path:
    xdg = os.environ.get('XDG_DATA_HOME')
    if xdg:
        data_dir = Path(xdg)
    else:
        data_dir = Path.home() / '.local' / 'share'
    d = data_dir / 'dungeona'
    d.mkdir(parents=True, exist_ok=True)
    return d / 'dungeon_map.db'

# Use per-user data directory for the map DB so system-wide installs
# do not attempt to write under /usr/lib
DB_PATH = _get_user_db_path()
DEFAULT_FLOORS = [
    [
        "####################",
        "#......#....D......#",
        "#.####.#.######.##.#",
        "#.#....#......#....#",
        "#.#.#########.#.##.#",
        "#.#.......#...#..>.#",
        "#.#.#####.#.#####..#",
        "#...#...#.#.....#..#",
        "###.#.###.###.#.#..#",
        "#...#.....M...#.#..#",
        "#.#######.#####.#..#",
        "#.....#...#.....#..#",
        "#.###.#.###.#####..#",
        "#.#...#...#.....#..#",
        "#.#.#####.#.###.#..#",
        "#.#.....#.#.#S..#..#",
        "#.#####.#.#.#.###..#",
        "#.....M...#.#......#",
        "####################",
    ],
    [
        "####################",
        "#..<....#.....#....#",
        "#.#####.#.###.#.##.#",
        "#.....#.#...#.#....#",
        "#.###.#.###.#.####.#",
        "#...#.#...#.#......#",
        "###.#.###.#.######.#",
        "#...#...#.#..M.....#",
        "#.#####.#.########.#",
        "#.....#.#.....#....#",
        "#.###.#.#####.#.##.#",
        "#.#...#.....#.#.#..#",
        "#.#.#######.#.#.#>.#",
        "#.#.#.....#.#.#.##.#",
        "#...#.###.#.#.#....#",
        "###.#...#.#.#.####.#",
        "#...###.#...#......#",
        "#.....M.....D......#",
        "####################",
    ],
    [
        "####################",
        "#..<......#........#",
        "#.######.#.#.#####.#",
        "#.#....#.#.#.#.....#",
        "#.#.##.#.#.#.#.###.#",
        "#.#.##.#.#.#.#.#...#",
        "#.#....#...#.#.#.#.#",
        "#.###########.#.#..#",
        "#.......#.....#.#..#",
        "#.#####.#.#####.#..#",
        "#.#...#.#.....#.#..#",
        "#.#.#.#.#####.#.#..#",
        "#...#.#.....#.#...#.#",
        "#####.#####.#.#####.#",
        "#...#.....#.#.....#.#",
        "#.#.###.#.#.#####.#.#",
        "#.#...M.#.#.....#...#",
        "#....S....D.........#",
        "####################",
    ],
]

PASSABLE_TILES = {".", "S", "M", " ", "<", ">"}
DIRECTIONS = [(0, -1), (1, 0), (0, 1), (-1, 0)]

TILE_INFO: Dict[str, Tuple[str, int]] = {
    "#": ("wall", 1),
    ".": ("floor", 2),
    "D": ("door", 3),
    "S": ("sword", 4),
    "M": ("monster", 5),
    ">": ("stairs down", 7),
    "<": ("stairs up", 7),
    " ": ("empty", 2),
}

PALETTE_ORDER = ["#", ".", "D", "S", "M", ">", "<", " "]


def normalize_floor_rows(rows: List[str]) -> List[List[str]]:
    width = max((len(row) for row in rows), default=1)
    return [list(row.ljust(width, "#")) for row in rows]


def initialize_map_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS floor_map_rows ("
            "floor_index INTEGER NOT NULL, "
            "row_index INTEGER NOT NULL, "
            "row_text TEXT NOT NULL, "
            "PRIMARY KEY (floor_index, row_index)"
            ")"
        )
        count = conn.execute("SELECT COUNT(*) FROM floor_map_rows").fetchone()[0]
        if count == 0:
            # Check for legacy single-floor data before populating defaults
            legacy_table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='map_rows'"
            ).fetchone()
            if legacy_table:
                legacy_rows = conn.execute("SELECT row_text FROM map_rows ORDER BY row_index").fetchall()
                if legacy_rows:
                    conn.executemany(
                        "INSERT INTO floor_map_rows (floor_index, row_index, row_text) VALUES (?, ?, ?)",
                        [(0, i, r[0]) for i, r in enumerate(legacy_rows)]
                    )
                    # Also add default remaining floors if any
                    for f_idx in range(1, len(DEFAULT_FLOORS)):
                        conn.executemany(
                            "INSERT INTO floor_map_rows (floor_index, row_index, row_text) VALUES (?, ?, ?)",
                            [(f_idx, r_idx, text) for r_idx, text in enumerate(DEFAULT_FLOORS[f_idx])]
                        )
                    conn.commit()
                    return

            conn.executemany(
                "INSERT INTO floor_map_rows (floor_index, row_index, row_text) VALUES (?, ?, ?)",
                [
                    (floor_index, row_index, row_text)
                    for floor_index, floor_rows in enumerate(DEFAULT_FLOORS)
                    for row_index, row_text in enumerate(floor_rows)
                ],
            )
        conn.commit()


def load_floors(db_path: Path = DB_PATH) -> List[List[List[str]]]:
    initialize_map_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT floor_index, row_index, row_text FROM floor_map_rows ORDER BY floor_index, row_index"
        ).fetchall()
        grouped: Dict[int, List[str]] = {}
        for floor_index, _row_index, row_text in rows:
            grouped.setdefault(int(floor_index), []).append(row_text)
        if grouped:
            return [normalize_floor_rows(grouped[index]) for index in sorted(grouped)]

    return [normalize_floor_rows(rows) for rows in DEFAULT_FLOORS]


def save_floors(floors: List[List[List[str]]], db_path: Path = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS floor_map_rows ("
            "floor_index INTEGER NOT NULL, "
            "row_index INTEGER NOT NULL, "
            "row_text TEXT NOT NULL, "
            "PRIMARY KEY (floor_index, row_index)"
            ")"
        )
        conn.execute("DELETE FROM floor_map_rows")
        conn.executemany(
            "INSERT INTO floor_map_rows (floor_index, row_index, row_text) VALUES (?, ?, ?)",
            [
                (floor_index, row_index, "".join(row))
                for floor_index, floor in enumerate(floors)
                for row_index, row in enumerate(floor)
            ],
        )
        conn.commit()


def setup_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, 245, -1)
    curses.init_pair(2, 250, -1)
    curses.init_pair(3, 220, -1)
    curses.init_pair(4, 226, -1)
    curses.init_pair(5, 196, -1)
    curses.init_pair(6, 51, -1)
    curses.init_pair(7, 159, -1)
    curses.init_pair(8, 46, -1)
    curses.init_pair(9, 16, 159)


def is_inside(grid: List[List[str]], x: int, y: int) -> bool:
    return 0 <= y < len(grid) and 0 <= x < len(grid[y])


def find_start(grid: List[List[str]]) -> Optional[Tuple[int, int]]:
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell in PASSABLE_TILES:
                return x, y
    return None


def flood_walkable(grid: List[List[str]], start: Tuple[int, int]) -> set[Tuple[int, int]]:
    seen: set[Tuple[int, int]] = set()
    stack = [start]
    while stack:
        x, y = stack.pop()
        if (x, y) in seen:
            continue
        if not is_inside(grid, x, y):
            continue
        if grid[y][x] not in PASSABLE_TILES:
            continue
        seen.add((x, y))
        for dx, dy in DIRECTIONS:
            stack.append((x + dx, y + dy))
    return seen


def verify_floor(grid: List[List[str]], floor_index: int, floor_count: int) -> List[str]:
    issues: List[str] = []
    if not grid or not grid[0]:
        return [f"Floor {floor_index + 1}: map is empty."]

    width = len(grid[0])
    for y, row in enumerate(grid):
        if len(row) != width:
            issues.append(f"Floor {floor_index + 1}: row {y} width differs from the first row.")

    sword_positions: List[Tuple[int, int]] = []
    monster_positions: List[Tuple[int, int]] = []
    passable_positions: List[Tuple[int, int]] = []
    stair_up_positions: List[Tuple[int, int]] = []
    stair_down_positions: List[Tuple[int, int]] = []

    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell not in TILE_INFO:
                issues.append(f"Floor {floor_index + 1}: unknown tile '{cell}' at {x},{y}.")
            if cell == "S":
                sword_positions.append((x, y))
            elif cell == "M":
                monster_positions.append((x, y))
            elif cell == "<":
                stair_up_positions.append((x, y))
            elif cell == ">":
                stair_down_positions.append((x, y))
            if cell in PASSABLE_TILES:
                passable_positions.append((x, y))

    if not passable_positions:
        issues.append(f"Floor {floor_index + 1}: map has no walkable floor.")

    start = find_start(grid)
    if start is None:
        issues.append(f"Floor {floor_index + 1}: no reachable starting floor tile.")
        return issues

    reachable = flood_walkable(grid, start)
    unreachable = [pos for pos in passable_positions if pos not in reachable]
    if unreachable:
        issues.append(f"Floor {floor_index + 1}: has {len(unreachable)} unreachable walkable tile(s).")

    for x in range(width):
        if grid[0][x] in PASSABLE_TILES:
            issues.append(f"Floor {floor_index + 1}: top border leak at {x},0.")
        if grid[len(grid) - 1][x] in PASSABLE_TILES:
            issues.append(f"Floor {floor_index + 1}: bottom border leak at {x},{len(grid) - 1}.")
    for y in range(len(grid)):
        if grid[y][0] in PASSABLE_TILES:
            issues.append(f"Floor {floor_index + 1}: left border leak at 0,{y}.")
        if grid[y][width - 1] in PASSABLE_TILES:
            issues.append(f"Floor {floor_index + 1}: right border leak at {width - 1},{y}.")

    for x, y in sword_positions + monster_positions + stair_up_positions + stair_down_positions:
        if (x, y) not in reachable:
            tile_name = TILE_INFO[grid[y][x]][0]
            issues.append(f"Floor {floor_index + 1}: {tile_name} at {x},{y} is unreachable.")

    if floor_index == 0 and stair_up_positions:
        issues.append("Floor 1: should not contain upstairs '<'.")
    if floor_index == floor_count - 1 and stair_down_positions:
        issues.append(f"Floor {floor_count}: should not contain downstairs '>'.")
    if floor_index > 0 and not stair_up_positions:
        issues.append(f"Floor {floor_index + 1}: missing upstairs '<'.")
    if floor_index < floor_count - 1 and not stair_down_positions:
        issues.append(f"Floor {floor_index + 1}: missing downstairs '>'.")

    return issues


def verify_floors(floors: List[List[List[str]]]) -> List[str]:
    issues: List[str] = []
    sword_total = 0
    monster_total = 0
    up_total = 0
    down_total = 0

    for floor_index, grid in enumerate(floors):
        issues.extend(verify_floor(grid, floor_index, len(floors)))
        for row in grid:
            sword_total += row.count("S")
            monster_total += row.count("M")
            up_total += row.count("<")
            down_total += row.count(">")

    if sword_total == 0:
        issues.append("Dungeon has no sword.")
    elif sword_total > 1:
        issues.append(f"Dungeon has {sword_total} swords; expected 1.")

    if monster_total == 0:
        issues.append("Dungeon has no monsters.")

    expected_links = max(0, len(floors) - 1)
    if up_total != expected_links:
        issues.append(f"Dungeon has {up_total} upstairs tiles; expected {expected_links}.")
    if down_total != expected_links:
        issues.append(f"Dungeon has {down_total} downstairs tiles; expected {expected_links}.")

    return issues


def cycle_tile(current: str, step: int) -> str:
    index = PALETTE_ORDER.index(current) if current in PALETTE_ORDER else 0
    return PALETTE_ORDER[(index + step) % len(PALETTE_ORDER)]


def place_tile(grid: List[List[str]], floors: List[List[List[str]]], floor_index: int, x: int, y: int, tile: str) -> None:
    if not is_inside(grid, x, y):
        return
    if tile == "S":
        for floor in floors:
            for row in floor:
                for index, value in enumerate(row):
                    if value == "S":
                        row[index] = "."
    elif tile == ">":
        for row in grid:
            for index, value in enumerate(row):
                if value == ">":
                    row[index] = "."
    elif tile == "<":
        for row in grid:
            for index, value in enumerate(row):
                if value == "<":
                    row[index] = "."

    if tile == "<" and floor_index == 0:
        return
    if tile == ">" and floor_index == len(floors) - 1:
        return

    grid[y][x] = tile


def draw_grid(stdscr, grid: List[List[str]], cursor_x: int, cursor_y: int, top: int, left: int) -> None:
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            _name, color = TILE_INFO.get(cell, ("?", 6))
            attr = curses.color_pair(color)
            display = cell if cell != " " else "."
            if (x, y) == (cursor_x, cursor_y):
                attr = curses.color_pair(9) | curses.A_BOLD
            elif cell in {"S", "M", "D", "<", ">"}:
                attr |= curses.A_BOLD
            try:
                stdscr.addch(top + y, left + x, display, attr)
            except curses.error:
                pass


def draw_sidebar(
    stdscr,
    floors: List[List[List[str]]],
    floor_index: int,
    selected_tile: str,
    cursor_x: int,
    cursor_y: int,
    message: str,
    verify_messages: List[str],
    saved: bool,
) -> None:
    height, width = stdscr.getmaxyx()
    grid = floors[floor_index]
    sidebar_left = len(grid[0]) + 4
    lines = [
        "Dungeon Editor",
        "",
        f"DB: {DB_PATH.name}",
        f"Floor: {floor_index + 1}/{len(floors)}",
        f"Cursor: {cursor_x},{cursor_y}",
        f"Tile: {selected_tile} ({TILE_INFO.get(selected_tile, ('?', 6))[0]})",
        f"Saved: {'yes' if saved else 'no'}",
        "",
        "Palette:",
    ]
    for key in PALETTE_ORDER:
        marker = ">" if key == selected_tile else " "
        shown = key if key != " " else "."
        lines.append(f" {marker} {shown} - {TILE_INFO[key][0]}")
    lines.extend([
        "",
        "Keys:",
        " arrows move cursor",
        " , and . change floor",
        " 1 wall   2 floor",
        " 3 door   4 sword",
        " 5 monster 6 stair down",
        " 7 stair up 0 empty",
        " space/place current",
        " [ ] cycle tile",
        " v verify whole dungeon",
        " s save",
        " q quit",
        "",
        "Message:",
        message or "ready",
        "",
        "Verify:",
    ])

    if verify_messages:
        lines.extend(verify_messages[: max(1, height - len(lines) - 1)])
    else:
        lines.append("not run yet")

    for index, text in enumerate(lines[: height - 1]):
        if sidebar_left < width - 1:
            try:
                attr = curses.color_pair(6) if index == 0 else curses.A_NORMAL
                stdscr.addstr(index, sidebar_left, text[: max(0, width - sidebar_left - 1)], attr)
            except curses.error:
                pass


def run(stdscr) -> int:
    curses.curs_set(0)
    stdscr.keypad(True)
    setup_colors()

    floors = load_floors()
    floor_index = 0
    cursor_x = 0
    cursor_y = 0
    selected_tile = "#"
    message = "Loaded dungeon floors."
    verify_messages: List[str] = []
    saved = True

    while True:
        grid = floors[floor_index]
        cursor_x = min(cursor_x, len(grid[0]) - 1)
        cursor_y = min(cursor_y, len(grid) - 1)

        stdscr.erase()
        draw_grid(stdscr, grid, cursor_x, cursor_y, 0, 0)
        draw_sidebar(stdscr, floors, floor_index, selected_tile, cursor_x, cursor_y, message, verify_messages, saved)
        stdscr.refresh()

        key = stdscr.getch()
        message = ""

        if key in (ord("q"), ord("Q")):
            break
        elif key == curses.KEY_LEFT:
            cursor_x = max(0, cursor_x - 1)
        elif key == curses.KEY_RIGHT:
            cursor_x = min(len(grid[0]) - 1, cursor_x + 1)
        elif key == curses.KEY_UP:
            cursor_y = max(0, cursor_y - 1)
        elif key == curses.KEY_DOWN:
            cursor_y = min(len(grid) - 1, cursor_y + 1)
        elif key in (ord(","), ord("<")):
            floor_index = max(0, floor_index - 1)
            message = f"Switched to floor {floor_index + 1}."
        elif key in (ord("."), ord(">")):
            floor_index = min(len(floors) - 1, floor_index + 1)
            message = f"Switched to floor {floor_index + 1}."
        elif key == ord("1"):
            selected_tile = "#"
        elif key == ord("2"):
            selected_tile = "."
        elif key == ord("3"):
            selected_tile = "D"
        elif key == ord("4"):
            selected_tile = "S"
        elif key == ord("5"):
            selected_tile = "M"
        elif key == ord("6"):
            selected_tile = ">"
        elif key == ord("7"):
            selected_tile = "<"
        elif key == ord("0"):
            selected_tile = " "
        elif key == ord("["):
            selected_tile = cycle_tile(selected_tile, -1)
        elif key == ord("]"):
            selected_tile = cycle_tile(selected_tile, 1)
        elif key in (ord(" "), ord("\n"), ord("p"), ord("P")):
            if selected_tile == "<" and floor_index == 0:
                message = "Cannot place upstairs on floor 1."
            elif selected_tile == ">" and floor_index == len(floors) - 1:
                message = f"Cannot place downstairs on floor {len(floors)}."
            else:
                place_tile(grid, floors, floor_index, cursor_x, cursor_y, selected_tile)
                saved = False
                message = f"Placed {TILE_INFO[selected_tile][0]} at {cursor_x},{cursor_y} on floor {floor_index + 1}."
        elif key in (ord("v"), ord("V")):
            issues = verify_floors(floors)
            if issues:
                verify_messages = issues
                message = f"Verification found {len(issues)} issue(s)."
            else:
                verify_messages = ["Dungeon verification OK."]
                message = "Dungeon verification OK."
        elif key in (ord("s"), ord("S")):
            save_floors(floors)
            saved = True
            message = "Dungeon saved to dungeon_map.db."

    return 0


def main() -> int:
    return curses.wrapper(run)


if __name__ == "__main__":
    raise SystemExit(main())
