import tkinter as tk
from typing import Dict, List, Optional, Tuple

import dungeona
from ans import AnsiCell, AnsiTexture

CELL_SIZE = 8
MINIMAP_TILE = 14
VIEW_MARGIN = 12
BACKGROUND = "#0a0c0f"
CEILING_COLOR = "#11161c"
FLOOR_BASE = "#1c1815"
TEXT_COLOR = "#d8dee9"
STATUS_BG = "#101419"

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

KEY_HELP = "WASD/arrows move, Q/E turn, Z/C strafe, Space act, . wait, M map, </> stairs"


class DungeonaGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Dungeona GUI")
        self.root.configure(bg=BACKGROUND)

        self.view_width_cells = 96
        self.view_height_cells = 56
        self.view_width_px = self.view_width_cells * CELL_SIZE
        self.view_height_px = self.view_height_cells * CELL_SIZE
        self.status_height = 90
        self.minimap_size = MINIMAP_TILE * 9

        self.canvas = tk.Canvas(
            self.root,
            width=self.view_width_px + VIEW_MARGIN * 2,
            height=self.view_height_px + VIEW_MARGIN * 2 + self.status_height,
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
            "background_key": None,
            "background_items": [],
            "frame_key": None,
            "frame_items": [],
            "last_render_key": None,
            "last_render_items": [],
        }
        self.dynamic_scene_items: List[int] = []
        self.dynamic_overlay_items: List[int] = []
        self.monster_detail_items: List[int] = []
        self.item_detail_items: List[int] = []

        self.root.bind("<KeyPress>", self.on_key)
        self.root.bind("<Configure>", self.on_resize)
        self.redraw(force_scene=True)

    def color_for(self, color_id: int, default: str = "#cfcfcf") -> str:
        return COLOR_MAP.get(color_id, default)

    def shade_color(self, color: str, factor: float) -> str:
        color = color.lstrip("#")
        if len(color) != 6:
            return color
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def floor_band_color(self, row: int) -> str:
        ratio = row / max(1, self.view_height_cells - 1)
        if ratio < 0.58:
            return CEILING_COLOR
        depth = (ratio - 0.58) / 0.42
        depth = max(0.0, min(1.0, depth))
        base = FLOOR_BASE.lstrip("#")
        r = int(base[0:2], 16)
        g = int(base[2:4], 16)
        b = int(base[4:6], 16)
        boost = int(24 * (1.0 - depth))
        return f"#{min(255, r + boost):02x}{min(255, g + boost):02x}{min(255, b + boost):02x}"

    def scene_origin(self) -> Tuple[int, int]:
        return VIEW_MARGIN, VIEW_MARGIN

    def clear_item_list(self, items: List[int]) -> None:
        for item in items:
            self.canvas.delete(item)
        items.clear()

    def rect_from_cells(self, x: int, y: int, w: int = 1, h: int = 1) -> Tuple[int, int, int, int]:
        ox, oy = self.scene_origin()
        return (
            ox + x * CELL_SIZE,
            oy + y * CELL_SIZE,
            ox + (x + w) * CELL_SIZE,
            oy + (y + h) * CELL_SIZE,
        )

    def draw_cell_rect(self, x: int, y: int, color: str) -> int:
        x0, y0, x1, y1 = self.rect_from_cells(x, y)
        return self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=color)

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

    def ensure_background_layer(self) -> None:
        background_key = (self.view_width_cells, self.view_height_cells, CELL_SIZE)
        if self.static_cache.get("background_key") == background_key:
            return
        old_items = self.static_cache.get("background_items", [])
        if isinstance(old_items, list):
            self.clear_item_list(old_items)
        items: List[int] = []
        for y in range(self.view_height_cells):
            color = self.floor_band_color(y)
            x0, y0, x1, y1 = self.rect_from_cells(0, y, self.view_width_cells, 1)
            items.append(self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=color))
        self.static_cache["background_key"] = background_key
        self.static_cache["background_items"] = items

    def ensure_frame_layer(self) -> None:
        frame_key = (self.view_width_px, self.view_height_px, self.status_height)
        if self.static_cache.get("frame_key") == frame_key:
            return
        old_items = self.static_cache.get("frame_items", [])
        if isinstance(old_items, list):
            self.clear_item_list(old_items)
        items: List[int] = []
        left, top = self.scene_origin()
        right = left + self.view_width_px
        bottom = top + self.view_height_px
        items.append(self.canvas.create_rectangle(left - 2, top - 2, right + 2, bottom + 2, outline="#20262d", width=2))
        items.append(self.canvas.create_line(left + self.view_width_px // 2, top + self.view_height_px // 2 - 8, left + self.view_width_px // 2, top + self.view_height_px // 2 + 8, fill="#33404d"))
        items.append(self.canvas.create_line(left + self.view_width_px // 2 - 8, top + self.view_height_px // 2, left + self.view_width_px // 2 + 8, top + self.view_height_px // 2, fill="#33404d"))
        self.static_cache["frame_key"] = frame_key
        self.static_cache["frame_items"] = items

    def on_resize(self, event) -> None:
        width = max(500, event.width)
        height = max(420, event.height)
        usable_w = max(320, width - VIEW_MARGIN * 2)
        usable_h = max(220, height - VIEW_MARGIN * 2 - self.status_height)
        new_view_width_cells = max(48, usable_w // CELL_SIZE)
        new_view_height_cells = max(32, usable_h // CELL_SIZE)
        size_changed = (
            new_view_width_cells != self.view_width_cells
            or new_view_height_cells != self.view_height_cells
        )
        self.view_width_cells = new_view_width_cells
        self.view_height_cells = new_view_height_cells
        self.view_width_px = self.view_width_cells * CELL_SIZE
        self.view_height_px = self.view_height_cells * CELL_SIZE
        self.redraw(force_scene=size_changed)

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
        elif key in {"q"}:
            self.state["facing"] = (int(self.state["facing"]) - 1) % 4
            self.state["message"] = "You turn left."
            acted = True
        elif key in {"e"}:
            self.state["facing"] = (int(self.state["facing"]) + 1) % 4
            self.state["message"] = "You turn right."
            acted = True
        elif key in {"z"}:
            old_pos = (self.state["x"], self.state["y"])
            dungeona.try_strafe(self.state, -1)
            self.state["message"] = "You sidestep left." if old_pos != (self.state["x"], self.state["y"]) else "Blocked on the left."
            acted = True
        elif key in {"c"}:
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
        self.redraw(force_scene=acted)

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
        base_map = {
            "Bk": "#000000",
            "Re": "#aa0000",
            "Gr": "#00aa00",
            "Ye": "#aa5500",
            "Bl": "#0000aa",
            "Ma": "#aa00aa",
            "Cy": "#00aaaa",
            "Wh": "#aaaaaa",
        }
        bright_map = {
            "Bk": "#555555",
            "Re": "#ff5555",
            "Gr": "#55ff55",
            "Ye": "#ffff55",
            "Bl": "#5555ff",
            "Ma": "#ff55ff",
            "Cy": "#55ffff",
            "Wh": "#ffffff",
        }
        dark_map = {
            "Bk": "#000000",
            "Re": "#550000",
            "Gr": "#005500",
            "Ye": "#553300",
            "Bl": "#000055",
            "Ma": "#550055",
            "Cy": "#005555",
            "Wh": "#555555",
        }
        if intensity == "hi":
            return bright_map.get(color_name, base_map["Wh"])
        if intensity == "lo":
            return dark_map.get(color_name, base_map["Wh"])
        return base_map.get(color_name, base_map["Wh"])

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

    def visible_monster_info(self) -> Optional[Tuple[int, int, int, str]]:
        grid = dungeona.current_grid(self.state)
        return dungeona.visible_monster(
            grid,
            int(self.state["x"]),
            int(self.state["y"]),
            int(self.state["facing"]),
        )

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
            pad = max(1, CELL_SIZE // 3)
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
        info = dungeona.monster_info(monster_tile)
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
            pad = max(1, CELL_SIZE // 3)
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

        #if scale >= 1.15:
        #    label = str(info["name"]).upper()
        #    tx = VIEW_MARGIN + center_x * CELL_SIZE
        #    ty = VIEW_MARGIN + max(8, top - 2) * CELL_SIZE
        #    self.monster_detail_items.append(self.canvas.create_text(tx, ty, text=label, fill=self.shade_color(palette["light"], 1.05), font=("TkFixedFont", max(8, int(8 * scale)), "bold")))

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
        rects: List[Tuple[int, int, str]] = []
        wall_textures = self.state.get("wall_textures") or {}
        cam_x = px + 0.5
        cam_y = py + 0.5
        dir_x, dir_y = dungeona.facing_vector(facing)
        plane_x, plane_y = -dir_y * dungeona.FOV_SCALE, dir_x * dungeona.FOV_SCALE

        wall_columns: Dict[int, Tuple[float, str, int, float, int, int]] = {}
        for x in range(self.view_width_cells):
            camera_x = 2.0 * x / max(1, self.view_width_cells - 1) - 1.0
            ray_dir_x = dir_x + plane_x * camera_x
            ray_dir_y = dir_y + plane_y * camera_x
            distance, cell, side, wall_hit = dungeona.cast_perspective_ray(grid, cam_x, cam_y, ray_dir_x, ray_dir_y)
            if cell in {"#", "D"}:
                line_height = int((self.view_height_cells * 0.92) / max(0.001, distance))
                draw_start = max(1, self.view_height_cells // 2 - line_height // 2)
                draw_end = min(self.view_height_cells - 3, self.view_height_cells // 2 + line_height // 2)
                wall_columns[x] = (distance, cell, side, wall_hit, draw_start, draw_end)

        for y, x, ch, color_id in items:
            if not (0 <= x < self.view_width_cells and 0 <= y < self.view_height_cells):
                continue
            fill: Optional[str] = None
            wall_sample = wall_columns.get(x)
            if wall_sample is not None:
                distance, cell, side, wall_hit, draw_start, draw_end = wall_sample
                if draw_start <= y <= draw_end and color_id in {1, 2}:
                    texture = wall_textures.get(cell)
                    if texture is not None:
                        y_ratio = (y - draw_start) / max(1, draw_end - draw_start)
                        texture_cell = self.sample_texture_cell(texture, wall_hit, y_ratio)
                        if texture_cell is not None:
                            fill = self.texture_cell_fill(texture_cell)
                            shade = max(0.22, min(1.08, (1.05 - min(1.0, distance / max(0.001, dungeona.MAX_RENDER_DEPTH)) * 0.55) * (0.84 if side == 1 else 1.0)))
                            fill = self.shade_color(fill, shade)
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
        left = VIEW_MARGIN + 10
        top = VIEW_MARGIN + 10
        radius = 4

        self.dynamic_overlay_items.append(self.canvas.create_rectangle(
            left - 8,
            top - 22,
            left + self.minimap_size + 8,
            top + self.minimap_size + 8,
            fill="#0b0f14",
            outline="#2c3742",
        ))
        self.dynamic_overlay_items.append(self.canvas.create_text(left, top - 12, anchor="w", fill="#7f9bb8", text=f"F{int(self.state['floor']) + 1}", font=("TkFixedFont", 10, "bold")))

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                mx = px + dx
                my = py + dy
                cell = dungeona.cell_at(grid, mx, my)
                x0 = left + (dx + radius) * MINIMAP_TILE
                y0 = top + (dy + radius) * MINIMAP_TILE
                color = "#161b21"
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
                self.dynamic_overlay_items.append(self.canvas.create_rectangle(x0, y0, x0 + MINIMAP_TILE - 1, y0 + MINIMAP_TILE - 1, fill=color, outline="#0a0d10"))

        center_x = left + radius * MINIMAP_TILE + MINIMAP_TILE // 2
        center_y = top + radius * MINIMAP_TILE + MINIMAP_TILE // 2
        self.dynamic_overlay_items.append(self.canvas.create_oval(center_x - 4, center_y - 4, center_x + 4, center_y + 4, fill="#48b060", outline=""))
        dx, dy = dungeona.DIRECTIONS[facing]
        self.dynamic_overlay_items.append(self.canvas.create_line(center_x, center_y, center_x + dx * 8, center_y + dy * 8, fill="#48b060", width=2))

    def draw_status(self) -> None:
        y0 = VIEW_MARGIN + self.view_height_px + 8
        width = self.view_width_px
        self.dynamic_overlay_items.append(self.canvas.create_rectangle(
            VIEW_MARGIN,
            y0,
            VIEW_MARGIN + width,
            y0 + self.status_height,
            fill=STATUS_BG,
            outline="#26303a",
        ))

        energy = int(self.state["energy"])
        bar_w = 220
        fill_w = int(bar_w * energy / max(1, dungeona.MAX_ENERGY))
        self.dynamic_overlay_items.append(self.canvas.create_text(VIEW_MARGIN + 12, y0 + 16, anchor="w", fill=TEXT_COLOR, text="Energy", font=("TkFixedFont", 10, "bold")))
        self.dynamic_overlay_items.append(self.canvas.create_rectangle(VIEW_MARGIN + 72, y0 + 8, VIEW_MARGIN + 72 + bar_w, y0 + 24, fill="#1e252c", outline="#34404c"))
        self.dynamic_overlay_items.append(self.canvas.create_rectangle(VIEW_MARGIN + 72, y0 + 8, VIEW_MARGIN + 72 + fill_w, y0 + 24, fill="#48b060", outline=""))

        quest_status = "done" if bool(self.state["quest_complete"]) else ("carrying" if bool(self.state["has_grail"]) else "missing")
        line1 = (
            f"Floor {int(self.state['floor']) + 1}/{len(self.state['floors'])}   "
            f"Pos {self.state['x']},{self.state['y']}   "
            f"Facing {dungeona.DIRECTION_NAMES[int(self.state['facing'])]}   "
            f"Defeated {self.state['score']}"
        )
        line2 = f"Inventory {dungeona.inventory_count(self.state)}/{dungeona.MAX_CARRIED_ITEMS}   Grail {quest_status}"
        line3 = str(self.state["message"])

        self.dynamic_overlay_items.append(self.canvas.create_text(VIEW_MARGIN + 12, y0 + 40, anchor="w", fill=TEXT_COLOR, text=line1, font=("TkFixedFont", 10)))
        self.dynamic_overlay_items.append(self.canvas.create_text(VIEW_MARGIN + 12, y0 + 58, anchor="w", fill="#c9b24a", text=line2, font=("TkFixedFont", 10)))
        self.dynamic_overlay_items.append(self.canvas.create_text(VIEW_MARGIN + 12, y0 + 76, anchor="w", fill="#7f9bb8", text=line3[:120], font=("TkFixedFont", 10)))
        self.dynamic_overlay_items.append(self.canvas.create_text(VIEW_MARGIN + width - 12, y0 + 16, anchor="e", fill="#7f8b97", text=KEY_HELP, font=("TkFixedFont", 9)))

    def draw_congrats_overlay(self) -> None:
        if not bool(self.state.get("show_congrats_banner")):
            return
        width = self.view_width_px
        height = self.view_height_px
        left = VIEW_MARGIN + 80
        top = VIEW_MARGIN + max(60, height // 3)
        right = VIEW_MARGIN + width - 80
        bottom = top + 120
        self.dynamic_overlay_items.append(self.canvas.create_rectangle(left, top, right, bottom, fill="#0d1014", outline="#c9b24a", width=3))
        self.dynamic_overlay_items.append(self.canvas.create_text(
            (left + right) // 2,
            top + 42,
            text="Congratulations.",
            fill="#d8c15f",
            font=("TkFixedFont", 22, "bold"),
        ))
        self.dynamic_overlay_items.append(self.canvas.create_text(
            (left + right) // 2,
            top + 78,
            text="Press any movement/action key to continue",
            fill="#d8dee9",
            font=("TkFixedFont", 10),
        ))

    def redraw(self, force_scene: bool = False) -> None:
        self.ensure_background_layer()
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


def main() -> None:
    app = DungeonaGUI()
    app.run()


if __name__ == "__main__":
    main()
