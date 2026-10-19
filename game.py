"""Battleship rules and in-memory game storage.

This file knows nothing about Flask or the web. app.py calls these
classes, and the browser only ever sees what state_for() returns.
"""
import random
import secrets
import threading

SIZE = 10
FLEET = [
    ("Carrier", 5),
    ("Battleship", 4),
    ("Cruiser", 3),
    ("Submarine", 3),
    ("Destroyer", 2),
]
FLEET_SIZES = dict(FLEET)
ROW_LABELS = "ABCDEFGHIJ"
CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I or O, they look like 1 and 0


class GameError(Exception):
    """A problem caused by the player. The message is safe to show them."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def label(row, col):
    return f"{ROW_LABELS[row]}{col + 1}"


def in_bounds(row, col):
    return 0 <= row < SIZE and 0 <= col < SIZE


def ship_cells(row, col, size, horizontal):
    if horizontal:
        return [(row, col + i) for i in range(size)]
    return [(row + i, col) for i in range(size)]


def random_fleet():
    """Return a valid random placement in the same format the browser sends."""
    taken = set()
    placement = []
    for name, size in FLEET:
        while True:
            horizontal = random.choice([True, False])
            row, col = random.randrange(SIZE), random.randrange(SIZE)
            cells = ship_cells(row, col, size, horizontal)
            if all(in_bounds(r, c) and (r, c) not in taken for r, c in cells):
                taken.update(cells)
                placement.append({"name": name, "row": row, "col": col, "horizontal": horizontal})
                break
    return placement


class Player:
    def __init__(self, name):
        self.name = name
        self.token = secrets.token_urlsafe(8)  # secret that identifies this player
        self.ships = {}           # ship name -> set of (row, col)
        self.shots_received = {}  # (row, col) -> "hit" or "miss"

    @property
    def ready(self):
        return bool(self.ships)

    def ship_at(self, row, col):
        for name, cells in self.ships.items():
            if (row, col) in cells:
                return name
        return None

    def is_sunk(self, ship_name):
        return all(cell in self.shots_received for cell in self.ships[ship_name])

    def sunk_ships(self):
        return [name for name in self.ships if self.is_sunk(name)]

    def all_sunk(self):
        return self.ready and len(self.sunk_ships()) == len(self.ships)


class Game:
    def __init__(self, code):
        self.code = code
        self.players = []
        self.turn = 0          # index of the player whose turn it is
        self.winner = None     # index of the winner once the game ends
        self.last_event = "Waiting for a second player to join."
        self.lock = threading.Lock()  # two browsers can hit the server at once

    @property
    def phase(self):
        if self.winner is not None:
            return "over"
        if len(self.players) < 2:
            return "waiting"
        if not all(p.ready for p in self.players):
            return "placing"
        return "playing"

    def _index(self, token):
        for i, player in enumerate(self.players):
            if secrets.compare_digest(player.token, str(token)):
                return i
        raise GameError("This game link is not valid. Check the address or start a new game.", 404)

    def add_player(self, name):
        with self.lock:
            if len(self.players) >= 2:
                raise GameError("That game already has two players. Start your own game instead.", 409)
            player = Player(name)
            self.players.append(player)
            if len(self.players) == 2:
                self.last_event = f"{name} joined. Both players can place ships now."
            return player

    def place_ships(self, token, placement):
        with self.lock:
            me = self.players[self._index(token)]
            if self.phase not in ("waiting", "placing"):
                raise GameError("Ships can only be placed before the battle starts.")
            if me.ready:
                raise GameError("Your ships are already placed.")
            me.ships = self._validate(placement)
            if self.phase == "playing":
                self.last_event = f"Both fleets are ready. {self.players[0].name} fires first."
            else:
                self.last_event = f"{me.name} has placed their ships."

    @staticmethod
    def _validate(placement):
        if not isinstance(placement, list):
            raise GameError("Ship placement must be a list of ships.")
        ships, taken = {}, set()
        for item in placement:
            if not isinstance(item, dict):
                raise GameError("Each ship needs a name, row, column and direction.")
            name = item.get("name")
            row, col, horizontal = item.get("row"), item.get("col"), item.get("horizontal")
            if name not in FLEET_SIZES:
                raise GameError(f"Unknown ship: {name}.")
            if name in ships:
                raise GameError(f"The {name} was placed twice.")
            if type(row) is not int or type(col) is not int or type(horizontal) is not bool:
                raise GameError(f"The {name} has an invalid position.")
            cells = ship_cells(row, col, FLEET_SIZES[name], horizontal)
            if not all(in_bounds(r, c) for r, c in cells):
                raise GameError(f"The {name} goes off the board.")
            if any(cell in taken for cell in cells):
                raise GameError(f"The {name} overlaps another ship.")
            taken.update(cells)
            ships[name] = set(cells)
        missing = [name for name, _ in FLEET if name not in ships]
        if missing:
            raise GameError("Place every ship first. Missing: " + ", ".join(missing) + ".")
        return ships

    def fire(self, token, row, col):
        with self.lock:
            i = self._index(token)
            me, them = self.players[i], self.players[1 - i] if len(self.players) == 2 else None
            if self.phase != "playing":
                raise GameError("The battle has not started yet." if self.winner is None else "The game is over.")
            if i != self.turn:
                raise GameError("Wait for your turn.")
            if type(row) is not int or type(col) is not int or not in_bounds(row, col):
                raise GameError("That square is not on the board.")
            if (row, col) in them.shots_received:
                raise GameError(f"You already fired at {label(row, col)}.")

            ship = them.ship_at(row, col)
            result = "hit" if ship else "miss"
            them.shots_received[(row, col)] = result
            sunk = ship if ship and them.is_sunk(ship) else None

            event = f"{me.name} fired at {label(row, col)} and it was a {result}."
            if sunk:
                event += f" {them.name}'s {sunk} sank."
            if them.all_sunk():
                self.winner = i
                event += f" {me.name} wins!"
            else:
                self.turn = 1 - i
            self.last_event = event
            return {"result": result, "sunk": sunk}

    def state_for(self, token):
        """Everything one player is allowed to see. Opponent ships stay hidden."""
        with self.lock:
            i = self._index(token)
            me = self.players[i]
            them = self.players[1 - i] if len(self.players) == 2 else None
            phase = self.phase
            return {
                "code": self.code,
                "phase": phase,
                "you": {"name": me.name, "ready": me.ready},
                "opponent": {"name": them.name, "ready": them.ready} if them else None,
                "your_turn": phase == "playing" and self.turn == i,
                "winner": None if self.winner is None else ("you" if self.winner == i else "opponent"),
                "my_board": self._own_view(me),
                "target_board": self._target_view(them, reveal=(phase == "over")),
                "my_sunk": me.sunk_ships(),
                "opponent_sunk": them.sunk_ships() if them else [],
                "fleet": [{"name": n, "size": s} for n, s in FLEET],
                "last_event": self.last_event,
            }

    @staticmethod
    def _own_view(player):
        grid = [["empty"] * SIZE for _ in range(SIZE)]
        for name, cells in player.ships.items():
            sunk = player.is_sunk(name)
            for r, c in cells:
                grid[r][c] = "sunk" if sunk else "ship"
        for (r, c), result in player.shots_received.items():
            if grid[r][c] != "sunk":
                grid[r][c] = result
        return grid

    @staticmethod
    def _target_view(player, reveal):
        grid = [["empty"] * SIZE for _ in range(SIZE)]
        if player is None:
            return grid
        for (r, c), result in player.shots_received.items():
            grid[r][c] = result
        for name, cells in player.ships.items():
            if player.is_sunk(name):
                for r, c in cells:
                    grid[r][c] = "sunk"
            elif reveal:  # after the game, show where the surviving ships were
                for r, c in cells:
                    if grid[r][c] == "empty":
                        grid[r][c] = "ship"
        return grid


class GameStore:
    """All games live in this dictionary, so they disappear when the server restarts."""

    def __init__(self):
        self.games = {}
        self.lock = threading.Lock()

    def create(self):
        with self.lock:
            while True:
                code = "".join(random.choice(CODE_LETTERS) for _ in range(4))
                if code not in self.games:
                    break
            game = Game(code)
            self.games[code] = game
            return game

    def get(self, code):
        code = (code or "").strip().upper()
        if not code:
            raise GameError("Enter a game code to join.")
        game = self.games.get(code)
        if game is None:
            raise GameError(f"There is no game with code {code}. Check the code with your opponent.", 404)
        return game
