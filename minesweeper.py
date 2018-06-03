from collections import namedtuple
from itertools import chain, product
from random import shuffle
import sys
import time
import typing

from asciimatics.event import KeyboardEvent, MouseEvent
from asciimatics.exceptions import ResizeScreenError, StopApplication
from asciimatics.scene import Scene
from asciimatics.screen import Screen
from asciimatics.widgets import Frame, Label, Layout, Button, Widget
import click


Position = namedtuple("Position", ["x", "y"])

# Game Statuses
NOT_STARTED = "Not Started"
IN_PROGRESS = "In Progress"
WON = "Won!"
LOST = "Lost!"

# Adjacency Types
STANDARD = "standard"
KNIGHTS = "knights"
ADJACENCY_TYPES = {
    STANDARD: list(product([-1, 0, 1], [-1, 0, 1])),
    KNIGHTS: list(chain(product([-1, 1], [-2, 2]), product([-2, 2], [-1, 1]))),
}


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
    def __init__(self, width: int, height: int, num_mines: int, mode: str = STANDARD):
        self.field = []
        self.width = width
        self.height = height
        self.num_mines = num_mines
        self.start_time = 0.0
        self.end_time = 0.0
        self.cursor = Position(0, 0)
        self.adjacency_mode = mode
        self.status = NOT_STARTED
        self.new(width, height, num_mines)

    def new(self, width: int = None, height: int = None, num_mines: int = None):
        if width is not None:
            self.width = width
        if height is not None:
            self.height = height
        if num_mines is not None:
            self.num_mines = num_mines
        self.place_mines(Position(0, 0))
        self.status = NOT_STARTED
        self.start_time = None
        self.end_time = None

    def place_mines(self, start_pos: Position):
        assert self.num_mines < self.width * self.height
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
            a = list(self.in_range(tile.pos))
            tile.neighbors = sum(1 if t.mine else 0 for t in self.in_range(tile.pos))
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

    @property
    def mines_left(self) -> int:
        return self.num_mines - sum(1 if t.marked else 0 for t in self.all_tiles())

    def reveal_all(self, pos: Position):
        self.reveal(pos)
        for neighbor in self.in_range(pos):
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

    def in_range(self, pos: Position):
        for offset in ADJACENCY_TYPES[self.adjacency_mode]:
            new_pos = Position(*[sum(v) for v in zip(offset, pos)])
            if self.in_bounds(new_pos):
                yield self[new_pos]

    def in_bounds(self, pos: Position):
        return (0 <= pos[0] < self.width) and (0 <= pos[1] < self.height)

    def __getitem__(self, pos: Position) -> Tile:
        return self.field[pos[1]][pos[0]]


class MineField(Widget):
    def __init__(self, board):
        super().__init__("MineField")
        self._board = board

    def update(self, frame_no):
        adjacent = list(self._board.in_range(self._board.cursor))
        cursor = self._board[self._board.cursor]
        for tile in self._board.all_tiles():
            color = Screen.COLOUR_WHITE
            bg = Screen.COLOUR_BLACK
            if tile.marked:
                color = Screen.COLOUR_RED
                char = "#"
            elif not tile.revealed:
                char = "░"
            elif tile.neighbors:
                char = str(tile.neighbors)
            else:
                char = " "
            if self._board.status in [WON, LOST]:
                if tile.marked and tile.mine:
                    color = Screen.COLOUR_GREEN
                elif tile.mine:
                    color = Screen.COLOUR_GREEN
                    if tile.revealed:
                        color = Screen.COLOUR_RED
                    char = "*"
                elif tile.marked:
                    color = Screen.COLOUR_RED
                    char = "X"
            else:
                if tile is cursor:
                    bg = Screen.COLOUR_YELLOW
                if cursor.revealed:
                    if tile in adjacent and not tile.revealed:
                        bg = Screen.COLOUR_CYAN
            self._frame.canvas.paint(
                char, self._x + tile.pos.x, self._y + tile.pos.y, color, bg=bg
            )

    def reset(self):
        pass

    def process_event(self, event):
        if self._has_focus and isinstance(event, KeyboardEvent):
            if event.key_code in (
                Screen.KEY_RIGHT,
                Screen.KEY_UP,
                Screen.KEY_LEFT,
                Screen.KEY_DOWN,
                Screen.KEY_PAGE_DOWN,
                Screen.KEY_PAGE_UP,
                Screen.KEY_END,
                Screen.KEY_HOME,
            ):
                new_x, new_y = self._board.cursor
                if event.key_code == Screen.KEY_DOWN:
                    new_y += 1
                elif event.key_code == Screen.KEY_UP:
                    new_y -= 1
                elif event.key_code == Screen.KEY_RIGHT:
                    new_x += 1
                elif event.key_code == Screen.KEY_LEFT:
                    new_x -= 1
                elif event.key_code == Screen.KEY_PAGE_UP:
                    new_y = 0
                elif event.key_code == Screen.KEY_PAGE_DOWN:
                    new_y = self._board.height - 1
                elif event.key_code == Screen.KEY_HOME:
                    new_x = 0
                elif event.key_code == Screen.KEY_END:
                    new_x = self._board.width - 1
                new_pos = Position(new_x, new_y)
                if self._board.in_bounds(new_pos):
                    self._board.cursor = new_pos
            elif event.key_code == ord(" "):
                if self._board[self._board.cursor].revealed:
                    self._board.reveal_all(self._board.cursor)
                else:
                    self._board.reveal(self._board.cursor)
            elif event.key_code in (ord("M"), ord("m")):
                if self._board[self._board.cursor].revealed:
                    for tile in self._board.in_range(self._board.cursor):
                        if not tile.marked:
                            self._board.mark(tile.pos)
                else:
                    self._board.mark(self._board.cursor)
            else:
                return event
        elif isinstance(event, MouseEvent):
            new_event = self._frame.rebase_event(event)
            if not self.is_mouse_over(new_event, include_label=False):
                return event
            if self._board.status in [WON, LOST]:
                return
            self.focus()
            pos = Position(new_event.x - self._x, new_event.y - self._y)
            self._board.cursor = pos
            if new_event.buttons & new_event.LEFT_CLICK:
                self._board.reveal(pos)
            elif new_event.buttons & new_event.RIGHT_CLICK:
                if self._board[pos].revealed:
                    for tile in self._board.in_range(pos):
                        if not tile.marked:
                            self._board.mark(tile.pos)
                else:
                    self._board.mark(pos)
            elif new_event.buttons & new_event.DOUBLE_CLICK:
                self._board.reveal_all(pos)
        else:
            return event

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
        super().__init__(
            screen,
            board.height + 4,
            board.width + 2,
            title="Minesweeper",
            hover_focus=False,
        )
        self._board = board
        layout1 = Layout([1, 1])
        self.add_layout(layout1)
        self._time_label = Label("0")
        self._mine_label = Label(str(self._board.num_mines))
        layout1.add_widget(self._time_label, 0)
        layout1.add_widget(self._mine_label, 1)
        self._mine_field = MineField(board)
        self._layout2 = Layout([100])
        self.add_layout(self._layout2)
        self._layout2.add_widget(self._mine_field)
        layout3 = Layout([1, 1, 1])
        self.add_layout(layout3)
        layout3.add_widget(Button("New", self.new_game), 0)
        layout3.add_widget(Button("Quit", self.quit), 2)
        self.fix()

    def new_game(self):
        self._board.new()

    def quit(self):
        raise StopApplication("User Quit")

    def process_event(self, event):
        if isinstance(event, KeyboardEvent):
            if event.key_code in (ord("Q"), ord("q")):
                self.quit()
            elif event.key_code in (ord("N"), ord("n")):
                self.new_game()
                return
        elif isinstance(event, MouseEvent):
            new_event = self.rebase_event(event)
            if self._mine_field.is_mouse_over(new_event):
                self.switch_focus(self._layout2, 0, 0)
        super().process_event(event)

    def _update(self, frame_no):
        self._time_label.text = str(round(self._board.play_duration))
        self._mine_label.text = str(self._board.mines_left)
        super()._update(frame_no)


def run_scene(screen, board):
    scenes = [Scene([GameBoard(screen, board)], -1, name="Main")]
    screen.play(scenes, stop_on_resize=True)


@click.command()
@click.option("--size", nargs=2, type=int)
@click.option("--mines", type=int)
@click.option("--mode", default=STANDARD, type=click.Choice(ADJACENCY_TYPES))
def main(size, mines, mode):
    if not size:
        size = (15, 15)
    if not mines:
        mines = int(size[0] * size[1] * 0.15)
    board = Board(size[0], size[1], mines, mode)
    while True:
        try:
            Screen.wrapper(run_scene, arguments=[board])
            sys.exit(0)
        except ResizeScreenError as e:
            pass


if __name__ == "__main__":
    main()
