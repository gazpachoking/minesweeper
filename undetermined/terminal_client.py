import sys

from asciimatics.event import KeyboardEvent, MouseEvent
from asciimatics.exceptions import ResizeScreenError, StopApplication
from asciimatics.scene import Scene
from asciimatics.screen import Screen
from asciimatics.widgets import Frame, Label, Layout, Button, Widget
import click

from undetermined import Position, GameState, AdjacencyType, NiceMode, Board

# Game Statuses


# Adjacency Types


# Niceness


STYLES = {
    "single": {
        "width": 1,
        "flag": "#",
        "wrong_flag": "X",
        "mine": "*",
        "exploded": "+",
        "unrevealed": " ",
        0: " ",
        1: "1",
        2: "2",
        3: "3",
        4: "4",
        5: "5",
        6: "6",
        7: "7",
        8: "8",
        9: "9",
    },
    "double": {
        "width": 2,
        # All of these characters are 'full width'
        "flag": "🚩",
        "wrong_flag": "Ｘ",
        "mine": "💣",
        "exploded": "💥",
        "unrevealed": "　",
        0: "　",
        1: "１",
        2: "２",
        3: "３",
        4: "４",
        5: "５",
        6: "６",
        7: "７",
        8: "８",
        9: "９",
    },
}


class MineField(Widget):
    def __init__(self, board, style):
        super().__init__("MineField")
        self._board = board
        self._style = style

    def update(self, frame_no):
        adjacent = list(self._board.in_range(self._board.cursor))
        cursor = self._board[self._board.cursor]
        for tile in self._board.all_tiles:
            color = Screen.COLOUR_WHITE
            bg = Screen.COLOUR_BLACK
            if tile.marked:
                color = Screen.COLOUR_RED
                char = self._style["flag"]
            elif not tile.revealed:
                bg = Screen.COLOUR_WHITE
                char = self._style["unrevealed"]
            elif tile.mine:
                char = self._style["mine"]
            else:
                char = self._style[tile.num_adjacent_mines]
            if self._board.status in [GameState.WON, GameState.LOST]:
                if self._board.status == GameState.WON:
                    bg = Screen.COLOUR_CYAN
                if tile.mine:
                    color = Screen.COLOUR_GREEN
                    if not tile.marked:
                        char = self._style["mine"]
                    if tile.revealed:
                        color = Screen.COLOUR_RED
                        char = self._style["exploded"]
                elif tile.marked:
                    color = Screen.COLOUR_RED
                    char = self._style["wrong_flag"]
                if tile.determined and not tile.mine and not tile.revealed:
                    bg = Screen.COLOUR_YELLOW
            else:
                # Debug (cheater) coloring
                # if not tile.revealed and tile.determined:
                #     if tile.mine:
                #         color = Screen.COLOUR_RED
                #     else:
                #         color = Screen.COLOUR_GREEN
                if tile is cursor:
                    bg = Screen.COLOUR_YELLOW
                if cursor.revealed:
                    if tile in adjacent and not tile.revealed:
                        bg = Screen.COLOUR_CYAN
            self._frame.canvas.paint(
                char,
                self._x + (tile.pos.x * self._style["width"]),
                self._y + tile.pos.y,
                color,
                bg=bg,
                attr=Screen.A_BOLD,
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
            pos = Position(
                int(event.x / self._style["width"]) - self._x, event.y - self._y
            )
            if not self._board.in_bounds(pos):
                return
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
    def __init__(self, screen, board: Board, style):
        self._style = style
        super().__init__(
            screen,
            board.height + 4,
            (board.width * self._style["width"]) + 2,
            title="Minesweeper",
            hover_focus=False,
        )
        self._board = board
        layout1 = Layout([1, 1])
        self.add_layout(layout1)
        self._time_label = Label("0")
        self._mine_label = Label(str(self._board.total_mines))
        layout1.add_widget(self._time_label, 0)
        layout1.add_widget(self._mine_label, 1)
        self._mine_field = MineField(board, style)
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
        self._mine_label.text = str(self._board.unmarked_mines)
        super()._update(frame_no)


def run_scene(screen, board, style):
    scenes = [Scene([GameBoard(screen, board, style)], -1, name="Main")]
    screen.play(scenes, stop_on_resize=True)


class EnumChoice(click.Choice):
    """Allows enum to be used as a click choice."""

    def __init__(self, enum, case_sensitive=False, use_value=True):
        self.enum = enum
        self.use_value = use_value
        choices = [str(e.value) if use_value else e.name for e in self.enum]
        super().__init__(choices, case_sensitive)

    def convert(self, value, param, ctx):
        if isinstance(value, self.enum) and value in self.enum:
            return value
        result = super().convert(value, param, ctx)
        # Find the original case in the enum
        if not self.case_sensitive and result not in self.choices:
            result = next(c for c in self.choices if result.lower() == c.lower())
        if self.use_value:
            return next(e for e in self.enum if str(e.value) == result)
        return self.enum[result]


@click.command()
@click.option("--size", default=(30, 20), nargs=2, type=int)
@click.option("--mines", default=0.2, type=float)
@click.option(
    "--adjacency", default=AdjacencyType.STANDARD, type=EnumChoice(AdjacencyType)
)
@click.option("--niceness", default=NiceMode.CRUEL, type=EnumChoice(NiceMode))
@click.option("--style", default="double", type=click.Choice(STYLES.keys()))
def main(size, mines, adjacency, niceness, style):
    if mines < 1:
        mines = int(size[0] * size[1] * mines)
    else:
        mines = int(mines)
    style = STYLES[style]
    board = Board(size[0], size[1], mines, adjacency, niceness)
    while True:
        try:
            Screen.wrapper(run_scene, arguments=[board, style], unicode_aware=True)
            sys.exit(0)
        except ResizeScreenError:
            pass


if __name__ == "__main__":
    main()
