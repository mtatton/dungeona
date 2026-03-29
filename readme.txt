DUNGEONA
========

Version
-------
Updated README for project archive: 20260329_dungeona_017.zip

Overview
--------
Dungeona is a retro-style first-person dungeon crawler written in Python.
This build includes:

- a terminal version built with curses
- two Tkinter windowed front ends
- a terminal dungeon editor with validation tools
- SQLite-backed multi-floor dungeon storage
- ANSI/ANS texture support for walls, doors, floor, ceiling, and rat animation

In the default adventure, your goal is to find the Holy Grail and deliver it
to the altar on the final floor.

Highlights of this build
------------------------
This archive includes:

- dungeona.py, the main terminal game
- dungeona_gui.py, a Tkinter GUI frontend with textured scene rendering
- dungeona_ren.py, an alternate Tkinter renderer/windowed frontend
- dungeon_editor.py, a curses map editor and validator
- ans.py, a reusable ANSI/ANS parser and texture viewer
- wall, door, floor, and ceiling ANSI textures
- animated rat frames in textures/rat001.ans through rat003.ans
- multi-floor dungeon data stored in SQLite
- monster chase behavior, minimap support, and energy-based combat

Included files
--------------
dungeona.py
    Main terminal game and core gameplay logic.

dungeona_gui.py
    Tkinter GUI frontend with textured scene rendering and status display.

dungeona_ren.py
    Alternate Tkinter renderer/windowed frontend with auto-scaling display.

dungeon_editor.py
    Terminal map editor and dungeon validator.

ans.py
    ANSI/ANS parser and optional terminal viewer utility.

dungeon_map.db
    SQLite dungeon data file used by the game and editor.

textures/
    ANSI art assets used by the renderer:
    - wall.ans
    - door.ans
    - floor.ans
    - ceiling.ans
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
- two optional Tkinter windowed front ends
- pseudo-3D corridor rendering
- ANSI/ANS wall, door, floor, and ceiling textures
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
- full-screen terminal dungeon editor with whole-dungeon validation

Requirements
------------
- Python 3.10 or newer recommended
- a terminal with curses support for the terminal game/editor
- Tkinter support for the windowed front ends
- no third-party packages required on Linux or macOS

Windows users may need:

    pip install windows-curses

How to run
----------
Run the terminal game:

    python dungeona.py

Run the main Tkinter GUI frontend:

    python dungeona_gui.py

Run the alternate Tkinter renderer frontend:

    python dungeona_ren.py

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
- X                 Quit the game or windowed frontend

Frontend notes
--------------
- dungeona.py is the curses terminal version.
- dungeona_gui.py is a textured Tkinter windowed version.
- dungeona_ren.py is an alternate Tkinter renderer that scales with window size.
- All front ends use the same dungeon data and core game logic.
- If Tkinter is missing from your Python installation, the windowed front ends
  may not launch.

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
- row_text      Map row contents as text

If the database is empty, the code can repopulate it with built-in default
floors.

Editor features
---------------
The editor lets you:
- move a cursor around the map
- switch between dungeon floors
- place walls, floors, doors, monsters, stairs, and quest items
- verify the entire dungeon for map errors
- save the dungeon back to dungeon_map.db

Editor controls
---------------
Navigation:
- Arrow Keys      Move the cursor
- , or <          Previous floor
- . or >          Next floor

Tile placement:
- 1               Wall
- 2               Floor
- 3               Door
- 4               Holy Grail
- 5               Altar
- 6               Rat
- 7               Skeleton
- 8               Ogre
- 9               Stairs down
- 0               Stairs up
- -               Generic monster marker
- =               Empty space
- [ or ]          Cycle selected tile
- Space / Enter   Place selected tile
- P               Place selected tile

Project actions:
- V               Verify the whole dungeon
- S               Save to dungeon_map.db
- Q               Quit editor

Validation checks
-----------------
The editor validator checks for common dungeon issues, including:
- empty maps
- inconsistent row widths
- unknown tile values
- unreachable walkable areas
- unreachable quest items, monsters, or stairs
- map leaks on the outer border
- missing or extra stair links
- missing or extra Holy Grails
- missing or extra altars
- missing monsters

Project notes
-------------
- Empty space is stored as a literal space character in the map data.
- The project is designed for terminal play and works best in a reasonably
  large console window.
- ANSI textures are optional visual enhancements used by the renderer.
- The texture loader in ans.py can also be reused in other Python tools.

License
-------
This project is distributed under the dungeona Donationware License v1.0.
See license.txt for the full license text.

Author
------
Copyright (c) 2026 mtatton

Donation
--------
PayPal:
https://paypal.me/michtatton
