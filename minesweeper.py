from collections import namedtuple
from itertools import chain
from random import shuffle
import time
import typing

from asciimatics import screen, event, widgets
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


class Game(object):
    def __init__(self, width: int, height: int, mines: int):
        self.width = width
        self.height = height
        self.mines = mines
        self.board = None
        self.screen = None

    def run(self, screen):
        self.screen = screen
        screen.clear()
        self.new()
        while True:
            ev = screen.get_event()
            if isinstance(ev, event.KeyboardEvent):
                if ev.key_code in (ord("Q"), ord("q")):
                    return
                elif ev.key_code in (ord("N"), ord("n")):
                    self.new()
            elif isinstance(ev, event.MouseEvent):
                if ev.x >= self.board.width or ev.y > self.board.height:
                    continue
                pos = Position(ev.x, ev.y)
                if ev.buttons & ev.LEFT_CLICK:
                    self.board.reveal(pos)
                if ev.buttons & ev.RIGHT_CLICK:
                    self.board.mark(pos)
                if ev.buttons & ev.DOUBLE_CLICK:
                    self.board.reveal_all(pos)
                if ev.buttons:
                    self.screen.clear()
            self.draw_board()
            self.screen.print_at(self.board.status, 0, self.board.height + 1)
            screen.refresh()

    def new(self):
        self.board = Board(self.width, self.height, self.mines)

    def draw_board(self):
        for tile in self.board.all_tiles():
            color = screen.Screen.COLOUR_WHITE
            if tile.marked:
                color = screen.Screen.COLOUR_RED
                char = "#"
            elif not tile.revealed:
                char = "░"
            elif tile.mine:
                color = screen.Screen.COLOUR_MAGENTA
                char = "*"
            elif tile.neighbors:
                char = str(tile.neighbors)
            else:
                char = " "
            self.screen.print_at(char, tile.pos.x, tile.pos.y, color)


@click.command()
@click.option("--size", nargs=2, type=int)
@click.option("--mines", type=int)
def main(size, mines):
    if not size:
        size = (15, 15)
    if not mines:
        mines = int(size[0] * size[1] * 0.15)
    # frame = widgets.Frame(screen, screen.height, screen.width)
    game = Game(size[0], size[1], mines)
    screen.Screen.wrapper(game.run)


if __name__ == "__main__":
    main()
