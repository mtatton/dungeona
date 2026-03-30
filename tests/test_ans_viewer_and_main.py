from __future__ import annotations

from pathlib import Path

import ans

from conftest import FakeStdScr


def test_view_texture_curses_handles_navigation_and_quit(monkeypatch):
    texture = ans.AnsiTexture(
        width=4,
        height=4,
        rows=[
            [ans.AnsiCell(char="A"), ans.AnsiCell(char="B"), ans.AnsiCell(char="C"), ans.AnsiCell(char="D")],
            [ans.AnsiCell(char="E"), ans.AnsiCell(char="F"), ans.AnsiCell(char="G"), ans.AnsiCell(char="H")],
            [ans.AnsiCell(char="I"), ans.AnsiCell(char="J"), ans.AnsiCell(char="K"), ans.AnsiCell(char="L")],
            [ans.AnsiCell(char="M"), ans.AnsiCell(char="N"), ans.AnsiCell(char="O"), ans.AnsiCell(char="P")],
        ],
        source_path="viewer.ans",
    )
    stdscr = FakeStdScr(
        keys=[
            ans.curses.KEY_RIGHT,
            ans.curses.KEY_DOWN,
            ans.curses.KEY_NPAGE,
            ans.curses.KEY_PPAGE,
            ans.curses.KEY_LEFT,
            ans.curses.KEY_UP,
            ord("q"),
        ],
        height=4,
        width=20,
    )

    monkeypatch.setattr(ans.curses, "start_color", lambda: None)
    monkeypatch.setattr(ans.curses, "use_default_colors", lambda: None)
    monkeypatch.setattr(ans.curses, "noecho", lambda: None)
    monkeypatch.setattr(ans.curses, "cbreak", lambda: None)
    monkeypatch.setattr(ans.curses, "curs_set", lambda _value: None)
    monkeypatch.setattr(ans, "curses_attr_for_cell", lambda cell: ord(cell.char))
    monkeypatch.setattr(ans.curses, "A_REVERSE", 999)

    result = ans.view_texture_curses(stdscr, texture)

    assert result == 0
    assert stdscr.keypad_enabled is True
    assert stdscr.timeout_value == -1
    rendered_text = [args[2] for name, args in stdscr.calls if name == "addstr"]
    assert any(text == "A" for text in rendered_text)
    assert any("viewer.ans" in text for text in rendered_text)


def test_view_texture_curses_autoscroll_exits_at_bottom(monkeypatch):
    texture = ans.AnsiTexture(
        width=1,
        height=5,
        rows=[[ans.AnsiCell(char=str(i))] for i in range(5)],
    )
    stdscr = FakeStdScr(keys=[-1, -1, -1, -1], height=3, width=8)

    monkeypatch.setattr(ans.curses, "start_color", lambda: None)
    monkeypatch.setattr(ans.curses, "use_default_colors", lambda: None)
    monkeypatch.setattr(ans.curses, "noecho", lambda: None)
    monkeypatch.setattr(ans.curses, "cbreak", lambda: None)
    monkeypatch.setattr(ans.curses, "curs_set", lambda _value: None)
    monkeypatch.setattr(ans, "curses_attr_for_cell", lambda _cell: 0)
    monkeypatch.setattr(ans.curses, "A_REVERSE", 0)

    assert ans.view_texture_curses(stdscr, texture, autoscroll=True) == 0
    assert stdscr.timeout_value == 100


def test_ans_main_plain_and_curses_modes(tmp_path: Path, monkeypatch, capsys):
    path = tmp_path / "plain.ans"
    path.write_bytes(b"ONE\nTWO")

    assert ans.main([str(path), "--plain"]) == 0
    assert capsys.readouterr().out.splitlines()[:2] == ["ONE", "TWO"]

    wrapper_calls = []
    monkeypatch.setattr(ans.curses, "wrapper", lambda fn: wrapper_calls.append(fn) or 7)
    assert ans.main([str(path)]) == 7
    assert len(wrapper_calls) == 1
