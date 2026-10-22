# Battleship

A two-player Battleship game built with Flask. One player starts a game and gets a four-letter code, the other joins with that code, both hide their fleets, and they take turns firing until one fleet is sunk. The server runs the game and only ever sends each player their own ships, so nobody can peek at the other board.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app app run --debug --port 5001
```

Open http://127.0.0.1:5001 and click **Start game**. To play against yourself, open a second window, go to the same address, and join with the code. Each player's seat is the secret part of their game URL, so two tabs in the same browser work fine.

To play from phones on the same Wi-Fi, run `flask --app app run --host=0.0.0.0 --port 5001` and open `http://<your laptop's IP>:5001` on the phones.

## How it works

- **Server, `game.py`:** holds every game in a Python dictionary, enforces the rules such as valid placement, turn order, no repeated shots and sinking, and builds a separate view for each player that hides the opponent's ships.
- **Server, `app.py`:** Flask routes. Pages for the start screen, rules and game, plus a small JSON API the game page calls: `state`, `place`, `fire` and `random-fleet`.
- **Browser, `static/game.js`:** asks the server for the latest state every second, draws both boards, and sends ship placements and shots back with `fetch`.

Errors such as a wrong game code, a full game, an invalid shot or a lost connection show a plain message instead of a traceback. Games live in memory, so restarting the server clears them.
