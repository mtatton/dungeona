from __future__ import annotations

from pathlib import Path

import dungeona
from ans import AnsiCell, AnsiTexture

from conftest import FakeStdScr, make_grid, make_state


def test_setup_colors_and_texture_loading_helpers(tmp_path: Path, monkeypatch):
    init_calls = []
    monkeypatch.setattr(dungeona.curses, "start_color", lambda: init_calls.append(("start",)))
    monkeypatch.setattr(dungeona.curses, "use_default_colors", lambda: init_calls.append(("default",)))
    monkeypatch.setattr(dungeona.curses, "init_pair", lambda pair, fg, bg: init_calls.append((pair, fg, bg)))

    dungeona.setup_colors()
    assert init_calls[0] == ("start",)
    assert init_calls[1] == ("default",)
    assert init_calls[-1] == (10, dungeona.QUEST_COLOR, -1)

    texture_dir = tmp_path / "textures"
    texture_dir.mkdir()
    for filename in ("wall.ans", "door.ans", "floor.ans", "ceiling.ans", "rat001.ans", "rat003.ans"):
        (texture_dir / filename).write_text("stub")
    monkeypatch.setattr(dungeona, "TEXTURE_DIR", texture_dir)

    loaded = []

    def fake_load(path):
        loaded.append(Path(path).name)
        if Path(path).name == "door.ans":
            raise ValueError("broken")
        return AnsiTexture(width=1, height=1, rows=[[AnsiCell(char=Path(path).stem[0].upper())]])

    monkeypatch.setattr(dungeona, "load_ans_texture", fake_load)

    wall_textures = dungeona.load_wall_textures()
    assert wall_textures.keys() == {"#"}
    assert wall_textures["#"].sample_char(0, 0) == "W"

    assert dungeona.load_surface_texture("floor.ans").sample_char(0, 0) == "F"
    assert dungeona.load_surface_texture("missing.ans") is None

    monkeypatch.setattr(
        dungeona,
        "load_ans_texture",
        lambda path: (_ for _ in ()).throw(RuntimeError("nope")) if Path(path).name == "ceiling.ans" else fake_load(path),
    )
    assert dungeona.load_surface_texture("ceiling.ans") is None

    monkeypatch.setattr(dungeona, "load_ans_texture", fake_load)
    animations = dungeona.load_animated_sprites()
    assert animations["rat"][0] == ["R"]
    assert animations["rat"][1] == ["R"]


def test_cast_ray_render_view_and_texture_fallbacks():
    texture = AnsiTexture(
        width=2,
        height=2,
        rows=[
            [AnsiCell(char="X"), AnsiCell(char="Y")],
            [AnsiCell(char="Z"), AnsiCell(char="W")],
        ],
    )
    blank = AnsiTexture(width=1, height=1, rows=[[AnsiCell(char=" ")]])

    grid = make_grid(
        "#########",
        "#.......#",
        "#..#....#",
        "#..D....#",
        "#.......#",
        "#########",
    )

    distance, cell, side, wall_hit = dungeona.cast_perspective_ray(grid, 1.5, 3.5, 1.0, 0.0)
    assert cell == "D"
    assert side == 0
    assert 0.0 <= wall_hit <= 1.0
    assert distance > 0

    door_down_grid = make_grid(
        "#####",
        "#...#",
        "#.D.#",
        "#...#",
        "#####",
    )
    distance2, cell2, side2, _wall_hit2 = dungeona.cast_perspective_ray(door_down_grid, 2.5, 1.5, 0.0, 1.0)
    assert cell2 == "D"
    assert side2 == 1
    assert distance2 > 0

    far_distance, far_cell, _far_side, _far_hit = dungeona.cast_perspective_ray(grid, 1.5, 1.5, 1.0, 0.0, max_depth=0.1)
    assert far_distance == 0.1
    assert far_cell == " "

    textured_items = dungeona.render_view(
        grid,
        px=1,
        py=3,
        facing=1,
        width=12,
        height=12,
        wall_textures={"D": texture},
        floor_texture=texture,
        ceiling_texture=blank,
    )
    chars = {ch for _y, _x, ch, _color in textured_items}
    assert {"X", "Y", "Z", "W"} & chars
    assert "." not in chars  # texture replaces some floor fallback characters

    side_shaded_grid = make_grid(
        "#####",
        "#...#",
        "#...#",
        "##.##",
        "#####",
    )
    side_items = dungeona.render_view(side_shaded_grid, px=2, py=1, facing=2, width=7, height=9)
    assert any(ch in {"▓", "▒", "░"} and color == 1 for _y, _x, ch, color in side_items)


def test_draw_minimap_banner_overlay_and_scene(monkeypatch):
    grid = make_grid(
        "#########",
        "#R.G.A<>#",
        "#.......#",
        "#########",
    )
    state = make_state([grid], x=3, y=2, facing=1, energy=5, score=2, has_grail=True, message="Beware!")
    state["show_congrats_banner"] = True

    stdscr = FakeStdScr(height=20, width=120)
    monkeypatch.setattr(dungeona.curses, "color_pair", lambda value: value * 10)
    monkeypatch.setattr(dungeona.curses, "A_BOLD", 1000)

    dungeona.draw_minimap(stdscr, grid, 3, 2, 1, 0, 3, 2)
    minimap_strings = [args[2] for name, args in stdscr.calls if name == "addstr"]
    assert "F1" in minimap_strings
    assert "rr" in minimap_strings
    assert "GG" in minimap_strings
    assert ">>" in minimap_strings
    assert "<<" in minimap_strings

    stdscr.calls.clear()
    dungeona.draw_banner_overlay(stdscr, ["WIN"], 8)
    assert any(name == "addch" and args[2] == "#" for name, args in stdscr.calls)
    assert any(name == "addstr" and args[2] == "WIN" for name, args in stdscr.calls)

    stdscr.calls.clear()
    overlays = []
    monkeypatch.setattr(dungeona, "render_view", lambda *args, **kwargs: [(2, 4, "@", 7)])
    monkeypatch.setattr(dungeona, "draw_minimap", lambda *args: overlays.append("map"))
    monkeypatch.setattr(dungeona, "draw_banner_overlay", lambda *args: overlays.append("banner"))

    dungeona.draw_scene(stdscr, state)

    scene_strings = [args[2] for name, args in stdscr.calls if name == "addstr"]
    assert any("Dungeona - Holy Grail Quest" in text for text in scene_strings)
    assert any("5/12" in text and "defeated:2" in text for text in scene_strings)
    assert any("Beware!" in text for text in scene_strings)
    assert overlays == ["map", "banner"]


def test_inventory_and_quest_helper_edges():
    floors = [make_grid("#####", "#.A<#", "#####") for _ in range(dungeona.QUEST_TARGET_FLOOR + 1)]
    state = make_state(
        floors,
        floor=dungeona.QUEST_TARGET_FLOOR,
        x=2,
        y=1,
        has_grail=True,
        quest_complete=False,
    )

    assert dungeona.inventory_count(state) == 1
    assert dungeona.can_pick_item(state) is True
    assert dungeona.deliver_quest_if_possible(state, floors[dungeona.QUEST_TARGET_FLOOR]) is True
    assert state["quest_complete"] is True
    assert state["message"].endswith("Quest complete!")

    blank_state = make_state([make_grid("###", "#<#", "###")], x=1, y=1, has_grail=False)
    assert dungeona.deliver_quest_if_possible(blank_state, blank_state["floors"][0]) is False
    assert dungeona.use_current_tile(blank_state) is True
    assert blank_state["message"] == "The stairs go nowhere."

    empty_state = make_state([make_grid("###", "#.#", "###")], x=1, y=1)
    assert dungeona.use_current_tile(empty_state) is False
    assert dungeona.find_start_position([make_grid("###", "###")]) == (0, 1, 1)
