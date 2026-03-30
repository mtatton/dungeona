from __future__ import annotations

from pathlib import Path

import dungeona
from ans import AnsiCell, AnsiTexture

from conftest import make_grid, make_state


def test_normalize_floor_rows_and_clamp():
    grid = dungeona.normalize_floor_rows(["##", "#"])
    assert grid == [["#", "#"], ["#", "#"]]
    assert dungeona.clamp(5, 1, 3) == 3
    assert dungeona.clamp(-1, 1, 3) == 1
    assert dungeona.clamp(2, 1, 3) == 2


def test_decorate_legacy_monsters_cycles_by_floor():
    grid = make_grid(
        "MMM",
        "M.M",
    )
    dungeona.decorate_legacy_monsters(grid, floor_index=1)
    assert [cell for row in grid for cell in row if cell != "."] == ["S", "O", "R", "S", "O"]


def test_initialize_and_load_floors_from_temp_db(tmp_path: Path):
    db_path = tmp_path / "dungeon_map.db"
    dungeona.initialize_map_db(db_path)
    floors = dungeona.load_floors(db_path)

    assert len(floors) == 3
    assert all(floors)
    assert dungeona.find_tile(floors[0], "G") is not None
    assert dungeona.find_tile(floors[2], "A") is not None


def test_current_grid_cell_queries_and_passability(empty_two_floor_dungeon):
    state = make_state(empty_two_floor_dungeon)
    grid = dungeona.current_grid(state)

    assert grid is empty_two_floor_dungeon[0]
    assert dungeona.is_inside(1, 1, grid) is True
    assert dungeona.is_inside(-1, 0, grid) is False
    assert dungeona.cell_at(grid, 3, 1) == ">"
    assert dungeona.cell_at(grid, 999, 999) == "#"
    assert dungeona.is_passable(".") is True
    assert dungeona.is_passable("G") is True
    assert dungeona.is_passable("R") is True
    assert dungeona.is_passable("D") is False
    assert dungeona.is_walkable_for_monster("A") is True
    assert dungeona.is_walkable_for_monster("R") is False


def test_texture_sampling_helpers_and_sprite_line_conversion():
    texture = AnsiTexture(
        width=2,
        height=2,
        rows=[
            [AnsiCell(char="A"), AnsiCell(char=" ")],
            [AnsiCell(char="C"), AnsiCell(char="D")],
        ],
    )

    assert dungeona.texture_to_sprite_lines(texture) == ["A", "CD"]
    assert dungeona.texture_char_for_column(texture, 0.0, 0.0, "?") == "A"
    assert dungeona.texture_char_for_column(texture, 1.0, 1.0, "?") == "D"
    assert dungeona.texture_char_for_column(texture, 0.9, 0.0, "?") == "A"
    assert dungeona.repeating_texture_char(texture, 2.2, 1.4, "?") == "A"
    assert dungeona.repeating_texture_char(None, 0.3, 0.3, "?") == "?"


def test_collect_tile_picks_up_grail_and_delivers_quest():
    floors = [make_grid("#####", "#G..#", "#..A#", "#####")]
    state = make_state(floors, x=1, y=1)

    dungeona.collect_tile(state, floors[0])
    assert state["has_grail"] is True
    assert floors[0][1][1] == "."
    assert "Holy Grail" in state["message"]

    state.update({"x": 3, "y": 2, "floor": dungeona.QUEST_TARGET_FLOOR, "quest_complete": False})
    floors = [make_grid("#####", "#...#", "#..A#", "#####") for _ in range(dungeona.QUEST_TARGET_FLOOR + 1)]
    state["floors"] = floors
    dungeona.collect_tile(state, floors[dungeona.QUEST_TARGET_FLOOR])

    assert state["has_grail"] is False
    assert state["quest_complete"] is True
    assert state["show_congrats_banner"] is True


def test_collect_tile_reports_full_inventory(monkeypatch):
    floors = [make_grid("#####", "#G..#", "#####")]
    state = make_state(floors, x=1, y=1)

    monkeypatch.setattr(dungeona, "can_pick_item", lambda _state: False)
    dungeona.collect_tile(state, floors[0])

    assert state["message"] == "Your inventory is full (0/3)."
    assert floors[0][1][1] == "G"


def test_try_move_try_strafe_and_find_start_position(empty_two_floor_dungeon):
    state = make_state(empty_two_floor_dungeon, x=1, y=1, facing=1)

    assert dungeona.try_move(state, 1) is True
    assert (state["x"], state["y"]) == (2, 1)

    result = dungeona.try_strafe(state, 1)
    assert result is None
    assert (state["x"], state["y"]) == (2, 2)

    blocked = dungeona.try_move(state, -10)
    assert blocked is False

    floors = [make_grid("###", "#A#", "###")]
    assert dungeona.find_start_position(floors) == (0, 1, 1)


def test_travel_stairs_success_and_failure(empty_two_floor_dungeon):
    state = make_state(empty_two_floor_dungeon, x=3, y=1, floor=0)

    message = dungeona.travel_stairs(state, 1)
    assert message == "You walk down the stairs to floor 2."
    assert (state["floor"], state["x"], state["y"]) == (1, 3, 1)

    fail = dungeona.travel_stairs(state, 5)
    assert fail == "The stairs go nowhere."

    broken_floors = [make_grid("###", "#>#", "###"), make_grid("###", "#.#", "###")]
    broken_state = make_state(broken_floors, x=1, y=1)
    assert dungeona.travel_stairs(broken_state, 1) == "The matching stairs cannot be found."


def test_use_action_handles_doors_combat_items_altars_stairs_and_empty(empty_two_floor_dungeon):
    floors = [
        make_grid(
            "#######",
            "#.DRG>#",
            "#.....#",
            "#######",
        ),
        empty_two_floor_dungeon[1],
        make_grid(
            "#######",
            "#..A..#",
            "#.....#",
            "#######",
        ),
    ]
    state = make_state(floors, x=1, y=1, facing=1, energy=5)

    assert dungeona.use_action(state) == "You open the door."
    assert floors[0][1][2] == "."

    state["x"] = 2
    assert dungeona.use_action(state) == "You skewer the giant rat. Energy -2."
    assert state["energy"] == 3
    assert state["score"] == 1

    state["x"] = 3
    assert dungeona.use_action(state) == "You take the Holy Grail. Inventory 1/3."
    assert state["has_grail"] is True

    state["energy"] = 1
    floors[0][1][5 - 1] = "R"
    state["x"] = 3
    state["has_grail"] = False
    assert dungeona.use_action(state) == "Too tired to fight. Wait to regain some energy."

    state["has_grail"] = True
    state["energy"] = 1
    assert dungeona.use_action(state) == "You skewer the giant rat. Energy -1."

    state["floor"] = 0
    state["x"] = 4
    floors[0][1][5] = ">"
    assert dungeona.use_action(state) == "You walk down the stairs to floor 2."

    altar_state = make_state(floors, floor=dungeona.QUEST_TARGET_FLOOR, x=2, y=1, facing=1, has_grail=True)
    assert dungeona.use_action(altar_state) == "You place the Holy Grail on the altar. Quest complete!"
    assert altar_state["quest_complete"] is True
    assert altar_state["show_congrats_banner"] is True

    altar_state = make_state(floors, floor=0, x=1, y=1, facing=1)
    assert dungeona.use_action(altar_state) == "Nothing happens."


def test_use_current_tile_activates_delivery_and_stairs(empty_two_floor_dungeon):
    stair_state = make_state(empty_two_floor_dungeon, floor=0, x=3, y=1)
    assert dungeona.use_current_tile(stair_state) is True
    assert stair_state["floor"] == 1
    assert "floor 2" in stair_state["message"]

    floors = [make_grid("#####", "#...#", "#.A.#", "#####") for _ in range(dungeona.QUEST_TARGET_FLOOR + 1)]
    altar_state = make_state(
        floors,
        floor=dungeona.QUEST_TARGET_FLOOR,
        x=2,
        y=2,
        has_grail=True,
    )
    assert dungeona.use_current_tile(altar_state) is True
    assert altar_state["quest_complete"] is True


def test_wall_and_floor_chars_and_facing_vector():
    assert dungeona.facing_vector(0) == (0.0, -1.0)
    assert dungeona.wall_char(0.1, 0, "#") == "█"
    assert dungeona.wall_char(0.1, 1, "D") == "|"
    assert dungeona.floor_char(3, 5, 20) == " "
    assert dungeona.floor_char(6, 5, 20) == "_"
    assert dungeona.floor_char(10, 5, 20) == "."
