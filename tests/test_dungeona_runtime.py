from __future__ import annotations

import dungeona

from conftest import FakeStdScr, make_grid, make_state


def test_use_action_handles_remaining_altar_branches():
    floors = [make_grid("#####", "#.A.#", "#####") for _ in range(dungeona.QUEST_TARGET_FLOOR + 1)]

    dormant = make_state(floors, floor=0, x=1, y=1, facing=1)
    assert dungeona.use_action(dormant) == "This altar is dormant."

    complete = make_state(floors, floor=dungeona.QUEST_TARGET_FLOOR, x=1, y=1, facing=1, quest_complete=True)
    assert dungeona.use_action(complete) == "The altar has already received the grail."

    missing = make_state(floors, floor=dungeona.QUEST_TARGET_FLOOR, x=1, y=1, facing=1, has_grail=False)
    assert dungeona.use_action(missing) == f"You need the {dungeona.QUEST_ITEM_NAME}."


def test_move_monsters_decrements_existing_chase_without_moving():
    floors = [make_grid(
        "#####",
        "#R#.#",
        "###.#",
        "#...#",
        "#####",
    )]
    state = make_state(
        floors,
        x=3,
        y=3,
        monster_chase={"0": {"1,1": 2}},
        message="keep",
    )

    dungeona.move_monsters(state)

    assert floors[0][1][1] == "R"
    assert state["monster_chase"]["0"] == {"1,1": 1}
    assert state["message"] == "keep"


def test_run_processes_key_actions_and_main_invokes_wrapper(monkeypatch):
    floors = [
        make_grid(
            "#######",
            "#.....#",
            "#.....#",
            "#.....#",
            "#######",
        )
    ]
    frames = []
    monkeypatch.setattr(dungeona, "load_floors", lambda: floors)
    monkeypatch.setattr(dungeona, "load_wall_textures", lambda: {"#": "wall"})
    monkeypatch.setattr(dungeona, "load_surface_texture", lambda _name: None)
    monkeypatch.setattr(dungeona, "load_animated_sprites", lambda: {"rat": [["rr"]]})
    monkeypatch.setattr(dungeona, "setup_colors", lambda: None)
    monkeypatch.setattr(dungeona, "collect_tile", lambda state, grid: None)
    monkeypatch.setattr(dungeona, "advance_world", lambda state: None)
    monkeypatch.setattr(dungeona.curses, "curs_set", lambda _value: None)
    monkeypatch.setattr(
        dungeona,
        "draw_scene",
        lambda _stdscr, state: frames.append({
            "x": state["x"],
            "y": state["y"],
            "facing": state["facing"],
            "energy": state["energy"],
            "show_map": state["show_map"],
            "message": state["message"],
            "action_count": state["action_count"],
        }),
    )

    stdscr = FakeStdScr(
        keys=[
            ord("q"),
            ord("e"),
            ord("w"),
            ord("s"),
            ord("z"),
            ord("c"),
            ord("m"),
            ord("."),
            ord(" "),
            ord("x"),
        ]
    )

    result = dungeona.run(stdscr)

    assert result == 0
    assert stdscr.nodelay_value is False
    assert stdscr.keypad_enabled is True
    assert frames[-1]["facing"] == 1
    assert frames[-1]["show_map"] is False
    assert frames[-1]["energy"] == dungeona.MAX_ENERGY
    assert frames[-1]["message"] == "Nothing happens."
    assert frames[-1]["action_count"] == 9

    wrapper_calls = []
    monkeypatch.setattr(dungeona, "initialize_map_db", lambda path: wrapper_calls.append(("init", path)))
    monkeypatch.setattr(dungeona.curses, "wrapper", lambda fn: wrapper_calls.append(("wrapper", fn)) or 42)
    assert dungeona.main() == 42
    assert wrapper_calls[0][0] == "init"
    assert wrapper_calls[1][0] == "wrapper"
