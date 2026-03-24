#!/usr/bin/env python3
import curses
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

Vec2 = Tuple[int, int]
DrawItem = Tuple[int, int, str, int]
FloorMap = List[str]
Grid = List[List[str]]

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

DIRECTIONS: List[Vec2] = [
    (0, -1),
    (1, 0),
    (0, 1),
    (-1, 0),
]
DIRECTION_NAMES = ["N", "E", "S", "W"]

WALL_COLOR = 244
DOOR_COLOR = 220
ACCENT_COLOR = 51
FLOOR_COLOR = 238
MAP_WALL_COLOR = 245
PLAYER_COLOR = 46
ENEMY_COLOR = 196
SWORD_COLOR = 226
STAIR_COLOR = 159
MAX_RENDER_DEPTH = 12.0
FOV_SCALE = 0.85
START_ENERGY = 12
MAX_ENERGY = 12
ATTACK_COST_WITH_SWORD = 1
ATTACK_COST_NO_SWORD = 2
WAIT_ENERGY_GAIN = 1

DEFAULT_FLOORS: List[FloorMap] = [
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
        "#...#.#.....#.#...##",
        "#####.#####.#.#####.#",
        "#...#.....#.#.....#.#",
        "#.#.###.#.#.#####.#.#",
        "#.#...M.#.#.....#...#",
        "#....S....D.........#",
        "####################",
    ],
]


def normalize_floor_rows(rows: List[str]) -> Grid:
    width = max((len(row) for row in rows), default=1)
    return [list(row.ljust(width, "#")) for row in rows]


def initialize_map_db(db_path: Path = DB_PATH) -> None:
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


def load_floors(db_path: Path = DB_PATH) -> List[Grid]:
    initialize_map_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT floor_index, row_index, row_text FROM floor_map_rows ORDER BY floor_index, row_index"
        ).fetchall()
    grouped: Dict[int, List[str]] = {}
    for floor_index, _row_index, row_text in rows:
        grouped.setdefault(int(floor_index), []).append(str(row_text))
    if grouped:
        return [normalize_floor_rows(grouped[index]) for index in sorted(grouped)]
    return [normalize_floor_rows(rows) for rows in DEFAULT_FLOORS]


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def setup_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, WALL_COLOR, -1)
    curses.init_pair(2, DOOR_COLOR, -1)
    curses.init_pair(3, ACCENT_COLOR, -1)
    curses.init_pair(4, FLOOR_COLOR, -1)
    curses.init_pair(5, MAP_WALL_COLOR, -1)
    curses.init_pair(6, PLAYER_COLOR, -1)
    curses.init_pair(7, ENEMY_COLOR, -1)
    curses.init_pair(8, SWORD_COLOR, -1)
    curses.init_pair(9, STAIR_COLOR, -1)


def current_grid(state: Dict[str, object]) -> Grid:
    floors = state["floors"]
    floor = int(state["floor"])
    return floors[floor]  # type: ignore[index]


def is_inside(x: int, y: int, grid: Grid) -> bool:
    return 0 <= y < len(grid) and 0 <= x < len(grid[y])


def cell_at(grid: Grid, x: int, y: int) -> str:
    if not is_inside(x, y, grid):
        return "#"
    return grid[y][x]


def is_passable(cell: str) -> bool:
    return cell in {".", " ", "S", "M", "<", ">"}


def facing_vector(facing: int) -> Tuple[float, float]:
    dx, dy = DIRECTIONS[facing]
    return float(dx), float(dy)


def cast_perspective_ray(
    grid: Grid,
    origin_x: float,
    origin_y: float,
    dir_x: float,
    dir_y: float,
    max_depth: float = MAX_RENDER_DEPTH,
) -> Tuple[float, str, int]:
    map_x = int(origin_x)
    map_y = int(origin_y)

    delta_dist_x = abs(1.0 / dir_x) if abs(dir_x) > 1e-9 else 1e30
    delta_dist_y = abs(1.0 / dir_y) if abs(dir_y) > 1e-9 else 1e30

    if dir_x < 0:
        step_x = -1
        side_dist_x = (origin_x - map_x) * delta_dist_x
    else:
        step_x = 1
        side_dist_x = (map_x + 1.0 - origin_x) * delta_dist_x

    if dir_y < 0:
        step_y = -1
        side_dist_y = (origin_y - map_y) * delta_dist_y
    else:
        step_y = 1
        side_dist_y = (map_y + 1.0 - origin_y) * delta_dist_y

    side = 0
    while True:
        if side_dist_x < side_dist_y:
            side_dist_x += delta_dist_x
            map_x += step_x
            side = 0
        else:
            side_dist_y += delta_dist_y
            map_y += step_y
            side = 1

        cell = cell_at(grid, map_x, map_y)
        if cell in {"#", "D"}:
            if side == 0:
                distance = (map_x - origin_x + (1 - step_x) / 2.0) / (dir_x if abs(dir_x) > 1e-9 else 1e-9)
            else:
                distance = (map_y - origin_y + (1 - step_y) / 2.0) / (dir_y if abs(dir_y) > 1e-9 else 1e-9)
            return max(0.001, distance), cell, side

        approx_distance = min(side_dist_x, side_dist_y)
        if approx_distance > max_depth:
            return max_depth, " ", side


def wall_char(distance: float, side: int, cell: str) -> str:
    if cell == "D":
        return "+" if side == 0 else "|"
    shades = "█▓▒░."
    index = min(len(shades) - 1, int(distance * 0.55) + side)
    return shades[index]


def floor_char(row: int, horizon: int, height: int) -> str:
    if row <= horizon:
        return " "
    ratio = (row - horizon) / max(1, height - horizon - 1)
    if ratio < 0.18:
        return "_"
    if ratio < 0.40:
        return "."
    if ratio < 0.68:
        return ","
    return "`"


def find_tile(grid: Grid, tile: str) -> Optional[Vec2]:
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell == tile:
                return x, y
    return None


def find_visible_tile(grid: Grid, px: int, py: int, facing: int, tile: str) -> Optional[Tuple[int, int, int]]:
    dx, dy = DIRECTIONS[facing]
    rx, ry = -dy, dx
    for distance in range(1, 6):
        cx = px + dx * distance
        cy = py + dy * distance
        center = cell_at(grid, cx, cy)
        if center == "#":
            return None
        if center == "D":
            break
        if center == tile:
            return distance, 0, 0
        for side, lateral in ((-1, -1), (1, 1)):
            sx = cx + rx * lateral
            sy = cy + ry * lateral
            side_cell = cell_at(grid, sx, sy)
            if side_cell == tile:
                return distance, side, lateral
    return None


def enemy_in_view(grid: Grid, px: int, py: int, facing: int) -> Optional[Tuple[int, int, int]]:
    return find_visible_tile(grid, px, py, facing, "M")


def sword_in_view(grid: Grid, px: int, py: int, facing: int) -> Optional[Tuple[int, int, int]]:
    return find_visible_tile(grid, px, py, facing, "S")


def stairs_in_view(grid: Grid, px: int, py: int, facing: int) -> Optional[Tuple[int, int, int, str]]:
    for tile in ("<", ">"):
        visible = find_visible_tile(grid, px, py, facing, tile)
        if visible is not None:
            distance, side, lateral = visible
            return distance, side, lateral, tile
    return None


def render_enemy_sprite(items: List[DrawItem], width: int, height: int, distance: int, side: int) -> None:
    perspective_scale = max(0.55, 2.4 / (distance + 0.35))
    perspective_scale *= 1.15 if side == 0 else 0.72
    center_x = width // 2 + side * max(3, width // max(8, 9 + distance * 2))
    floor_y = height - 4
    sprite = [
        "  M  ",
        " /#\\ ",
        "/###\\",
        " / \\",
    ]
    sprite_height = max(2, int(round(len(sprite) * perspective_scale)))
    sprite_width = max(3, int(round(len(sprite[0]) * perspective_scale * (0.95 if side == 0 else 0.85))))
    sprite_top = max(1, floor_y - sprite_height + 1)

    for target_row in range(sprite_height):
        source_row = min(len(sprite) - 1, int(target_row / max(0.001, perspective_scale)))
        row = sprite[source_row]
        sy = sprite_top + target_row
        start_x = center_x - sprite_width // 2
        for target_col in range(sprite_width):
            source_col = min(len(row) - 1, int(target_col / max(0.001, sprite_width / len(row))))
            ch = row[source_col]
            if ch != " ":
                items.append((sy, start_x + target_col, ch, 7))


def render_sword_sprite(items: List[DrawItem], width: int, height: int, distance: int, side: int) -> None:
    perspective_scale = max(0.45, 2.0 / (distance + 0.2))
    perspective_scale *= 1.18 if side == 0 else 0.72
    center_x = width // 2 + side * max(2, width // max(10, 11 + distance * 2))
    floor_y = height - 4
    sprite = [
        "  /  ",
        " /   ",
        "/    ",
        "||== ",
        "||   ",
    ]
    sprite_height = max(2, int(round(len(sprite) * perspective_scale)))
    sprite_width = max(2, int(round(len(sprite[0]) * perspective_scale * (0.92 if side == 0 else 0.82))))
    sprite_top = max(1, floor_y - sprite_height + 1)

    for target_row in range(sprite_height):
        source_row = min(len(sprite) - 1, int(target_row / max(0.001, perspective_scale)))
        row = sprite[source_row]
        sy = sprite_top + target_row
        start_x = center_x - sprite_width // 2
        for target_col in range(sprite_width):
            source_col = min(len(row) - 1, int(target_col / max(0.001, sprite_width / len(row))))
            ch = row[source_col]
            if ch != " ":
                items.append((sy, start_x + target_col, ch, 8))


def render_stairs_sprite(items: List[DrawItem], width: int, height: int, distance: int, side: int, tile: str) -> None:
    perspective_scale = max(0.50, 2.2 / (distance + 0.25))
    center_x = width // 2 + side * max(2, width // max(9, 10 + distance * 2))
    floor_y = height - 4
    sprite = [
        "_____",
        " ___ ",
        "  __ ",
        "   _ ",
    ] if tile == ">" else [
        " _   ",
        " __  ",
        " ___ ",
        "_____",
    ]
    sprite_height = max(2, int(round(len(sprite) * perspective_scale)))
    sprite_width = max(3, int(round(len(sprite[0]) * perspective_scale)))
    sprite_top = max(1, floor_y - sprite_height + 1)

    for target_row in range(sprite_height):
        source_row = min(len(sprite) - 1, int(target_row / max(0.001, perspective_scale)))
        row = sprite[source_row]
        sy = sprite_top + target_row
        start_x = center_x - sprite_width // 2
        for target_col in range(sprite_width):
            source_col = min(len(row) - 1, int(target_col / max(0.001, sprite_width / len(row))))
            ch = row[source_col]
            if ch != " ":
                items.append((sy, start_x + target_col, ch, 9))


def render_view(grid: Grid, px: int, py: int, facing: int, width: int, height: int) -> List[DrawItem]:
    items: List[DrawItem] = []
    horizon = height // 2
    cam_x, cam_y = px + 0.5, py + 0.5
    dir_x, dir_y = facing_vector(facing)
    plane_x, plane_y = -dir_y * FOV_SCALE, dir_x * FOV_SCALE

    for y in range(horizon, height - 2):
        char = floor_char(y, horizon, height)
        for x in range(width):
            items.append((y, x, char, 4))

    for x in range(width):
        camera_x = 2.0 * x / max(1, width - 1) - 1.0
        ray_dir_x = dir_x + plane_x * camera_x
        ray_dir_y = dir_y + plane_y * camera_x
        distance, cell, side = cast_perspective_ray(grid, cam_x, cam_y, ray_dir_x, ray_dir_y)
        if cell == " ":
            continue

        line_height = int((height * 0.92) / max(0.001, distance))
        draw_start = max(1, horizon - line_height // 2)
        draw_end = min(height - 3, horizon + line_height // 2)
        char = wall_char(distance, side, cell)
        color = 2 if cell == "D" else 1

        for y in range(draw_start, draw_end + 1):
            draw_char = char
            if cell == "D":
                mid = (draw_start + draw_end) // 2
                if abs(y - mid) <= max(1, line_height // 10):
                    draw_char = "="
                elif x % 2 == 0:
                    draw_char = "|"
            elif side == 1 and draw_char in {"█", "▓", "▒"}:
                draw_char = {"█": "▓", "▓": "▒", "▒": "░"}.get(draw_char, draw_char)
            items.append((y, x, draw_char, color))

        ceiling_limit = max(1, draw_start - 1)
        if ceiling_limit > 1 and x % 3 == 0:
            items.append((ceiling_limit, x, "_", 4))

    visible_stairs = stairs_in_view(grid, px, py, facing)
    if visible_stairs is not None:
        distance, side, _, tile = visible_stairs
        render_stairs_sprite(items, width, height, distance, side, tile)

    visible_sword = sword_in_view(grid, px, py, facing)
    if visible_sword is not None:
        distance, side, _ = visible_sword
        render_sword_sprite(items, width, height, distance, side)

    visible_enemy = enemy_in_view(grid, px, py, facing)
    if visible_enemy is not None:
        distance, side, _ = visible_enemy
        render_enemy_sprite(items, width, height, distance, side)

    return items


def draw_minimap(stdscr, grid: Grid, px: int, py: int, facing: int, floor_index: int, top: int, left: int) -> None:
    view_radius = 4
    label = f"F{floor_index + 1}"
    try:
        stdscr.addstr(top - 1, left, label, curses.color_pair(9) | curses.A_BOLD)
    except curses.error:
        pass

    for dy in range(-view_radius, view_radius + 1):
        for dx in range(-view_radius, view_radius + 1):
            mx = px + dx
            my = py + dy
            ch = cell_at(grid, mx, my)
            sy = top + dy + view_radius
            sx = left + (dx + view_radius) * 2
            if ch == "#":
                char = "##"
                attr = curses.color_pair(5)
            elif ch == "D":
                char = "[]"
                attr = curses.color_pair(2) | curses.A_BOLD
            elif ch == "M":
                char = "MM"
                attr = curses.color_pair(7) | curses.A_BOLD
            elif ch == "S":
                char = "/="
                attr = curses.color_pair(8) | curses.A_BOLD
            elif ch == ">":
                char = ">>"
                attr = curses.color_pair(9) | curses.A_BOLD
            elif ch == "<":
                char = "<<"
                attr = curses.color_pair(9) | curses.A_BOLD
            else:
                char = "  "
                attr = curses.color_pair(4)
            try:
                stdscr.addstr(sy, sx, char, attr)
            except curses.error:
                pass

    arrow = ["^", ">", "v", "<"][facing]
    try:
        stdscr.addstr(top + view_radius, left + view_radius * 2, arrow, curses.color_pair(6) | curses.A_BOLD)
    except curses.error:
        pass


def collect_tile(state: Dict[str, object], grid: Grid) -> None:
    x = int(state["x"])
    y = int(state["y"])
    if cell_at(grid, x, y) == "S":
        grid[y][x] = "."
        state["has_sword"] = True
        state["message"] = "You take the sword. Fighting is now easier."


def try_move(state: Dict[str, object], step: int) -> None:
    grid = current_grid(state)
    dx, dy = DIRECTIONS[int(state["facing"])]
    nx = int(state["x"]) + dx * step
    ny = int(state["y"]) + dy * step
    if is_passable(cell_at(grid, nx, ny)):
        state["x"] = nx
        state["y"] = ny
        collect_tile(state, grid)


def try_strafe(state: Dict[str, object], step: int) -> None:
    grid = current_grid(state)
    facing = int(state["facing"])
    side = (facing + step) % 4
    dx, dy = DIRECTIONS[side]
    nx = int(state["x"]) + dx
    ny = int(state["y"]) + dy
    if is_passable(cell_at(grid, nx, ny)):
        state["x"] = nx
        state["y"] = ny
        collect_tile(state, grid)


def travel_stairs(state: Dict[str, object], delta: int) -> str:
    current_floor = int(state["floor"])
    floors = state["floors"]  # type: ignore[assignment]
    new_floor = current_floor + delta
    if not (0 <= new_floor < len(floors)):
        return "The stairs go nowhere."

    destination_tile = "<" if delta > 0 else ">"
    destination = find_tile(floors[new_floor], destination_tile)
    if destination is None:
        return "The matching stairs cannot be found."

    state["floor"] = new_floor
    state["x"], state["y"] = destination
    collect_tile(state, floors[new_floor])
    return f"You walk {'down' if delta > 0 else 'up'} the stairs to floor {new_floor + 1}."


def use_action(state: Dict[str, object]) -> str:
    grid = current_grid(state)
    dx, dy = DIRECTIONS[int(state["facing"])]
    tx = int(state["x"]) + dx
    ty = int(state["y"]) + dy
    target = cell_at(grid, tx, ty)
    if target == "D":
        grid[ty][tx] = "."
        return "You open the door."
    if target == "M":
        has_sword = bool(state["has_sword"])
        cost = ATTACK_COST_WITH_SWORD if has_sword else ATTACK_COST_NO_SWORD
        energy = int(state["energy"])
        if energy < cost:
            return "Too tired to fight. Wait to regain some energy."
        state["energy"] = max(0, energy - cost)
        grid[ty][tx] = "."
        state["score"] = int(state["score"]) + 1
        return f"You defeat the enemy. Energy -{cost}."
    if target == "S":
        grid[ty][tx] = "."
        state["has_sword"] = True
        return "You take the sword."
    if target == ">":
        return travel_stairs(state, 1)
    if target == "<":
        return travel_stairs(state, -1)
    return "Nothing happens."


def use_current_tile(state: Dict[str, object]) -> bool:
    grid = current_grid(state)
    tile = cell_at(grid, int(state["x"]), int(state["y"]))
    if tile == ">":
        state["message"] = travel_stairs(state, 1)
        return True
    if tile == "<":
        state["message"] = travel_stairs(state, -1)
        return True
    return False


def draw_scene(stdscr, state: Dict[str, object]) -> None:
    grid = current_grid(state)
    height, width = stdscr.getmaxyx()
    stdscr.erase()

    title = " ANSI Dungeon - SQLite map "
    energy = int(state["energy"])
    filled = max(0, min(MAX_ENERGY, energy))
    empty = max(0, MAX_ENERGY - filled)
    health_bar = "[" + ("#" * filled) + ("-" * empty) + "]"
    status = (
        f" {health_bar} {energy}/{MAX_ENERGY}"
        f" floor:{int(state['floor']) + 1}/{len(state['floors'])}"
        f" pos:{state['x']},{state['y']} facing:{DIRECTION_NAMES[int(state['facing'])]}"
        f" sword:{'yes' if bool(state['has_sword']) else 'no'} defeated:{state['score']} "
    )
    help_text = " arrows/WASD move | q/e turn | z/c strafe | space act | . wait | m map | x quit "
    view_height = max(6, height - 3)

    if width > len(title) + 2:
        try:
            stdscr.addstr(0, max(0, (width - len(title)) // 2), title, curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass

    for y, x, ch, color in render_view(grid, int(state["x"]), int(state["y"]), int(state["facing"]), width, view_height):
        if 1 <= y < height - 3 and 0 <= x < width:
            try:
                attr = curses.color_pair(color)
                if color in (2, 3, 7, 8, 9):
                    attr |= curses.A_BOLD
                stdscr.addch(y, x, ch, attr)
            except curses.error:
                pass

    if bool(state["show_map"]):
        draw_minimap(stdscr, grid, int(state["x"]), int(state["y"]), int(state["facing"]), int(state["floor"]), 3, 2)

    try:
        stdscr.addstr(height - 3, 1, help_text[: max(0, width - 2)], curses.color_pair(3))
    except curses.error:
        pass
    try:
        stdscr.addstr(height - 2, 1, status[: max(0, width - 2)], curses.color_pair(4) | curses.A_BOLD)
    except curses.error:
        pass
    try:
        stdscr.addstr(height - 1, 1, str(state["message"])[: max(0, width - 2)], curses.color_pair(9))
    except curses.error:
        pass


def find_start_position(floors: List[Grid]) -> Tuple[int, int, int]:
    for floor_index, grid in enumerate(floors):
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell in {".", "S", "<", ">", "M", " "}:
                    return floor_index, x, y
    return 0, 1, 1


def run(stdscr) -> int:
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)
    setup_colors()

    floors = load_floors()
    start_floor, start_x, start_y = find_start_position(floors)
    state: Dict[str, object] = {
        "floors": floors,
        "floor": start_floor,
        "x": start_x,
        "y": start_y,
        "facing": 1,
        "energy": START_ENERGY,
        "score": 0,
        "has_sword": False,
        "show_map": True,
        "message": f"Loaded dungeon from {DB_PATH.name}.",
    }
    collect_tile(state, current_grid(state))

    while True:
        draw_scene(stdscr, state)
        stdscr.refresh()
        key = stdscr.getch()

        if key in (ord("x"), ord("X")):
            break
        if key in (ord("q"), ord("Q")):
            state["facing"] = (int(state["facing"]) - 1) % 4
            state["message"] = "You turn left."
        elif key in (ord("e"), ord("E")):
            state["facing"] = (int(state["facing"]) + 1) % 4
            state["message"] = "You turn right."
        elif key in (curses.KEY_UP, ord("w"), ord("W")):
            old_pos = (state["x"], state["y"])
            try_move(state, 1)
            state["message"] = "You move forward." if old_pos != (state["x"], state["y"]) else "A wall blocks your way."
            use_current_tile(state)
        elif key in (curses.KEY_DOWN, ord("s"), ord("S")):
            old_pos = (state["x"], state["y"])
            try_move(state, -1)
            state["message"] = "You move backward." if old_pos != (state["x"], state["y"]) else "You cannot move there."
            use_current_tile(state)
        elif key in (ord("z"), ord("Z")):
            old_pos = (state["x"], state["y"])
            try_strafe(state, -1)
            state["message"] = "You sidestep left." if old_pos != (state["x"], state["y"]) else "Blocked on the left."
            use_current_tile(state)
        elif key in (ord("c"), ord("C")):
            old_pos = (state["x"], state["y"])
            try_strafe(state, 1)
            state["message"] = "You sidestep right." if old_pos != (state["x"], state["y"]) else "Blocked on the right."
            use_current_tile(state)
        elif key in (ord("m"), ord("M")):
            state["show_map"] = not bool(state["show_map"])
            state["message"] = f"Map {'shown' if state['show_map'] else 'hidden'}."
        elif key in (ord("."),):
            state["energy"] = min(MAX_ENERGY, int(state["energy"]) + WAIT_ENERGY_GAIN)
            state["message"] = "You wait and regain a little energy."
        elif key in (ord(" "), ord("\n")):
            state["message"] = use_action(state)
        elif key == ord(">"):
            state["message"] = travel_stairs(state, 1)
        elif key == ord("<"):
            state["message"] = travel_stairs(state, -1)

    return 0


def main() -> int:
    initialize_map_db(DB_PATH)
    return curses.wrapper(run)


if __name__ == "__main__":
    raise SystemExit(main())
