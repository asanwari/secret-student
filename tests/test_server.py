from fastapi.testclient import TestClient

from app.server import app


def test_game_routes_force_browser_cache_revalidation():
    with TestClient(app) as client:
        game = client.get("/game")
        world = client.get("/game-static/src/world.js")

    assert game.status_code == 200
    assert game.headers["cache-control"] == "no-store"
    assert world.status_code == 200
    assert world.headers["cache-control"] == "no-cache, max-age=0, must-revalidate"


def test_gradio_shell_versions_the_embedded_game_url():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "/game?v=20260615-2" in response.text
