DUNGEONA
========

Version
-------
Updated README for the project archive: 20260328_dungeona_015.zip

Overview
--------
Dungeona is a retro-style first-person dungeon crawler written in Python.
This archive includes:
- a terminal game built with curses
- a Tkinter-based GUI frontend
- a terminal dungeon editor
- SQLite-backed multi-floor dungeon storage
- ANSI/ANS texture support for walls, doors, and animated rat art

In the default adventure, your goal is to find the Holy Grail and deliver it
to the altar on the final floor.

What's updated in this build
----------------------------
This archive includes everything from the recent textured builds, plus:
- dungeona_gui.py, a windowed Tkinter frontend for the game
- animated rat texture frames in textures/rat001.ans through rat003.ans
- monster spotting and short chase behavior
- a multi-floor map editor and dungeon validator

Included files
--------------
dungeona.py
    Main terminal game.

dungeona_gui.py
    Tkinter GUI frontend for the same dungeon and game logic.

dungeon_editor.py
    Terminal map editor and dungeon validator.

ans.py
    ANSI/ANS parser and optional texture viewer utility.

dungeon_map.db
    SQLite dungeon data file used by the game and editor.

textures/
    ANSI art assets used by the renderer:
    - wall.ans
    - door.ans
    - rat001.ans
    - rat002.ans
    - rat003.ans

license.txt
    Donationware license.

readme.txt
    Project documentation.

Features
--------
- terminal-based first-person dungeon exploration
- optional Tkinter GUI frontend
- pseudo-3D corridor rendering
- ANSI/ANS wall and door textures
- animated rat artwork when rat texture frames are available
- three connected dungeon floors in the default adventure
- Holy Grail quest objective with altar delivery
- rats, skeletons, and ogres
- monster spotting and short chase behavior
- door interaction from the tile directly ahead
- stairs linking multiple floors
- toggleable minimap with facing direction
- energy-based combat and waiting system
- SQLite-backed map storage
- full-screen terminal dungeon editor with validation tools

Requirements
------------
- Python 3.10 or newer recommended
- a terminal with curses support for the terminal game/editor
- Tkinter support for the GUI frontend
- no third-party packages required on Linux or macOS

Windows users may need:

    pip install windows-curses

How to run
----------
Run the terminal game:

    python dungeona.py

Run the GUI frontend:

    python dungeona_gui.py

Run the dungeon editor:

    python dungeon_editor.py

How to view ANSI textures
-------------------------
The included ans.py utility can display or print .ANS texture files.

Open a texture in the curses viewer:

    python ans.py textures/wall.ans

Open with autoscroll:

    python ans.py textures/wall.ans --autoscroll

Print plain text only:

    python ans.py textures/wall.ans --plain

Texture viewer controls
-----------------------
- Arrow Keys   Scroll
- Page Up      Scroll up faster
- Page Down    Scroll down faster
- Q            Quit viewer

Game objective
--------------
1. Explore the dungeon.
2. Find the Holy Grail.
3. Reach the altar on floor 3.
4. Place the grail on the altar to complete the quest.

Game controls
-------------
Movement and facing:
- Up Arrow / W      Move forward
- Down Arrow / S    Move backward
- Q                 Turn left
- E                 Turn right
- Z                 Strafe left
- C                 Strafe right

Actions:
- Space / Enter     Interact with the tile directly ahead
- .                 Wait and regain energy
- M                 Toggle minimap
- >                 Use stairs down
- <                 Use stairs up
- X                 Quit the game

GUI notes
---------
- The GUI frontend uses the same dungeon data and core game logic as the
  terminal version.
- It opens in a window using Tkinter rather than curses.
- If Tkinter is missing from your Python install, the GUI may not launch.

Gameplay rules
--------------
- Energy starts at 12 and is capped at 12.
- Waiting restores 1 energy.
- Monsters are defeated by interacting with them when directly ahead.
- Combat costs 2 energy before you have the grail, and 1 energy while carrying it.
- Doors open when you interact with a door tile directly in front of you.
- Standing on stairs can move you between linked floors.
- The grail can be picked up by stepping onto it or interacting with it.
- The grail is delivered by using the altar or standing on it on floor 3.
- Monsters can spot the player and continue pursuing for several turns.
- The HUD/status display shows floor, position, facing, item count, grail
  status, and defeated monsters.

Inventory note
--------------
The current build exposes an inventory capacity of 3 item slots in the status
logic. The Holy Grail uses one of those slots.

Monster reference
-----------------
- R   Rat
- S   Skeleton
- O   Ogre
- M   Generic legacy monster marker supported by the loader/editor

Tile reference
--------------
- #   Wall
- .   Floor
- D   Door
- G   Holy Grail
- A   Altar
- R   Rat
- S   Skeleton
- O   Ogre
- M   Generic monster marker (legacy support)
- >   Stairs down
- <   Stairs up
- (space) Empty walkable tile

Dungeon data
------------
Dungeon data is stored in:

    dungeon_map.db

Primary multi-floor table:
- floor_map_rows

Columns:
- floor_index   Zero-based floor number
- row_index     Zero-based row number within the floor
- row_text      Raw text for that row

Notes:
- If the multi-floor table is empty, the game/editor can repopulate it with
  built-in default floors.
- Legacy single-floor data in a map_rows table is also supported.

Dungeon editor
--------------
The editor lets you build, inspect, validate, and save multi-floor maps.
It includes a tile palette, floor switching, and whole-dungeon verification.

Editor controls
---------------
- Arrow Keys        Move cursor
- ,                 Previous floor
- .                 Next floor
- 1                 Wall
- 2                 Floor
- 3                 Door
- 4                 Holy Grail
- 5                 Altar
- 6                 Rat
- 7                 Skeleton
- 8                 Ogre
- 9                 Stairs down
- 0                 Stairs up
- -                 Generic monster marker
- =                 Empty tile
- Space / Enter     Place current tile
- [ or ]            Cycle selected tile
- V                 Verify the whole dungeon
- S                 Save to dungeon_map.db
- Q                 Quit editor

Editor validation checks
------------------------
The validator checks for problems such as:
- empty maps
- inconsistent row widths
- unknown tile values
- unreachable walkable areas
- unreachable quest tiles, monsters, or stairs
- leaks on the outer border
- missing or extra stair links
- missing or extra Holy Grails
- missing or extra altars
- missing monsters

Project notes
-------------
- Empty space is shown with a visible marker in the editor, but stored as a
  literal space character in the map data.
- The default adventure contains three linked floors.
- The game works best in a reasonably large terminal window.
- ans.py can be reused outside the game to load or inspect ANSI art.
- Missing texture files do not stop the game; the game falls back to text rendering.

License
-------
This project is distributed under the dungeona Donationware License v1.0.
See license.txt for the full text.

Author
------
Copyright (c) 2026 mtatton

Donation
--------
PayPal: https://paypal.me/michtatton
