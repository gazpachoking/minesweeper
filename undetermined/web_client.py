import asyncio
import os
import pickle
import random
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import nats
import nats.errors
import nats.js.errors
from nats.js.api import KeyValueConfig
from datastar_py import ServerSentEventGenerator, SSE_HEADERS

from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from jinja2_fragments import render_block
from nats.js.errors import KeyNotFoundError
from nats.js.kv import KeyValue
from pydantic import BaseModel, Field
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import StreamingResponse, RedirectResponse

from undetermined import Board, NiceMode, AdjacencyType, Position


kv: KeyValue = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    nc = await nats.connect(
        f"nats://{os.environ.get('UNDETERMINED_NATS', 'nats')}:4222"
    )
    js = nc.jetstream()
    global kv
    try:
        kv = await js.create_key_value(
            KeyValueConfig("undetermined", history=2, ttl=6 * 60 * 60)
        )
    except nats.js.errors.BadRequestError as exc:
        # If we changed the config just delete and recreate the bucket
        print("removing kv store")
        await js.delete_key_value("undetermined")
        kv = await js.create_key_value(KeyValueConfig("undetermined", history=3))
    yield
    await nc.close()


PACKAGE_DIR = Path(__file__).parent
middleware = [
    Middleware(SessionMiddleware, secret_key="tawoerugeconaewmum12ea5teauem65")
]
app = FastAPI(lifespan=lifespan, middleware=middleware)
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
templates.context_processors = [
    lambda request: {
        "nice_modes": NiceMode,
        "adjacency_modes": AdjacencyType,
    }
]
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")


async def get_board(room_name: str):
    try:
        entry = await kv.get(f"{room_name}.state")
    except KeyNotFoundError:
        board = Board(12, 12, 30)
        # Using pickle is super inefficient, but :shrug:
        await kv.put(f"{room_name}.state", pickle.dumps(board))
    else:
        board = pickle.loads(entry.value)
    start_moves = board.moves
    yield board
    if board.moves > start_moves:
        await kv.put(f"{room_name}.state", pickle.dumps(board))


async def get_session_id(request: Request):
    return request.session.setdefault("session_id", uuid.uuid4().hex)


def get_position(x: int, y: int):
    return Position(x, y)


async def get_rooms():
    try:
        streams = await kv.keys()
    except nats.js.errors.NoKeysError:
        streams = []
    rooms = [r.removesuffix(".state") for r in streams if r.endswith(".state")]
    return reversed(rooms)


BoardDep = Annotated[Board, Depends(get_board)]
SessionDep = Annotated[str, Depends(get_session_id)]
PositionDep = Annotated[Position, Depends(get_position)]


class SSE(StreamingResponse):
    def __init__(self, *args, **kwargs):
        kwargs["headers"] = {**SSE_HEADERS, **kwargs.get("headers", {})}
        super().__init__(*args, **kwargs)


@app.get("/")
async def index(request: Request):
    rooms = await get_rooms()
    return templates.TemplateResponse(request, "index.html", {"rooms": rooms})


@app.get("/room_list")
async def room_list():
    async def gen():
        while True:
            rooms = await get_rooms()
            yield ServerSentEventGenerator.merge_fragments(
                [
                    render_block(
                        templates.env, "index.html", "room_list", {"rooms": rooms}
                    )
                ]
            )
            await asyncio.sleep(10)

    return SSE(gen())


@app.get("/room")
async def new_room(request: Request):
    animal = random.choice(
        (PACKAGE_DIR / "assets" / "animals.txt").open().readlines()
    ).strip()
    adjective = random.choice(
        (PACKAGE_DIR / "assets" / "adjectives.txt").open().readlines()
    ).strip()
    room_name = f"{adjective.title()}{animal.title()}"
    return RedirectResponse(f"/room/{room_name}", status_code=302)


@app.get("/room/{room_name}", response_class=HTMLResponse)
async def root(request: Request, room_name: str, board: BoardDep):
    return templates.TemplateResponse(
        request, "game.html", {"board": board, "room_name": room_name}
    )


class HoverPos(BaseModel):
    pos: Position
    session: str
    time: float = Field(default_factory=lambda: time.time())

    @property
    def color(self):
        random.seed(self.session)
        return "#" + "".join([random.choice("789ABCDE") for _ in range(6)])

    @property
    def valid(self):
        return self.pos.x >= 0 and self.time > time.time() - 15


@app.get("/room/{room_name}/stream")
async def stream(request: Request, room_name: str, session_id: SessionDep):
    async def gen():
        try:
            state = await kv.get(f"{room_name}.state")
        except nats.js.errors.KeyNotFoundError:
            # Room no longer exists
            yield ServerSentEventGenerator.execute_script(
                "window.location.replace('/')"
            )
            return
        board = pickle.loads(state.value)
        watcher = await kv.watch(f"{room_name}.>")
        hovers = {}
        while True:
            try:
                update = await watcher.updates(timeout=1)
            except nats.errors.TimeoutError:
                yield ServerSentEventGenerator.merge_fragments(
                    [f'<span id="time">{int(board.play_duration)}</span>']
                )
                update = None

            if not update:
                pass
            elif update.key.endswith(".state"):
                board = pickle.loads(update.value)
            else:
                new_hover = HoverPos.model_validate_json(update.value)
                if new_hover.session != session_id:
                    hovers[new_hover.session] = new_hover
                else:
                    continue
            if any(not h.valid for h in hovers.values()):
                hovers = {k: v for k, v in hovers.items() if v.valid}
            elif not update:
                continue

            yield ServerSentEventGenerator.merge_fragments(
                [
                    render_block(
                        templates.env,
                        "game.html",
                        "main",
                        {
                            "board": board,
                            "room_name": room_name,
                            "hover": hovers.values(),
                        },
                    )
                ]
            )

    return SSE(gen(), headers={"X-Accel-Buffering": "no"})


class RoomOptions(BaseModel):
    width: int
    height: int
    mines: int
    nice_mode: NiceMode
    adjacency_mode: AdjacencyType


@app.post("/room/{room_name}/new")
async def new(
    request: Request, room_name: str, options: Annotated[RoomOptions, Form()]
):
    board = Board(
        options.width,
        options.height,
        options.mines,
        niceness=options.nice_mode,
        adjacency=options.adjacency_mode,
    )
    await kv.put(f"{room_name}.state", pickle.dumps(board))
    return Response(status_code=204)


@app.get("/room/{room_name}/reveal")
async def on_click(pos: PositionDep, board: BoardDep):
    board.reveal(pos)
    return Response(status_code=204)


@app.get("/room/{room_name}/mark")
async def on_mark(pos: PositionDep, board: BoardDep):
    if board[pos].revealed:
        board.mark_all(pos)
    else:
        board.mark(pos)

    return Response(status_code=204)


@app.get("/room/{room_name}/reveal_all")
async def on_dbl(pos: PositionDep, board: BoardDep):
    board.reveal_all(pos)
    return Response(status_code=204)


@app.post("/room/{room_name}/undo")
async def undo(room_name: str):
    hist = await kv.history(f"{room_name}.state")
    if len(hist) >= 2:
        await kv.put(f"{room_name}.state", hist[-2].value)
    return Response(status_code=204)


@app.get("/room/{room_name}/mouseover")
async def on_mouseover(room_name: str, pos: PositionDep, session_id: SessionDep):
    await kv.put(
        f"{room_name}.mouse.{session_id}",
        HoverPos(pos=pos, session=session_id).model_dump_json().encode(),
    )
    return Response(status_code=204)


if __name__ == "__main__":
    uvicorn.run("undetermined.web_client:app", host="0.0.0.0", port=8000, reload=True)
