"""Tests for the game rules in game.py."""
import pytest

from game import FLEET, Game, GameError, random_fleet


def two_player_game():
    game = Game("TEST")
    p1 = game.add_player("Ana")
    p2 = game.add_player("Ben")
    return game, p1, p2


def row_fleet():
    """Every ship laid horizontally on its own row, starting at column 0."""
    return [{"name": name, "row": i, "col": 0, "horizontal": True} for i, (name, _) in enumerate(FLEET)]


def test_random_fleet_is_always_valid():
    for _ in range(50):
        ships = Game._validate(random_fleet())
        assert len(ships) == len(FLEET)


def test_overlapping_ships_are_rejected():
    game, p1, _ = two_player_game()
    fleet = row_fleet()
    fleet[1]["row"] = 0  # Battleship now sits on top of the Carrier
    with pytest.raises(GameError, match="overlaps"):
        game.place_ships(p1.token, fleet)


def test_ship_off_the_board_is_rejected():
    game, p1, _ = two_player_game()
    fleet = row_fleet()
    fleet[0]["col"] = 8  # a size-5 Carrier starting at column 9 runs off the edge
    with pytest.raises(GameError, match="off the board"):
        game.place_ships(p1.token, fleet)


def test_players_must_take_turns():
    game, p1, p2 = two_player_game()
    game.place_ships(p1.token, row_fleet())
    game.place_ships(p2.token, row_fleet())
    game.fire(p1.token, 9, 9)
    with pytest.raises(GameError, match="Wait for your turn"):
        game.fire(p1.token, 9, 8)


def test_opponent_ships_stay_hidden():
    game, p1, p2 = two_player_game()
    game.place_ships(p1.token, row_fleet())
    game.place_ships(p2.token, row_fleet())
    target = game.state_for(p1.token)["target_board"]
    assert all(cell == "empty" for row in target for cell in row)


def test_sinking_every_ship_wins_the_game():
    game, p1, p2 = two_player_game()
    game.place_ships(p1.token, row_fleet())
    game.place_ships(p2.token, row_fleet())
    misses = iter((r, c) for r in range(5, 10) for c in range(10))  # empty water
    for i, (_, size) in enumerate(FLEET):
        for col in range(size):
            game.fire(p1.token, i, col)
            if game.phase == "playing":
                game.fire(p2.token, *next(misses))
    assert game.phase == "over"
    assert game.state_for(p1.token)["winner"] == "you"
    assert game.state_for(p2.token)["winner"] == "opponent"
