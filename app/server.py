from __future__ import annotations

from pathlib import Path

import gradio as gr
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import app as fastapi_app


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend" / "static"


@fastapi_app.get("/game", include_in_schema=False)
async def game_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


fastapi_app.mount(
    "/game-static",
    StaticFiles(directory=FRONTEND_DIR),
    name="game-static",
)


def _gradio_shell() -> gr.Blocks:
    # Gradio is the required host for the hackathon. The actual game remains a
    # full custom Phaser app in an iframe so we keep keyboard/canvas control.
    with gr.Blocks(title="Secret Student") as demo:
        gr.HTML(
            """
            <iframe
              title="Secret Student game"
              src="/game"
              style="width:100%;height:min(92vh,900px);border:0;border-radius:8px;background:#111827;"
              allow="camera; microphone; clipboard-read; clipboard-write"
            ></iframe>
            """
        )
    return demo


app = gr.mount_gradio_app(fastapi_app, _gradio_shell(), path="/")


@fastapi_app.get("/embed-health", include_in_schema=False)
async def embed_health() -> HTMLResponse:
    return HTMLResponse("ok")
