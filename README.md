Minesweeper
===========

Minesweeper. No losing from guessing. Two interfaces.

The web interface is available (for now) at http://minesweeper.gazpachoking.net


![minesweeper](https://gazpachoking.github.io/minesweeper/minesweeper.emoji.png)
![web](https://gazpachoking.github.io/minesweeper/minesweeper.web.png)

Features
--------

- Two interfaces
  - Play by yourself from the terminal. (boring)
  - Play on the web, with ~~griefing~~ coop!
- Cross platform
- Kaboom mode:
  - Cruel but fair, where guessing is punished, 
  but when only guesses are left you are guaranteed not to be wrong.
  - Based on the blog post [here](https://pwmarcz.pl/blog/kaboom/).
- Keyboard or mouse (or hybrid) control
- Standard and Knight's move modes
- Double-width characters (if your terminal supports it)
- QoL features:
  - Highlight adjacent tiles
  - Clear all adjacent
  - Mark all adjacent
  - Shows spaces that were provably empty after a loss (marked with yellow)

Running
-------

CLI
===
Check out the code. Run `uv run minesweeper`.

Web
===
Check out the code. Run `docker compose up` to start the server. Connect to `http://localhost:8080`

Controls
--------

- **N** New game
- **Q** Quit
- **Right-click/M** Mark mine/mark all adjacent
- **Click/Space** Reveal tile
- **Double-click/Space** Reveal all adjacent (except marked mines)

Legend
------

- ░ Unrevealed tile
- **\#** Marked as mine
- **1-8** Number of adjacent mines
- **\*** Unmarked mine (after game end)
- **X** Incorrect mark (after game end) 

CLI
---

- **--size X Y** Specify field size
- **--mines N** Specify number (or fraction of board) of mines
- **--niceness cruel|normal|fair|nice**
  - **nice** Any click that could result in an empty tile is an empty tile.
  - **fair** If guessing is the only move available, you will not guess wrong.
  - **normal** Traditional minesweeper.
  - **cruel** Any click that could result in a mine is a mine. (Except when guessing is the only move available.)
- **--style single|double** double mode uses full width unicode characters to
  double the cell size. Use single if this causes problems with your terminal. 

  

