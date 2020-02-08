Minesweeper
===========

Simple terminal based minesweeper. Python 3 required.

![minesweeper](https://gazpachoking.github.io/minesweeper/double.width.characters.png)

Features
--------

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

  

