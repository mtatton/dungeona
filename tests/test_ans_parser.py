from __future__ import annotations

from pathlib import Path

import ans


def build_sauce(*, width: int = 12, height: int = 3, title: str = "Demo") -> bytes:
    sauce = bytearray(128)
    sauce[0:5] = b"SAUCE"
    sauce[5:7] = b"00"
    sauce[7:42] = title.encode("cp437").ljust(35, b" ")
    sauce[42:62] = b"Tester".ljust(20, b" ")
    sauce[62:82] = b"Group".ljust(20, b" ")
    sauce[82:90] = b"20260329"
    sauce[90:94] = (123).to_bytes(4, "little")
    sauce[94] = 1
    sauce[95] = 1
    sauce[96:98] = width.to_bytes(2, "little")
    sauce[98:100] = height.to_bytes(2, "little")
    return bytes(sauce)


def test_parse_bytes_defaults_and_padding():
    texture = ans.AnsiParser().parse_bytes(b"AB\nC", source_path="memory.ans")

    assert texture.source_path == "memory.ans"
    assert texture.width == 80
    assert texture.height == 25
    assert texture.to_plain_lines()[:2] == ["AB", "C"]
    assert texture.sample_char(0, 0) == "A"
    assert texture.sample_char(1, 0) == "B"
    assert texture.sample_char(0, 1) == "C"
    assert texture.sample_char(999, 999, "?") == "?"


def test_parse_bytes_handles_escape_colors_and_cursor_forward():
    payload = b"\x1b[31mR\x1b[42mG\x1b[22m\x1b[1mH\x1b[2mL\x1b[39mW\x1b[49mB\x1b[2CX"
    texture = ans.AnsiParser().parse_bytes(payload)
    row = texture.rows[0]

    assert row[0].char == "R"
    assert (row[0].fg, row[0].bg, row[0].intensity) == ("Re", "Bk", "me")
    assert (row[1].char, row[1].bg) == ("G", "Gr")
    assert row[2].intensity == "hi"
    assert row[3].intensity == "lo"
    assert row[4].fg == "Wh"
    assert row[5].bg == "Bk"
    assert row[6].char == " "
    assert row[7].char == " "
    assert row[8].char == "X"


def test_parse_bytes_reads_sauce_metadata_and_hints():
    payload = b"HELLO\nWORLD" + build_sauce(width=9, height=4, title="Quest Art")
    texture = ans.AnsiParser().parse_bytes(payload)

    assert texture.sauce is not None
    assert texture.sauce.title == "Quest Art"
    assert texture.width == 9
    assert texture.height == 4
    assert texture.to_plain_lines()[:2] == ["HELLO", "WORLD"]


def test_decode_text_and_pad_row_helpers():
    parser = ans.AnsiParser()
    assert parser._decode_text(b"caf\x82 ") == "café"

    padded = parser._pad_row([ans.AnsiCell(char="X")], 3)
    assert [cell.char for cell in padded] == ["X", " ", " "]

    trimmed = parser._pad_row([ans.AnsiCell(char="A"), ans.AnsiCell(char="B")], 1)
    assert [cell.char for cell in trimmed] == ["A"]


def test_load_ans_texture_and_plain_lines_round_trip(tmp_path: Path):
    path = tmp_path / "sample.ans"
    path.write_bytes(b"ONE\nTWO")

    texture = ans.load_ans_texture(path)
    plain = ans.load_ans_plain_lines(path)

    assert texture.source_path == str(path)
    assert plain[:2] == ["ONE", "TWO"]


def test_curses_attr_for_cell_caches_attributes(monkeypatch):
    cache_fn = ans._curses_attr_cache
    if hasattr(cache_fn, "cache"):
        delattr(cache_fn, "cache")
    if hasattr(cache_fn, "next_pair"):
        delattr(cache_fn, "next_pair")

    init_calls = []
    monkeypatch.setattr(ans.curses, "init_pair", lambda pair, fg, bg: init_calls.append((pair, fg, bg)))
    monkeypatch.setattr(ans.curses, "color_pair", lambda pair: pair * 100)
    monkeypatch.setattr(ans.curses, "A_BOLD", 1000)
    monkeypatch.setattr(ans.curses, "A_DIM", 2000)

    hi = ans.curses_attr_for_cell(ans.AnsiCell(char="X", fg="Re", bg="Bk", intensity="hi"))
    hi_again = ans.curses_attr_for_cell(ans.AnsiCell(char="Y", fg="Re", bg="Bk", intensity="hi"))
    low = ans.curses_attr_for_cell(ans.AnsiCell(char="Z", fg="Cy", bg="Bl", intensity="lo"))

    assert hi == hi_again
    assert hi & 1000
    assert low & 2000
    assert len(init_calls) == 2
