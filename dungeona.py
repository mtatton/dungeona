import curses
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

Vec2 = Tuple[int, int]
DrawItem = Tuple[int, int, str, int]

DB_PATH = Path(__file__).with_name('dungeon_map.db')
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
MAX_RENDER_DEPTH = 12.0
FOV_SCALE = 0.85
START_ENERGY = 12
MAX_ENERGY = 12
ATTACK_COST_WITH_SWORD = 1
ATTACK_COST_NO_SWORD = 2
ENEMY_DAMAGE_WITH_SWORD = 1
ENEMY_DAMAGE_NO_SWORD = 3
WAIT_ENERGY_GAIN = 1


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def initialize_map_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'CREATE TABLE IF NOT EXISTS map_rows ('
            'row_index INTEGER PRIMARY KEY, '
            'row_text TEXT NOT NULL'
            ')'
        )
        count = conn.execute('SELECT COUNT(*) FROM map_rows').fetchone()[0]
        if count == 0:
            conn.executemany(
                'INSERT INTO map_rows (row_index, row_text) VALUES (?, ?)',
                list(enumerate(DEFAULT_MAP_DATA)),
            )
        conn.commit()


def load_map_data(db_path: Path = DB_PATH) -> List[str]:
    initialize_map_db(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            'SELECT row_text FROM map_rows ORDER BY row_index'
        ).fetchall()
    map_data = [row[0] for row in rows if row and row[0]]
    return map_data or list(DEFAULT_MAP_DATA)


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


def is_inside(x: int, y: int, grid: List[List[str]]) -> bool:
    return 0 <= y < len(grid) and 0 <= x < len(grid[y])


def cell_at(grid: List[List[str]], x: int, y: int) -> str:
    if not is_inside(x, y, grid):
        return '#'
    return grid[y][x]


def is_passable(cell: str) -> bool:
    return cell in {'.', ' ', 'S', 'M'}


def facing_vector(facing: int) -> Tuple[float, float]:
    dx, dy = DIRECTIONS[facing]
    return float(dx), float(dy)


def cast_perspective_ray(
    grid: List[List[str]],
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
        if cell in {'#', 'D'}:
            if side == 0:
                distance = (map_x - origin_x + (1 - step_x) / 2.0) / (dir_x if abs(dir_x) > 1e-9 else 1e-9)
            else:
                distance = (map_y - origin_y + (1 - step_y) / 2.0) / (dir_y if abs(dir_y) > 1e-9 else 1e-9)
            return max(0.001, distance), cell, side

        approx_distance = min(side_dist_x, side_dist_y)
        if approx_distance > max_depth:
            return max_depth, ' ', side


def wall_char(distance: float, side: int, cell: str) -> str:
    if cell == 'D':
        return '+' if side == 0 else '|'
    if cell == 'M':
        return 'M'
    if cell == 'S':
        return '/'
    shades = "█▓▒░."
    index = min(len(shades) - 1, int(distance * 0.55) + side)
    return shades[index]


def floor_char(row: int, horizon: int, height: int) -> str:
    if row <= horizon:
        return ' '
    ratio = (row - horizon) / max(1, height - horizon - 1)
    if ratio < 0.18:
        return '_'
    if ratio < 0.40:
        return '.'
    if ratio < 0.68:
        return ','
    return '`'


def find_nearest_walkable(grid: List[List[str]], x: int, y: int) -> Optional[Vec2]:
    if is_passable(cell_at(grid, x, y)) and cell_at(grid, x, y) != 'M':
        return x, y
    max_radius = max(len(grid), max((len(row) for row in grid), default=0))
    for radius in range(1, max_radius + 1):
        for ny in range(y - radius, y + radius + 1):
            for nx in range(x - radius, x + radius + 1):
                if abs(nx - x) + abs(ny - y) != radius:
                    continue
                if is_passable(cell_at(grid, nx, ny)) and cell_at(grid, nx, ny) != 'M':
                    return nx, ny
    return None


def normalize_enemies(grid: List[List[str]]) -> None:
    enemies: List[Vec2] = []
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell == 'M':
                enemies.append((x, y))
                grid[y][x] = '.'

    used: set[Vec2] = set()
    for x, y in enemies:
        target = find_nearest_walkable(grid, x, y)
        if target is None:
            continue
        if target in used:
            alternative = None
            tx, ty = target
            for radius in range(1, max(len(grid), max((len(row) for row in grid), default=0)) + 1):
                found = False
                for ny in range(ty - radius, ty + radius + 1):
                    for nx in range(tx - radius, tx + radius + 1):
                        pos = (nx, ny)
                        if pos in used:
                            continue
                        if is_passable(cell_at(grid, nx, ny)) and cell_at(grid, nx, ny) != 'M':
                            alternative = pos
                            found = True
                            break
                    if found:
                        break
                if found:
                    break
            target = alternative
        if target is None:
            continue
        used.add(target)
        tx, ty = target
        grid[ty][tx] = 'M'


def find_visible_tile(grid: List[List[str]], px: int, py: int, facing: int, tile: str) -> Optional[Tuple[int, int, int]]:
    dx, dy = DIRECTIONS[facing]
    rx, ry = -dy, dx
    for distance in range(1, 6):
        cx = px + dx * distance
        cy = py + dy * distance
        center = cell_at(grid, cx, cy)
        if center == '#':
            return None
        if center == 'D':
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


def enemy_in_view(grid: List[List[str]], px: int, py: int, facing: int) -> Optional[Tuple[int, int, int]]:
    return find_visible_tile(grid, px, py, facing, 'M')


def sword_in_view(grid: List[List[str]], px: int, py: int, facing: int) -> Optional[Tuple[int, int, int]]:
    return find_visible_tile(grid, px, py, facing, 'S')


def render_enemy_sprite(items: List[DrawItem], width: int, height: int, distance: int, side: int) -> None:
    perspective_scale = max(0.55, 2.4 / (distance + 0.35))
    if side == 0:
        perspective_scale *= 1.15
    else:
        perspective_scale *= 0.72

    center_x = width // 2 + side * max(3, width // max(8, 9 + distance * 2))
    floor_y = height - 4
    sprite = [
        '  M  ',
        ' /#\\ ',
        '/###\\',
        ' / \\',
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
            if ch != ' ':
                items.append((sy, start_x + target_col, ch, 7))


def render_sword_sprite(items: List[DrawItem], width: int, height: int, distance: int, side: int) -> None:
    perspective_scale = max(0.45, 2.0 / (distance + 0.2))
    if side == 0:
        perspective_scale *= 1.18
    else:
        perspective_scale *= 0.72

    center_x = width // 2 + side * max(2, width // max(10, 11 + distance * 2))
    floor_y = height - 4
    sprite = [
        '  /  ',
        ' /   ',
        '/    ',
        '||== ',
        '||   ',
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
            if ch != ' ':
                items.append((sy, start_x + target_col, ch, 8))


def render_view(grid: List[List[str]], px: int, py: int, facing: int, width: int, height: int) -> List[DrawItem]:
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

        if cell == ' ':
            continue

        line_height = int((height * 0.92) / max(0.001, distance))
        draw_start = max(1, horizon - line_height // 2)
        draw_end = min(height - 3, horizon + line_height // 2)
        char = wall_char(distance, side, cell)
        color = 2 if cell == 'D' else 7 if cell == 'M' else 8 if cell == 'S' else 1

        for y in range(draw_start, draw_end + 1):
            draw_char = char
            if cell == 'D':
                mid = (draw_start + draw_end) // 2
                if abs(y - mid) <= max(1, line_height // 10):
                    draw_char = '='
                elif x % 2 == 0:
                    draw_char = '|'
            elif side == 1 and draw_char in {'█', '▓', '▒'}:
                draw_char = {'█': '▓', '▓': '▒', '▒': '░'}.get(draw_char, draw_char)
            items.append((y, x, draw_char, color))

        ceiling_limit = max(1, draw_start - 1)
        if ceiling_limit > 1 and x % 3 == 0:
            items.append((ceiling_limit, x, '_', 4))

    visible_sword = sword_in_view(grid, px, py, facing)
    if visible_sword is not None:
        distance, side, _ = visible_sword
        render_sword_sprite(items, width, height, distance, side)

    visible_enemy = enemy_in_view(grid, px, py, facing)
    if visible_enemy is not None:
        distance, side, _ = visible_enemy
        render_enemy_sprite(items, width, height, distance, side)

    return items


def draw_minimap(stdscr, grid: List[List[str]], px: int, py: int, facing: int, top: int, left: int) -> None:
    view_radius = 4
    for dy in range(-view_radius, view_radius + 1):
        for dx in range(-view_radius, view_radius + 1):
            mx = px + dx
            my = py + dy
            ch = cell_at(grid, mx, my)
            sy = top + dy + view_radius
            sx = left + (dx + view_radius) * 2
            if ch == '#':
                char = '##'
                attr = curses.color_pair(5)
            elif ch == 'D':
                char = '[]'
                attr = curses.color_pair(2) | curses.A_BOLD
            elif ch == 'M':
                char = 'MM'
                attr = curses.color_pair(7) | curses.A_BOLD
            elif ch == 'S':
                char = '/='
                attr = curses.color_pair(8) | curses.A_BOLD
            else:
                char = '  '
                attr = curses.color_pair(4)
            try:
                stdscr.addstr(sy, sx, char, attr)
            except curses.error:
                pass

    arrow = ['^', '>', 'v', '<'][facing]
    try:
        stdscr.addstr(top + view_radius, left + view_radius * 2, arrow, curses.color_pair(6) | curses.A_BOLD)
    except curses.error:
        pass


def collect_tile(state: Dict[str, int | str], grid: List[List[str]]) -> None:
    x = int(state['x'])
    y = int(state['y'])
    if cell_at(grid, x, y) == 'S':
        grid[y][x] = '.'
        state['has_sword'] = 1
        state['message'] = 'You take the sword. Fighting is now easier.'


def try_move(state: Dict[str, int | str], grid: List[List[str]], step: int) -> None:
    dx, dy = DIRECTIONS[int(state['facing'])]
    nx = int(state['x']) + dx * step
    ny = int(state['y']) + dy * step
    if is_passable(cell_at(grid, nx, ny)):
        state['x'] = nx
        state['y'] = ny
        collect_tile(state, grid)


def try_strafe(state: Dict[str, int | str], grid: List[List[str]], step: int) -> None:
    facing = int(state['facing'])
    side = (facing + step) % 4
    dx, dy = DIRECTIONS[side]
    nx = int(state['x']) + dx
    ny = int(state['y']) + dy
    if is_passable(cell_at(grid, nx, ny)):
        state['x'] = nx
        state['y'] = ny
        collect_tile(state, grid)


def use_action(state: Dict[str, int | str], grid: List[List[str]]) -> str:
    dx, dy = DIRECTIONS[int(state['facing'])]
    tx = int(state['x']) + dx
    ty = int(state['y']) + dy
    target = cell_at(grid, tx, ty)
    if target == 'D':
        grid[ty][tx] = '.'
        return 'You open the door.'
    if target == 'M':
        has_sword = bool(state['has_sword'])
        cost = ATTACK_COST_WITH_SWORD if has_sword else ATTACK_COST_NO_SWORD
        energy = int(state['energy'])
        if energy < cost:
            return 'Too tired to fight. Wait to regain some energy.'
        state['energy'] = max(0, energy - cost)
        grid[ty][tx] = '.'
        state['score'] = int(state['score']) + 1
        return f'You defeat the enemy. Energy -{cost}.'
    if target == 'S':
        grid[ty][tx] = '.'
        state['has_sword'] = 1
        return 'You take the sword.'
    return 'Nothing happens.'


def draw_scene(stdscr, grid: List[List[str]], state: Dict[str, int | str]) -> None:
    height, width = stdscr.getmaxyx()
    stdscr.erase()

    title = ' ANSI Dungeon - perspective crawler view '
    energy = int(state['energy'])
    filled = max(0, min(MAX_ENERGY, energy))
    empty = max(0, MAX_ENERGY - filled)
    health_bar = '[' + ('#' * filled) + ('-' * empty) + ']'
    status = (
        f" {health_bar} {energy}/{MAX_ENERGY}"
        f" pos:{state['x']},{state['y']} facing:{DIRECTION_NAMES[int(state['facing'])]}"
        f" sword:{'yes' if bool(state['has_sword']) else 'no'} defeated:{state['score']} "
    )
    help_text = ' arrows/WASD move | q/e turn | z/c strafe | space act/fight | . wait | m map | x quit '
    view_height = max(6, height - 3)

    if width > len(title) + 2:
        try:
            stdscr.addstr(0, max(0, (width - len(title)) // 2), title, curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass

    for y, x, ch, color in render_view(grid, int(state['x']), int(state['y']), int(state['facing']), width, view_height):
        if 1 <= y < height - 3 and 0 <= x < width:
            try:
                attr = curses.color_pair(color)
                if color in (2, 3):
                    attr |= curses.A_BOLD
                stdscr.addch(y, x, ch, attr)
            except curses.error:
                pass

    if bool(state['show_map']):
        draw_minimap(stdscr, grid, int(state['x']), int(state['y']), int(state['facing']), 2, 2)

    try:
        stdscr.addstr(height - 2, 1, status[: max(0, width - 2)], curses.color_pair(4) | curses.A_BOLD)
    except curses.error:
        pass
    try:
        stdscr.addstr(height - 1, 1, (help_text + str(state['message']))[: max(0, width - 2)], curses.color_pair(3))
    except curses.error:
        pass

    stdscr.refresh()


def run(stdscr) -> int:
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)
    setup_colors()

    grid = [list(row) for row in load_map_data()]
    normalize_enemies(grid)
    state: Dict[str, int | str] = {
        'x': 1,
        'y': 1,
        'facing': 1,
        'show_map': 1,
        'message': 'Find the sword, then defeat enemies. Keep your energy up.',
        'energy': START_ENERGY,
        'has_sword': 0,
        'score': 0,
        'alive': 1,
    }

    while True:
        draw_scene(stdscr, grid, state)
        key = stdscr.getch()
        state['message'] = ''

        if not bool(state['alive']):
            break

        if key in (ord('x'), ord('X')):
            break
        elif key in (ord('q'), ord('Q')):
            state['facing'] = (int(state['facing']) - 1) % 4
        elif key in (ord('e'), ord('E')):
            state['facing'] = (int(state['facing']) + 1) % 4
        elif key in (curses.KEY_UP, ord('w'), ord('W')):
            try_move(state, grid, 1)
        elif key in (curses.KEY_DOWN, ord('s'), ord('S')):
            try_move(state, grid, -1)
        elif key in (ord('z'), ord('Z')):
            try_strafe(state, grid, -1)
        elif key in (ord('c'), ord('C')):
            try_strafe(state, grid, 1)
        elif key == ord(' '):
            state['message'] = use_action(state, grid)
        elif key in (ord('.'), ord(',')):
            previous = int(state['energy'])
            state['energy'] = min(MAX_ENERGY, previous + WAIT_ENERGY_GAIN)
            if int(state['energy']) > previous:
                state['message'] = 'You wait and regain a little energy.'
            else:
                state['message'] = 'You wait and feel fully rested.'
        elif key in (ord('m'), ord('M')):
            state['show_map'] = 0 if bool(state['show_map']) else 1

    return 0


def main() -> int:
    return curses.wrapper(run)


if __name__ == '__main__':
    raise SystemExit(main())
