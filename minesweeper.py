from collections import namedtuple
from enum import Enum
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
import z3


Position = namedtuple("Position", ["x", "y"])

# Game Statuses
class GameState(Enum):
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


class Tile:
    def __init__(self, pos: Position, board : 'Board'):
        self.pos = pos
        self.board = board
        self.determined = False
        self.mine = False
        self.revealed = False
        self.marked = False
        self.adjacent_mines = 0

    @property
    def undetermined(self):
        return not self.determined

    @property
    def var_name(self):
        return f"t{self.pos.x},{self.pos.y}"

    @property
    def var(self):
        return z3.Bool(self.var_name)

    def __repr__(self):
        return f"Tile(pos={self.pos})"


class Board:
    def __init__(self, width: int, height: int, num_mines: int, mode: str = STANDARD):
        assert num_mines < self.width * self.height
        self.field = {}
        self.width = width
        self.height = height
        self.total_mines = num_mines
        self.start_time = 0.0
        self.end_time = 0.0
        self.cursor = Position(0, 0)
        self.adjacency_mode = mode
        self.status = GameState.NOT_STARTED
        self.place_tiles()

    @property
    def placed_mines(self):
        return sum(1 if t.determined and t.mine else 0 for t in self.all_tiles())

    @property
    def unplaced_mines(self):
        return self.total_mines - self.placed_mines

    def place_tiles(self):
        self.field.clear()
        for row_num in range(self.height):
            for col_num in range(self.width):
                pos = Position(row_num, col_num)
                self.field[pos] = Tile(pos=pos, board=self)
        self.status = GameState.IN_PROGRESS
        self.start_time = time.time()

    def undetermined_tiles(self):
        return [t for t in self.all_tiles() if t.undetermined]

    def solver(self):
        solver = z3.Solver()
        # The sum of all undetermined tiles that are a mine must equal the number of unplaced mines
        solver.add(z3.PbEq([(t.var, 1) for t in self.undetermined_tiles()], self.unplaced_mines))
        # The sum of all undetermined tiles touching a revealed number must equal that number
        for t in self.all_tiles():
            if t.determined and t.adjacent_mines and not t.mine:
                known_mine_neighbors = sum(
                    1 for n in self.in_range(t) if n.determined and n.mine
                )
                if known_mine_neighbors < t.adjacent_mines:
                    solver.add(
                        z3.PbEq(
                            [(n.var, 1) for n in self.in_range(t) if n.undetermined],
                            t.adjacent_mines - known_mine_neighbors,
                        )
                    )
        return solver

    def reveal(self, pos: Position):
        tile = self[pos]
        if tile.marked or tile.revealed:
            return
        if not tile.determined:
            pass
        tile.revealed = True
        if not tile.neighbors:
            self.reveal_all(tile.pos)
        if self.is_lose():
            self.status = GameState.LOST
            self.end_time = time.time()
        elif self.is_win():
            self.status = GameState.WON
            self.end_time = time.time()

    @property
    def play_duration(self) -> float:
        if not self.start_time:
            return 0
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def unmarked_mines(self) -> int:
        return self.total_mines - sum(1 if t.marked else 0 for t in self.all_tiles())

    def reveal_all(self, pos: Position):
        self.reveal(pos)
        for neighbor in self.in_range(pos):
            if neighbor.marked:
                continue
            self.reveal(neighbor.pos)

    def mark(self, pos: Position):
        if self.status == GameState.NOT_STARTED:
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
        return self.field.values()

    def in_range(self, pos: Position):
        for offset in ADJACENCY_TYPES[self.adjacency_mode]:
            new_pos = Position(*[sum(v) for v in zip(offset, pos)])
            if self.in_bounds(new_pos):
                yield self[new_pos]

    def in_bounds(self, pos: Position):
        return pos in self.field
        #return (0 <= pos[0] < self.width) and (0 <= pos[1] < self.height)

    def __getitem__(self, pos: Position) -> Tile:
        return self.field[pos]


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
            if self._board.status in [GameState.WON, GameState.LOST]:
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
            if not self.is_mouse_over(event, include_label=False):
                return event
            if self._board.status in [GameState.WON, GameState.LOST]:
                return
            self.focus()
            pos = Position(event.x - self._x, event.y - self._y)
            self._board.cursor = pos
            if event.buttons & event.LEFT_CLICK:
                self._board.reveal(pos)
            elif event.buttons & event.RIGHT_CLICK:
                if self._board[pos].revealed:
                    for tile in self._board.in_range(pos):
                        if not tile.marked:
                            self._board.mark(tile.pos)
                else:
                    self._board.mark(pos)
            elif event.buttons & event.DOUBLE_CLICK:
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
@click.option("--size", default=(30, 20), nargs=2, type=int)
@click.option("--mines", default=0.2, type=float)
@click.option("--mode", default=STANDARD, type=click.Choice(ADJACENCY_TYPES))
def main(size, mines, mode):
    if mines < 1:
        mines = int(size[0] * size[1] * mines)
    board = Board(size[0], size[1], mines, mode)
    while True:
        try:
            Screen.wrapper(run_scene, arguments=[board])
            sys.exit(0)
        except ResizeScreenError as e:
            pass


if __name__ == "__main__":
    main()
