from collections import namedtuple
from itertools import chain
from random import shuffle
import time
import typing

from asciimatics.event import KeyboardEvent, MouseEvent
from asciimatics.exceptions import StopApplication
from asciimatics.scene import Scene
from asciimatics.screen import Screen
from asciimatics.widgets import (
    Frame,
    Label,
    ListBox,
    Layout,
    Divider,
    Text,
    Button,
    TextBox,
    Widget,
)
import click


Position = namedtuple("Position", ["x", "y"])

NOT_STARTED = "Not Started"
IN_PROGRESS = "In Progress"
WON = "Won!"
LOST = "Lost!"


class Tile(object):
    def __init__(self, mine=False):
        self.mine = mine
        self.revealed = False
        self.marked = False
        self.neighbors = None
        self.pos = None

    def __repr__(self):
        return f"Tile(mine={self.mine})"


class Board(object):
    def __init__(self, width: int, height: int, num_mines: int):
        assert num_mines < width * height
        self.width = width
        self.height = height
        self.num_mines = num_mines
        self.field = []
        self.place_mines(Position(0, 0))
        self.status = NOT_STARTED
        self.start_time = None
        self.end_time = None

    def place_mines(self, start_pos: Position):
        self.field.clear()
        tiles = [
            Tile(mine=x < self.num_mines) for x in range(self.width * self.height - 1)
        ]
        shuffle(tiles)
        tiles = iter(tiles)
        for row_num in range(self.height):
            row = []
            self.field.append(row)
            for col_num in range(self.width):
                pos = Position(col_num, row_num)
                if pos == start_pos:
                    tile = Tile(mine=False)
                else:
                    tile = next(tiles)
                tile.pos = pos
                row.append(tile)
        # Initialize number of neighbors
        for tile in self.all_tiles():
            tile.neighbors = sum(1 if t.mine else 0 for t in self._in_range(tile.pos))
        self.status = IN_PROGRESS
        self.start_time = time.time()

    def reveal(self, pos: Position):
        if self.status == NOT_STARTED:
            self.place_mines(pos)
        tile = self[pos]
        if tile.marked or tile.revealed:
            return
        tile.revealed = True
        if not tile.neighbors:
            self.reveal_all(tile.pos)
        if self.is_lose():
            self.status = LOST
            self.reveal_mines()
            self.end_time = time.time()
        elif self.is_win():
            self.status = WON
            self.end_time = time.time()

    @property
    def play_duration(self) -> float:
        if not self.start_time:
            return 0
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    def reveal_all(self, pos: Position):
        self.reveal(pos)
        for neighbor in self._in_range(pos):
            if neighbor.marked:
                continue
            self.reveal(neighbor.pos)

    def mark(self, pos: Position):
        if self.status == NOT_STARTED:
            return
        tile = self[pos]
        if tile.revealed:
            return
        tile.marked = not tile.marked

    def is_win(self) -> bool:
        return all(t.mine or t.revealed for t in self.all_tiles())

    def is_lose(self) -> bool:
        return any(t.mine and t.revealed for t in self.all_tiles())

    def all_tiles(self) -> typing.Iterable[Tile]:
        return chain(*self.field)

    def reveal_mines(self):
        for tile in self.all_tiles():
            if tile.mine:
                tile.revealed = True

    def _in_range(self, pos: Position):
        x, y = pos
        x1 = max(0, min(x - 1, self.width - 1))
        x2 = max(0, min(x + 1, self.width - 1))
        y1 = max(0, min(y - 1, self.height - 1))
        y2 = max(0, min(y + 1, self.height - 1))
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                yield self.field[y][x]

    def __getitem__(self, pos: Position) -> Tile:
        return self.field[pos[1]][pos[0]]


class MineField(Widget):
    def __init__(self, board):
        super().__init__("MineField")
        self._board = board

    def update(self, frame_no):
        for tile in self._board.all_tiles():
            color = Screen.COLOUR_WHITE
            if tile.marked:
                color = Screen.COLOUR_RED
                char = "#"
            elif not tile.revealed:
                char = "░"
            elif tile.mine:
                color = Screen.COLOUR_MAGENTA
                char = "*"
            elif tile.neighbors:
                char = str(tile.neighbors)
            else:
                char = " "
            self._frame.canvas.print_at(char, self._x + tile.pos.x, self._y + tile.pos.y, color)
            self._frame.canvas.print_at("aoeu", 0, 0)

    def reset(self):
        pass

    def process_event(self, event):
        if isinstance(event, KeyboardEvent):
            if event.key_code in (ord("Q"), ord("q")):
                raise StopApplication('User Quit')
            elif event.key_code in (ord("N"), ord("n")):
                self.new()
        elif isinstance(event, MouseEvent):
            event = self._frame.rebase_event(event)
            if not self.is_mouse_over(event, include_label=False):
                return
            pos = Position(event.x-self._x, event.y-self._y)
            if event.buttons & event.LEFT_CLICK:
                self._board.reveal(pos)
            if event.buttons & event.RIGHT_CLICK:
                self._board.mark(pos)
            if event.buttons & event.DOUBLE_CLICK:
                self._board.reveal_all(pos)

    def required_height(self, offset, width):
        return self._board.height

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val


class GameBoard(Frame):
    def __init__(self, screen, board):
        super().__init__(screen, board.height+3, board.width+2, title="Minesweeper")
        layout1 = Layout([1, 1, 1, 1])
        self.add_layout(layout1)
        layout1.add_widget(Label("Time"), 0)
        layout1.add_widget(Label("0"), 1)
        layout1.add_widget(Label("Mines"), 2)
        layout1.add_widget(Label(str(board.num_mines)), 3)
        self._mine_field = MineField(board)
        layout = Layout([100])
        self.add_layout(layout)
        layout.add_widget(self._mine_field)
        self.fix()


def run_scene(screen, board):
    scenes = [Scene([GameBoard(screen, board)], -1, name="Main")]
    screen.play(scenes)


@click.command()
@click.option("--size", nargs=2, type=int)
@click.option("--mines", type=int)
def main(size, mines):
    if not size:
        size = (15, 15)
    if not mines:
        mines = int(size[0] * size[1] * 0.15)
    # frame = widgets.Frame(screen, screen.height, screen.width)
    board = Board(size[0], size[1], mines)
    Screen.wrapper(run_scene, arguments=[board])


if __name__ == "__main__":
    main()
