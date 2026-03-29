import math
import tkinter as tk
from typing import Dict, List, Optional, Tuple

import dungeona
from ans import AnsiCell, AnsiTexture

WINDOW_WIDTH = 320
WINDOW_HEIGHT = 200
STATUS_HEIGHT = 64
VIEW_HEIGHT = WINDOW_HEIGHT - STATUS_HEIGHT
BACKGROUND = "#0a0c0f"
STATUS_BG = "#101419"
TEXT_COLOR = "#d8dee9"
CELL_W = 4
CELL_H = 4
VIEW_WIDTH_CELLS = WINDOW_WIDTH // CELL_W
VIEW_HEIGHT_CELLS = VIEW_HEIGHT // CELL_H
MINIMAP_TILE = 10
MIN_RENDER_SCALE = 1
MAX_RENDER_SCALE = 4

COLOR_MAP = {
    1: "#586270",
    2: "#b58a3b",
    3: "#4fa7bf",
    4: "#4e463e",
    5: "#5c6670",
    6: "#45a85a",
    7: "#b45151",
    8: "#c9b24a",
    9: "#6f95c8",
    10: "#8f5db0",
}
ANSI_RGB = {
    "Bk": "#000000",
    "Re": "#aa0000",
    "Gr": "#00aa00",
    "Ye": "#aa5500",
    "Bl": "#0000aa",
    "Ma": "#aa00aa",
    "Cy": "#00aaaa",
    "Wh": "#aaaaaa",
}
BRIGHT_ANSI_RGB = {
    "Bk": "#555555",
    "Re": "#ff5555",
    "Gr": "#55ff55",
    "Ye": "#ffff55",
    "Bl": "#5555ff",
    "Ma": "#ff55ff",
    "Cy": "#55ffff",
    "Wh": "#ffffff",
}
DARK_ANSI_RGB = {
    "Bk": "#000000",
    "Re": "#550000",
    "Gr": "#005500",
    "Ye": "#553300",
    "Bl": "#000055",
    "Ma": "#550055",
    "Cy": "#005555",
    "Wh": "#555555",
}

KEY_HELP = "WASD/arrows move  Q/E turn  Z/C strafe  Space act  . wait  M map  X quit"


class DungeonaRenderer:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Dungeona Renderer")
        self.root.configure(bg=BACKGROUND)
        self.root.resizable(True, True)

        self.window_width = WINDOW_WIDTH
        self.window_height = WINDOW_HEIGHT
        self.status_height = STATUS_HEIGHT
        self.render_scale = MIN_RENDER_SCALE
        self.cell_w = CELL_W
        self.cell_h = CELL_H
        self.minimap_tile = MINIMAP_TILE
        self.view_height = self.window_height - self.status_height
        self.view_width_cells = VIEW_WIDTH_CELLS
        self.view_height_cells = VIEW_HEIGHT_CELLS

        self.canvas = tk.Canvas(
            self.root,
            width=self.window_width,
            height=self.window_height,
            bg=BACKGROUND,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

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
            "message": f"Loaded dungeon from {dungeona.DB_PATH.name}.",
            "show_congrats_banner": False,
            "wall_textures": dungeona.load_wall_textures(),
            "floor_texture": dungeona.load_surface_texture(dungeona.FLOOR_TEXTURE_FILE),
            "ceiling_texture": dungeona.load_surface_texture(dungeona.CEILING_TEXTURE_FILE),
            "animated_sprites": dungeona.load_animated_sprites(),
            "static_sprites": dungeona.load_static_sprites(),
            "action_count": 0,
            "monster_chase": {},
        }
        dungeona.collect_tile(self.state, dungeona.current_grid(self.state))
        self.state["message"] = (
            f"Find the {dungeona.QUEST_ITEM_NAME} on floor {dungeona.QUEST_START_FLOOR + 1} "
            f"and bring it to the altar on floor {dungeona.QUEST_TARGET_FLOOR + 1}."
        )

        self.static_cache: Dict[str, object] = {
            "frame_key": None,
            "frame_items": [],
            "last_render_key": None,
            "last_render_items": [],
        }
        self.dynamic_scene_items: List[int] = []
        self.dynamic_overlay_items: List[int] = []
        self.monster_detail_items: List[int] = []
        self.item_detail_items: List[int] = []
        self.view_antialias_samples = 2

        self.root.bind("<KeyPress>", self.on_key)
        self.root.bind("<Configure>", self.on_resize)
        self.draw_scene(force_scene=True)

    def color_for(self, color_id: int, default: str = "#cfcfcf") -> str:
        return COLOR_MAP.get(color_id, default)

    def shade_color(self, color: str, factor: float) -> str:
        color = color.lstrip("#")
        if len(color) != 6:
            return "#cfcfcf"
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def mix_colors(self, color_a: str, color_b: str, amount: float) -> str:
        amount = max(0.0, min(1.0, amount))
        a = color_a.lstrip("#")
        b = color_b.lstrip("#")
        if len(a) != 6 or len(b) != 6:
            return color_a
        ar, ag, ab = int(a[0:2], 16), int(a[2:4], 16), int(a[4:6], 16)
        br, bg, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
        r = int(ar * (1.0 - amount) + br * amount)
        g = int(ag * (1.0 - amount) + bg * amount)
        b2 = int(ab * (1.0 - amount) + bb * amount)
        return f"#{r:02x}{g:02x}{b2:02x}"

    def clear_item_list(self, items: List[int]) -> None:
        for item in items:
            self.canvas.delete(item)
        items.clear()

    def update_render_metrics(self, width: int, height: int) -> None:
        self.window_width = max(320, width)
        self.window_height = max(240, height)
        self.status_height = max(48, int(self.window_height * 0.16))
        self.view_height = max(CELL_H * 24, self.window_height - self.status_height)
        width_scale = max(1, self.window_width // WINDOW_WIDTH)
        height_scale = max(1, self.view_height // VIEW_HEIGHT)
        self.render_scale = max(MIN_RENDER_SCALE, min(MAX_RENDER_SCALE, min(width_scale, height_scale)))
        self.cell_w = CELL_W * self.render_scale
        self.cell_h = CELL_H * self.render_scale
        self.minimap_tile = MINIMAP_TILE * self.render_scale
        self.view_width_cells = max(48, self.window_width // self.cell_w)
        self.view_height_cells = max(24, self.view_height // self.cell_h)

    def rect_from_cells(self, x: int, y: int, w: int = 1, h: int = 1) -> Tuple[int, int, int, int]:
        return (
            x * self.cell_w,
            y * self.cell_h,
            (x + w) * self.cell_w,
            (y + h) * self.cell_h,
        )

    def batch_runs_by_row(self, rects: List[Tuple[int, int, str]]) -> List[Tuple[int, int, int, str]]:
        if not rects:
            return []
        rects = sorted(rects, key=lambda item: (item[1], item[0]))
        runs: List[Tuple[int, int, int, str]] = []
        start_x, y, color = rects[0]
        width = 1
        prev_x = start_x
        for x, row_y, row_color in rects[1:]:
            if row_y == y and row_color == color and x == prev_x + 1:
                width += 1
            else:
                runs.append((start_x, y, width, color))
                start_x, y, color = x, row_y, row_color
                width = 1
            prev_x = x
        runs.append((start_x, y, width, color))
        return runs

    def create_batched_rectangles(self, rects: List[Tuple[int, int, str]], target_items: List[int]) -> None:
        for x, y, width, color in self.batch_runs_by_row(rects):
            x0, y0, x1, y1 = self.rect_from_cells(x, y, width, 1)
            target_items.append(self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=color))

    def procedural_ceiling_color(self, x: int, y: int) -> str:
        horizon = self.view_height_cells // 2
        ratio = y / max(1, horizon)
        base = "#2a2018"
        color = self.mix_colors(base, "#3b2b1f", 0.25 * (1.0 - ratio))
        plank_h = max(2, 3 // max(1, self.render_scale))
        board = (y // plank_h) % 6
        grain = ((x * 3 + y * 5) % 9)
        factor = 0.88 + board * 0.015 + grain * 0.01
        if y % plank_h == 0:
            factor *= 0.72
        if x % max(6, 10 // max(1, self.render_scale)) == 0:
            factor *= 0.92
        return self.shade_color(color, min(1.08, factor))

    def floor_distance_shade(self, distance: float) -> float:
        depth = max(0.0, min(1.0, distance / max(0.001, dungeona.MAX_RENDER_DEPTH)))
        return max(0.28, 1.18 - depth * 0.92)

    def procedural_floor_world_color(self, world_x: float, world_y: float, distance: float) -> str:
        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)
        frac_x = world_x - tile_x
        frac_y = world_y - tile_y

        slab_mix = ((tile_x * 17 + tile_y * 31) & 15) / 15.0
        base = self.mix_colors("#5b5750", "#8b867d", slab_mix * 0.55)

        seam_w = max(0.025, 0.06 - min(0.03, distance * 0.002))
        edge_dist = min(frac_x, frac_y, 1.0 - frac_x, 1.0 - frac_y)
        if edge_dist < seam_w * 0.55:
            color = "#2b2724"
        elif edge_dist < seam_w:
            color = "#3a3531"
        else:
            color = base
            chip = ((tile_x * 13 + tile_y * 11 + int(frac_x * 11) * 5 + int(frac_y * 9) * 7) % 23)
            speck = ((tile_x * 19 + tile_y * 23 + int(frac_x * 17) * 3 + int(frac_y * 13) * 5) % 29)
            vein = abs(frac_x - frac_y) < 0.035 or abs(frac_x - (1.0 - frac_y)) < 0.03
            if chip in {0, 1}:
                color = self.shade_color(color, 0.72)
            elif chip in {2, 3, 4}:
                color = self.shade_color(color, 0.86)
            if speck in {0, 1, 2, 27, 28}:
                color = self.shade_color(color, 1.10)
            elif speck in {7, 8, 9}:
                color = self.shade_color(color, 0.92)
            if vein:
                color = self.mix_colors(color, "#a8a39a", 0.10)
            highlight = (0.5 - abs(frac_x - 0.5)) * 0.08 + (0.5 - abs(frac_y - 0.5)) * 0.05
            color = self.shade_color(color, 0.98 + highlight)

        distance_factor = self.floor_distance_shade(distance)
        fog_amount = max(0.0, min(0.72, (distance - 2.0) / max(0.001, dungeona.MAX_RENDER_DEPTH - 2.0)))
        color = self.shade_color(color, distance_factor)
        return self.mix_colors(color, "#111316", fog_amount * 0.55)

    def ensure_frame_layer(self) -> None:
        frame_key = (self.window_width, self.view_height, self.status_height)
        if self.static_cache.get("frame_key") == frame_key:
            return
        old_items = self.static_cache.get("frame_items", [])
        if isinstance(old_items, list):
            self.clear_item_list(old_items)
        items: List[int] = []
        items.append(self.canvas.create_rectangle(0, 0, self.window_width - 1, self.view_height - 1, outline="#20262d", width=2))
        center_x = self.window_width // 2
        center_y = self.view_height // 2
        items.append(self.canvas.create_line(center_x, center_y - 8, center_x, center_y + 8, fill="#33404d"))
        items.append(self.canvas.create_line(center_x - 8, center_y, center_x + 8, center_y, fill="#33404d"))
        self.static_cache["frame_key"] = frame_key
        self.static_cache["frame_items"] = items

    def scene_render_key(self) -> Tuple[object, ...]:
        return (
            int(self.state["floor"]),
            int(self.state["x"]),
            int(self.state["y"]),
            int(self.state["facing"]),
            int(self.state.get("action_count", 0)),
            self.view_width_cells,
            self.view_height_cells,
        )

    def ansi_color_to_hex(self, color_name: str, intensity: str = "me") -> str:
        if intensity == "hi":
            return BRIGHT_ANSI_RGB.get(color_name, ANSI_RGB["Wh"])
        if intensity == "lo":
            return DARK_ANSI_RGB.get(color_name, ANSI_RGB["Wh"])
        return ANSI_RGB.get(color_name, ANSI_RGB["Wh"])

    def texture_cell_fill(self, cell: AnsiCell) -> Optional[str]:
        ch = cell.char
        fg = self.ansi_color_to_hex(cell.fg, cell.intensity)
        bg = self.ansi_color_to_hex(cell.bg, "me")
        if ch == " ":
            return bg
        if ch in {"█", "▓", "▒", "░", "▄", "▀", "■"}:
            return fg
        if ch in {".", ",", "`", "_"}:
            return self.shade_color(fg, 0.8)
        return fg

    def distance_shade_factor(self, distance: float, side: int = 0) -> float:
        depth = max(0.0, min(1.0, distance / max(0.001, dungeona.MAX_RENDER_DEPTH)))
        factor = 1.05 - depth * 0.55
        if side == 1:
            factor *= 0.84
        return max(0.22, min(1.08, factor))

    def sample_texture_cell(self, texture: Optional[AnsiTexture], x_ratio: float, y_ratio: float) -> Optional[AnsiCell]:
        if texture is None or texture.width <= 0 or texture.height <= 0:
            return None
        tx = min(texture.width - 1, max(0, int(x_ratio * max(1, texture.width - 1))))
        ty = min(texture.height - 1, max(0, int(y_ratio * max(1, texture.height - 1))))
        return texture.rows[ty][tx]

    def char_fill(self, ch: str, color_id: int) -> Optional[str]:
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
        return self.shade_color(base, 1.00)

    def detailed_monster_palette(self, monster_tile: str) -> Dict[str, str]:
        info = dungeona.monster_info(monster_tile)
        base = self.color_for(int(info["color"]))
        if monster_tile == "S":
            base = "#c9ced6"
            return {
                "base": base,
                "shadow": self.shade_color(base, 0.42),
                "mid": self.shade_color(base, 0.74),
                "light": self.shade_color(base, 1.08),
                "accent": "#7a5dcb",
                "eye": "#7fd7ff",
                "bone": self.shade_color(base, 1.18),
            }
        if monster_tile == "O":
            base = "#6f8d52"
            return {
                "base": base,
                "shadow": self.shade_color(base, 0.40),
                "mid": self.shade_color(base, 0.72),
                "light": self.shade_color(base, 1.02),
                "accent": "#b8a06a",
                "eye": "#ffb347",
                "bone": self.shade_color(base, 1.12),
            }
        return {
            "base": base,
            "shadow": self.shade_color(base, 0.38),
            "mid": self.shade_color(base, 0.72),
            "light": self.shade_color(base, 1.06),
            "accent": "#d9a35f",
            "eye": "#ff6b57",
            "bone": self.shade_color(base, 1.10),
        }

    def detailed_item_palette(self, item_tile: str) -> Dict[str, str]:
        if item_tile == dungeona.QUEST_TARGET_TILE:
            base = "#8f5db0"
            return {
                "base": base,
                "shadow": self.shade_color(base, 0.42),
                "mid": self.shade_color(base, 0.76),
                "light": self.shade_color(base, 1.08),
                "accent": "#d9d2ea",
                "glow": "#b794d8",
                "spark": "#efe6ff",
            }
        base = "#c9b24a"
        return {
            "base": base,
            "shadow": self.shade_color(base, 0.42),
            "mid": self.shade_color(base, 0.78),
            "light": self.shade_color(base, 1.08),
            "accent": "#fff2a6",
            "glow": "#e0c85d",
            "spark": "#fff7cc",
        }

    def visible_monster_info(self) -> Optional[Tuple[int, int, int, str]]:
        grid = dungeona.current_grid(self.state)
        return dungeona.visible_monster(
            grid,
            int(self.state["x"]),
            int(self.state["y"]),
            int(self.state["facing"]),
        )

    def draw_enhanced_item_detail_art(self, item_tile: str, distance: int, side: int) -> None:
        palette = self.detailed_item_palette(item_tile)
        center_x = self.view_width_cells // 2 + side * max(2, self.view_width_cells // max(9, 10 + distance * 2))
        floor_y = self.view_height_cells - 4
        scale = max(0.85, 3.0 / (distance + 0.2))
        scale *= 1.12 if side == 0 else 0.82

        if item_tile == dungeona.QUEST_TARGET_TILE:
            body_w = max(7, int(round(12 * scale)))
            body_h = max(6, int(round(9 * scale)))
        else:
            body_w = max(6, int(round(9 * scale)))
            body_h = max(7, int(round(10 * scale)))

        left = center_x - body_w // 2
        top = floor_y - body_h + 1

        shadow_w = max(4, int(body_w * 0.95))
        shadow_h = max(2, int(body_h * 0.18))
        x0, y0, x1, y1 = self.rect_from_cells(center_x - shadow_w // 2, floor_y + 1, shadow_w, shadow_h)
        self.item_detail_items.append(self.canvas.create_oval(x0, y0, x1, y1, fill="#090a0c", outline=""))

        def add_rect(cx: int, cy: int, cw: int, ch: int, color: str, outline: str = "") -> None:
            x0, y0, x1, y1 = self.rect_from_cells(cx, cy, cw, ch)
            self.item_detail_items.append(self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=outline or color))

        def add_glow(cx: int, cy: int, cw: int, ch: int, color: str) -> None:
            x0, y0, x1, y1 = self.rect_from_cells(cx, cy, cw, ch)
            pad = max(1, self.cell_w // 2)
            self.item_detail_items.append(self.canvas.create_oval(x0 - pad, y0 - pad, x1 + pad, y1 + pad, fill=color, outline=""))

        if item_tile == dungeona.QUEST_TARGET_TILE:
            add_rect(left + 1, top + body_h - 2, max(5, body_w - 2), 2, palette["shadow"])
            add_rect(left + 2, top + body_h - 4, max(4, body_w - 4), 2, palette["mid"])
            add_rect(left + 3, top + 2, max(3, body_w - 6), max(2, body_h - 6), palette["base"])
            add_rect(left + 2, top + 1, max(5, body_w - 4), 2, palette["light"])
            add_rect(left + 1, top + 2, 1, max(3, body_h - 4), palette["shadow"])
            add_rect(left + body_w - 2, top + 2, 1, max(3, body_h - 4), palette["shadow"])
            add_rect(left + body_w // 2 - 1, top + 2, 2, max(2, body_h - 5), palette["accent"])
            add_rect(left + body_w // 3, top + body_h // 2, max(1, body_w // 6), 1, palette["accent"])
            add_rect(left + body_w - 1 - max(1, body_w // 6) - body_w // 3, top + body_h // 2, max(1, body_w // 6), 1, palette["accent"])
            add_glow(left + body_w // 2 - 1, top + 1, 2, 1, self.shade_color(palette["glow"], 0.95))
            add_rect(left + body_w // 2, top + 0, 1, 1, palette["spark"])
        else:
            cup_w = max(4, body_w - 3)
            add_rect(left + 1, top + body_h - 2, max(3, body_w - 2), 1, palette["shadow"])
            add_rect(left + 2, top + 1, cup_w, max(2, body_h // 3), palette["light"])
            add_rect(left + 1, top + 2, 1, max(2, body_h // 3), palette["accent"])
            add_rect(left + body_w - 2, top + 2, 1, max(2, body_h // 3), palette["accent"])
            add_rect(left + 3, top + body_h // 3 + 1, max(2, body_w - 6), max(1, body_h // 4), palette["mid"])
            add_rect(left + body_w // 2 - 1, top + body_h // 2, 2, max(2, body_h // 3), palette["base"])
            add_rect(left + body_w // 2 - max(2, body_w // 4), top + body_h - 1, max(4, body_w // 2), 1, palette["mid"])
            add_glow(left + 2, top + 0, max(2, body_w - 4), 1, self.shade_color(palette["glow"], 0.9))
            add_rect(left + body_w // 2, top + 0, 1, 1, palette["spark"])

    def draw_item_detail_art(self) -> None:
        self.clear_item_list(self.item_detail_items)
        grid = dungeona.current_grid(self.state)
        px = int(self.state["x"])
        py = int(self.state["y"])
        facing = int(self.state["facing"])
        visible_grail = dungeona.grail_in_view(grid, px, py, facing)
        visible_altar = dungeona.altar_in_view(grid, px, py, facing)
        candidates: List[Tuple[int, int, str]] = []
        if visible_grail is not None:
            distance, side, _ = visible_grail
            candidates.append((distance, side, dungeona.QUEST_ITEM_TILE))
        if visible_altar is not None:
            distance, side, _ = visible_altar
            candidates.append((distance, side, dungeona.QUEST_TARGET_TILE))
        if not candidates:
            return
        distance, side, item_tile = sorted(candidates, key=lambda entry: entry[0])[0]
        self.draw_enhanced_item_detail_art(item_tile, distance, side)

    def draw_monster_detail_art(self) -> None:
        self.clear_item_list(self.monster_detail_items)
        seen = self.visible_monster_info()
        if seen is None:
            return
        distance, side, _lateral, monster_tile = seen
        palette = self.detailed_monster_palette(monster_tile)
        center_x = self.view_width_cells // 2 + side * max(3, self.view_width_cells // max(8, 9 + distance * 2))
        floor_y = self.view_height_cells - 4
        scale = max(0.9, 3.2 / (distance + 0.15))
        scale *= 1.12 if side == 0 else 0.84
        body_w = max(6, int(round(10 * scale)))
        body_h = max(6, int(round(10 * scale)))
        left = center_x - body_w // 2
        top = floor_y - body_h + 1

        shadow_w = max(4, int(body_w * 0.9))
        shadow_h = max(2, int(body_h * 0.18))
        x0, y0, x1, y1 = self.rect_from_cells(center_x - shadow_w // 2, floor_y + 1, shadow_w, shadow_h)
        self.monster_detail_items.append(self.canvas.create_oval(x0, y0, x1, y1, fill="#0a0b0d", outline=""))

        def add_rect(cx: int, cy: int, cw: int, ch: int, color: str, outline: str = "") -> None:
            x0, y0, x1, y1 = self.rect_from_cells(cx, cy, cw, ch)
            self.monster_detail_items.append(self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=outline or color))

        def add_eye(ex: int, ey: int, glow: str, pupil: str) -> None:
            gx0, gy0, gx1, gy1 = self.rect_from_cells(ex, ey, 1, 1)
            pad = max(1, self.cell_w // 2)
            self.monster_detail_items.append(self.canvas.create_oval(gx0 - pad, gy0 - pad, gx1 + pad, gy1 + pad, fill=glow, outline=""))
            self.monster_detail_items.append(self.canvas.create_oval(gx0 + 1, gy0 + 1, gx1 - 1, gy1 - 1, fill=pupil, outline=""))

        if monster_tile == "R":
            add_rect(left + 2, top + 3, max(4, body_w - 4), max(3, body_h - 4), palette["mid"])
            add_rect(left + 3, top + 2, max(4, body_w - 5), max(3, body_h // 2), palette["light"])
            add_rect(left + body_w - 3, top + body_h // 2, 2, 2, palette["accent"])
            add_rect(left + 1, top + 2, 2, 2, palette["light"])
            add_rect(left + body_w - 1, top + 1, 1, max(3, body_h // 2), palette["bone"])
            add_rect(left + 0, top + body_h - 2, max(2, body_w // 4), 1, palette["shadow"])
            add_rect(left + body_w // 3, top + body_h - 1, max(2, body_w // 5), 1, palette["shadow"])
            add_rect(left + body_w - 3, top + body_h - 2, 1, 2, palette["shadow"])
            add_eye(left + body_w // 3, top + max(1, body_h // 3), self.shade_color(palette["eye"], 1.2), palette["eye"])
            add_eye(left + body_w // 2 + 1, top + max(1, body_h // 3), self.shade_color(palette["eye"], 1.2), palette["eye"])
        elif monster_tile == "S":
            skull_w = max(4, body_w - 4)
            skull_h = max(3, body_h // 3)
            rib_w = max(3, body_w - 6)
            add_rect(left + 2, top + 1, skull_w, skull_h, palette["bone"])
            add_rect(left + 3, top + 2, skull_w - 2, max(1, skull_h - 2), palette["light"])
            add_rect(left + 3, top + skull_h + 1, rib_w, max(3, body_h // 3), palette["mid"])
            add_rect(left + body_w // 2 - 1, top + skull_h, 2, max(4, body_h // 2), palette["shadow"])
            add_rect(left + 2, top + body_h - 3, 1, 3, palette["bone"])
            add_rect(left + body_w - 3, top + body_h - 3, 1, 3, palette["bone"])
            add_rect(left + 1, top + body_h - 1, max(2, body_w // 3), 1, palette["shadow"])
            add_rect(left + body_w - 1 - max(2, body_w // 3), top + body_h - 1, max(2, body_w // 3), 1, palette["shadow"])
            add_eye(left + body_w // 3, top + 2, self.shade_color(palette["eye"], 0.7), palette["eye"])
            add_eye(left + body_w // 2 + 1, top + 2, self.shade_color(palette["eye"], 0.7), palette["eye"])
            add_rect(left + body_w // 2 - 1, top + skull_h - 1, 2, 1, palette["accent"])
        else:
            add_rect(left + 1, top + 2, max(5, body_w - 2), max(4, body_h - 3), palette["base"])
            add_rect(left + 2, top + 1, max(4, body_w - 4), max(3, body_h // 2), palette["light"])
            add_rect(left + 0, top + body_h // 2, 2, max(3, body_h // 2), palette["shadow"])
            add_rect(left + body_w - 2, top + body_h // 2, 2, max(3, body_h // 2), palette["shadow"])
            add_rect(left + body_w // 3, top + body_h - 2, max(2, body_w // 5), 2, palette["shadow"])
            add_rect(left + body_w // 2 + 1, top + body_h - 2, max(2, body_w // 5), 2, palette["shadow"])
            add_rect(left + 2, top + 0, max(2, body_w // 4), 2, palette["accent"])
            add_rect(left + body_w - 2 - max(2, body_w // 4), top + 0, max(2, body_w // 4), 2, palette["accent"])
            add_eye(left + body_w // 3, top + max(1, body_h // 3), self.shade_color(palette["eye"], 0.9), palette["eye"])
            add_eye(left + body_w // 2 + 1, top + max(1, body_h // 3), self.shade_color(palette["eye"], 0.9), palette["eye"])

    def blend_hex_colors(self, colors: List[str]) -> Optional[str]:
        valid = [color for color in colors if color and isinstance(color, str) and color.startswith("#") and len(color) == 7]
        if not valid:
            return None
        r = sum(int(color[1:3], 16) for color in valid) // len(valid)
        g = sum(int(color[3:5], 16) for color in valid) // len(valid)
        b = sum(int(color[5:7], 16) for color in valid) // len(valid)
        return f"#{r:02x}{g:02x}{b:02x}"

    def sample_wall_column_color(
        self,
        grid: List[List[str]],
        cam_x: float,
        cam_y: float,
        dir_x: float,
        dir_y: float,
        plane_x: float,
        plane_y: float,
        screen_x: int,
        screen_y: int,
        wall_textures: Dict[str, AnsiTexture],
    ) -> Optional[str]:
        samples = max(1, int(self.view_antialias_samples))
        colors: List[str] = []
        for sample_index in range(samples):
            sub_x = screen_x + (sample_index + 0.5) / samples
            camera_x = 2.0 * sub_x / max(1, self.view_width_cells) - 1.0
            ray_dir_x = dir_x + plane_x * camera_x
            ray_dir_y = dir_y + plane_y * camera_x
            distance, cell, side, wall_hit = dungeona.cast_perspective_ray(grid, cam_x, cam_y, ray_dir_x, ray_dir_y)
            if cell == " ":
                continue
            line_height = int((self.view_height_cells * 0.92) / max(0.001, distance))
            draw_start = max(1, (self.view_height_cells // 2) - line_height // 2)
            draw_end = min(self.view_height_cells - 3, (self.view_height_cells // 2) + line_height // 2)
            if not (draw_start <= screen_y <= draw_end):
                continue
            texture = wall_textures.get(cell)
            fill: Optional[str] = None
            if texture is not None:
                y_ratio = (screen_y - draw_start) / max(1, draw_end - draw_start)
                texture_cell = self.sample_texture_cell(texture, wall_hit, y_ratio)
                if texture_cell is not None:
                    fill = self.texture_cell_fill(texture_cell)
            if fill is None:
                char = dungeona.wall_char(distance, side, cell)
                color_id = 2 if cell == "D" else 1
                fill = self.char_fill(char, color_id)
            if fill is not None:
                colors.append(self.shade_color(fill, self.distance_shade_factor(distance, side)))
        return self.blend_hex_colors(colors)

    def compute_floor_rects(self) -> List[Tuple[int, int, str]]:
        rects: List[Tuple[int, int, str]] = []
        px = float(self.state["x"]) + 0.5
        py = float(self.state["y"]) + 0.5
        facing = int(self.state["facing"])
        dir_x, dir_y = dungeona.facing_vector(facing)
        plane_x, plane_y = -dir_y * dungeona.FOV_SCALE, dir_x * dungeona.FOV_SCALE
        ray0_x = dir_x - plane_x
        ray0_y = dir_y - plane_y
        ray1_x = dir_x + plane_x
        ray1_y = dir_y + plane_y
        horizon = self.view_height_cells // 2

        for y in range(self.view_height_cells):
            if y <= horizon:
                for x in range(self.view_width_cells):
                    rects.append((x, y, self.procedural_ceiling_color(x, y)))
                continue

            row_distance = self.view_height_cells / max(0.001, 2.0 * (y - horizon))
            step_x = row_distance * (ray1_x - ray0_x) / max(1, self.view_width_cells)
            step_y = row_distance * (ray1_y - ray0_y) / max(1, self.view_width_cells)
            floor_x = px + row_distance * ray0_x
            floor_y = py + row_distance * ray0_y

            for x in range(self.view_width_cells):
                color = self.procedural_floor_world_color(floor_x, floor_y, row_distance)
                rects.append((x, y, color))
                floor_x += step_x
                floor_y += step_y

        return rects

    def compute_scene_rects(self) -> List[Tuple[int, int, str]]:
        grid = dungeona.current_grid(self.state)
        px = int(self.state["x"])
        py = int(self.state["y"])
        facing = int(self.state["facing"])
        items = dungeona.render_view(
            grid,
            px,
            py,
            facing,
            self.view_width_cells,
            self.view_height_cells,
            self.state.get("wall_textures"),
            self.state.get("floor_texture"),
            self.state.get("ceiling_texture"),
            self.state.get("animated_sprites"),
            self.state.get("static_sprites"),
            int(self.state.get("action_count", 0)),
        )
        textured_pixels: Dict[Tuple[int, int], str] = {}
        wall_textures = self.state.get("wall_textures") or {}
        cam_x, cam_y = px + 0.5, py + 0.5
        dir_x, dir_y = dungeona.facing_vector(facing)
        plane_x, plane_y = -dir_y * dungeona.FOV_SCALE, dir_x * dungeona.FOV_SCALE

        for y, x, ch, color_id in items:
            if 0 <= x < self.view_width_cells and 0 <= y < self.view_height_cells and color_id in {1, 2}:
                fill = self.sample_wall_column_color(
                    grid,
                    cam_x,
                    cam_y,
                    dir_x,
                    dir_y,
                    plane_x,
                    plane_y,
                    x,
                    y,
                    wall_textures,
                )
                if fill is not None:
                    textured_pixels[(x, y)] = fill

        rects = self.compute_floor_rects()
        for y, x, ch, color_id in items:
            if 0 <= x < self.view_width_cells and 0 <= y < self.view_height_cells:
                fill = textured_pixels.get((x, y))
                if fill is None:
                    fill = self.char_fill(ch, color_id)
                if fill is not None:
                    rects.append((x, y, fill))
        return rects

    def draw_view(self, force_scene: bool = False) -> None:
        render_key = self.scene_render_key()
        if force_scene or self.static_cache.get("last_render_key") != render_key:
            rects = self.compute_scene_rects()
            self.static_cache["last_render_key"] = render_key
            self.static_cache["last_render_items"] = rects
        else:
            rects = self.static_cache.get("last_render_items", [])
        self.clear_item_list(self.dynamic_scene_items)
        if isinstance(rects, list):
            self.create_batched_rectangles(rects, self.dynamic_scene_items)

    def draw_minimap(self) -> None:
        if not bool(self.state.get("show_map")):
            return
        grid = dungeona.current_grid(self.state)
        px = int(self.state["x"])
        py = int(self.state["y"])
        facing = int(self.state["facing"])
        radius = 4
        left = 10 * self.render_scale
        top = 10 * self.render_scale

        self.dynamic_overlay_items.append(self.canvas.create_rectangle(
            left - 6,
            top - 18,
            left + self.minimap_tile * 9 + 6,
            top + self.minimap_tile * 9 + 6,
            fill="#0b0f14",
            outline="#2c3742",
        ))
        self.dynamic_overlay_items.append(self.canvas.create_text(left, top - 10, anchor="w", fill="#7f9bb8", text=f"F{int(self.state['floor']) + 1}", font=("TkFixedFont", 9, "bold")))

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                mx = px + dx
                my = py + dy
                cell = dungeona.cell_at(grid, mx, my)
                color = "#1a1d21"
                if cell == "#":
                    color = "#4e5762"
                elif cell == "D":
                    color = "#9f7833"
                elif dungeona.is_monster(cell):
                    info = dungeona.monster_info(cell if cell in dungeona.MONSTER_TILES else "R")
                    color = self.color_for(int(info["color"]))
                elif cell == dungeona.QUEST_ITEM_TILE:
                    color = "#bba643"
                elif cell == dungeona.QUEST_TARGET_TILE:
                    color = "#7f4ea1"
                elif cell in {"<", ">"}:
                    color = "#5d7fae"
                elif cell in {".", " "}:
                    color = "#2a241f"
                x0 = left + (dx + radius) * self.minimap_tile
                y0 = top + (dy + radius) * self.minimap_tile
                self.dynamic_overlay_items.append(self.canvas.create_rectangle(x0, y0, x0 + self.minimap_tile - 1, y0 + self.minimap_tile - 1, fill=color, outline="#0a0d10"))

        cx = left + radius * self.minimap_tile + self.minimap_tile // 2
        cy = top + radius * self.minimap_tile + self.minimap_tile // 2
        self.dynamic_overlay_items.append(self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill="#48b060", outline=""))
        dx, dy = dungeona.DIRECTIONS[facing]
        self.dynamic_overlay_items.append(self.canvas.create_line(cx, cy, cx + dx * 8, cy + dy * 8, fill="#48b060", width=2))

    def draw_status(self) -> None:
        y0 = self.view_height
        self.dynamic_overlay_items.append(self.canvas.create_rectangle(0, y0, self.window_width, self.window_height, fill=STATUS_BG, outline="#26303a"))

        energy = int(self.state["energy"])
        bar_w = 180
        fill_w = int(bar_w * energy / max(1, dungeona.MAX_ENERGY))
        self.dynamic_overlay_items.append(self.canvas.create_text(12, y0 + 14, anchor="w", fill=TEXT_COLOR, text="Energy", font=("TkFixedFont", 10, "bold")))
        self.dynamic_overlay_items.append(self.canvas.create_rectangle(70, y0 + 6, 70 + bar_w, y0 + 22, fill="#1e252c", outline="#34404c"))
        self.dynamic_overlay_items.append(self.canvas.create_rectangle(70, y0 + 6, 70 + fill_w, y0 + 22, fill="#48b060", outline=""))

        quest_status = "done" if bool(self.state["quest_complete"]) else ("carrying" if bool(self.state["has_grail"]) else "missing")
        line1 = (
            f"Floor {int(self.state['floor']) + 1}/{len(self.state['floors'])}   "
            f"Pos {self.state['x']},{self.state['y']}   "
            f"Facing {dungeona.DIRECTION_NAMES[int(self.state['facing'])]}   "
            f"Defeated {self.state['score']}"
        )
        line2 = f"Inventory {dungeona.inventory_count(self.state)}/{dungeona.MAX_CARRIED_ITEMS}   Grail {quest_status}"
        line3 = str(self.state["message"])[:100]

        self.dynamic_overlay_items.append(self.canvas.create_text(12, y0 + 34, anchor="w", fill=TEXT_COLOR, text=line1, font=("TkFixedFont", 10)))
        self.dynamic_overlay_items.append(self.canvas.create_text(12, y0 + 50, anchor="w", fill="#c9b24a", text=line2, font=("TkFixedFont", 10)))
        self.dynamic_overlay_items.append(self.canvas.create_text(self.window_width - 12, y0 + 14, anchor="e", fill="#7f8b97", text=KEY_HELP, font=("TkFixedFont", 9)))
        self.dynamic_overlay_items.append(self.canvas.create_text(12, y0 + 62, anchor="w", fill="#7f9bb8", text=line3, font=("TkFixedFont", 9)))

    def draw_congrats_overlay(self) -> None:
        if not bool(self.state.get("show_congrats_banner")):
            return
        left = max(40, self.window_width // 8)
        top = max(60, self.view_height // 3)
        right = self.window_width - max(40, self.window_width // 8)
        bottom = min(self.view_height - 20, top + 110)
        self.dynamic_overlay_items.append(self.canvas.create_rectangle(left, top, right, bottom, fill="#0d1014", outline="#c9b24a", width=3))
        self.dynamic_overlay_items.append(self.canvas.create_text((left + right) // 2, top + 36, text="Congratulations.", fill="#d8c15f", font=("TkFixedFont", 20, "bold")))
        self.dynamic_overlay_items.append(self.canvas.create_text((left + right) // 2, top + 74, text="Quest complete.", fill="#d8dee9", font=("TkFixedFont", 11)))

    def advance_if_acted(self, acted: bool) -> None:
        if acted:
            self.state["action_count"] = int(self.state.get("action_count", 0)) + 1
            dungeona.advance_world(self.state)

    def on_key(self, event) -> None:
        key = event.keysym.lower()
        char = event.char
        acted = False

        if self.state.get("show_congrats_banner") and key not in {"x"}:
            self.state["show_congrats_banner"] = False

        if key in {"up", "w"}:
            old_pos = (self.state["x"], self.state["y"])
            dungeona.try_move(self.state, 1)
            self.state["message"] = "You move forward." if old_pos != (self.state["x"], self.state["y"]) else "A wall blocks your way."
            acted = True
        elif key in {"down", "s"}:
            old_pos = (self.state["x"], self.state["y"])
            dungeona.try_move(self.state, -1)
            self.state["message"] = "You move backward." if old_pos != (self.state["x"], self.state["y"]) else "You cannot move there."
            acted = True
        elif key == "q":
            self.state["facing"] = (int(self.state["facing"]) - 1) % 4
            self.state["message"] = "You turn left."
            acted = True
        elif key == "e":
            self.state["facing"] = (int(self.state["facing"]) + 1) % 4
            self.state["message"] = "You turn right."
            acted = True
        elif key == "z":
            old_pos = (self.state["x"], self.state["y"])
            dungeona.try_strafe(self.state, -1)
            self.state["message"] = "You sidestep left." if old_pos != (self.state["x"], self.state["y"]) else "Blocked on the left."
            acted = True
        elif key == "c":
            old_pos = (self.state["x"], self.state["y"])
            dungeona.try_strafe(self.state, 1)
            self.state["message"] = "You sidestep right." if old_pos != (self.state["x"], self.state["y"]) else "Blocked on the right."
            acted = True
        elif key in {"space", "return"}:
            self.state["message"] = dungeona.use_action(self.state)
            acted = True
        elif char == ".":
            self.state["energy"] = min(dungeona.MAX_ENERGY, int(self.state["energy"]) + dungeona.WAIT_ENERGY_GAIN)
            self.state["message"] = "You wait and regain a little energy."
            acted = True
        elif key == "m":
            self.state["show_map"] = not bool(self.state["show_map"])
            self.state["message"] = f"Map {'shown' if self.state['show_map'] else 'hidden'}."
            acted = True
        elif char == ">":
            self.state["message"] = dungeona.travel_stairs(self.state, 1)
            acted = True
        elif char == "<":
            self.state["message"] = dungeona.travel_stairs(self.state, -1)
            acted = True
        elif key == "x":
            self.root.destroy()
            return

        self.advance_if_acted(acted)
        self.draw_scene(force_scene=acted)

    def draw_scene(self, force_scene: bool = False) -> None:
        self.ensure_frame_layer()
        self.draw_view(force_scene=force_scene)
        self.draw_monster_detail_art()
        self.draw_item_detail_art()
        self.clear_item_list(self.dynamic_overlay_items)
        self.draw_minimap()
        self.draw_status()
        self.draw_congrats_overlay()

    def run(self) -> None:
        self.root.mainloop()

    def on_resize(self, event) -> None:
        if event.widget is not self.root:
            return
        prev_metrics = (
            self.window_width,
            self.window_height,
            self.view_height,
            self.view_width_cells,
            self.view_height_cells,
            self.render_scale,
        )
        self.update_render_metrics(event.width, event.height)
        new_metrics = (
            self.window_width,
            self.window_height,
            self.view_height,
            self.view_width_cells,
            self.view_height_cells,
            self.render_scale,
        )
        if new_metrics == prev_metrics:
            return
        self.canvas.config(width=self.window_width, height=self.window_height)
        self.static_cache["last_render_key"] = None
        self.draw_scene(force_scene=True)


def main() -> None:
    app = DungeonaRenderer()
    app.run()


if __name__ == "__main__":
    main()
