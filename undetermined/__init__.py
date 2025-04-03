import itertools
import time
import typing
from collections import namedtuple
from enum import Enum, Flag, auto, IntFlag
from itertools import product, chain
from random import shuffle
from typing import NamedTuple

import z3


class Position(NamedTuple):
    x: int
    y: int


class GameState(Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    WON = "Won!"
    LOST = "Lost!"


class AdjacencyType(Enum):
    STANDARD = "standard"
    KNIGHTS = "knights"


class TileState(IntFlag):
    MINE = auto()
    MARKED = auto()
    REVEALED = auto()
    DETERMINED = auto()


NEIGHBORS = {
    AdjacencyType.STANDARD: list(product([-1, 0, 1], [-1, 0, 1])),
    AdjacencyType.KNIGHTS: list(
        chain(product([-1, 1], [-2, 2]), product([-2, 2], [-1, 1]))
    ),
}


class NiceMode(Enum):
    # Any click that could result in an empty tile is an empty tile.
    NICE = "nice"
    # If guessing is the only move available, you will not guess wrong.
    FAIR = "fair"
    # Traditional minesweeper.
    NORMAL = "normal"
    # Any click that could result in a mine is a mine. (Except when guessing is the only move available.)
    CRUEL = "cruel"


class Tile:
    def __init__(self, pos: Position, board: "Board"):
        self.pos = pos
        self.board = board
        self.determined = False
        self.mine = False
        self.revealed = False
        self.marked = False
        self.num_adjacent_mines = None

    @property
    def classes(self):
        classes = []
        # classes.append("determined" if self.determined else "undetermined")
        classes.append("revealed" if self.revealed else "unrevealed")
        if self.board.is_loss() or self.board.is_win():
            if self.mine:
                classes.append("mine")
            if self.marked and not self.mine:
                classes.append("wrong")
        if self.marked:
            classes.append("marked")
        if self.revealed and self.num_adjacent_mines:
            classes.append(f"adjacent-{self.num_adjacent_mines}")
        return classes

    @property
    def undetermined(self) -> bool:
        return not self.determined

    @property
    def neighbors(self) -> typing.Iterable["Tile"]:
        return self.board.in_range(self.pos)

    @property
    def on_boundary(self) -> bool:
        return any(n.revealed != self.revealed for n in self.neighbors)

    # @property
    # def num_adjacent_mines(self) -> int:
    #     return sum(1 for t in self.neighbors if t.mine)

    @property
    def var(self):
        return z3.Bool(f"t{self.pos.x},{self.pos.y}")
    #
    # def serialize(self) -> int:
    #     state = TileState(0)
    #     if self.marked:
    #         state |= TileState.MARKED
    #     if self.mine:
    #         state |= TileState.MINE
    #     if self.determined:
    #         state |= TileState.DETERMINED
    #     if self.revealed:
    #         state |= TileState.REVEALED
    #     return int(state)
    #
    # @classmethod
    # def deserialize(cls, pos: Position, board: "Board", state: int | TileState):
    #     tile = cls(pos, board)
    #     state = TileState(state)
    #     tile.marked = TileState.MARKED in state
    #     tile.mine = TileState.MINE in state
    #     tile.revealed = TileState.REVEALED in state
    #     tile.determined = TileState.DETERMINED in state
    #     return tile




    def __repr__(self):
        return f"Tile(pos={self.pos}, determined={self.determined}, mine={self.mine}, revealed={self.revealed})"


class Board:
    def __init__(
        self,
        width: int,
        height: int,
        num_mines: int,
        adjacency: AdjacencyType = AdjacencyType.STANDARD,
        niceness: NiceMode = NiceMode.CRUEL,
    ):
        if num_mines >= width * height:
            raise RuntimeError("More mines than space.")
        self.field = {}
        self.width = width
        self.height = height
        self.total_mines = num_mines
        self.start_time = 0.0
        self.end_time = 0.0
        self.cursor = Position(0, 0)
        self.adjacency_mode = adjacency
        self.nice_mode = niceness
        self.status = GameState.NOT_STARTED
        self.moves = 0
        self.place_tiles()
        self.replace_mines()

    def new(self):
        self.status = GameState.NOT_STARTED
        self.start_time = 0
        self.end_time = 0
        self.place_tiles()
        self.replace_mines()
        self.moves += 1

    @property
    def num_determined_mines(self) -> int:
        return sum(1 for t in self.tiles(determined=True, mine=True))

    @property
    def num_undetermined_mines(self) -> int:
        return self.total_mines - self.num_determined_mines

    @property
    def all_tiles(self) -> typing.Iterable[Tile]:
        return self.field.values()

    def tiles(
        self, revealed=None, determined=None, on_boundary=None, mine=None
    ) -> typing.Iterable[Tile]:
        for tile in self.all_tiles:
            if revealed is not None and tile.revealed != revealed:
                continue
            if determined is not None and tile.determined != determined:
                continue
            if on_boundary is not None and tile.on_boundary != on_boundary:
                continue
            if mine is not None and tile.mine != mine:
                continue
            yield tile

    def place_tiles(self):
        self.field.clear()
        for row_num in range(self.height):
            for col_num in range(self.width):
                pos = Position(col_num, row_num)
                self.field[pos] = Tile(pos=pos, board=self)
        self.status = GameState.IN_PROGRESS

    def solver(self):
        solver = z3.Solver()
        # Cheat a bit to randomize possible solution by adding constraints in a random order
        undetermined = list(self.tiles(determined=False))
        revealed_boundary = list(self.tiles(revealed=True, on_boundary=True))
        shuffle(undetermined)
        shuffle(revealed_boundary)

        # The sum of all undetermined tiles that are a mine must equal the number of unplaced mines
        if self.num_undetermined_mines:
            solver.add(
                z3.PbEq([(t.var, 1) for t in undetermined], self.num_undetermined_mines)
            )

        # The sum of all undetermined tiles touching a revealed number must equal that number
        for t in revealed_boundary:
            known_mine_neighbors = sum(
                1 for n in t.neighbors if n.determined and n.mine
            )
            if all(n.determined for n in t.neighbors):
                continue
            solver.add(
                z3.PbEq(
                    [(n.var, 1) for n in t.neighbors if n.undetermined],
                    t.num_adjacent_mines - known_mine_neighbors,
                )
            )
        return solver

    def replace_mines(self):
        """Places all mines on tiles randomly, but in accordance with revealed hints."""
        solver = self.solver()
        assert solver.check() == z3.sat
        model = solver.model()
        for t in self.tiles(determined=False):
            t.mine = bool(model[t.var])

    def recalc(self):
        """Determine any tiles that should no longer be variable."""
        solver = self.solver()
        # Lock in certain tiles that must/must not be mines.
        for t in self.tiles(revealed=False, determined=False, on_boundary=True):
            can_be_mine = solver.check(t.var) == z3.sat
            can_be_open = solver.check(z3.Not(t.var)) == z3.sat
            if not (can_be_mine and can_be_open):
                t.determined = True

    def reveal(self, pos: Position, cascade=False):
        if self.status != GameState.IN_PROGRESS:
            return
        tile = self[pos]
        if tile.marked or tile.revealed:
            return

        self.moves += 1

        changed = False
        # First click, prevent hitting mine, start the timer
        if not any(self.tiles(determined=True)):
            self.start_time = time.time()
            changed = tile.mine
            tile.mine = False
        # Tile can still be changed, figure out if we'll change it
        elif not tile.determined and not cascade and self.nice_mode != NiceMode.NORMAL:
            safe_moves = any(
                self.tiles(on_boundary=True, mine=False, determined=True, revealed=False)
            )
            boundary_moves = list(self.tiles(on_boundary=True, revealed=False))
            if safe_moves and self.nice_mode == NiceMode.CRUEL:
                changed = not tile.mine
                tile.mine = True
            # If there are no safe moves, guarantee next boundary move is safe.
            # Or, if there are no boundary moves, guarantee any guess is safe.
            elif NiceMode.NICE or not boundary_moves or tile in boundary_moves:
                changed = tile.mine
                tile.mine = False
        tile.determined = True

        # If we changed the state of a mine, recalculate all mines into valid positions
        if changed:
            self.replace_mines()

        tile.revealed = True

        if tile.mine:
            self.status = GameState.LOST
            self.end_time = time.time()
            return

        tile.num_adjacent_mines = sum(1 for n in tile.neighbors if n.mine)
        if not tile.num_adjacent_mines:
            self.reveal_all(tile.pos, cascade=True)
        # Once all new tiles have been revealed, lock in any tiles which can no longer be changed
        if not cascade:
            self.recalc()
        if self.is_win():
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
        return self.total_mines - sum(1 if t.marked else 0 for t in self.all_tiles)

    def reveal_all(self, pos: Position, cascade=False):
        self.reveal(pos)
        for neighbor in self.in_range(pos):
            if neighbor.marked:
                continue
            self.reveal(neighbor.pos, cascade=cascade)

    def mark(self, pos: Position):
        if self.status != GameState.IN_PROGRESS:
            return
        tile = self[pos]
        if tile.revealed:
            return
        tile.marked = not tile.marked
        self.moves += 1

    def mark_all(self, pos: Position):
        for neighbor in self.in_range(pos):
            if not neighbor.revealed and not neighbor.marked:
                self.mark(neighbor.pos)

    def is_win(self) -> bool:
        return all(t.mine or t.revealed for t in self.all_tiles)

    def is_loss(self) -> bool:
        return any(t.mine and t.revealed for t in self.all_tiles)

    def is_over(self):
        return self.status in (GameState.WON, GameState.LOST)

    def in_range(self, pos: Position):
        for offset in NEIGHBORS[self.adjacency_mode]:
            new_pos = Position(*[sum(v) for v in zip(offset, pos)])
            if self.in_bounds(new_pos):
                yield self[new_pos]

    def in_bounds(self, pos: Position):
        return pos in self.field

    def __getitem__(self, pos: Position) -> Tile:
        return self.field[pos]
