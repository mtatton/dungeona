#!/usr/bin/python3
"""Reusable ANSI/ANS file parser and optional terminal viewer.

This module exposes helpers that make ANSI art accessible from other Python
files, especially dungeona.py where parsed ANS files can be used as wall
textures.
"""

from __future__ import annotations

import argparse
import curses
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

CMATU = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,199,252,233,226,228,224,229,231,234,235,232,239,238,236,196,197,201,230,198,244,246,242,251,249,255,214,220,162,163,165,8359,402,225,237,243,250,241,209,170,186,191,8976,172,189,188,161,171,187,9617,9618,9619,9474,9508,9569,9570,9558,9557,9571,9553,9559,9565,9564,9563,9488,9492,9524,9516,9500,9472,9532,9566,9567,9562,9556,9577,9574,9568,9552,9580,9575,9576,9572,9573,9561,9560,9554,9555,9579,9578,9496,9484,9608,9604,9612,9616,9600,945,223,915,960,931,963,181,964,934,920,937,948,8734,966,949,8745,8801,177,8805,8804,8992,8993,247,8776,176,8729,183,8730,8319,178,9632,160]

COLOR_NAME_BY_CODE = {
    0: "Bk",
    1: "Re",
    2: "Gr",
    3: "Ye",
    4: "Bl",
    5: "Ma",
    6: "Cy",
    7: "Wh",
}

CURSES_COLOR_BY_NAME = {
    "Bk": curses.COLOR_BLACK,
    "Re": curses.COLOR_RED,
    "Gr": curses.COLOR_GREEN,
    "Ye": curses.COLOR_YELLOW,
    "Bl": curses.COLOR_BLUE,
    "Ma": curses.COLOR_MAGENTA,
    "Cy": curses.COLOR_CYAN,
    "Wh": curses.COLOR_WHITE,
}


@dataclass(frozen=True)
class AnsiCell:
    char: str = " "
    fg: str = "Wh"
    bg: str = "Bk"
    intensity: str = "me"


@dataclass(frozen=True)
class SauceInfo:
    title: str
    author: str
    group: str
    date: str
    file_size: int
    data_type: int
    file_type: int
    tinfo1: int
    tinfo2: int
    tinfo3: int
    tinfo4: int
    comments: int


@dataclass
class AnsiTexture:
    width: int
    height: int
    rows: List[List[AnsiCell]]
    sauce: Optional[SauceInfo] = None
    source_path: Optional[str] = None

    def to_plain_lines(self) -> List[str]:
        return ["".join(cell.char for cell in row).rstrip() for row in self.rows]

    def sample_char(self, x: int, y: int, default: str = " ") -> str:
        if y < 0 or y >= self.height:
            return default
        if x < 0 or x >= self.width:
            return default
        return self.rows[y][x].char


class AnsiParser:
    def parse_bytes(self, data: bytes, source_path: Optional[str] = None) -> AnsiTexture:
        payload, sauce, width_hint, height_hint = self._split_sauce(data)
        rows = self._parse_payload(payload)
        width = max((len(row) for row in rows), default=width_hint or 0)
        if width_hint:
            width = max(width, width_hint)
        if height_hint:
            while len(rows) < height_hint:
                rows.append([])
        normalized = [self._pad_row(row, width) for row in rows] or [self._pad_row([], max(1, width_hint or 80))]
        width = max((len(row) for row in normalized), default=max(1, width_hint or 80))
        normalized = [self._pad_row(row, width) for row in normalized]
        return AnsiTexture(
            width=width,
            height=len(normalized),
            rows=normalized,
            sauce=sauce,
            source_path=source_path,
        )

    def parse_file(self, path: str | Path) -> AnsiTexture:
        file_path = Path(path)
        return self.parse_bytes(file_path.read_bytes(), source_path=str(file_path))

    def _split_sauce(self, data: bytes) -> Tuple[bytes, Optional[SauceInfo], int, int]:
        if len(data) >= 128 and data[-128:-123] == b"SAUCE" and data[-123:-121] == b"00":
            sauce_bytes = data[-128:]
            sauce = SauceInfo(
                title=self._decode_text(sauce_bytes[7:42]),
                author=self._decode_text(sauce_bytes[42:62]),
                group=self._decode_text(sauce_bytes[62:82]),
                date=self._decode_text(sauce_bytes[82:90]),
                file_size=int.from_bytes(sauce_bytes[90:94], "little"),
                data_type=int.from_bytes(sauce_bytes[94:95], "little"),
                file_type=int.from_bytes(sauce_bytes[95:96], "little"),
                tinfo1=int.from_bytes(sauce_bytes[96:98], "little"),
                tinfo2=int.from_bytes(sauce_bytes[98:100], "little"),
                tinfo3=int.from_bytes(sauce_bytes[100:102], "little"),
                tinfo4=int.from_bytes(sauce_bytes[102:104], "little"),
                comments=int.from_bytes(sauce_bytes[104:105], "little"),
            )
            return data[:-128], sauce, sauce.tinfo1 or 80, sauce.tinfo2 or 25
        return data, None, 80, 25

    def _decode_text(self, raw: bytes) -> str:
        return raw.decode("cp437", errors="replace").rstrip(" \x00")

    def _pad_row(self, row: List[AnsiCell], width: int) -> List[AnsiCell]:
        if len(row) >= width:
            return row[:width]
        return row + [AnsiCell() for _ in range(width - len(row))]

    def _parse_payload(self, data: bytes) -> List[List[AnsiCell]]:
        rows: List[List[AnsiCell]] = [[]]
        x = 0
        y = 0
        fg = "Wh"
        bg = "Bk"
        intensity = "me"
        state = ""
        attr_buffer = ""

        for value in data:
            if value == 10:
                y += 1
                x = 0
                while len(rows) <= y:
                    rows.append([])
                continue
            if value == 13:
                x = 0
                continue
            if value == 27:
                state = "E"
                attr_buffer = ""
                continue

            if state == "E":
                if value == ord("["):
                    state = "ES"
                else:
                    state = ""
                continue

            if state == "ES":
                if ord("0") <= value <= ord("9"):
                    attr_buffer += chr(value)
                    continue
                if value in (ord(";"), ord("m"), ord("C")):
                    number = int(attr_buffer) if attr_buffer else 0
                    if value == ord("C"):
                        x += number
                        attr_buffer = ""
                        state = ""
                        continue
                    if number == 0:
                        intensity = "me"
                        fg = "Wh"
                        bg = "Bk"
                    elif number == 1:
                        intensity = "hi"
                    elif number == 2:
                        intensity = "lo"
                    elif number == 22:
                        intensity = "me"
                    elif number == 39:
                        fg = "Wh"
                    elif number == 49:
                        bg = "Bk"
                    elif 30 <= number <= 37:
                        fg = COLOR_NAME_BY_CODE[number % 10]
                    elif 90 <= number <= 97:
                        intensity = "hi"
                        fg = COLOR_NAME_BY_CODE[number % 10]
                    elif 40 <= number <= 47:
                        bg = COLOR_NAME_BY_CODE[number % 10]
                    elif 100 <= number <= 107:
                        bg = COLOR_NAME_BY_CODE[number % 10]
                    attr_buffer = ""
                    if value == ord("m"):
                        state = ""
                    continue
                state = ""

            char = chr(CMATU[value]) if value < len(CMATU) else chr(value)
            while len(rows) <= y:
                rows.append([])
            row = rows[y]
            while len(row) < x:
                row.append(AnsiCell())
            row.append(AnsiCell(char=char, fg=fg, bg=bg, intensity=intensity))
            x += 1

        return rows


def load_ans_texture(path: str | Path) -> AnsiTexture:
    return AnsiParser().parse_file(path)


def load_ans_plain_lines(path: str | Path) -> List[str]:
    return load_ans_texture(path).to_plain_lines()


def _curses_attr_cache() -> dict[Tuple[str, str, str], int]:
    if not hasattr(_curses_attr_cache, "cache"):
        setattr(_curses_attr_cache, "cache", {})
        setattr(_curses_attr_cache, "next_pair", 1)
    return getattr(_curses_attr_cache, "cache")


def curses_attr_for_cell(cell: AnsiCell) -> int:
    cache = _curses_attr_cache()
    key = (cell.fg, cell.bg, cell.intensity)
    if key not in cache:
        next_pair = getattr(_curses_attr_cache, "next_pair")
        curses.init_pair(next_pair, CURSES_COLOR_BY_NAME[cell.fg], CURSES_COLOR_BY_NAME[cell.bg])
        attr = curses.color_pair(next_pair)
        if cell.intensity == "hi":
            attr |= curses.A_BOLD
        elif cell.intensity == "lo":
            attr |= curses.A_DIM
        cache[key] = attr
        setattr(_curses_attr_cache, "next_pair", next_pair + 1)
    return cache[key]


def view_texture_curses(stdscr, texture: AnsiTexture, autoscroll: bool = False) -> int:
    curses.start_color()
    curses.use_default_colors()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    shift_y = 0
    shift_x = 0
    delay = 100 if autoscroll else -1
    stdscr.timeout(delay)

    while True:
        height, width = stdscr.getmaxyx()
        viewport_h = max(1, height - 1)
        viewport_w = max(1, width)
        stdscr.erase()

        for sy in range(viewport_h):
            ty = shift_y + sy
            if ty >= texture.height:
                break
            row = texture.rows[ty]
            for sx in range(viewport_w):
                tx = shift_x + sx
                if tx >= texture.width:
                    break
                cell = row[tx]
                try:
                    stdscr.addstr(sy, sx, cell.char, curses_attr_for_cell(cell))
                except curses.error:
                    pass

        status = f" {texture.source_path or '<memory>'}  {shift_x},{shift_y}  q quit  arrows scroll "
        try:
            stdscr.addstr(height - 1, 0, status[: max(0, width - 1)], curses.A_REVERSE)
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            return 0
        if key == curses.KEY_UP:
            shift_y = max(0, shift_y - 1)
        elif key == curses.KEY_DOWN:
            shift_y = min(max(0, texture.height - viewport_h), shift_y + 1)
        elif key == curses.KEY_LEFT:
            shift_x = max(0, shift_x - 1)
        elif key == curses.KEY_RIGHT:
            shift_x = min(max(0, texture.width - viewport_w), shift_x + 1)
        elif key == curses.KEY_PPAGE:
            shift_y = max(0, shift_y - max(1, viewport_h - 2))
        elif key == curses.KEY_NPAGE:
            shift_y = min(max(0, texture.height - viewport_h), shift_y + max(1, viewport_h - 2))
        elif key == -1 and autoscroll:
            if shift_y < max(0, texture.height - viewport_h):
                shift_y += 1
            else:
                return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="View or parse ANSI/ANS art files.")
    parser.add_argument("file", help="Path to ANSI/ANS file")
    parser.add_argument("-a", "--autoscroll", action="store_true", help="Autoscroll the viewer")
    parser.add_argument("--plain", action="store_true", help="Print plain text only, without curses colors")
    args = parser.parse_args(argv)

    texture = load_ans_texture(args.file)
    if args.plain:
        for line in texture.to_plain_lines():
            print(line)
        return 0
    return curses.wrapper(lambda stdscr: view_texture_curses(stdscr, texture, autoscroll=args.autoscroll))


if __name__ == "__main__":
    raise SystemExit(main())
