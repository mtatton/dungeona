import curses
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

DB_PATH = Path(__file__).with_name("dungeon_map.db")
DEFAULT_MAP_DATA = [
    "####################",
    "#..D.....#........##",
    "#..#.###.#.######..#",
    "#..#...#.#......#..#",
    "#..###.#.####.#.#..#",
    "#...S..#....#.#.#..#",
    "#.######.##.#.#.#..#",
    "#.#..M.#....#...#..#",
    "#.#.##.##########..#",
    "#...##......D...M..#",
    "###.######.#########",
    "#......#...........#",
    "#.####.#.#####M###.#",
    "#.#....#.....#.....#",
    "#.#.########.#.###.#",
    "#.#......M...#...#.#",
    "#.#############.#..#",
    "#..................#",
    "####################",
]

PASSABLE_TILES = {".", "S", "M", " "}
DIRECTIONS = [(0, -1), (1, 0), (0, 1), (-1, 0)]

TILE_INFO = {
    "#": ("wall", 1),
    ".": ("floor", 2),
    "D": ("door", 3),
    "S": ("sword", 4),
    "M": ("monster", 5),
    " ": ("empty", 2),
}

PALETTE_ORDER = ["#", ".", "D", "S", "M", " "]


def initialize_map_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS map_rows ("
            "row_index INTEGER PRIMARY KEY, "
            "row_text TEXT NOT NULL"
            ")"
        )
        count = conn.execute("SELECT COUNT(*) FROM map_rows").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO map_rows (row_index, row_text) VALUES (?, ?)",
                list(enumerate(DEFAULT_MAP_DATA)),
            )
        conn.commit()


def load_map(db_path: Path = DB_PATH) -> List[List[str]]:
    initialize_map_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT row_text FROM map_rows ORDER BY row_index"
        ).fetchall()
    raw = [row[0] for row in rows if row and row[0] is not None]
    if not raw:
        raw = list(DEFAULT_MAP_DATA)
    width = max((len(row) for row in raw), default=1)
    return [list(row.ljust(width, "#")) for row in raw]


def save_map(grid: List[List[str]], db_path: Path = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS map_rows ("
            "row_index INTEGER PRIMARY KEY, "
            "row_text TEXT NOT NULL"
            ")"
        )
        conn.execute("DELETE FROM map_rows")
        conn.executemany(
            "INSERT INTO map_rows (row_index, row_text) VALUES (?, ?)",
            [(index, "".join(row)) for index, row in enumerate(grid)],
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
    curses.init_pair(7, 16, 159)
    curses.init_pair(8, 46, -1)


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


def verify_map(grid: List[List[str]]) -> List[str]:
    issues: List[str] = []
    if not grid or not grid[0]:
        return ["Map is empty."]

    width = len(grid[0])
    for y, row in enumerate(grid):
        if len(row) != width:
            issues.append(f"Row {y} width differs from the first row.")

    sword_positions: List[Tuple[int, int]] = []
    monster_positions: List[Tuple[int, int]] = []
    passable_positions: List[Tuple[int, int]] = []

    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell not in TILE_INFO:
                issues.append(f"Unknown tile '{cell}' at {x},{y}.")
            if cell == "S":
                sword_positions.append((x, y))
            elif cell == "M":
                monster_positions.append((x, y))
            if cell in PASSABLE_TILES:
                passable_positions.append((x, y))

    if not passable_positions:
        issues.append("Map has no walkable floor.")

    if len(sword_positions) == 0:
        issues.append("Map has no sword.")
    elif len(sword_positions) > 1:
        issues.append(f"Map has {len(sword_positions)} swords; expected 1.")

    if len(monster_positions) == 0:
        issues.append("Map has no monsters.")

    start = find_start(grid)
    if start is None:
        issues.append("Map has no reachable starting floor tile.")
        return issues

    reachable = flood_walkable(grid, start)
    unreachable = [pos for pos in passable_positions if pos not in reachable]
    if unreachable:
        issues.append(f"Map has {len(unreachable)} unreachable walkable tile(s).")

    for x in range(width):
        if grid[0][x] in PASSABLE_TILES:
            issues.append(f"Top border leak at {x},0.")
        if grid[len(grid) - 1][x] in PASSABLE_TILES:
            issues.append(f"Bottom border leak at {x},{len(grid) - 1}.")
    for y in range(len(grid)):
        if grid[y][0] in PASSABLE_TILES:
            issues.append(f"Left border leak at 0,{y}.")
        if grid[y][width - 1] in PASSABLE_TILES:
            issues.append(f"Right border leak at {width - 1},{y}.")

    for x, y in sword_positions + monster_positions:
        if (x, y) not in reachable:
            tile_name = "sword" if grid[y][x] == "S" else "monster"
            issues.append(f"{tile_name.capitalize()} at {x},{y} is unreachable.")

    return issues


def cycle_tile(current: str, step: int) -> str:
    index = PALETTE_ORDER.index(current) if current in PALETTE_ORDER else 0
    return PALETTE_ORDER[(index + step) % len(PALETTE_ORDER)]


def place_tile(grid: List[List[str]], x: int, y: int, tile: str) -> None:
    if not is_inside(grid, x, y):
        return
    if tile == "S":
        for row in grid:
            for index, value in enumerate(row):
                if value == "S":
                    row[index] = "."
    grid[y][x] = tile


def draw_grid(stdscr, grid: List[List[str]], cursor_x: int, cursor_y: int, top: int, left: int) -> None:
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            name, color = TILE_INFO.get(cell, ("?", 6))
            attr = curses.color_pair(color)
            if (x, y) == (cursor_x, cursor_y):
                attr = curses.color_pair(7) | curses.A_BOLD
            elif cell in {"S", "M", "D"}:
                attr |= curses.A_BOLD
            try:
                stdscr.addch(top + y, left + x, cell if cell != " " else ".", attr)
            except curses.error:
                pass


def draw_sidebar(
    stdscr,
    grid: List[List[str]],
    selected_tile: str,
    cursor_x: int,
    cursor_y: int,
    message: str,
    verify_messages: List[str],
    saved: bool,
) -> None:
    height, width = stdscr.getmaxyx()
    sidebar_left = len(grid[0]) + 4
    lines = [
        "Dungeon Editor",
        "",
        f"DB: {DB_PATH.name}",
        f"Cursor: {cursor_x},{cursor_y}",
        f"Tile: {selected_tile} ({TILE_INFO.get(selected_tile, ('?', 6))[0]})",
        f"Saved: {'yes' if saved else 'no'}",
        "",
        "Palette:",
    ]
    for key in PALETTE_ORDER:
        marker = ">" if key == selected_tile else " "
        lines.append(f" {marker} {key if key != ' ' else '.'} - {TILE_INFO[key][0]}")
    lines.extend([
        "",
        "Keys:",
        " arrows move cursor",
        " 1 wall   2 floor",
        " 3 door   4 sword",
        " 5 monster 0 empty",
        " space/place current",
        " [ ] cycle tile",
        " v verify",
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

    grid = load_map()
    cursor_x = 0
    cursor_y = 0
    selected_tile = "#"
    message = "Loaded map."
    verify_messages: List[str] = []
    saved = True

    while True:
        stdscr.erase()
        draw_grid(stdscr, grid, cursor_x, cursor_y, 0, 0)
        draw_sidebar(stdscr, grid, selected_tile, cursor_x, cursor_y, message, verify_messages, saved)
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
        elif key == ord("0"):
            selected_tile = " "
        elif key == ord("["):
            selected_tile = cycle_tile(selected_tile, -1)
        elif key == ord("]"):
            selected_tile = cycle_tile(selected_tile, 1)
        elif key in (ord(" "), ord("\n"), ord("p"), ord("P")):
            place_tile(grid, cursor_x, cursor_y, selected_tile)
            saved = False
            message = f"Placed {TILE_INFO[selected_tile][0]} at {cursor_x},{cursor_y}."
        elif key in (ord("v"), ord("V")):
            issues = verify_map(grid)
            if issues:
                verify_messages = issues
                message = f"Verification found {len(issues)} issue(s)."
            else:
                verify_messages = ["Map verification OK."]
                message = "Map verification OK."
        elif key in (ord("s"), ord("S")):
            save_map(grid)
            saved = True
            message = "Map saved to dungeon_map.db."

    return 0


def main() -> int:
    return curses.wrapper(run)


if __name__ == "__main__":
    raise SystemExit(main())
