DUNGEONA
========

![game screenshot](game-screenshot.png?raw=true)

Overview
--------
Dungeona is a terminal dungeon crawler written in Python with the built-in
curses module. It renders a pseudo-3D first-person ASCII view, stores dungeon
data in SQLite, and includes a separate terminal editor for building and
validating dungeon floors.

[Donate](https://paypal.me/michtatton)

Project contents
----------------
dungeona.py        Main game
dungeon_editor.py  Terminal editor and dungeon validator
dungeon_map.db     SQLite database containing dungeon floor rows
license.txt        Donationware license
readme.txt         This file

Features
--------
- First-person ASCII dungeon exploration
- Three connected dungeon floors in the default data set
- Doors that can be opened from the tile directly ahead
- Monsters that cost energy to defeat
- A sword pickup that reduces combat energy cost
- Stairs for moving between floors
- Toggleable minimap with player position and facing direction
- SQLite-backed dungeon storage
- Built-in dungeon editor with verification tools

Requirements
------------
- Python 3.10 or newer recommended
- A terminal with curses support
- No third-party packages required on Linux or macOS
- On Windows, install curses support first:

  pip install windows-curses

How to run
----------
From the project folder:

  python dungeona.py

To open the dungeon editor:

  python dungeon_editor.py

Debian/Ubuntu Package Installation
----------------------------------

There is a repository available for Debian/Ubuntu Linux distributions:

```shell
# Add VitexSoftware repository
sudo apt install lsb-release wget apt-transport-https bzip2

wget -qO- https://repo.vitexsoftware.com/KEY.gpg | sudo tee /etc/apt/trusted.gpg.d/vitexsoftware.gpg
echo "deb [signed-by=/etc/apt/trusted.gpg.d/vitexsoftware.gpg]  https://repo.vitexsoftware.com  $(lsb_release -sc) games" | sudo tee /etc/apt/sources.list.d/vitexsoftware-games.list
sudo apt update

# Install the package
sudo apt install dungeona
```

Game summary
------------
The game loads all dungeon floors from dungeon_map.db and starts on the first
walkable tile it finds. You explore in first-person view, manage energy, fight
monsters, collect the sword, open doors, and move between floors with stairs.

By default, the dungeon contains three floors linked by stair tiles:
- >  stairs down
- <  stairs up

The minimap can be shown or hidden during play. The status line displays
current energy, floor number, map position, facing direction, sword status,
and defeated enemy count.

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
- Space / Enter    Interact with the tile ahead
- .                Wait and regain 1 energy
- M                Toggle minimap
- >                Use stairs down immediately
- <                Use stairs up immediately
- X                Quit

Gameplay rules
--------------
- Energy starts at 12 and is capped at 12.
- Waiting restores 1 energy.
- Defeating a monster costs:
  - 2 energy without the sword
  - 1 energy with the sword
- Picking up the sword updates future combat cost.
- The sword is collected automatically if you step onto its tile.
- Doors open when you interact with a door tile directly in front of you.
- Using stairs moves you to the matching stair tile on the adjacent floor.
- Defeated monsters increase the on-screen score counter.

Dungeon data
------------
Dungeon data is stored in dungeon_map.db in the table:

  floor_map_rows

Columns:
- floor_index   Zero-based floor number
- row_index     Zero-based row number within that floor
- row_text      Raw text for the row

If the database is empty, the game and editor populate it with the built-in
default floors.

Tile reference
--------------
- #  Wall
- .  Floor
- D  Door
- S  Sword
- M  Monster
- >  Stairs down
- <  Stairs up
- (space) Empty walkable tile

Dungeon editor
--------------
The editor lets you inspect and modify dungeon floors stored in the database.
It can switch between floors, place tiles, verify the dungeon, and save changes
back to dungeon_map.db.

Editor controls
---------------
- Arrow keys       Move cursor
- , or <           Previous floor
- . or >           Next floor
- 1                Wall
- 2                Floor
- 3                Door
- 4                Sword
- 5                Monster
- 6                Stairs down
- 7                Stairs up
- 0                Empty space
- [ or ]           Cycle selected tile
- Space / Enter    Place selected tile
- V                Verify the whole dungeon
- S                Save to dungeon_map.db
- Q                Quit editor

Editor behavior and validation
------------------------------
- The editor maintains exactly one sword across the full dungeon.
- Each floor can have at most one upstairs tile and one downstairs tile.
- Upstairs cannot be placed on floor 1.
- Downstairs cannot be placed on the final floor.
- Verification checks for:
  - empty maps
  - inconsistent row widths
  - unknown tile values
  - unreachable walkable tiles
  - unreachable sword or monsters
  - leaks on the outer border
  - missing or extra stair links across floors
  - missing sword
  - missing monsters

Notes
-----
- Empty space is displayed as . in the editor for visibility, but it is stored
  as a literal space character in the map.
- The editor can read legacy single-floor data from a map_rows table, but the
  current game data format is the multi-floor floor_map_rows table.
- If you change the database outside the editor, keep stair links consistent
  between floors.

License
-------
This project is distributed under the dungeona Donationware License v1.0.
See license.txt for the full license text.

Author
------
Copyright (c) 2026 mtatton
