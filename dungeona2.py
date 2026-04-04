#!/usr/bin/env python3
"""Pygame/SDL frontend for Dungeona.

This frontend reuses the dungeon rules from ``dungeona.py`` and the ANSI
texture parser from ``ans.py``. It renders the pseudo-3D view into a low-
resolution software surface and scales it up for a chunky retro look.

Controls
--------
W / Up       move forward
S / Down     move backward
Q / E        turn left / right
Z / C        strafe left / right
Space / Enter interact / attack / open
.            wait and regain energy
M            toggle minimap
< / >        use stairs
X / Esc      quit
"""

from __future__ import annotations

import argparse
import math
from typing import Dict, List, Optional, Tuple

import dungeona
from ans import AnsiCell, AnsiTexture

try:  # pragma: no cover - runtime dependency check
    import pygame
except Exception:  # pragma: no cover - pygame is optional until runtime
    pygame = None  # type: ignore[assignment]

RGB = Tuple[int, int, int]

BACKGROUND: RGB = (10, 12, 15)
STATUS_BG: RGB = (16, 20, 25)
TEXT_COLOR: RGB = (216, 222, 233)
SUBTLE_TEXT: RGB = (127, 139, 151)
MAP_PANEL_BG: RGB = (11, 15, 20)
MAP_PANEL_BORDER: RGB = (44, 55, 66)
PLAYER_COLOR: RGB = (72, 176, 96)
CROSSHAIR_COLOR: RGB = (52, 64, 77)

COLOR_MAP: Dict[int, RGB] = {
    1: (88, 98, 112),
    2: (181, 138, 59),
    3: (79, 167, 191),
    4: (78, 70, 62),
    5: (92, 102, 112),
    6: (69, 168, 90),
    7: (180, 81, 81),
    8: (201, 178, 74),
    9: (111, 149, 200),
    10: (143, 93, 176),
}

ANSI_RGB: Dict[str, RGB] = {
    "Bk": (0, 0, 0),
    "Re": (170, 0, 0),
    "Gr": (0, 170, 0),
    "Ye": (170, 85, 0),
    "Bl": (0, 0, 170),
    "Ma": (170, 0, 170),
    "Cy": (0, 170, 170),
    "Wh": (170, 170, 170),
}

BRIGHT_ANSI_RGB: Dict[str, RGB] = {
    "Bk": (85, 85, 85),
    "Re": (255, 85, 85),
    "Gr": (85, 255, 85),
    "Ye": (255, 255, 85),
    "Bl": (85, 85, 255),
    "Ma": (255, 85, 255),
    "Cy": (85, 255, 255),
    "Wh": (255, 255, 255),
}

DARK_ANSI_RGB: Dict[str, RGB] = {
    "Bk": (0, 0, 0),
    "Re": (85, 0, 0),
    "Gr": (0, 85, 0),
    "Ye": (85, 51, 0),
    "Bl": (0, 0, 85),
    "Ma": (85, 0, 85),
    "Cy": (0, 85, 85),
    "Wh": (85, 85, 85),
}

KEY_HELP = "Mouse look  WASD/arrows move  Q/E turn  Space act  . wait  M map  </> stairs  Tab mouse  X quit"


class Dungeona2:
    def __init__(self, width: int = 1280, height: int = 800, *, fullscreen: bool = False, fps: int = 30) -> None:
        if pygame is None:  # pragma: no cover - guarded for runtime only
            raise RuntimeError("pygame is not installed. Install it with: pip install pygame")

        pygame.init()
        pygame.font.init()

        flags = pygame.RESIZABLE
        if fullscreen:
            flags |= pygame.FULLSCREEN

        self.fps = max(15, fps)
        self.screen = pygame.display.set_mode((max(800, width), max(600, height)), flags)
        pygame.display.set_caption("Dungeona2")
        self.clock = pygame.time.Clock()

        self.window_width = max(800, width)
        self.window_height = max(600, height)
        self.status_height = 108
        self.view_rect = (0, 0, self.window_width, self.window_height - self.status_height)
        self.view_width_cells = 160
        self.view_height_cells = 96
        self.view_surface: Optional["pygame.Surface"] = None

        self.texture_fill_cache: Dict[Tuple[object, ...], Tuple[Tuple[Optional[RGB], ...], ...]] = {}
        self.trimmed_texture_cache: Dict[Tuple[object, ...], Tuple[Tuple[AnsiCell, ...], ...]] = {}
        self.glyph_cache: Dict[Tuple[str, RGB, int, int], "pygame.Surface"] = {}
        self.sprite_font_cache: Dict[int, "pygame.font.Font"] = {}
        self.mouse_sensitivity = 0.0084
        self.mouse_captured = True
        self._ignore_mousemotion_events = 0
        self.view_angle = 0.0
        self.view_pitch = 0.0
        self.max_view_pitch = 0.90
        self.max_head_yaw = math.radians(72.0)
        self.ansi_sprite_assets = self.load_ansi_sprite_assets()
        self.resize(self.window_width, self.window_height)

        floors = dungeona.load_floors()
        start_floor, start_x, start_y = dungeona.find_start_position(floors)
        self.state: Dict[str, object] = {
            "floors": floors,
            "floor": start_floor,
            "x": start_x,
            "y": start_y,
            "facing": 1,
            "energy": dungeona.START_ENERGY,
            "score": 0,
            "has_grail": False,
            "quest_complete": False,
            "show_map": True,
            "message": (
                f"Find the {dungeona.QUEST_ITEM_NAME} on floor {dungeona.QUEST_START_FLOOR + 1} "
                f"and bring it to the altar on floor {dungeona.QUEST_TARGET_FLOOR + 1}."
            ),
            "show_congrats_banner": False,
            "wall_textures": dungeona.load_wall_textures(),
            "floor_texture": dungeona.load_surface_texture(dungeona.FLOOR_TEXTURE_FILE),
            "ceiling_texture": dungeona.load_surface_texture(dungeona.CEILING_TEXTURE_FILE),
            "animated_sprites": dungeona.load_animated_sprites(),
            "action_count": 0,
            "monster_chase": {},
        }
        self.view_angle = self.facing_to_angle(int(self.state["facing"]))
        self.set_mouse_capture(True)
        dungeona.collect_tile(self.state, dungeona.current_grid(self.state))

    # ---------- color and texture helpers ----------
    def resize(self, width: int, height: int) -> None:
        self.window_width = max(800, width)
        self.window_height = max(600, height)
        self.status_height = max(104, min(156, int(self.window_height * 0.16)))
        self.view_rect = (0, 0, self.window_width, self.window_height - self.status_height)

        target_w = max(112, min(220, self.window_width // 6))
        target_h = max(64, min(140, self.view_rect[3] // 6))
        self.view_width_cells = target_w
        self.view_height_cells = target_h
        self.view_surface = pygame.Surface((self.view_width_cells, self.view_height_cells))

        small_size = max(14, min(18, self.window_width // 72))
        medium_size = max(18, min(24, self.window_width // 58))
        title_size = max(22, min(32, self.window_width // 42))
        mono_names = ["Consolas", "DejaVu Sans Mono", "Menlo", "Monaco", "Courier New"]
        self.font_small = pygame.font.SysFont(mono_names, small_size)
        self.font_medium = pygame.font.SysFont(mono_names, medium_size)
        self.font_medium_bold = pygame.font.SysFont(mono_names, medium_size, bold=True)
        self.font_title = pygame.font.SysFont(mono_names, title_size, bold=True)

    def color_for(self, color_id: int, default: RGB = (207, 207, 207)) -> RGB:
        return COLOR_MAP.get(color_id, default)

    def shade_color(self, color: RGB, factor: float) -> RGB:
        return (
            max(0, min(255, int(color[0] * factor))),
            max(0, min(255, int(color[1] * factor))),
            max(0, min(255, int(color[2] * factor))),
        )

    def blend_colors(self, low: RGB, high: RGB, high_weight: float) -> RGB:
        high_weight = max(0.0, min(1.0, high_weight))
        low_weight = 1.0 - high_weight
        return (
            int(low[0] * low_weight + high[0] * high_weight),
            int(low[1] * low_weight + high[1] * high_weight),
            int(low[2] * low_weight + high[2] * high_weight),
        )

    def floor_band_color(self, row: int) -> RGB:
        ratio = row / max(1, self.view_height_cells - 1)
        if ratio < 0.58:
            return (17, 22, 28)
        depth = max(0.0, min(1.0, (ratio - 0.58) / 0.42))
        base = (28, 24, 21)
        boost = int(24 * (1.0 - depth))
        return (
            min(255, base[0] + boost),
            min(255, base[1] + boost),
            min(255, base[2] + boost),
        )

    def ansi_color_to_rgb(self, color_name: str, intensity: str = "me") -> RGB:
        if intensity == "hi":
            return BRIGHT_ANSI_RGB.get(color_name, ANSI_RGB["Wh"])
        if intensity == "lo":
            return DARK_ANSI_RGB.get(color_name, ANSI_RGB["Wh"])
        return ANSI_RGB.get(color_name, ANSI_RGB["Wh"])

    def texture_cell_fill(self, cell: AnsiCell) -> Optional[RGB]:
        ch = cell.char
        fg = self.ansi_color_to_rgb(cell.fg, cell.intensity)
        bg = self.ansi_color_to_rgb(cell.bg, "me")
        if ch == " ":
            return bg
        if ch in {"█", "■"}:
            return fg
        if ch in {"▀", "▄"}:
            return self.blend_colors(bg, fg, 0.50)
        if ch == "▓":
            return self.blend_colors(bg, fg, 0.72)
        if ch == "▒":
            return self.blend_colors(bg, fg, 0.50)
        if ch == "░":
            return self.blend_colors(bg, fg, 0.28)
        if ch in {".", ",", "`", "_"}:
            return self.blend_colors(bg, fg, 0.20)
        return fg

    def texture_identity(self, texture: Optional[AnsiTexture]) -> Optional[Tuple[object, ...]]:
        if texture is None:
            return None
        return (
            getattr(texture, "source_path", None),
            texture.width,
            texture.height,
            id(texture),
        )

    def texture_fill_rows(self, texture: Optional[AnsiTexture]) -> Optional[Tuple[Tuple[Optional[RGB], ...], ...]]:
        texture_id = self.texture_identity(texture)
        if texture_id is None:
            return None
        cached = self.texture_fill_cache.get(texture_id)
        if cached is not None:
            return cached
        assert texture is not None
        rows = tuple(tuple(self.texture_cell_fill(cell) for cell in row) for row in texture.rows)
        self.texture_fill_cache[texture_id] = rows
        return rows

    def make_text_texture(self, lines: List[str], *, fg: str = "Wh", bg: str = "Bk", intensity: str = "hi") -> AnsiTexture:
        width = max((len(line) for line in lines), default=1)
        rows: List[List[AnsiCell]] = []
        for line in lines:
            row = [AnsiCell(char=ch, fg=fg, bg=bg, intensity=intensity) for ch in line.ljust(width)]
            rows.append(row)
        return AnsiTexture(width=width, height=len(rows), rows=rows)

    def load_ansi_sprite_assets(self) -> Dict[str, object]:
        def load_one(filename: str) -> Optional[AnsiTexture]:
            return dungeona.load_surface_texture(filename)

        rat_frames = [
            texture
            for texture in (load_one(filename) for filename in dungeona.RAT_ANIMATION_FILES)
            if texture is not None
        ]
        return {
            "rat": rat_frames,
            "ogre": load_one("ogre.ans"),
            "skeleton": load_one("skeleton.ans"),
            "grail": load_one("grail.ans"),
            "altar": load_one("altar.ans"),
            "stairs_up": self.make_text_texture([" _   ", " __  ", " ___ ", "_____"], fg="Cy", intensity="hi"),
            "stairs_down": self.make_text_texture(["_____", " ___ ", "  __ ", "   _ "], fg="Cy", intensity="hi"),
        }

    def trimmed_texture_rows(self, texture: Optional[AnsiTexture]) -> Tuple[Tuple[AnsiCell, ...], ...]:
        texture_id = self.texture_identity(texture)
        if texture_id is None or texture is None:
            return ()
        cached = self.trimmed_texture_cache.get(texture_id)
        if cached is not None:
            return cached

        min_x = texture.width
        min_y = texture.height
        max_x = -1
        max_y = -1
        for y, row in enumerate(texture.rows):
            for x, cell in enumerate(row):
                if cell.char != " " or cell.bg != "Bk":
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)

        if max_x < min_x or max_y < min_y:
            trimmed: Tuple[Tuple[AnsiCell, ...], ...] = ()
        else:
            trimmed = tuple(
                tuple(texture.rows[y][x] for x in range(min_x, max_x + 1))
                for y in range(min_y, max_y + 1)
            )

        self.trimmed_texture_cache[texture_id] = trimmed
        return trimmed

    def sprite_font(self, pixel_height: int) -> "pygame.font.Font":
        size = max(8, pixel_height)
        cached = self.sprite_font_cache.get(size)
        if cached is not None:
            return cached
        mono_names = ["Consolas", "DejaVu Sans Mono", "Menlo", "Monaco", "Courier New"]
        font = pygame.font.SysFont(mono_names, size, bold=True)
        self.sprite_font_cache[size] = font
        return font

    def glyph_surface(self, ch: str, color: RGB, width: int, height: int) -> "pygame.Surface":
        key = (ch, color, max(1, width), max(1, height))
        cached = self.glyph_cache.get(key)
        if cached is not None:
            return cached

        font = self.sprite_font(max(8, int(height * 1.35)))
        rendered = font.render(ch, False, color)
        glyph = pygame.transform.scale(rendered, (max(1, width), max(1, height))).convert_alpha()
        self.glyph_cache[key] = glyph
        return glyph

    def sprite_face_color(self, cell: AnsiCell, brightness: float) -> RGB:
        return self.shade_color(self.ansi_color_to_rgb(cell.fg, cell.intensity), brightness)

    def sprite_shadow_color(self, face_color: RGB, depth_step: int, depth_total: int) -> RGB:
        layer_mix = 0.10 + 0.16 * ((depth_total - depth_step + 1) / max(1, depth_total))
        return self.blend_colors((0, 0, 0), face_color, layer_mix)

    def monster_texture(self, monster_tile: str, animation_step: int) -> Optional[AnsiTexture]:
        info = dungeona.monster_info(monster_tile)
        name = str(info["name"])
        if name == "rat":
            rat_frames = self.ansi_sprite_assets.get("rat")
            if isinstance(rat_frames, list) and rat_frames:
                return rat_frames[animation_step % len(rat_frames)]
        texture = self.ansi_sprite_assets.get(name)
        return texture if isinstance(texture, AnsiTexture) else None

    def draw_ansi_texture_billboard(
        self,
        texture: Optional[AnsiTexture],
        *,
        distance: int,
        side: float,
        base_scale: float,
        distance_bias: float,
        min_scale: float,
        side_scale: float,
        center_scale: float = 1.0,
        width_scale_front: float = 1.0,
        width_scale_side: float = 0.82,
        opaque_black_background: bool = False,
    ) -> None:
        trimmed_rows = self.trimmed_texture_rows(texture)
        if not trimmed_rows:
            return

        cell_rows = len(trimmed_rows)
        cell_cols = max(len(row) for row in trimmed_rows)
        perspective_scale = max(min_scale, base_scale / (distance + distance_bias))
        side_abs = min(1.0, abs(side))
        center_mix = 1.0 - side_abs
        perspective_scale *= side_scale + (center_scale - side_scale) * center_mix
        center_x_logic = self.view_width_cells // 2 + int(round(side * self.view_width_cells * 0.33))
        floor_y_logic = self.view_height_cells - 4 + self.view_pitch_cells()
        sprite_height_logic = max(3, int(round(cell_rows * perspective_scale)))
        width_scale = width_scale_side + (width_scale_front - width_scale_side) * center_mix
        sprite_width_logic = max(3, int(round(cell_cols * perspective_scale * width_scale)))
        sprite_left_logic = center_x_logic - sprite_width_logic / 2.0
        sprite_top_logic = floor_y_logic - sprite_height_logic + 1

        vx, vy, vw, vh = self.view_rect
        sprite_w_px = max(cell_cols, int(round(sprite_width_logic * vw / max(1, self.view_width_cells))))
        sprite_h_px = max(cell_rows, int(round(sprite_height_logic * vh / max(1, self.view_height_cells))))
        cell_w = max(2, sprite_w_px // cell_cols)
        cell_h = max(2, sprite_h_px // cell_rows)
        actual_w = cell_w * cell_cols
        actual_h = cell_h * cell_rows

        screen_x = vx + int(round(sprite_left_logic * vw / max(1, self.view_width_cells)))
        screen_y = vy + int(round(sprite_top_logic * vh / max(1, self.view_height_cells)))
        screen_x += (sprite_w_px - actual_w) // 2
        screen_y += (sprite_h_px - actual_h) // 2

        depth_px = max(1, min(14, int(round(min(cell_w, cell_h) * 0.34))))
        face_brightness = max(0.42, min(1.05, 1.02 - distance * 0.10))
        face_brightness *= 1.0 - 0.06 * side_abs

        sprite_surface = pygame.Surface((actual_w + depth_px + 2, actual_h + depth_px + 2), pygame.SRCALPHA)
        for row_index, row in enumerate(trimmed_rows):
            for col_index, cell in enumerate(row):
                if cell.char == " " and cell.bg == "Bk" and not opaque_black_background:
                    continue

                dest_x = col_index * cell_w
                dest_y = row_index * cell_h
                bg_color = (0, 0, 0) if opaque_black_background else self.ansi_color_to_rgb(cell.bg, "me")
                if opaque_black_background or cell.bg != "Bk":
                    pygame.draw.rect(
                        sprite_surface,
                        self.shade_color(bg_color, max(0.28, face_brightness * 0.78)),
                        (dest_x, dest_y, cell_w, cell_h),
                    )

                if cell.char != " ":
                    face_color = self.sprite_face_color(cell, face_brightness)
                    for depth_step in range(depth_px, 0, -1):
                        shadow = self.sprite_shadow_color(face_color, depth_step, depth_px)
                        sprite_surface.blit(
                            self.glyph_surface(cell.char, shadow, cell_w, cell_h),
                            (dest_x + depth_step, dest_y + depth_step),
                        )
                    sprite_surface.blit(self.glyph_surface(cell.char, face_color, cell_w, cell_h), (dest_x, dest_y))

        prior_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(vx, vy, vw, vh))
        self.screen.blit(sprite_surface, (screen_x, screen_y))
        self.screen.set_clip(prior_clip)

    def sample_texture_fill(
        self,
        texture: Optional[AnsiTexture],
        x_ratio: float,
        y_ratio: float,
        *,
        repeat: bool = False,
    ) -> Optional[RGB]:
        fill_rows = self.texture_fill_rows(texture)
        if fill_rows is None or texture is None or texture.width <= 0 or texture.height <= 0:
            return None
        if repeat:
            x_ratio %= 1.0
            y_ratio %= 1.0
            tx = min(texture.width - 1, max(0, int(x_ratio * texture.width)))
            ty = min(texture.height - 1, max(0, int(y_ratio * texture.height)))
        else:
            tx = min(texture.width - 1, max(0, int(x_ratio * max(1, texture.width - 1))))
            ty = min(texture.height - 1, max(0, int(y_ratio * max(1, texture.height - 1))))
        return fill_rows[ty][tx]

    def normalize_angle(self, angle: float) -> float:
        while angle <= -math.pi:
            angle += math.tau
        while angle > math.pi:
            angle -= math.tau
        return angle

    def facing_to_angle(self, facing: int) -> float:
        dx, dy = dungeona.DIRECTIONS[facing % len(dungeona.DIRECTIONS)]
        return math.atan2(float(dy), float(dx))

    def angle_to_facing(self, angle: float) -> int:
        aim_x = math.cos(angle)
        aim_y = math.sin(angle)
        best_index = 0
        best_dot = -10.0
        for index, (dx, dy) in enumerate(dungeona.DIRECTIONS):
            dot = aim_x * dx + aim_y * dy
            if dot > best_dot:
                best_dot = dot
                best_index = index
        return best_index

    def sync_facing_to_view_angle(self) -> None:
        self.state["facing"] = self.angle_to_facing(self.view_angle)

    def set_mouse_capture(self, capture: bool) -> None:
        self.mouse_captured = bool(capture)
        try:
            pygame.event.set_grab(self.mouse_captured)
            pygame.mouse.set_visible(not self.mouse_captured)
            pygame.mouse.get_rel()
            if self.mouse_captured:
                self.center_mouse()
        except Exception:
            pass

    def camera_basis(self) -> Tuple[float, float, float, float]:
        dir_x = math.cos(self.view_angle)
        dir_y = math.sin(self.view_angle)
        plane_x = -dir_y * dungeona.FOV_SCALE
        plane_y = dir_x * dungeona.FOV_SCALE
        return dir_x, dir_y, plane_x, plane_y

    def view_pitch_cells(self) -> int:
        return int(round(self.view_pitch * (self.view_height_cells * 0.22)))

    def horizon_row(self) -> int:
        base_horizon = self.view_height_cells // 2
        return max(8, min(self.view_height_cells - 8, base_horizon + self.view_pitch_cells()))

    def billboard_projection(self, tile_x: int, tile_y: int, *, max_distance: float = 6.5) -> Optional[Tuple[float, float]]:
        cam_x = float(self.state["x"]) + 0.5
        cam_y = float(self.state["y"]) + 0.5
        rel_x = tile_x + 0.5 - cam_x
        rel_y = tile_y + 0.5 - cam_y
        euclidean = math.hypot(rel_x, rel_y)
        if euclidean <= 0.05 or euclidean > max_distance:
            return None

        dir_x, dir_y, plane_x, plane_y = self.camera_basis()
        inv_det = 1.0 / (plane_x * dir_y - dir_x * plane_y)
        transform_x = inv_det * (dir_y * rel_x - dir_x * rel_y)
        transform_y = inv_det * (-plane_y * rel_x + plane_x * rel_y)
        if transform_y <= 0.12:
            return None
        screen_offset = transform_x / transform_y
        if abs(screen_offset) > 1.35:
            return None

        grid = dungeona.current_grid(self.state)
        wall_distance, wall_cell, _side, _hit = dungeona.cast_perspective_ray(
            grid,
            cam_x,
            cam_y,
            rel_x / euclidean,
            rel_y / euclidean,
            max_depth=euclidean + 0.25,
        )
        if wall_cell in {"#", "D"} and wall_distance + 0.30 < euclidean:
            return None
        return transform_y, screen_offset

    def gather_visible_billboards(self) -> List[Tuple[float, float, str, Optional[AnsiTexture]]]:
        grid = dungeona.current_grid(self.state)
        px = int(self.state["x"])
        py = int(self.state["y"])
        action_count = int(self.state.get("action_count", 0))
        billboards: List[Tuple[float, float, str, Optional[AnsiTexture]]] = []

        for tile_y in range(max(0, py - 6), min(len(grid), py + 7)):
            row = grid[tile_y]
            for tile_x in range(max(0, px - 6), min(len(row), px + 7)):
                cell = row[tile_x]
                kind: Optional[str] = None
                texture: Optional[AnsiTexture] = None
                if dungeona.is_monster(cell):
                    kind = f"monster:{cell}"
                    texture = self.monster_texture(cell if cell in dungeona.MONSTER_TILES else "R", action_count)
                elif cell == dungeona.QUEST_ITEM_TILE:
                    kind = "grail"
                    candidate = self.ansi_sprite_assets.get("grail")
                    texture = candidate if isinstance(candidate, AnsiTexture) else None
                elif cell == dungeona.QUEST_TARGET_TILE:
                    kind = "altar"
                    candidate = self.ansi_sprite_assets.get("altar")
                    texture = candidate if isinstance(candidate, AnsiTexture) else None
                elif cell == ">":
                    kind = "stairs_down"
                    candidate = self.ansi_sprite_assets.get("stairs_down")
                    texture = candidate if isinstance(candidate, AnsiTexture) else None
                elif cell == "<":
                    kind = "stairs_up"
                    candidate = self.ansi_sprite_assets.get("stairs_up")
                    texture = candidate if isinstance(candidate, AnsiTexture) else None

                if kind is None or texture is None:
                    continue
                projection = self.billboard_projection(tile_x, tile_y)
                if projection is None:
                    continue
                distance, screen_offset = projection
                billboards.append((distance, screen_offset, kind, texture))

        return sorted(billboards, key=lambda item: item[0], reverse=True)

    def char_fill(self, ch: str, color_id: int) -> Optional[RGB]:
        if ch == " ":
            return None
        base = self.color_for(color_id)
        if ch in {"░", ".", ",", "`", "_"}:
            return self.shade_color(base, 0.62)
        if ch in {"▒", "|", "/", "\\"}:
            return self.shade_color(base, 0.80)
        if ch in {"▓", "=", "+", "#"}:
            return self.shade_color(base, 0.96)
        if ch in {"█", "@", "%", "&"}:
            return self.shade_color(base, 1.08)
        return base

    # ---------- scene rendering ----------
    def draw_scene_surface(self) -> None:
        assert self.view_surface is not None
        grid = dungeona.current_grid(self.state)
        px = int(self.state["x"])
        py = int(self.state["y"])
        wall_textures = self.state.get("wall_textures") or {}
        floor_texture = self.state.get("floor_texture")
        ceiling_texture = self.state.get("ceiling_texture")
        horizon = self.horizon_row()
        cam_x = px + 0.5
        cam_y = py + 0.5
        dir_x, dir_y, plane_x, plane_y = self.camera_basis()

        surface = self.view_surface
        surface.lock()
        try:
            for y in range(self.view_height_cells):
                row_color = self.floor_band_color(y)
                surface.fill(row_color, (0, y, self.view_width_cells, 1))

            if ceiling_texture is not None:
                for y in range(1, horizon):
                    ceiling_depth = (horizon - y) / max(1, horizon)
                    shade = max(0.30, min(1.00, 0.48 + (1.0 - ceiling_depth) * 0.42))
                    for x in range(self.view_width_cells):
                        ceiling_x_ratio = x / max(1, self.view_width_cells)
                        fill = self.sample_texture_fill(
                            ceiling_texture,
                            ceiling_x_ratio * 2.0 + ceiling_depth * 0.35,
                            ceiling_depth * 3.0,
                            repeat=True,
                        )
                        if fill is not None:
                            surface.set_at((x, y), self.shade_color(fill, shade))

            for y in range(horizon + 1, self.view_height_cells - 2):
                floor_depth = (y - horizon) / max(1, self.view_height_cells - horizon - 1)
                shade = max(0.28, min(1.08, 0.34 + floor_depth * 0.74))
                for x in range(self.view_width_cells):
                    fill = self.sample_texture_fill(
                        floor_texture,
                        x / max(1, self.view_width_cells) * (1.2 + floor_depth * 2.8),
                        floor_depth * 3.2,
                        repeat=True,
                    )
                    if fill is not None:
                        surface.set_at((x, y), self.shade_color(fill, shade))

            for x in range(self.view_width_cells):
                camera_x = 2.0 * x / max(1, self.view_width_cells - 1) - 1.0
                ray_dir_x = dir_x + plane_x * camera_x
                ray_dir_y = dir_y + plane_y * camera_x
                distance, cell, side, wall_hit = dungeona.cast_perspective_ray(grid, cam_x, cam_y, ray_dir_x, ray_dir_y)
                if cell not in {"#", "D"}:
                    continue

                line_height = int((self.view_height_cells * 0.92) / max(0.001, distance))
                draw_start = max(1, horizon - line_height // 2)
                draw_end = min(self.view_height_cells - 3, horizon + line_height // 2)
                color_id = 2 if cell == "D" else 1
                texture = wall_textures.get(cell)
                shade = max(
                    0.22,
                    min(
                        1.08,
                        (1.05 - min(1.0, distance / max(0.001, dungeona.MAX_RENDER_DEPTH)) * 0.55)
                        * (0.84 if side == 1 else 1.0),
                    ),
                )
                mid = (draw_start + draw_end) // 2

                for y in range(draw_start, draw_end + 1):
                    wall_fill: Optional[RGB]
                    if texture is not None:
                        y_ratio = (y - draw_start) / max(1, draw_end - draw_start)
                        base_fill = self.sample_texture_fill(texture, wall_hit, y_ratio)
                        wall_fill = self.shade_color(base_fill, shade) if base_fill is not None else None
                    else:
                        draw_char = dungeona.wall_char(distance, side, cell)
                        if cell == "D":
                            if abs(y - mid) <= max(1, line_height // 10):
                                draw_char = "="
                            elif x % 2 == 0:
                                draw_char = "|"
                        elif side == 1 and draw_char in {"█", "▓", "▒"}:
                            draw_char = {"█": "▓", "▓": "▒", "▒": "░"}.get(draw_char, draw_char)
                        wall_fill = self.char_fill(draw_char, color_id)
                    if wall_fill is not None:
                        surface.set_at((x, y), wall_fill)

                ceiling_limit = max(1, draw_start - 1)
                if ceiling_limit > 1 and x % 3 == 0:
                    edge_fill = self.char_fill("_", 4)
                    if edge_fill is not None:
                        surface.set_at((x, ceiling_limit), edge_fill)

        finally:
            surface.unlock()

    # ---------- UI drawing ----------
    def draw_scaled_view(self) -> None:
        assert self.view_surface is not None
        vx, vy, vw, vh = self.view_rect
        scaled = pygame.transform.scale(self.view_surface, (vw, vh))
        self.screen.blit(scaled, (vx, vy))

    def draw_ansi_billboards(self) -> None:
        for distance, screen_offset, kind, texture in self.gather_visible_billboards():
            if kind == "grail":
                object_projection_scale = 3.0
                self.draw_ansi_texture_billboard(
                    texture,
                    distance=int(max(1, round(distance))),
                    side=screen_offset,
                    base_scale=2.0 * object_projection_scale,
                    distance_bias=0.2,
                    min_scale=0.45 * object_projection_scale,
                    side_scale=0.72,
                    center_scale=1.18,
                    width_scale_front=0.92,
                    width_scale_side=0.82,
                    opaque_black_background=True,
                )
            elif kind == "altar":
                object_projection_scale = 3.0
                self.draw_ansi_texture_billboard(
                    texture,
                    distance=int(max(1, round(distance))),
                    side=screen_offset,
                    base_scale=2.1 * object_projection_scale,
                    distance_bias=0.25,
                    min_scale=0.48 * object_projection_scale,
                    side_scale=0.78,
                    center_scale=1.0,
                    width_scale_front=1.0,
                    width_scale_side=0.86,
                    opaque_black_background=True,
                )
            elif kind in {"stairs_up", "stairs_down"}:
                stairs_projection_scale = 3.0
                self.draw_ansi_texture_billboard(
                    texture,
                    distance=int(max(1, round(distance))),
                    side=screen_offset,
                    base_scale=2.0 * stairs_projection_scale,
                    distance_bias=0.22,
                    min_scale=0.46 * stairs_projection_scale,
                    side_scale=0.76,
                    center_scale=1.06,
                    width_scale_front=0.98,
                    width_scale_side=0.88,
                    opaque_black_background=True,
                )
            else:
                monster_projection_scale = 3.0
                self.draw_ansi_texture_billboard(
                    texture,
                    distance=int(max(1, round(distance))),
                    side=screen_offset,
                    base_scale=2.4 * monster_projection_scale,
                    distance_bias=0.35,
                    min_scale=0.55 * monster_projection_scale,
                    side_scale=0.72,
                    center_scale=1.15,
                    width_scale_front=0.95,
                    width_scale_side=0.85,
                    opaque_black_background=True,
                )

        vx, vy, vw, vh = self.view_rect
        center_x = vx + vw // 2
        center_y = vy + vh // 2
        pygame.draw.line(self.screen, CROSSHAIR_COLOR, (center_x - 8, center_y), (center_x + 8, center_y), 1)
        pygame.draw.line(self.screen, CROSSHAIR_COLOR, (center_x, center_y - 8), (center_x, center_y + 8), 1)
        pygame.draw.rect(self.screen, (32, 38, 45), (vx, vy, vw, vh), 2)

    def draw_minimap(self) -> None:
        if not bool(self.state.get("show_map")):
            return

        grid = dungeona.current_grid(self.state)
        px = int(self.state["x"])
        py = int(self.state["y"])
        facing = self.angle_to_facing(self.view_angle)
        radius = 4
        tile = max(12, min(22, self.window_width // 60))
        panel_left = 14
        panel_top = 14
        map_size = tile * (radius * 2 + 1)
        panel = pygame.Rect(panel_left, panel_top, map_size + 16, map_size + 36)
        pygame.draw.rect(self.screen, MAP_PANEL_BG, panel)
        pygame.draw.rect(self.screen, MAP_PANEL_BORDER, panel, 2)

        label = self.font_medium_bold.render(f"F{int(self.state['floor']) + 1}", True, (127, 155, 184))
        self.screen.blit(label, (panel.left + 8, panel.top + 6))

        map_left = panel.left + 8
        map_top = panel.top + 28
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                mx = px + dx
                my = py + dy
                cell = dungeona.cell_at(grid, mx, my)
                color = (22, 27, 33)
                if cell == "#":
                    color = (78, 87, 98)
                elif cell == "D":
                    color = (159, 120, 51)
                elif dungeona.is_monster(cell):
                    info = dungeona.monster_info(cell if cell in dungeona.MONSTER_TILES else "R")
                    color = self.color_for(int(info["color"]))
                elif cell == dungeona.QUEST_ITEM_TILE:
                    color = (187, 166, 67)
                elif cell == dungeona.QUEST_TARGET_TILE:
                    color = (127, 78, 161)
                elif cell in {"<", ">"}:
                    color = (93, 127, 174)
                elif cell in {".", " "}:
                    color = (42, 36, 31)
                rect = pygame.Rect(map_left + (dx + radius) * tile, map_top + (dy + radius) * tile, tile - 1, tile - 1)
                pygame.draw.rect(self.screen, color, rect)

        center_x = map_left + radius * tile + tile // 2
        center_y = map_top + radius * tile + tile // 2
        pygame.draw.circle(self.screen, PLAYER_COLOR, (center_x, center_y), max(4, tile // 4))
        aim_x = math.cos(self.view_angle)
        aim_y = math.sin(self.view_angle)
        pygame.draw.line(self.screen, PLAYER_COLOR, (center_x, center_y), (center_x + int(round(aim_x * (tile // 2))), center_y + int(round(aim_y * (tile // 2)))), 2)

    def draw_text(self, text: str, pos: Tuple[int, int], color: RGB, font, *, align_right: bool = False) -> None:
        surf = font.render(text, True, color)
        rect = surf.get_rect()
        if align_right:
            rect.topright = pos
        else:
            rect.topleft = pos
        self.screen.blit(surf, rect)

    def draw_status(self) -> None:
        y0 = self.window_height - self.status_height
        panel = pygame.Rect(0, y0, self.window_width, self.status_height)
        pygame.draw.rect(self.screen, STATUS_BG, panel)
        pygame.draw.line(self.screen, (38, 48, 58), (0, y0), (self.window_width, y0), 2)

        energy = int(self.state["energy"])
        bar_x = 20
        bar_y = y0 + 18
        bar_w = min(300, max(160, self.window_width // 4))
        bar_h = 18
        fill_w = int(bar_w * energy / max(1, dungeona.MAX_ENERGY))

        self.draw_text("Energy", (bar_x, bar_y - 3), TEXT_COLOR, self.font_medium_bold)
        pygame.draw.rect(self.screen, (30, 37, 44), (bar_x + 84, bar_y, bar_w, bar_h))
        pygame.draw.rect(self.screen, PLAYER_COLOR, (bar_x + 84, bar_y, fill_w, bar_h))
        pygame.draw.rect(self.screen, (52, 64, 76), (bar_x + 84, bar_y, bar_w, bar_h), 1)

        quest_status = "done" if bool(self.state["quest_complete"]) else ("carrying" if bool(self.state["has_grail"]) else "missing")
        line1 = (
            f"Floor {int(self.state['floor']) + 1}/{len(self.state['floors'])}   "
            f"Pos {self.state['x']},{self.state['y']}   "
            f"Facing {dungeona.DIRECTION_NAMES[int(self.state['facing'])]}   "
            f"Defeated {self.state['score']}"
        )
        line2 = f"Inventory {dungeona.inventory_count(self.state)}/{dungeona.MAX_CARRIED_ITEMS}   Grail {quest_status}"
        line3 = str(self.state["message"])

        info_x = 20
        self.draw_text(line1, (info_x, y0 + 46), TEXT_COLOR, self.font_medium)
        self.draw_text(line2, (info_x, y0 + 68), self.color_for(8), self.font_medium)
        self.draw_text(line3[:140], (info_x, y0 + 90), (127, 155, 184), self.font_small)
        self.draw_text(KEY_HELP, (self.window_width - 18, y0 + 18), SUBTLE_TEXT, self.font_small, align_right=True)

    def draw_congrats_overlay(self) -> None:
        if not bool(self.state.get("show_congrats_banner")):
            return

        overlay = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        box_w = min(self.window_width - 80, 760)
        box_h = 160
        box = pygame.Rect((self.window_width - box_w) // 2, max(80, self.view_rect[3] // 3), box_w, box_h)
        pygame.draw.rect(self.screen, (13, 16, 20), box)
        pygame.draw.rect(self.screen, self.color_for(8), box, 3)
        self.draw_text("Congratulations.", (box.left + 32, box.top + 32), (216, 193, 95), self.font_title)
        self.draw_text("Press any action or movement key to continue", (box.left + 32, box.top + 88), TEXT_COLOR, self.font_medium)

    def render(self) -> None:
        self.screen.fill(BACKGROUND)
        self.draw_scene_surface()
        self.draw_scaled_view()
        self.draw_ansi_billboards()
        self.draw_minimap()
        self.draw_status()
        self.draw_congrats_overlay()
        pygame.display.flip()

    # ---------- input and game updates ----------
    def advance_if_acted(self, acted: bool) -> None:
        if acted:
            self.state["action_count"] = int(self.state.get("action_count", 0)) + 1
            dungeona.advance_world(self.state)

    def center_mouse(self) -> None:
        if not self.mouse_captured:
            return
        try:
            rect = self.screen.get_rect()
            self._ignore_mousemotion_events = max(self._ignore_mousemotion_events, 2)
            pygame.mouse.set_pos(rect.center)
            pygame.mouse.get_rel()
        except Exception:
            pass

    def handle_keydown(self, event: "pygame.event.Event") -> bool:
        key = event.key
        unicode_text = getattr(event, "unicode", "")
        acted = False

        if self.state.get("show_congrats_banner") and key not in {pygame.K_x, pygame.K_ESCAPE}:
            self.state["show_congrats_banner"] = False

        recenter_after_step = False

        if key in {pygame.K_UP, pygame.K_w}:
            old_pos = (self.state["x"], self.state["y"])
            dungeona.try_move(self.state, 1)
            moved = old_pos != (self.state["x"], self.state["y"])
            self.state["message"] = "You move forward." if moved else "A wall blocks your way."
            recenter_after_step = moved
            acted = True
        elif key in {pygame.K_DOWN, pygame.K_s}:
            old_pos = (self.state["x"], self.state["y"])
            dungeona.try_move(self.state, -1)
            moved = old_pos != (self.state["x"], self.state["y"])
            self.state["message"] = "You move backward." if moved else "You cannot move there."
            recenter_after_step = moved
            acted = True
        elif key in {pygame.K_LEFT, pygame.K_a, pygame.K_z}:
            old_pos = (self.state["x"], self.state["y"])
            dungeona.try_strafe(self.state, -1)
            moved = old_pos != (self.state["x"], self.state["y"])
            self.state["message"] = "You sidestep left." if moved else "Blocked on the left."
            recenter_after_step = moved
            acted = True
        elif key in {pygame.K_RIGHT, pygame.K_d, pygame.K_c}:
            old_pos = (self.state["x"], self.state["y"])
            dungeona.try_strafe(self.state, 1)
            moved = old_pos != (self.state["x"], self.state["y"])
            self.state["message"] = "You sidestep right." if moved else "Blocked on the right."
            recenter_after_step = moved
            acted = True
        elif key == pygame.K_q:
            self.view_angle = self.normalize_angle(self.view_angle - (math.pi / 2.0))
            self.sync_facing_to_view_angle()
            self.state["message"] = "You turn left."
            acted = True
        elif key == pygame.K_e:
            self.view_angle = self.normalize_angle(self.view_angle + (math.pi / 2.0))
            self.sync_facing_to_view_angle()
            self.state["message"] = "You turn right."
            acted = True
        elif key in {pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER}:
            self.state["message"] = dungeona.use_action(self.state)
            acted = True
        elif key == pygame.K_PERIOD or unicode_text == ".":
            self.state["energy"] = min(dungeona.MAX_ENERGY, int(self.state["energy"]) + dungeona.WAIT_ENERGY_GAIN)
            self.state["message"] = "You wait and regain a little energy."
            acted = True
        elif key == pygame.K_m:
            self.state["show_map"] = not bool(self.state["show_map"])
            self.state["message"] = f"Map {'shown' if self.state['show_map'] else 'hidden'}."
            acted = True
        elif key == pygame.K_TAB:
            self.set_mouse_capture(not self.mouse_captured)
            self.state["message"] = f"Mouse look {'enabled' if self.mouse_captured else 'released'}."
        elif unicode_text == ">":
            self.state["message"] = dungeona.travel_stairs(self.state, 1)
            acted = True
        elif unicode_text == "<":
            self.state["message"] = dungeona.travel_stairs(self.state, -1)
            acted = True
        elif key in {pygame.K_x, pygame.K_ESCAPE}:
            return False

        self.advance_if_acted(acted)
        if recenter_after_step:
            self.view_angle = self.facing_to_angle(int(self.state["facing"]))
            self.view_pitch = 0.0
            self.center_mouse()
        return True

    def handle_mousemotion(self, event: "pygame.event.Event") -> None:
        if not self.mouse_captured:
            return
        if self._ignore_mousemotion_events > 0:
            self._ignore_mousemotion_events -= 1
            return
        rel = getattr(event, "rel", (0, 0))
        if not rel:
            return
        delta_x = float(rel[0])
        delta_y = float(rel[1])
        if abs(delta_x) >= 0.01:
            body_angle = self.facing_to_angle(int(self.state["facing"]))
            candidate_angle = self.normalize_angle(self.view_angle + delta_x * self.mouse_sensitivity)
            yaw_offset = self.normalize_angle(candidate_angle - body_angle)
            yaw_offset = max(-self.max_head_yaw, min(self.max_head_yaw, yaw_offset))
            self.view_angle = self.normalize_angle(body_angle + yaw_offset)
        if abs(delta_y) >= 0.01:
            self.view_pitch = max(-self.max_view_pitch, min(self.max_view_pitch, self.view_pitch - delta_y * self.mouse_sensitivity))
        if abs(delta_x) >= 0.01 or abs(delta_y) >= 0.01:
            self.center_mouse()

    def run(self) -> int:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode((max(800, event.w), max(600, event.h)), pygame.RESIZABLE)
                    self.resize(event.w, event.h)
                    if self.mouse_captured:
                        self.center_mouse()
                elif event.type == pygame.KEYDOWN:
                    running = self.handle_keydown(event)
                    if not running:
                        break
                elif event.type == pygame.MOUSEMOTION:
                    self.handle_mousemotion(event)

            self.render()
            self.clock.tick(self.fps)

        pygame.quit()
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play Dungeona in a pygame / SDL window.")
    parser.add_argument("--width", type=int, default=1280, help="Initial window width.")
    parser.add_argument("--height", type=int, default=800, help="Initial window height.")
    parser.add_argument("--fps", type=int, default=30, help="Frame cap for the renderer.")
    parser.add_argument("--fullscreen", action="store_true", help="Start in fullscreen mode.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if pygame is None:
        print("pygame is not installed. Install it with: pip install pygame")
        return 1
    dungeona.initialize_map_db(dungeona.DB_PATH)
    app = Dungeona2(args.width, args.height, fullscreen=args.fullscreen, fps=args.fps)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
