from __future__ import annotations

import typing
from typing import TYPE_CHECKING

import htpy as h
from datastar_py import attribute_generator as data
from htpy import Renderable
from markupsafe import Markup

from undetermined import NiceMode, AdjacencyType, ShowDetermined

if TYPE_CHECKING:
    from undetermined import Board, Tile
    from undetermined.web_client import HoverPos


def layout_page(title: str, content: Renderable, update_sse: str | None = None):
    return h.html(lang="en")[
        h.head[
            h.meta(charset="UTF-8"),
            h.meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            h.title[title],
            h.script(type="module", src="/static/datastar.js"),
            h.link(
                rel="stylesheet",
                href="https://cdn.jsdelivr.net/npm/@picocss/pico@1/css/pico.min.css",
            ),
            h.link(rel="stylesheet", href="/static/main.css"),
        ],
        h.body(data.on_load(update_sse))[content],
    ]


def room_list_fragment(rooms: typing.Iterable[str]):
    return h.div("#room-list")[
        h.h2["Room List"],
        [h.p[h.a(href=f"/room/{room}")[room]] for room in rooms],
        h.button("#newroombutton", data.on("click", "@post('/room')"), role="button")[
            "New Room"
        ],
    ]


def room_list_page(rooms: typing.Iterable[str]):
    content = h.main("#main.container")[
        h.h1("#title")["🚩 Undeter", h.span(style="color: orangered")["mined"], " 💣"],
        room_list_fragment(rooms),
        h.article("#info")[
            h.h4["Info"],
            h.ul[
                h.li["Left-click to reveal a tile."],
                h.li["Right-click to mark a tile as a mine. (long press on mobile)"],
                h.li["Numbers indicate how many adjacent tile are mines."],
                h.li["Double-click a number to reveal all (non-marked) adjacent tile."],
                h.li["Right-click a number to mark all adjacent tile as mines."],
                h.li["Anyone can join a room with you."],
                h.li[
                    "There are several modes. Drop down the options while in a room to select:",
                    h.ul[
                        h.li[
                            h.strong["Cruel:"],
                            Markup(
                                f" If you guessed, you guessed wrong. If you {h.em['had']} to "
                                "guess, you guessed correctly. This is the one you should use."
                            ),
                        ],
                        h.li[
                            h.strong["Fair:"],
                            " If you must guess, you guessed correctly. No extra punishment for "
                            "guessing when you didn't have to.",
                        ],
                        h.li[
                            h.strong["Nice:"],
                            " If you guessed, you were correct. Unless it was a really stupid guess.",
                        ],
                        h.li[h.strong["Normal:"], " The mines won't move. Lame."],
                    ],
                ],
                h.li[
                    h.strong["Undo"],
                    " Is there anyone else watching? Are they judging you? Don't worry, the "
                    "mines will move, you still have to use logic.",
                ],
                h.li[h.strong["Knights Move"], " adjacency mode. For sadists."],
                h.li["Oh yeah, reveal all the tiles that aren't mines."],
                h.li[
                    "Source code is on ",
                    h.a(href="https://github.com/gazpachoking/minesweeper")["GitHub."],
                ],
            ],
        ],
    ]
    return layout_page(
        title="Undetermined", content=content, update_sse="@get('/room_list')"
    )


def tile_fragment(tile: Tile, hovers: typing.Iterable[HoverPos]):
    classes = [tile.revealed and "revealed"]
    content = None
    style = None
    for hover in hovers or []:
        if hover.pos == tile.pos:
            style = f"background-color: {hover.color}"
    if tile.num_adjacent_mines:
        content = tile.num_adjacent_mines
        classes.append(f"adjacent-{tile.num_adjacent_mines}")
    elif tile.marked:
        content = "🚩"
        classes.append("marked")
    elif tile.mine and tile.revealed:
        content = "💥"
    elif tile.board.is_over() and tile.mine:
        content = "💣"
    if tile.board.is_over():
        if tile.mine and tile.revealed:
            classes.append("incorrect")
        elif tile.determined:
            if tile.marked and tile.mine:
                classes.append("correct")
            elif tile.marked:
                classes.append("incorrect")
            elif tile.mine and tile.board.is_win():
                classes.append("correct")
    if tile.undetermined and (
        tile.board.show_determined == ShowDetermined.ALWAYS
        or tile.board.is_loss()
        and tile.board.show_determined == ShowDetermined.ON_LOSS
    ):
        classes.append("undetermined")

    return h.div(
        id=f"{tile.pos.x},{tile.pos.y}",
        style=style,
        class_=classes,
    )[content]


def game_fragment(
    room_name: str, board: Board, hovers: typing.Iterable[HoverPos] = None
):
    return h.fragment[
        h.div("#game-info")[
            h.p[
                "Mines Left: ",
                h.span("#mines-left")[board.unmarked_mines],
            ],
            h.p[
                "Time: ",
                h.span[int(board.play_duration)],
            ],
        ],
        h.div(
            "#board.board",
            data.on(
                "contextmenu", f"@get('/room/{room_name}/mark?pos='+evt.target.id)"
            ).prevent,
            data.on("mouseleave", f"@get('/room/{room_name}/mouseover?pos=-1,-1')"),
            data.on("click", f"@get('/room/{room_name}/reveal?pos='+evt.target.id)"),
            data.on(
                "dblclick", f"@get('/room/{room_name}/reveal_all?pos='+evt.target.id)"
            ),
            data.on(
                "mouseover", f"@get('/room/{room_name}/mouseover?pos='+evt.target.id)"
            ).throttle(80),
            style=f"grid-template-columns: repeat({board.width}, 30px)",
        )[[tile_fragment(tile, hovers) for tile in board.all_tiles]],
        h.div("#gameover-buttons")[
            board.is_loss()
            and board.undo
            and h.button(
                "#undo",
                data.on("click", f"@post('/room/{room_name}/undo')"),
            )["Undo"],
            board.is_over()
            and h.button(
                "#newgame",
                data.on(
                    "click",
                    f"@post('/room/{room_name}/new', {{contentType: 'form', selector: '#gameoptions'}})",
                ),
            )["New Game"],
        ],
    ]


def game_page(room_name: str, board: Board):
    content = h.main("#main.content")[
        h.h1("#title")["🚩 Undeter", h.span(style="color: orangered")["mined"], " 💣"],
        game_fragment(room_name, board),
        h.details("#optionsSection", data_ref="options")[
            h.summary(".secondary", role="button")["Options"],
            h.form("#gameoptions")[
                h.fieldset(".grid")[
                    h.label[
                        "Width",
                        h.input(
                            type="number",
                            name="width",
                            value=board.width,
                            min=2,
                            max=30,
                        ),
                    ],
                    h.label[
                        "Height",
                        h.input(
                            type="number",
                            name="height",
                            value=board.height,
                            min=2,
                            max=30,
                        ),
                    ],
                ],
                h.label[
                    "Mines",
                    h.input(
                        type="number",
                        name="mines",
                        value=board.total_mines,
                    ),
                ],
                h.label[
                    "Niceness Mode",
                    h.select(name="nice_mode")[
                        [
                            h.option(
                                value=mode.value, selected=mode == board.nice_mode
                            )[mode.name.title()]
                            for mode in NiceMode
                        ],
                    ],
                ],
                h.label[
                    "Adjacency Mode",
                    h.select(name="adjacency_mode")[
                        [
                            h.option(
                                value=mode.value, selected=mode == board.adjacency_mode
                            )[mode.name.title()]
                            for mode in AdjacencyType
                        ],
                    ],
                ],
                h.fieldset[
                    h.legend[h.strong["Cheating"]],
                    h.label[
                        h.input(type="checkbox", name="undo", checked=board.undo),
                        "Allow Undo",
                    ],
                ],
                h.label[
                    "Show Determined Tiles",
                    h.select(name="show_determined")[
                        [
                            h.option(
                                value=mode.value,
                                selected=mode == board.show_determined,
                            )[mode.name.title().replace("_", " ")]
                            for mode in ShowDetermined
                        ]
                    ],
                ],
                h.button(
                    data.on(
                        "click",
                        f"""@post('/room/{room_name}/new', {{contentType: 'form'}});
                        $options.removeAttribute('open');""",
                    ),
                    type="button",
                )["New Game"],
            ],
        ],
    ]
    return layout_page(
        title="Undetermined",
        content=content,
        update_sse=f"@get('/room/{room_name}/stream')",
    )
