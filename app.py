"""Flask routes for Battleship. Game rules live in game.py."""
from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException

from game import GameError, GameStore, random_fleet

app = Flask(__name__)
store = GameStore()


def clean_name(raw, fallback):
    name = (raw or "").strip()[:20]
    return name or fallback


# ---------- Pages ----------

@app.get("/")
def index():
    return render_template("index.html")


@app.post("/new")
def new_game():
    game = store.create()
    player = game.add_player(clean_name(request.form.get("name"), "Player 1"))
    return redirect(url_for("play", code=game.code, token=player.token))


@app.post("/join")
def join_game():
    code = request.form.get("code", "")
    name = clean_name(request.form.get("name"), "Player 2")
    try:
        game = store.get(code)
        player = game.add_player(name)
    except GameError as e:
        return render_template("index.html", error=e.message, code=code, name=name), e.status
    return redirect(url_for("play", code=game.code, token=player.token))


@app.get("/game/<code>/<token>")
def play(code, token):
    game = store.get(code)
    game.state_for(token)  # raises a friendly error if the link is wrong
    return render_template("game.html", code=game.code, token=token)


@app.get("/rules")
def rules():
    return render_template("rules.html")


# ---------- JSON API used by static/game.js ----------

@app.get("/api/game/<code>/<token>/state")
def api_state(code, token):
    return jsonify(store.get(code).state_for(token))


@app.post("/api/game/<code>/<token>/place")
def api_place(code, token):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "ships" not in data:
        raise GameError("Send the ship placement as JSON.")
    store.get(code).place_ships(token, data["ships"])
    return jsonify(ok=True)


@app.post("/api/game/<code>/<token>/fire")
def api_fire(code, token):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise GameError("Send the target square as JSON.")
    return jsonify(store.get(code).fire(token, data.get("row"), data.get("col")))


@app.get("/api/random-fleet")
def api_random_fleet():
    return jsonify(ships=random_fleet())


if __name__ == "__main__":
    app.run(debug=True)
