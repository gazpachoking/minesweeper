import pickle
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

import nats
import nats.errors
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
from pydantic import BaseModel, Json
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import StreamingResponse

from undetermined import Board, NiceMode, AdjacencyType, Position


kv: KeyValue = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    nc = await nats.connect("nats://127.0.0.1:4222")
    js = nc.jetstream()
    global kv
    kv = await js.create_key_value(KeyValueConfig("undetermined"))
    yield
    await nc.close()


middleware = [
    Middleware(SessionMiddleware, secret_key="tawoerugeconaewmum12ea5teauem65")
]
app = FastAPI(lifespan=lifespan, middleware=middleware)
templates = Jinja2Templates(directory="templates")
templates.context_processors = [
    lambda request: {
        "nice_modes": NiceMode,
        "adjacency_modes": AdjacencyType,
    }
]
app.mount("/static", StaticFiles(directory="static"), name="static")


async def get_board(room_name: str):
    try:
        entry = await kv.get(f"{room_name}.state")
    except KeyNotFoundError:
        board = Board(10, 10, 10)
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


BoardDep = Annotated[Board, Depends(get_board)]
SessionDep = Annotated[str, Depends(get_session_id)]
PositionDep = Annotated[Position, Depends(get_position)]


class SSE(StreamingResponse):
    def __init__(self, *args, **kwargs):
        kwargs["headers"] = {**SSE_HEADERS, **kwargs.get("headers", {})}
        super().__init__(*args, **kwargs)


@app.get("/room/{room_name}", response_class=HTMLResponse)
async def root(request: Request, room_name: str, board: BoardDep):
    return templates.TemplateResponse(
        request, "index.html", {"board": board, "room_name": room_name}
    )


class HoverPos(BaseModel):
    pos: Position
    session: str


@app.get("/room/{room_name}/stream")
async def stream(request: Request, room_name: str, session_id: SessionDep):

    async def gen():
        state = await kv.get(f"{room_name}.state")
        board = pickle.loads(state.value)
        watcher = await kv.watch(f"{room_name}.*")
        hover = None
        while True:
            try:
                update = await watcher.updates(timeout=1)
            except nats.errors.TimeoutError:
                yield ServerSentEventGenerator.merge_fragments(
                    [f'<span id="time">{int(board.play_duration)}</span>']
                )
                continue

            if not update:
                pass
            elif update.key.endswith(".state"):
                board = pickle.loads(update.value)
            else:
                new_hover = HoverPos.model_validate_json(update.value)
                if new_hover.session != session_id:
                    hover = new_hover
                else:
                    continue
            yield ServerSentEventGenerator.merge_fragments(
                [
                    render_block(
                        templates.env,
                        "index.html",
                        "main",
                        {"board": board, "room_name": room_name, "hover": hover},
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


@app.get("/room/{room_name}/mouseover")
async def on_mouseover(
    room_name: str, pos: PositionDep, session_id: SessionDep
):
    await kv.put(
        f"{room_name}.mouse",
        HoverPos(pos=pos, session=session_id).model_dump_json().encode(),
    )
    return Response(status_code=204)


if __name__ == "__main__":
    uvicorn.run("undetermined.web_client:app", host="0.0.0.0", port=8000, reload=True)
