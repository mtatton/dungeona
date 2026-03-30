from __future__ import annotations

import importlib

import dungeona
from ans import AnsiCell, AnsiTexture

from conftest import DummyCanvas, DummyEvent, DummyRoot, make_grid


def _texture(*rows: str) -> AnsiTexture:
    return AnsiTexture(
        width=max(len(r) for r in rows),
        height=len(rows),
        rows=[[AnsiCell(char=ch) for ch in row] for row in rows],
    )


def build_gui(monkeypatch):
    import dungeona_gui

    root = DummyRoot()
    canvas = DummyCanvas()
    floors = [make_grid("#######", "#..G..#", "#.RA>.#", "#..<A.#", "#######")]

    monkeypatch.setattr(dungeona_gui.tk, "Tk", lambda: root)
    monkeypatch.setattr(dungeona_gui.tk, "Canvas", lambda *args, **kwargs: canvas)
    monkeypatch.setattr(dungeona_gui.dungeona, "load_floors", lambda: floors)
    monkeypatch.setattr(dungeona_gui.dungeona, "find_start_position", lambda _floors: (0, 1, 1))
    monkeypatch.setattr(dungeona_gui.dungeona, "load_wall_textures", lambda: {})
    monkeypatch.setattr(dungeona_gui.dungeona, "load_surface_texture", lambda _name: None)
    monkeypatch.setattr(dungeona_gui.dungeona, "load_animated_sprites", lambda: {})
    monkeypatch.setattr(dungeona_gui.dungeona, "collect_tile", lambda state, grid: None)

    original_redraw = dungeona_gui.DungeonaGUI.redraw
    monkeypatch.setattr(dungeona_gui.DungeonaGUI, "redraw", lambda self, force_scene=False: setattr(self, "_init_redraw", force_scene))
    app = dungeona_gui.DungeonaGUI()
    monkeypatch.setattr(dungeona_gui.DungeonaGUI, "redraw", original_redraw)
    return dungeona_gui, app, root, canvas


def build_renderer(monkeypatch):
    import dungeona_ren

    root = DummyRoot()
    canvas = DummyCanvas()
    floors = [make_grid("#######", "#..G..#", "#.RA>.#", "#..<A.#", "#######")]

    monkeypatch.setattr(dungeona_ren.tk, "Tk", lambda: root)
    monkeypatch.setattr(dungeona_ren.tk, "Canvas", lambda *args, **kwargs: canvas)
    monkeypatch.setattr(dungeona_ren.dungeona, "load_floors", lambda: floors)
    monkeypatch.setattr(dungeona_ren.dungeona, "find_start_position", lambda _floors: (0, 1, 1))
    monkeypatch.setattr(dungeona_ren.dungeona, "load_wall_textures", lambda: {})
    monkeypatch.setattr(dungeona_ren.dungeona, "load_surface_texture", lambda _name: None)
    monkeypatch.setattr(dungeona_ren.dungeona, "load_animated_sprites", lambda: {})
    monkeypatch.setattr(dungeona_ren.dungeona, "collect_tile", lambda state, grid: None)

    original_draw_scene = dungeona_ren.DungeonaRenderer.draw_scene
    monkeypatch.setattr(dungeona_ren.DungeonaRenderer, "draw_scene", lambda self, force_scene=False: setattr(self, "_init_scene", force_scene))
    app = dungeona_ren.DungeonaRenderer()
    monkeypatch.setattr(dungeona_ren.DungeonaRenderer, "draw_scene", original_draw_scene)
    return dungeona_ren, app, root, canvas


def test_gui_init_and_core_helpers(monkeypatch):
    dungeona_gui, app, root, canvas = build_gui(monkeypatch)

    assert root.titles == ["Dungeona GUI"]
    assert any(event == "<KeyPress>" for event, _handler in root.bound)
    assert any(event == "<Configure>" for event, _handler in root.bound)
    assert app._init_redraw is True
    assert "Find the Holy Grail" in app.state["message"]

    assert app.color_for(1) == dungeona_gui.COLOR_MAP[1]
    assert app.color_for(999, "#abc") == "#abc"
    assert app.shade_color("#808080", 0.5) == "#404040"
    assert app.shade_color("oops", 0.5) == "oops"
    assert app.blend_colors("#000000", "#ffffff", 0.25) == "#3f3f3f"
    assert app.blend_colors("bad", "#ffffff", 0.8) == "ffffff"
    assert app.floor_band_color(0) == dungeona_gui.CEILING_COLOR
    assert app.floor_band_color(app.view_height_cells - 1).startswith("#")
    assert app.scene_origin() == (dungeona_gui.VIEW_MARGIN, dungeona_gui.VIEW_MARGIN)
    assert app.rect_from_cells(1, 2, 3, 4) == (
        dungeona_gui.VIEW_MARGIN + dungeona_gui.CELL_SIZE,
        dungeona_gui.VIEW_MARGIN + 2 * dungeona_gui.CELL_SIZE,
        dungeona_gui.VIEW_MARGIN + 4 * dungeona_gui.CELL_SIZE,
        dungeona_gui.VIEW_MARGIN + 6 * dungeona_gui.CELL_SIZE,
    )
    rect_id = app.draw_cell_rect(0, 0, "#123456")
    assert rect_id > 0

    items = [101, 102]
    app.clear_item_list(items)
    assert items == []
    assert canvas.deleted[-2:] == [101, 102]

    runs = app.fill_rows_to_runs([[None, "#1", "#1", None, "#2"], ["#3", "#3", None, None, "#4"]])
    assert runs == [(1, 0, 2, "#1"), (4, 0, 1, "#2"), (0, 1, 2, "#3"), (4, 1, 1, "#4")]

    target_items = []
    app.create_batched_rectangles(runs[:2], target_items)
    assert len(target_items) == 2
    assert any(kind == "rectangle" for kind, _args, _kwargs in canvas.created)


def test_gui_texture_surface_and_detail_helpers(monkeypatch):
    _mod, app, _root, canvas = build_gui(monkeypatch)
    texture = AnsiTexture(
        width=3,
        height=2,
        rows=[
            [AnsiCell(" ", "Re", "Bk", "me"), AnsiCell("█", "Re", "Bk", "hi"), AnsiCell("░", "Wh", "Bl", "lo")],
            [AnsiCell(".", "Cy", "Bk", "me"), AnsiCell("▒", "Cy", "Bk", "me"), AnsiCell("X", "Gr", "Bk", "me")],
        ],
        source_path="sample.ans",
    )
    app.state["floor_texture"] = texture
    app.state["ceiling_texture"] = texture

    assert app.ansi_color_to_hex("Re", "hi") == "#ff5555"
    assert app.ansi_color_to_hex("Cy", "lo") == "#005555"
    assert app.ansi_color_to_hex("??", "me") == "#aaaaaa"
    assert app.texture_cell_fill(texture.rows[0][0]) == "#000000"
    assert app.texture_cell_fill(texture.rows[0][1]) == "#ff5555"
    assert app.texture_cell_fill(texture.rows[0][2]).startswith("#")
    assert app.texture_cell_fill(texture.rows[1][0]).startswith("#")
    assert app.texture_cell_fill(texture.rows[1][1]).startswith("#")
    assert app.texture_cell_fill(texture.rows[1][2]) == "#00aa00"

    assert app.sample_texture_cell(texture, 0.0, 0.0) == texture.rows[0][0]
    assert app.sample_texture_cell(texture, 1.0, 1.0) == texture.rows[1][2]
    assert app.sample_texture_cell(None, 0.2, 0.3) is None
    assert app.sample_repeating_texture_cell(texture, 2.2, 1.4) == texture.rows[0][0]
    assert app.texture_identity(texture)[1:3] == (3, 2)

    fill_rows = app.texture_fill_rows(texture)
    assert fill_rows is app.texture_fill_rows(texture)
    assert app.sample_texture_fill(texture, 1.0, 1.0) == fill_rows[1][2]
    assert app.sample_texture_fill(texture, 2.2, 1.4, repeat=True) == fill_rows[0][0]
    assert app.sample_texture_fill(None, 0.3, 0.4) is None

    surfaces = app.surface_fill_rows()
    assert isinstance(surfaces, tuple)
    assert surfaces is app.surface_fill_rows()
    assert any(any(cell is not None for cell in row) for row in surfaces)

    assert app.char_fill(" ", 1) is None
    assert app.char_fill("░", 1).startswith("#")
    assert app.char_fill("▒", 1).startswith("#")
    assert app.char_fill("▓", 1).startswith("#")
    assert app.char_fill("█", 1).startswith("#")
    assert app.char_fill("x", 1).startswith("#")

    assert app.detailed_monster_palette("R")["eye"] == "#ff6b57"
    assert app.detailed_monster_palette("S")["accent"] == "#7a5dcb"
    assert app.detailed_monster_palette("O")["eye"] == "#ffb347"
    assert app.detailed_item_palette(dungeona.QUEST_ITEM_TILE)["spark"] == "#fff7cc"
    assert app.detailed_item_palette(dungeona.QUEST_TARGET_TILE)["spark"] == "#efe6ff"

    monkeypatch.setattr(app, "visible_monster_info", lambda: (1, 0, 0, "R"))
    app.draw_monster_detail_art()
    assert app.monster_detail_items

    monkeypatch.setattr(dungeona, "grail_in_view", lambda *args: (2, 1, 1))
    monkeypatch.setattr(dungeona, "altar_in_view", lambda *args: (1, -1, -1))
    app.draw_item_detail_art()
    assert app.item_detail_items

    app.clear_item_list(app.item_detail_items)
    monkeypatch.setattr(dungeona, "grail_in_view", lambda *args: None)
    monkeypatch.setattr(dungeona, "altar_in_view", lambda *args: None)
    app.draw_item_detail_art()
    assert app.item_detail_items == []

    monkeypatch.setattr(app, "compute_scene_rects", lambda: [(1, 2, 3, "#abcdef")])
    app.draw_view(force_scene=True)
    first_scene_count = len(app.dynamic_scene_items)
    app.draw_view(force_scene=False)
    assert len(app.dynamic_scene_items) == first_scene_count

    app.state["show_map"] = True
    app.draw_minimap()
    assert app.dynamic_overlay_items
    overlay_count = len(app.dynamic_overlay_items)
    app.state["show_map"] = False
    app.draw_minimap()
    assert len(app.dynamic_overlay_items) == overlay_count

    app.draw_status()
    app.state["show_congrats_banner"] = True
    app.draw_congrats_overlay()
    assert len(app.dynamic_overlay_items) > overlay_count

    calls = []
    monkeypatch.setattr(app, "ensure_background_layer", lambda: calls.append("bg"))
    monkeypatch.setattr(app, "ensure_frame_layer", lambda: calls.append("frame"))
    monkeypatch.setattr(app, "draw_view", lambda force_scene=False: calls.append(("view", force_scene)))
    monkeypatch.setattr(app, "draw_monster_detail_art", lambda: calls.append("monster"))
    monkeypatch.setattr(app, "draw_item_detail_art", lambda: calls.append("item"))
    monkeypatch.setattr(app, "draw_minimap", lambda: calls.append("map"))
    monkeypatch.setattr(app, "draw_status", lambda: calls.append("status"))
    monkeypatch.setattr(app, "draw_congrats_overlay", lambda: calls.append("congrats"))
    app.redraw(force_scene=True)
    assert calls == ["bg", "frame", ("view", True), "monster", "item", "map", "status", "congrats"]


def test_gui_key_resize_run_and_main(monkeypatch):
    dungeona_gui, app, root, _canvas = build_gui(monkeypatch)
    moves = []
    monkeypatch.setattr(dungeona, "advance_world", lambda state: moves.append(("advance", state["action_count"])))
    monkeypatch.setattr(dungeona, "try_move", lambda state, step: (state.__setitem__("x", int(state["x"]) + (1 if step > 0 else 0)), moves.append(("move", step))))
    monkeypatch.setattr(dungeona, "try_strafe", lambda state, step: (state.__setitem__("y", int(state["y"]) + (1 if step > 0 else 0)), moves.append(("strafe", step))))
    monkeypatch.setattr(dungeona, "use_action", lambda state: "acted")
    monkeypatch.setattr(dungeona, "travel_stairs", lambda state, direction: f"stairs {direction}")
    redraw_calls = []
    monkeypatch.setattr(app, "redraw", lambda force_scene=False: redraw_calls.append(force_scene))

    app.state["show_congrats_banner"] = True
    app.on_key(DummyEvent(keysym="w", char="w"))
    assert app.state["message"] == "You move forward."
    assert app.state["show_congrats_banner"] is False

    app.on_key(DummyEvent(keysym="s", char="s"))
    assert app.state["message"] in {"You move backward.", "You cannot move there."}

    app.on_key(DummyEvent(keysym="q", char="q"))
    app.on_key(DummyEvent(keysym="e", char="e"))
    app.on_key(DummyEvent(keysym="z", char="z"))
    app.on_key(DummyEvent(keysym="c", char="c"))
    app.on_key(DummyEvent(keysym="space", char=" "))
    app.on_key(DummyEvent(keysym="period", char="."))
    app.on_key(DummyEvent(keysym="m", char="m"))
    app.on_key(DummyEvent(keysym="greater", char=">") )
    app.on_key(DummyEvent(keysym="less", char="<"))
    assert app.state["message"] == "stairs -1"
    assert app.state["action_count"] >= 9
    assert redraw_calls[-1] is True

    app.on_key(DummyEvent(keysym="x", char="x"))
    assert root.destroyed is True

    resize_calls = []
    monkeypatch.setattr(app, "redraw", lambda force_scene=False: resize_calls.append(force_scene))
    app.on_resize(DummyEvent(width=900, height=700))
    assert resize_calls == [True]
    assert app.view_width_cells >= 48
    app.run()
    assert root.mainloop_called is True

    called = []
    class FakeGUI:
        def run(self):
            called.append("run")
    monkeypatch.setattr(dungeona_gui, "DungeonaGUI", FakeGUI)
    dungeona_gui.main()
    assert called == ["run"]


def test_renderer_init_helpers_and_draw_pipeline(monkeypatch):
    dungeona_ren, app, root, canvas = build_renderer(monkeypatch)

    assert root.titles == ["Dungeona Renderer"]
    assert any(event == "resizable" for event, _args in root.bound)
    assert app._init_scene is True
    assert "Find the Holy Grail" in app.state["message"]

    app.update_render_metrics(1000, 700)
    assert app.window_width >= 320
    assert app.window_height >= 240
    assert dungeona_ren.MIN_RENDER_SCALE <= app.render_scale <= dungeona_ren.MAX_RENDER_SCALE
    assert app.rect_from_cells(1, 2, 3, 4) == (app.cell_w, 2 * app.cell_h, 4 * app.cell_w, 6 * app.cell_h)

    assert app.color_for(123, "#abc") == "#abc"
    assert app.shade_color("#808080", 0.5) == "#404040"
    assert app.shade_color("oops", 0.5) == "#cfcfcf"
    assert app.blend_colors("#000000", "#ffffff", 0.75) == "#bfbfbf"
    assert app.floor_band_color(0) == "#11161c"
    assert 0.22 <= app.distance_shade_factor(99.0, 1) <= 1.08
    assert app.ansi_color_to_hex("Re", "hi") == dungeona_ren.BRIGHT_ANSI_RGB["Re"]
    assert app.ansi_color_to_hex("Re", "lo") == dungeona_ren.DARK_ANSI_RGB["Re"]
    assert app.ansi_color_to_hex("??", "me") == dungeona_ren.ANSI_RGB["Wh"]

    texture = _texture("A ", "CD")
    app.state["floor_texture"] = texture
    app.state["ceiling_texture"] = texture
    assert app.texture_cell_fill(AnsiCell(" ", "Re", "Bk", "me")) == dungeona_ren.ANSI_RGB["Bk"]
    assert app.texture_cell_fill(AnsiCell("█", "Re", "Bk", "me")) == dungeona_ren.ANSI_RGB["Re"]
    assert app.sample_texture_cell(texture, 1.0, 1.0).char == "D"
    assert app.sample_repeating_texture_cell(texture, 2.2, 1.4).char == "A"
    assert app.texture_fill_rows(texture) is app.texture_fill_rows(texture)
    assert app.sample_texture_fill(texture, 1.0, 1.0).startswith("#")
    assert app.sample_texture_fill(texture, 2.2, 1.4, repeat=True).startswith("#")
    surfaces = app.surface_fill_rows()
    assert isinstance(surfaces, tuple)
    assert surfaces is app.surface_fill_rows()
    assert app.char_fill(" ", 1) is None
    assert app.char_fill("@", 1).startswith("#")

    assert app.detailed_monster_palette("S")["accent"] == "#7a5dcb"
    assert app.detailed_item_palette(dungeona.QUEST_TARGET_TILE)["spark"] == "#efe6ff"
    monkeypatch.setattr(app, "visible_monster_info", lambda: (1, 0, 0, "S"))
    app.draw_monster_detail_art()
    assert app.monster_detail_items
    monkeypatch.setattr(dungeona, "grail_in_view", lambda *args: (2, 1, 0))
    monkeypatch.setattr(dungeona, "altar_in_view", lambda *args: None)
    app.draw_item_detail_art()
    assert app.item_detail_items

    runs = app.fill_rows_to_runs([[None, "#1", "#1"], ["#2", None, "#3"]])
    assert runs == [(1, 0, 2, "#1"), (0, 1, 1, "#2"), (2, 1, 1, "#3")]
    target = []
    app.create_batched_rectangles(runs, target)
    assert len(target) == 3

    monkeypatch.setattr(app, "compute_scene_rects", lambda: [(1, 1, 2, "#123456")])
    app.draw_view(force_scene=True)
    assert app.dynamic_scene_items
    app.state["show_map"] = True
    app.draw_minimap()
    app.draw_status()
    app.state["show_congrats_banner"] = True
    app.draw_congrats_overlay()
    assert app.dynamic_overlay_items
    calls = []
    monkeypatch.setattr(app, "ensure_background_layer", lambda: calls.append("bg"))
    monkeypatch.setattr(app, "ensure_frame_layer", lambda: calls.append("frame"))
    monkeypatch.setattr(app, "draw_view", lambda force_scene=False: calls.append(("view", force_scene)))
    monkeypatch.setattr(app, "draw_monster_detail_art", lambda: calls.append("monster"))
    monkeypatch.setattr(app, "draw_item_detail_art", lambda: calls.append("item"))
    monkeypatch.setattr(app, "draw_minimap", lambda: calls.append("map"))
    monkeypatch.setattr(app, "draw_status", lambda: calls.append("status"))
    monkeypatch.setattr(app, "draw_congrats_overlay", lambda: calls.append("congrats"))
    app.draw_scene(force_scene=True)
    assert calls == ["bg", "frame", ("view", True), "monster", "item", "map", "status", "congrats"]


def test_renderer_events_resize_run_and_main(monkeypatch):
    dungeona_ren, app, root, _canvas = build_renderer(monkeypatch)
    events = []
    monkeypatch.setattr(dungeona, "advance_world", lambda state: events.append(("advance", state["action_count"])))
    monkeypatch.setattr(dungeona, "try_move", lambda state, step: (state.__setitem__("x", int(state["x"]) + (1 if step > 0 else 0)), events.append(("move", step))))
    monkeypatch.setattr(dungeona, "try_strafe", lambda state, step: (state.__setitem__("y", int(state["y"]) + (1 if step > 0 else 0)), events.append(("strafe", step))))
    monkeypatch.setattr(dungeona, "use_action", lambda state: "acted")
    monkeypatch.setattr(dungeona, "travel_stairs", lambda state, direction: f"stairs {direction}")
    draw_calls = []
    monkeypatch.setattr(app, "draw_scene", lambda force_scene=False: draw_calls.append(force_scene))

    app.state["show_congrats_banner"] = True
    app.on_key(DummyEvent(keysym="w", char="w"))
    app.on_key(DummyEvent(keysym="s", char="s"))
    app.on_key(DummyEvent(keysym="q", char="q"))
    app.on_key(DummyEvent(keysym="e", char="e"))
    app.on_key(DummyEvent(keysym="z", char="z"))
    app.on_key(DummyEvent(keysym="c", char="c"))
    app.on_key(DummyEvent(keysym="space", char=" "))
    app.on_key(DummyEvent(keysym="period", char="."))
    app.on_key(DummyEvent(keysym="m", char="m"))
    app.on_key(DummyEvent(keysym="greater", char=">") )
    app.on_key(DummyEvent(keysym="less", char="<"))
    assert app.state["show_congrats_banner"] is False
    assert app.state["action_count"] >= 9
    assert draw_calls[-1] is True
    app.on_key(DummyEvent(keysym="x", char="x"))
    assert root.destroyed is True

    resize_calls = []
    monkeypatch.setattr(app, "draw_scene", lambda force_scene=False: resize_calls.append(force_scene))
    app.on_resize(DummyEvent(widget=object(), width=700, height=500))
    assert resize_calls == []
    app.on_resize(DummyEvent(widget=root, width=900, height=700))
    assert resize_calls == [True]
    assert app.canvas.config_calls

    app.run()
    assert root.mainloop_called is True

    called = []
    class FakeRenderer:
        def run(self):
            called.append("run")
    monkeypatch.setattr(dungeona_ren, "DungeonaRenderer", FakeRenderer)
    dungeona_ren.main()
    assert called == ["run"]


def test_gui_real_scene_rects_and_layer_caches(monkeypatch):
    _mod, app, _root, canvas = build_gui(monkeypatch)
    app.state["floor_texture"] = _texture("..", "``")
    app.state["ceiling_texture"] = _texture("__", "..")

    app.ensure_background_layer()
    bg_count = len(app.static_cache["background_items"])
    app.ensure_background_layer()
    assert len(app.static_cache["background_items"]) == bg_count

    app.ensure_frame_layer()
    frame_count = len(app.static_cache["frame_items"])
    app.ensure_frame_layer()
    assert len(app.static_cache["frame_items"]) == frame_count

    key1 = app.scene_render_key()
    runs = app.compute_scene_rects()
    assert runs
    app.state["action_count"] = int(app.state.get("action_count", 0)) + 1
    assert app.scene_render_key() != key1
    assert app.visible_monster_info() is not None


def test_renderer_real_scene_rects_and_layer_caches(monkeypatch):
    _mod, app, _root, _canvas = build_renderer(monkeypatch)
    app.state["floor_texture"] = _texture("..", "``")
    app.state["ceiling_texture"] = _texture("__", "..")

    app.ensure_background_layer()
    bg_count = len(app.static_cache["background_items"])
    app.ensure_background_layer()
    assert len(app.static_cache["background_items"]) == bg_count

    app.ensure_frame_layer()
    frame_count = len(app.static_cache["frame_items"])
    app.ensure_frame_layer()
    assert len(app.static_cache["frame_items"]) == frame_count

    key1 = app.scene_render_key()
    runs = app.compute_scene_rects()
    assert runs
    app.state["action_count"] = int(app.state.get("action_count", 0)) + 1
    assert app.scene_render_key() != key1
    assert app.visible_monster_info() is not None
