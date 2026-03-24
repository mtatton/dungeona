DUNGEONA
=========

Overview
--------

Dungeona is a small terminal dungeon crawler written in Python using 
the built-in curses module. It renders a pseudo-3D first-person dungeon 
view in ASCII/ANSI style and includes a separate terminal map editor 
for changing the dungeon layout stored in a SQLite database.

Project contents
----------------
dungeona.py        Main game
dungeon_editor.py  Map editor and validator
dungeon_map.db     SQLite database containing the map rows
license.txt        Donationware license
readme.txt         This file

Gameplay summary
----------------
- Explore the dungeon from a first-person view.
- Open doors.
- Pick up the sword to reduce combat cost.
- Defeat monsters while managing energy.
- Toggle the minimap as needed.

Requirements
------------
- Python 3.10+ recommended
- A terminal that supports curses and ANSI-style character rendering
- No third-party Python packages are required on Linux/macOS
- On Windows, you may need the "windows-curses" package for curses support

How to run
----------
From the project folder:

  python dungeona.py

To open the map editor:

  python dungeon_editor.py

Game controls
-------------
Movement and view:
- Up arrow / W     Move forward
- Down arrow / S   Move backward
- Q                Turn left
- E                Turn right
- Z                Strafe left
- C                Strafe right

Actions:
- Space            Interact / open door / attack / pick up sword
- . or ,           Wait and recover 1 energy
- M                Toggle minimap
- X                Quit

Game systems
------------
- Energy starts at 12 and caps at 12.
- Waiting restores 1 energy.
- Fighting costs:
  - 1 energy with the sword
  - 2 energy without the sword
- Enemies defeated increase the score counter.
- Doors can be opened from the tile directly in front of the player.

Map data
--------
The dungeon layout is stored in dungeon_map.db in a table named map_rows.
Each row of the dungeon is saved as text.

Tile meanings:
- #  Wall
- .  Floor
- D  Door
- S  Sword
- M  Monster
- (space) Empty/passable area

Editor features
---------------
The editor lets you place tiles, save the map, and run validation checks.
Validation looks for issues such as:
- inconsistent row widths
- missing sword
- missing monsters
- unreachable walkable tiles
- unreachable sword or monsters
- leaks in the outer border
- unknown tile values

Editor controls
---------------
- Arrow keys       Move cursor
- 1                Wall
- 2                Floor
- 3                Door
- 4                Sword
- 5                Monster
- 0                Empty space
- [ or ]           Cycle selected tile
- Space / Enter    Place selected tile
- V                Verify map
- S                Save map to dungeon_map.db
- Q                Quit editor

Notes
-----
- The game loads the map from dungeon_map.db at startup.
- If the database is empty, the scripts populate it with a default map.
- The editor enforces a single sword when placing a new sword tile.
- Monsters are normalized onto walkable cells when the game starts.

License
-------
This project is distributed under the dungeona Donationware License v1.0.
See license.txt for the full license text.

Author
------
Copyright (c) 2026 mtatton
