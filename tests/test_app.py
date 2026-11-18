"""Tests for the Flask routes in app.py."""
import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Start a game" in response.data


def test_starting_a_game_redirects_to_the_board(client):
    response = client.post("/new", data={"name": "Ana"})
    assert response.status_code == 302
    assert "/game/" in response.headers["Location"]


def test_joining_a_missing_game_shows_a_friendly_error(client):
    response = client.post("/join", data={"code": "ZZZZ", "name": "Ben"})
    assert response.status_code == 404
    assert b"There is no game with code ZZZZ" in response.data
    assert b"Traceback" not in response.data


def test_random_fleet_api_returns_five_ships(client):
    response = client.get("/api/random-fleet")
    assert response.status_code == 200
    assert len(response.get_json()["ships"]) == 5
