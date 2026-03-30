from __future__ import annotations

import dungeona

from conftest import make_grid, make_state


def test_find_visible_tile_variants_and_stairs_helpers():
    grid = make_grid(
        "#########",
        "#.......#",
        "#..G.R..#",
        "#..P....#",
        "#..A.>..#",
        "#....<..#",
        "#########",
    )
    grid[3][3] = "."
    px, py, facing = 3, 3, 0

    assert dungeona.find_visible_tile(grid, px, py, facing, "G") == (1, 0, 0)
    assert dungeona.grail_in_view(grid, px, py, facing) == (1, 0, 0)

    grid[2][3] = "."
    grid[2][4] = "R"
    assert dungeona.visible_monster(grid, px, py, facing) == (1, 1, 1, "R")

    grid[2][4] = "."
    grid[4][3] = "A"
    assert dungeona.altar_in_view(grid, px, py, 2) == (1, 0, 0)

    grid[4][4] = ">"
    assert dungeona.stairs_in_view(grid, px, py, 2) == (1, -1, -1, ">")


def test_find_visible_tile_stops_at_walls_and_doors():
    grid = make_grid(
        "#######",
        "#..D.G#",
        "#.....#",
        "#######",
    )
    assert dungeona.find_visible_tile(grid, 1, 1, 1, "G") is None

    wall_grid = make_grid(
        "#######",
        "#..#.G#",
        "#.....#",
        "#######",
    )
    assert dungeona.find_visible_tile(wall_grid, 1, 1, 1, "G") is None


def test_render_helpers_produce_draw_items():
    monster_items = []
    dungeona.render_monster_sprite(monster_items, width=80, height=24, distance=2, side=0, monster_tile="R")
    assert monster_items
    assert all(len(item) == 4 for item in monster_items)

    animated = {"rat": [["XX"], ["YY"]]}
    animated_items = []
    dungeona.render_monster_sprite(
        animated_items,
        width=80,
        height=24,
        distance=2,
        side=0,
        monster_tile="R",
        animated_sprites=animated,
        animation_step=1,
    )
    assert any(ch == "Y" for _y, _x, ch, _color in animated_items)

    grail_items = []
    altar_items = []
    stairs_items = []
    dungeona.render_grail_sprite(grail_items, 80, 24, 2, 0)
    dungeona.render_altar_sprite(altar_items, 80, 24, 2, 0)
    dungeona.render_stairs_sprite(stairs_items, 80, 24, 2, 0, ">")
    assert grail_items and altar_items and stairs_items


def test_monster_line_of_sight_rules():
    grid = make_grid(
        "########",
        "#R....P#",
        "########",
    )
    grid[1][6] = "."
    assert dungeona.monster_has_line_of_sight(grid, 1, 1, 6, 1) is True
    assert dungeona.monster_has_line_of_sight(grid, 1, 1, 6, 2) is False

    blocked = make_grid(
        "########",
        "#R.#..P#",
        "########",
    )
    blocked[1][6] = "."
    assert dungeona.monster_has_line_of_sight(blocked, 1, 1, 6, 1) is False


def test_iter_monsters_and_move_monsters_chase_behavior():
    floors = [make_grid(
        "#########",
        "#R.....P#",
        "#########",
    )]
    floors[0][1][7] = "."
    state = make_state(floors, x=7, y=1, monster_chase={})

    monsters = dungeona.iter_monsters(floors[0])
    assert monsters == [(1, 1, "R")]

    dungeona.move_monsters(state)

    assert floors[0][1][1] == "."
    assert floors[0][1][2] == "R"
    assert state["monster_chase"]["0"]["2,1"] == dungeona.MONSTER_CHASE_TURNS
    assert state["message"] == "A rat spots you!"


def test_move_monsters_respects_obstacles_and_multiple_seen_names():
    floors = [make_grid(
        "#######",
        "#.R...#",
        "#.....#",
        "#.S...#",
        "#.....#",
        "#######",
    )]
    state = make_state(floors, x=2, y=2, monster_chase={})

    dungeona.move_monsters(state)

    assert state["message"] == "Monsters spot you!"
    assert floors[0][1][2] == "R"
    assert floors[0][3][2] == "S"


def test_advance_world_moves_monsters_and_uses_current_tile(empty_two_floor_dungeon):
    state = make_state(empty_two_floor_dungeon, x=3, y=1, floor=0)
    dungeona.advance_world(state)

    assert state["floor"] == 1
    assert "floor 2" in state["message"]
