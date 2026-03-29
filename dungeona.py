import curses
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ans import AnsiTexture, load_ans_texture

Vec2 = Tuple[int, int]
DrawItem = Tuple[int, int, str, int]
FloorMap = List[str]
Grid = List[List[str]]

DB_PATH = Path(__file__).with_name("dungeon_map.db")
TEXTURE_DIR = Path(__file__).with_name("textures")
WALL_TEXTURE_FILES = {
    "#": "wall.ans",
    "D": "door.ans",
}
FLOOR_TEXTURE_FILE = "floor.ans"
CEILING_TEXTURE_FILE = "ceiling.ans"
RAT_ANIMATION_FILES = ["rat001.ans", "rat002.ans", "rat003.ans"]
SPRITE_TEXTURE_FILES = {
    "altar": "altar.ans",
    "grail": "grail.ans",
    "ogre": "ogre.ans",
    "skeleton": "skeleton.ans",
}

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
GRAIL_COLOR = 226
STAIR_COLOR = 159
QUEST_COLOR = 93
MAX_RENDER_DEPTH = 12.0
FOV_SCALE = 0.85
START_ENERGY = 12
MAX_ENERGY = 12
ATTACK_COST_WITH_GRAIL = 1
ATTACK_COST_NO_GRAIL = 2
WAIT_ENERGY_GAIN = 1
QUEST_ITEM_TILE = "G"
QUEST_TARGET_TILE = "A"
QUEST_ITEM_NAME = "Holy Grail"
QUEST_START_FLOOR = 0
QUEST_TARGET_FLOOR = 0
MAX_CARRIED_ITEMS = 3
CONGRATS_BANNER = [
    "  ____                            _         _       _   _                 ",
    " / ___|___  _ __   __ _ _ __ __ _| |_ _   _| | __ _| |_(_) ___  _ __  ___ ",
    "| |   / _ \\| '_ \\ / _` | '__/ _` | __| | | | |/ _` | __| |/ _ \\| '_ \\/ __|",
    "| |__| (_) | | | | (_| | | | (_| | |_| |_| | | (_| | |_| | (_) | | | \\__ \\",
    " \\____\\___/|_| |_|\\__, |_|  \\__,_|\\__|\\__,_|_|\\__,_|\\__|_|\\___/|_| |_|___/",
    "                  |___/                                                         ",
]

MONSTER_TYPES: Dict[str, Dict[str, object]] = {
    "R": {
        "name": "rat",
        "color": 7,
        "map": "rr",
        "sprite": [
            " /^-\\",
            "(o.o )",
            " /|\\~",
        ],
        "animated_sprite_key": "rat",
        "defeat": "You skewer the giant rat.",
    },
    "S": {
        "name": "skeleton",
        "color": 10,
        "map": "SK",
        "sprite": [
            " .-. ",
            "(o o)",
            " |#| ",
            " / \\",
        ],
        "defeat": "You shatter the skeleton.",
    },
    "O": {
        "name": "ogre",
        "color": 2,
        "map": "OG",
        "sprite": [
            " /^^\\ ",
            "( ** )",
            " /##\\ ",
            " /  \\",
        ],
        "defeat": "You bring down the ogre.",
    },
}
MONSTER_TILES = set(MONSTER_TYPES)
LEGACY_MONSTER_TILE = "M"
MONSTER_CHASE_TURNS = 3

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
        "#...#.....R...#.#..#",
        "#.#######.#####.#..#",
        "#.....#...#.....#..#",
        "#.###.#.###.#####..#",
        "#.#...#...#.....#..#",
        "#.#.#####.#.###.#..#",
        "#.#.....#.#.#G..#..#",
        "#.#####.#.#.#.###..#",
        "#.....S...#.#......#",
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
        "#...#...#.#..O.....#",
        "#.#####.#.########.#",
        "#.....#.#.....#....#",
        "#.###.#.#####.#.##.#",
        "#.#...#.....#.#.#..#",
        "#.#.#######.#.#.#>.#",
        "#.#.#.....#.#.#.##.#",
        "#...#.###.#.#.#....#",
        "###.#...#.#.#.####.#",
        "#...###.#...#......#",
        "#.....R.....D......#",
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
        "#.#...S.#.#.....#...#",
        "#....A....D.........#",
        "####################",
    ],
]


def normalize_floor_rows(rows: List[str]) -> Grid:
    width = max((len(row) for row in rows), default=1)
    return [list(row.ljust(width, "#")) for row in rows]


def decorate_legacy_monsters(grid: Grid, floor_index: int) -> None:
    cycle = ["R", "S", "O"]
    counter = 0
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell == LEGACY_MONSTER_TILE:
                grid[y][x] = cycle[(floor_index + counter) % len(cycle)]
                counter += 1


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
        floors = [normalize_floor_rows(grouped[index]) for index in sorted(grouped)]
    else:
        floors = [normalize_floor_rows(rows) for rows in DEFAULT_FLOORS]
    for floor_index, grid in enumerate(floors):
        decorate_legacy_monsters(grid, floor_index)
    return floors


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
    curses.init_pair(8, GRAIL_COLOR, -1)
    curses.init_pair(9, STAIR_COLOR, -1)
    curses.init_pair(10, QUEST_COLOR, -1)


def load_wall_textures() -> Dict[str, AnsiTexture]:
    textures: Dict[str, AnsiTexture] = {}
    for tile, filename in WALL_TEXTURE_FILES.items():
        path = TEXTURE_DIR / filename
        if path.exists():
            try:
                textures[tile] = load_ans_texture(path)
            except Exception:
                pass
    return textures


def load_surface_texture(filename: str) -> Optional[AnsiTexture]:
    path = TEXTURE_DIR / filename
    if not path.exists():
        return None
    try:
        return load_ans_texture(path)
    except Exception:
        return None


def texture_to_sprite_lines(texture: AnsiTexture) -> List[str]:
    lines = [line.rstrip() for line in texture.to_plain_lines()]
    while lines and not lines[-1]:
        lines.pop()
    return lines or ["?"]


def load_animated_sprites() -> Dict[str, List[List[str]]]:
    animations: Dict[str, List[List[str]]] = {}
    frames: List[List[str]] = []
    for filename in RAT_ANIMATION_FILES:
        path = TEXTURE_DIR / filename
        if not path.exists():
            continue
        try:
            frames.append(texture_to_sprite_lines(load_ans_texture(path)))
        except Exception:
            continue
    if frames:
        animations["rat"] = frames
    return animations


def load_static_sprites() -> Dict[str, List[str]]:
    sprites: Dict[str, List[str]] = {}
    for key, filename in SPRITE_TEXTURE_FILES.items():
        path = TEXTURE_DIR / filename
        if not path.exists():
            continue
        try:
            sprites[key] = texture_to_sprite_lines(load_ans_texture(path))
        except Exception:
            continue
    return sprites


def texture_char_for_column(texture: Optional[AnsiTexture], x_ratio: float, y_ratio: float, fallback: str) -> str:
    if texture is None or texture.width <= 0 or texture.height <= 0:
        return fallback
    tx = min(texture.width - 1, max(0, int(x_ratio * max(1, texture.width - 1))))
    ty = min(texture.height - 1, max(0, int(y_ratio * max(1, texture.height - 1))))
    sampled = texture.sample_char(tx, ty, fallback)
    return sampled if sampled.strip() else fallback


def repeating_texture_char(texture: Optional[AnsiTexture], x_ratio: float, y_ratio: float, fallback: str) -> str:
    if texture is None or texture.width <= 0 or texture.height <= 0:
        return fallback
    wrapped_x = x_ratio % 1.0
    wrapped_y = y_ratio % 1.0
    tx = min(texture.width - 1, max(0, int(wrapped_x * texture.width)))
    ty = min(texture.height - 1, max(0, int(wrapped_y * texture.height)))
    sampled = texture.sample_char(tx, ty, fallback)
    return sampled if sampled.strip() else fallback


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


def is_monster(cell: str) -> bool:
    return cell in MONSTER_TILES or cell == LEGACY_MONSTER_TILE


def monster_info(tile: str) -> Dict[str, object]:
    if tile in MONSTER_TYPES:
        return MONSTER_TYPES[tile]
    return MONSTER_TYPES["R"]


def is_passable(cell: str) -> bool:
    return cell in {".", " ", QUEST_ITEM_TILE, "<", ">", QUEST_TARGET_TILE} or is_monster(cell)


def is_walkable_for_monster(cell: str) -> bool:
    return cell in {".", " ", QUEST_ITEM_TILE, "<", ">", QUEST_TARGET_TILE}


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
) -> Tuple[float, str, int, float]:
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
                wall_hit = origin_y + distance * dir_y
            else:
                distance = (map_y - origin_y + (1 - step_y) / 2.0) / (dir_y if abs(dir_y) > 1e-9 else 1e-9)
                wall_hit = origin_x + distance * dir_x
            wall_hit -= int(wall_hit)
            if (side == 0 and dir_x > 0) or (side == 1 and dir_y < 0):
                wall_hit = 1.0 - wall_hit
            return max(0.001, distance), cell, side, wall_hit

        approx_distance = min(side_dist_x, side_dist_y)
        if approx_distance > max_depth:
            return max_depth, " ", side, 0.0


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


def visible_monster(grid: Grid, px: int, py: int, facing: int) -> Optional[Tuple[int, int, int, str]]:
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
        if is_monster(center):
            return distance, 0, 0, center if center in MONSTER_TILES else "R"
        for side, lateral in ((-1, -1), (1, 1)):
            sx = cx + rx * lateral
            sy = cy + ry * lateral
            side_cell = cell_at(grid, sx, sy)
            if is_monster(side_cell):
                return distance, side, lateral, side_cell if side_cell in MONSTER_TILES else "R"
    return None


def grail_in_view(grid: Grid, px: int, py: int, facing: int) -> Optional[Tuple[int, int, int]]:
    return find_visible_tile(grid, px, py, facing, QUEST_ITEM_TILE)


def altar_in_view(grid: Grid, px: int, py: int, facing: int) -> Optional[Tuple[int, int, int]]:
    return find_visible_tile(grid, px, py, facing, QUEST_TARGET_TILE)


def stairs_in_view(grid: Grid, px: int, py: int, facing: int) -> Optional[Tuple[int, int, int, str]]:
    for tile in ("<", ">"):
        visible = find_visible_tile(grid, px, py, facing, tile)
        if visible is not None:
            distance, side, lateral = visible
            return distance, side, lateral, tile
    return None


def render_monster_sprite(
    items: List[DrawItem],
    width: int,
    height: int,
    distance: int,
    side: int,
    monster_tile: str,
    animated_sprites: Optional[Dict[str, List[List[str]]]] = None,
    static_sprites: Optional[Dict[str, List[str]]] = None,
    animation_step: int = 0,
) -> None:
    info = monster_info(monster_tile)
    perspective_scale = max(0.55, 2.4 / (distance + 0.35))
    perspective_scale *= 1.15 if side == 0 else 0.72
    center_x = width // 2 + side * max(3, width // max(8, 9 + distance * 2))
    floor_y = height - 4
    sprite = info["sprite"]  # type: ignore[assignment]
    animation_key = info.get("animated_sprite_key")
    if isinstance(animation_key, str) and animated_sprites and animation_key in animated_sprites:
        frames = animated_sprites[animation_key]
        if frames:
            sprite = frames[animation_step % len(frames)]
    elif static_sprites:
        static_key = str(info["name"])
        if static_key in static_sprites:
            sprite = static_sprites[static_key]
    color = int(info["color"])
    sprite_height = max(2, int(round(len(sprite) * perspective_scale)))
    max_row_width = max((len(row) for row in sprite), default=1)
    sprite_width = max(3, int(round(max_row_width * perspective_scale * (0.95 if side == 0 else 0.85))))
    sprite_bottom = floor_y
    sprite_top = max(1, sprite_bottom - sprite_height + 1)

    for target_row in range(sprite_height):
        source_row = min(len(sprite) - 1, int(target_row / max(0.001, perspective_scale)))
        row = sprite[source_row]
        if not row:
            continue
        sy = sprite_top + target_row
        start_x = center_x - sprite_width // 2
        col_scale = max(0.001, sprite_width / len(row))
        for target_col in range(sprite_width):
            source_col = min(len(row) - 1, int(target_col / col_scale))
            ch = row[source_col]
            if ch != " ":
                items.append((sy, start_x + target_col, ch, color))


def render_grail_sprite(
    items: List[DrawItem],
    width: int,
    height: int,
    distance: int,
    side: int,
    static_sprites: Optional[Dict[str, List[str]]] = None,
) -> None:
    perspective_scale = max(0.45, 2.0 / (distance + 0.2))
    perspective_scale *= 1.18 if side == 0 else 0.72
    center_x = width // 2 + side * max(2, width // max(10, 11 + distance * 2))
    floor_y = height - 4
    sprite = (static_sprites or {}).get("grail", [
        " .^. ",
        "(===)",
        " \\_/ ",
        "  |  ",
        " _|_ ",
    ])
    sprite_height = max(2, int(round(len(sprite) * perspective_scale)))
    max_row_width = max((len(row) for row in sprite), default=1)
    sprite_width = max(2, int(round(max_row_width * perspective_scale * (0.92 if side == 0 else 0.82))))
    sprite_bottom = floor_y
    sprite_top = max(1, sprite_bottom - sprite_height + 1)

    for target_row in range(sprite_height):
        source_row = min(len(sprite) - 1, int(target_row / max(0.001, perspective_scale)))
        row = sprite[source_row]
        if not row:
            continue
        sy = sprite_top + target_row
        start_x = center_x - sprite_width // 2
        col_scale = max(0.001, sprite_width / len(row))
        for target_col in range(sprite_width):
            source_col = min(len(row) - 1, int(target_col / col_scale))
            ch = row[source_col]
            if ch != " ":
                items.append((sy, start_x + target_col, ch, 8))


def render_altar_sprite(
    items: List[DrawItem],
    width: int,
    height: int,
    distance: int,
    side: int,
    static_sprites: Optional[Dict[str, List[str]]] = None,
) -> None:
    perspective_scale = max(0.48, 2.1 / (distance + 0.25))
    center_x = width // 2 + side * max(2, width // max(10, 11 + distance * 2))
    floor_y = height - 4
    sprite = (static_sprites or {}).get("altar", [
        " _____ ",
        "/_A_A_\\",
        "|_____|",
        "  |_|  ",
    ])
    sprite_height = max(2, int(round(len(sprite) * perspective_scale)))
    max_row_width = max((len(row) for row in sprite), default=1)
    sprite_width = max(3, int(round(max_row_width * perspective_scale)))
    sprite_bottom = floor_y
    sprite_top = max(1, sprite_bottom - sprite_height + 1)

    for target_row in range(sprite_height):
        source_row = min(len(sprite) - 1, int(target_row / max(0.001, perspective_scale)))
        row = sprite[source_row]
        if not row:
            continue
        sy = sprite_top + target_row
        start_x = center_x - sprite_width // 2
        col_scale = max(0.001, sprite_width / len(row))
        for target_col in range(sprite_width):
            source_col = min(len(row) - 1, int(target_col / col_scale))
            ch = row[source_col]
            if ch != " ":
                items.append((sy, start_x + target_col, ch, 10))


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
    max_row_width = max((len(row) for row in sprite), default=1)
    sprite_width = max(3, int(round(max_row_width * perspective_scale)))
    sprite_bottom = floor_y
    sprite_top = max(1, sprite_bottom - sprite_height + 1)

    for target_row in range(sprite_height):
        source_row = min(len(sprite) - 1, int(target_row / max(0.001, perspective_scale)))
        row = sprite[source_row]
        if not row:
            continue
        sy = sprite_top + target_row
        start_x = center_x - sprite_width // 2
        col_scale = max(0.001, sprite_width / len(row))
        for target_col in range(sprite_width):
            source_col = min(len(row) - 1, int(target_col / col_scale))
            ch = row[source_col]
            if ch != " ":
                items.append((sy, start_x + target_col, ch, 9))


def render_view(
    grid: Grid,
    px: int,
    py: int,
    facing: int,
    width: int,
    height: int,
    wall_textures: Optional[Dict[str, AnsiTexture]] = None,
    floor_texture: Optional[AnsiTexture] = None,
    ceiling_texture: Optional[AnsiTexture] = None,
    animated_sprites: Optional[Dict[str, List[List[str]]]] = None,
    static_sprites: Optional[Dict[str, List[str]]] = None,
    animation_step: int = 0,
) -> List[DrawItem]:
    items: List[DrawItem] = []
    horizon = height // 2
    cam_x, cam_y = px + 0.5, py + 0.5
    dir_x, dir_y = facing_vector(facing)
    plane_x, plane_y = -dir_y * FOV_SCALE, dir_x * FOV_SCALE

    for y in range(1, height - 2):
        if y < horizon:
            ceiling_depth = (horizon - y) / max(1, horizon)
            for x in range(width):
                ceiling_x_ratio = x / max(1, width)
                ceiling_y_ratio = ceiling_depth * 3.0
                char = repeating_texture_char(
                    ceiling_texture,
                    ceiling_x_ratio * 2.0 + ceiling_depth * 0.35,
                    ceiling_y_ratio,
                    " ",
                )
                items.append((y, x, char, 4))
        elif y > horizon:
            floor_depth = (y - horizon) / max(1, height - horizon - 1)
            base_char = floor_char(y, horizon, height)
            for x in range(width):
                floor_x_ratio = x / max(1, width)
                char = repeating_texture_char(
                    floor_texture,
                    floor_x_ratio * (1.2 + floor_depth * 2.8),
                    floor_depth * 3.2,
                    base_char,
                )
                items.append((y, x, char, 4))

    for x in range(width):
        camera_x = 2.0 * x / max(1, width - 1) - 1.0
        ray_dir_x = dir_x + plane_x * camera_x
        ray_dir_y = dir_y + plane_y * camera_x
        distance, cell, side, wall_hit = cast_perspective_ray(grid, cam_x, cam_y, ray_dir_x, ray_dir_y)
        if cell == " ":
            continue

        line_height = int((height * 0.92) / max(0.001, distance))
        draw_start = max(1, horizon - line_height // 2)
        draw_end = min(height - 3, horizon + line_height // 2)
        char = wall_char(distance, side, cell)
        color = 2 if cell == "D" else 1
        texture = (wall_textures or {}).get(cell)

        for y in range(draw_start, draw_end + 1):
            draw_char = char
            if texture is not None:
                y_ratio = (y - draw_start) / max(1, draw_end - draw_start)
                draw_char = texture_char_for_column(texture, wall_hit, y_ratio, draw_char)
            if cell == "D":
                mid = (draw_start + draw_end) // 2
                if abs(y - mid) <= max(1, line_height // 10):
                    draw_char = "="
                elif x % 2 == 0 and texture is None:
                    draw_char = "|"
            elif side == 1 and texture is None and draw_char in {"█", "▓", "▒"}:
                draw_char = {"█": "▓", "▓": "▒", "▒": "░"}.get(draw_char, draw_char)
            items.append((y, x, draw_char, color))

        ceiling_limit = max(1, draw_start - 1)
        if ceiling_limit > 1 and x % 3 == 0:
            items.append((ceiling_limit, x, "_", 4))

    visible_stairs = stairs_in_view(grid, px, py, facing)
    if visible_stairs is not None:
        distance, side, _, tile = visible_stairs
        render_stairs_sprite(items, width, height, distance, side, tile)

    visible_grail = grail_in_view(grid, px, py, facing)
    if visible_grail is not None:
        distance, side, _ = visible_grail
        render_grail_sprite(items, width, height, distance, side, static_sprites)

    visible_altar = altar_in_view(grid, px, py, facing)
    if visible_altar is not None:
        distance, side, _ = visible_altar
        render_altar_sprite(items, width, height, distance, side, static_sprites)

    seen_monster = visible_monster(grid, px, py, facing)
    if seen_monster is not None:
        distance, side, _, tile = seen_monster
        render_monster_sprite(items, width, height, distance, side, tile, animated_sprites, static_sprites, animation_step)

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
            elif is_monster(ch):
                info = monster_info(ch if ch in MONSTER_TILES else "R")
                char = str(info["map"])
                attr = curses.color_pair(int(info["color"])) | curses.A_BOLD
            elif ch == QUEST_ITEM_TILE:
                char = "GG"
                attr = curses.color_pair(8) | curses.A_BOLD
            elif ch == QUEST_TARGET_TILE:
                char = "AA"
                attr = curses.color_pair(10) | curses.A_BOLD
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


def inventory_count(state: Dict[str, object]) -> int:
    return 1 if bool(state["has_grail"]) else 0


def can_pick_item(state: Dict[str, object]) -> bool:
    return inventory_count(state) < MAX_CARRIED_ITEMS


def deliver_quest_if_possible(state: Dict[str, object], grid: Grid) -> bool:
    x = int(state["x"])
    y = int(state["y"])
    if (
        cell_at(grid, x, y) == QUEST_TARGET_TILE
        and bool(state["has_grail"])
        and not bool(state["quest_complete"])
        and int(state["floor"]) == QUEST_TARGET_FLOOR
    ):
        state["has_grail"] = False
        state["quest_complete"] = True
        state["show_congrats_banner"] = True
        state["message"] = f"You place the {QUEST_ITEM_NAME} on the altar. Quest complete!"
        return True
    return False


def collect_tile(state: Dict[str, object], grid: Grid) -> None:
    x = int(state["x"])
    y = int(state["y"])
    if cell_at(grid, x, y) == QUEST_ITEM_TILE:
        if can_pick_item(state):
            grid[y][x] = "."
            state["has_grail"] = True
            state["message"] = (
                f"You take the {QUEST_ITEM_NAME}. "
                f"Inventory {inventory_count(state)}/{MAX_CARRIED_ITEMS}. "
                f"Bring it to floor {QUEST_TARGET_FLOOR + 1}."
            )
        else:
            state["message"] = f"Your inventory is full ({inventory_count(state)}/{MAX_CARRIED_ITEMS})."
    else:
        deliver_quest_if_possible(state, grid)


def try_move(state: Dict[str, object], step: int) -> bool:
    grid = current_grid(state)
    dx, dy = DIRECTIONS[int(state["facing"])]
    nx = int(state["x"]) + dx * step
    ny = int(state["y"]) + dy * step
    if is_passable(cell_at(grid, nx, ny)):
        state["x"] = nx
        state["y"] = ny
        collect_tile(state, grid)
        return True
    return False


def try_strafe(state: Dict[str, object], step: int) -> bool:
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
    if is_monster(target):
        has_grail = bool(state["has_grail"])
        cost = ATTACK_COST_WITH_GRAIL if has_grail else ATTACK_COST_NO_GRAIL
        energy = int(state["energy"])
        if energy < cost:
            return "Too tired to fight. Wait to regain some energy."
        state["energy"] = max(0, energy - cost)
        grid[ty][tx] = "."
        state["score"] = int(state["score"]) + 1
        info = monster_info(target if target in MONSTER_TILES else "R")
        return f"{info['defeat']} Energy -{cost}."
    if target == QUEST_ITEM_TILE:
        if not can_pick_item(state):
            return f"Your inventory is full ({inventory_count(state)}/{MAX_CARRIED_ITEMS})."
        grid[ty][tx] = "."
        state["has_grail"] = True
        return f"You take the {QUEST_ITEM_NAME}. Inventory {inventory_count(state)}/{MAX_CARRIED_ITEMS}."
    if target == QUEST_TARGET_TILE:
        if int(state["floor"]) != QUEST_TARGET_FLOOR:
            return "This altar is dormant."
        if bool(state["quest_complete"]):
            return "The altar has already received the grail."
        if bool(state["has_grail"]):
            state["has_grail"] = False
            state["quest_complete"] = True
            state["show_congrats_banner"] = True
            return f"You place the {QUEST_ITEM_NAME} on the altar. Quest complete!"
        return f"You need the {QUEST_ITEM_NAME}."
    if target == ">":
        return travel_stairs(state, 1)
    if target == "<":
        return travel_stairs(state, -1)
    return "Nothing happens."


def use_current_tile(state: Dict[str, object]) -> bool:
    grid = current_grid(state)
    tile = cell_at(grid, int(state["x"]), int(state["y"]))
    if deliver_quest_if_possible(state, grid):
        return True
    if tile == ">":
        state["message"] = travel_stairs(state, 1)
        return True
    if tile == "<":
        state["message"] = travel_stairs(state, -1)
        return True
    return False


def draw_banner_overlay(stdscr, lines: List[str], color: int) -> None:
    height, width = stdscr.getmaxyx()
    box_width = min(width - 4, max(len(line) for line in lines) + 4)
    box_height = min(height - 4, len(lines) + 4)
    left = max(2, (width - box_width) // 2)
    top = max(1, (height - box_height) // 2)

    for y in range(top, top + box_height):
        for x in range(left, left + box_width):
            ch = " "
            if y in {top, top + box_height - 1}:
                ch = "#"
            elif x in {left, left + box_width - 1}:
                ch = "#"
            try:
                stdscr.addch(y, x, ch, curses.color_pair(color) | curses.A_BOLD)
            except curses.error:
                pass

    for index, line in enumerate(lines):
        sy = top + 2 + index
        sx = left + max(2, (box_width - len(line)) // 2)
        if 0 <= sy < height:
            try:
                stdscr.addstr(sy, sx, line[: max(0, width - sx - 1)], curses.color_pair(color) | curses.A_BOLD)
            except curses.error:
                pass


def monster_has_line_of_sight(grid: Grid, mx: int, my: int, px: int, py: int, max_distance: int = 6) -> bool:
    dx = px - mx
    dy = py - my
    if dx == 0 and dy == 0:
        return True
    if dx != 0 and dy != 0:
        return False
    distance = abs(dx) + abs(dy)
    if distance > max_distance:
        return False
    step_x = 0 if dx == 0 else (1 if dx > 0 else -1)
    step_y = 0 if dy == 0 else (1 if dy > 0 else -1)
    x = mx + step_x
    y = my + step_y
    while (x, y) != (px, py):
        if cell_at(grid, x, y) in {"#", "D"}:
            return False
        x += step_x
        y += step_y
    return True


def iter_monsters(grid: Grid) -> List[Tuple[int, int, str]]:
    monsters: List[Tuple[int, int, str]] = []
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if is_monster(cell):
                monsters.append((x, y, cell if cell in MONSTER_TILES else "R"))
    return monsters


def move_monsters(state: Dict[str, object]) -> None:
    grid = current_grid(state)
    px = int(state["x"])
    py = int(state["y"])
    chase_map = state.setdefault("monster_chase", {})
    floor_key = str(int(state["floor"]))
    floor_chase = chase_map.setdefault(floor_key, {})
    seen_names: List[str] = []

    for mx, my, tile in iter_monsters(grid):
        monster_key = f"{mx},{my}"
        if monster_has_line_of_sight(grid, mx, my, px, py):
            floor_chase[monster_key] = MONSTER_CHASE_TURNS
            seen_names.append(str(monster_info(tile)["name"]))

    updated_chase: Dict[str, int] = {}
    occupied = {(x, y) for x, y, _tile in iter_monsters(grid)}

    for mx, my, tile in iter_monsters(grid):
        old_key = f"{mx},{my}"
        chase_turns = int(floor_chase.get(old_key, 0))
        if chase_turns <= 0:
            continue

        moved = False
        options: List[Tuple[int, int, int, int]] = []
        for dx, dy in DIRECTIONS:
            nx = mx + dx
            ny = my + dy
            if (nx, ny) == (px, py):
                continue
            if not is_walkable_for_monster(cell_at(grid, nx, ny)):
                continue
            if (nx, ny) in occupied:
                continue
            distance = abs(px - nx) + abs(py - ny)
            options.append((distance, nx, ny, chase_turns))

        if options:
            options.sort(key=lambda item: item[0])
            _distance, nx, ny, _ = options[0]
            current_distance = abs(px - mx) + abs(py - my)
            if _distance < current_distance:
                grid[my][mx] = "."
                grid[ny][nx] = tile
                occupied.remove((mx, my))
                occupied.add((nx, ny))
                mx, my = nx, ny
                moved = True

        remaining = chase_turns - 1
        if moved and monster_has_line_of_sight(grid, mx, my, px, py):
            remaining = MONSTER_CHASE_TURNS
        if remaining > 0:
            updated_chase[f"{mx},{my}"] = remaining

    chase_map[floor_key] = updated_chase
    if seen_names:
        unique_names = []
        for name in seen_names:
            if name not in unique_names:
                unique_names.append(name)
        if len(unique_names) == 1:
            state["message"] = f"A {unique_names[0]} spots you!"
        else:
            state["message"] = "Monsters spot you!"


def advance_world(state: Dict[str, object]) -> None:
    move_monsters(state)
    use_current_tile(state)


def draw_scene(stdscr, state: Dict[str, object]) -> None:
    grid = current_grid(state)
    height, width = stdscr.getmaxyx()
    stdscr.erase()

    title = "Dungeona - Holy Grail Quest"
    energy = int(state["energy"])
    filled = max(0, min(MAX_ENERGY, energy))
    empty = max(0, MAX_ENERGY - filled)
    health_bar = "[" + ("#" * filled) + ("-" * empty) + "]"
    quest_status = "done" if bool(state["quest_complete"]) else ("carrying" if bool(state["has_grail"]) else "missing")
    status = (
        f" {health_bar} {energy}/{MAX_ENERGY}"
        f" floor:{int(state['floor']) + 1}/{len(state['floors'])}"
        f" pos:{state['x']},{state['y']} facing:{DIRECTION_NAMES[int(state['facing'])]}"
        f" items:{inventory_count(state)}/{MAX_CARRIED_ITEMS} grail:{quest_status} defeated:{state['score']} "
    )
    help_text = " arrows/WASD move | q/e turn | z/c strafe | space act | . wait | m map | x quit | quest: take grail to altar "
    view_height = max(6, height - 3)

    if width > len(title) + 2:
        try:
            stdscr.addstr(0, max(0, (width - len(title)) // 2), title, curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass

    for y, x, ch, color in render_view(
        grid,
        int(state["x"]),
        int(state["y"]),
        int(state["facing"]),
        width,
        view_height,
        state.get("wall_textures"),
        state.get("floor_texture"),
        state.get("ceiling_texture"),
        state.get("animated_sprites"),
        state.get("static_sprites"),
        int(state.get("action_count", 0)),
    ):
        if 1 <= y < height - 3 and 0 <= x < width:
            try:
                attr = curses.color_pair(color)
                if color in (2, 3, 7, 8, 9, 10):
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

    if bool(state.get("show_congrats_banner")):
        draw_banner_overlay(stdscr, CONGRATS_BANNER, 8)


def find_start_position(floors: List[Grid]) -> Tuple[int, int, int]:
    for floor_index, grid in enumerate(floors):
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell in {".", QUEST_ITEM_TILE, "<", ">", " ", QUEST_TARGET_TILE} or is_monster(cell):
                    return floor_index, x, y
    return 0, 1, 1


def run(stdscr) -> int:
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)
    setup_colors()

    floors = load_floors()
    start_floor, start_x, start_y = find_start_position(floors)
    wall_textures = load_wall_textures()
    floor_texture = load_surface_texture(FLOOR_TEXTURE_FILE)
    ceiling_texture = load_surface_texture(CEILING_TEXTURE_FILE)
    animated_sprites = load_animated_sprites()
    static_sprites = load_static_sprites()
    state: Dict[str, object] = {
        "floors": floors,
        "floor": start_floor,
        "x": start_x,
        "y": start_y,
        "facing": 1,
        "energy": START_ENERGY,
        "score": 0,
        "has_grail": False,
        "quest_complete": False,
        "show_map": True,
        "message": f"Loaded dungeon from {DB_PATH.name}. Find the {QUEST_ITEM_NAME} on floor {QUEST_START_FLOOR + 1} and bring it to the altar on floor {QUEST_TARGET_FLOOR + 1}. Beware of rats, skeletons, and ogres.",
        "show_congrats_banner": False,
        "wall_textures": wall_textures,
        "floor_texture": floor_texture,
        "ceiling_texture": ceiling_texture,
        "animated_sprites": animated_sprites,
        "static_sprites": static_sprites,
        "action_count": 0,
        "monster_chase": {},
    }
    collect_tile(state, current_grid(state))

    while True:
        draw_scene(stdscr, state)
        stdscr.refresh()
        key = stdscr.getch()

        if bool(state.get("show_congrats_banner")):
            state["show_congrats_banner"] = False
            if key in (ord("x"), ord("X")):
                break
            continue

        acted = False
        if key in (ord("x"), ord("X")):
            break
        if key in (ord("q"), ord("Q")):
            state["facing"] = (int(state["facing"]) - 1) % 4
            state["message"] = "You turn left."
            acted = True
        elif key in (ord("e"), ord("E")):
            state["facing"] = (int(state["facing"]) + 1) % 4
            state["message"] = "You turn right."
            acted = True
        elif key in (curses.KEY_UP, ord("w"), ord("W")):
            old_pos = (state["x"], state["y"])
            try_move(state, 1)
            state["message"] = "You move forward." if old_pos != (state["x"], state["y"]) else "A wall blocks your way."
            acted = True
        elif key in (curses.KEY_DOWN, ord("s"), ord("S")):
            old_pos = (state["x"], state["y"])
            try_move(state, -1)
            state["message"] = "You move backward." if old_pos != (state["x"], state["y"]) else "You cannot move there."
            acted = True
        elif key in (ord("z"), ord("Z")):
            old_pos = (state["x"], state["y"])
            try_strafe(state, -1)
            state["message"] = "You sidestep left." if old_pos != (state["x"], state["y"]) else "Blocked on the left."
            acted = True
        elif key in (ord("c"), ord("C")):
            old_pos = (state["x"], state["y"])
            try_strafe(state, 1)
            state["message"] = "You sidestep right." if old_pos != (state["x"], state["y"]) else "Blocked on the right."
            acted = True
        elif key in (ord("m"), ord("M")):
            state["show_map"] = not bool(state["show_map"])
            state["message"] = f"Map {'shown' if state['show_map'] else 'hidden'}."
            acted = True
        elif key in (ord("."),):
            state["energy"] = min(MAX_ENERGY, int(state["energy"]) + WAIT_ENERGY_GAIN)
            state["message"] = "You wait and regain a little energy."
            acted = True
        elif key in (ord(" "), ord("\n")):
            state["message"] = use_action(state)
            acted = True
        elif key == ord(">"):
            state["message"] = travel_stairs(state, 1)
            acted = True
        elif key == ord("<"):
            state["message"] = travel_stairs(state, -1)
            acted = True

        if acted:
            state["action_count"] = int(state.get("action_count", 0)) + 1
            advance_world(state)

    return 0


def main() -> int:
    initialize_map_db(DB_PATH)
    return curses.wrapper(run)


if __name__ == "__main__":
    raise SystemExit(main())
