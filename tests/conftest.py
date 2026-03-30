from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import dungeona  # noqa: E402


def make_grid(*rows: str):
    return [list(row) for row in rows]


def make_state(
    floors,
    *,
    floor: int = 0,
    x: int = 1,
    y: int = 1,
    facing: int = 1,
    energy: int = dungeona.START_ENERGY,
    score: int = 0,
    has_grail: bool = False,
    quest_complete: bool = False,
    message: str = "",
    show_map: bool = True,
    show_congrats_banner: bool = False,
    action_count: int = 0,
    monster_chase=None,
):
    return {
        "floors": floors,
        "floor": floor,
        "x": x,
        "y": y,
        "facing": facing,
        "energy": energy,
        "score": score,
        "has_grail": has_grail,
        "quest_complete": quest_complete,
        "show_map": show_map,
        "message": message,
        "show_congrats_banner": show_congrats_banner,
        "wall_textures": {},
        "floor_texture": None,
        "ceiling_texture": None,
        "animated_sprites": {},
        "action_count": action_count,
        "monster_chase": monster_chase if monster_chase is not None else {},
    }


class FakeStdScr:
    def __init__(self, keys=None, *, height: int = 24, width: int = 80):
        self.keys = list(keys or [])
        self.height = height
        self.width = width
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.keypad_enabled = False
        self.nodelay_value = None
        self.timeout_value = None

    def _record(self, name: str, *args):
        self.calls.append((name, args))

    def keypad(self, value: bool):
        self.keypad_enabled = value
        self._record("keypad", value)

    def nodelay(self, value: bool):
        self.nodelay_value = value
        self._record("nodelay", value)

    def timeout(self, value: int):
        self.timeout_value = value
        self._record("timeout", value)

    def erase(self):
        self._record("erase")

    def clear(self):
        self._record("clear")

    def refresh(self):
        self._record("refresh")

    def border(self):
        self._record("border")

    def getmaxyx(self):
        return (self.height, self.width)

    def addstr(self, *args):
        self._record("addstr", *args)

    def addch(self, *args):
        self._record("addch", *args)

    def getch(self):
        if self.keys:
            return self.keys.pop(0)
        return ord("q")


class DummyEvent:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class DummyCanvas:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.created: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.deleted: list[Any] = []
        self.config_calls: list[dict[str, Any]] = []
        self._next_id = 1

    def pack(self, *args, **kwargs):
        self.created.append(("pack", args, kwargs))

    def _create(self, kind: str, *args, **kwargs):
        item_id = self._next_id
        self._next_id += 1
        self.created.append((kind, args, kwargs))
        return item_id

    def create_rectangle(self, *args, **kwargs):
        return self._create("rectangle", *args, **kwargs)

    def create_line(self, *args, **kwargs):
        return self._create("line", *args, **kwargs)

    def create_text(self, *args, **kwargs):
        return self._create("text", *args, **kwargs)

    def create_oval(self, *args, **kwargs):
        return self._create("oval", *args, **kwargs)

    def delete(self, item):
        self.deleted.append(item)

    def config(self, **kwargs):
        self.config_calls.append(kwargs)


class DummyRoot:
    def __init__(self):
        self.bound: list[tuple[str, Any]] = []
        self.configured: list[dict[str, Any]] = []
        self.destroyed = False
        self.mainloop_called = False
        self.titles: list[str] = []

    def title(self, text: str):
        self.titles.append(text)

    def configure(self, **kwargs):
        self.configured.append(kwargs)

    def resizable(self, *args):
        self.bound.append(("resizable", args))

    def bind(self, event: str, handler):
        self.bound.append((event, handler))

    def destroy(self):
        self.destroyed = True

    def mainloop(self):
        self.mainloop_called = True


@pytest.fixture

def small_floor():
    return make_grid(
        "#######",
        "#..G..#",
        "#.DRA>#",
        "#..<..#",
        "#######",
    )


@pytest.fixture

def empty_two_floor_dungeon():
    return [
        make_grid(
            "#######",
            "#..>..#",
            "#.....#",
            "#######",
        ),
        make_grid(
            "#######",
            "#..<..#",
            "#..A..#",
            "#######",
        ),
    ]
