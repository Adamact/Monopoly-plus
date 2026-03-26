from flask import Flask, render_template, request, jsonify, session
import random
import config
import player_settings as psettings
from location_data import location

app = Flask(__name__)
app.secret_key = "monopoly-plus-secret-key"

# In-memory game store (keyed by session)
games = {}


class Player:
    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.balance = psettings.settings["player"]["start_balance"]
        self.position = 0
        self.streets = []
        self.in_jail = False
        self.jail_turns = 0

    def to_dict(self):
        return {
            "name": self.name,
            "color": self.color,
            "balance": self.balance,
            "position": self.position,
            "streets": self.streets,
            "in_jail": self.in_jail,
        }


class Game:
    PLAYER_COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]

    def __init__(self):
        self.players = []
        self.names = []
        self.current_turn = 0
        self.started = False
        self.log = []

    def add_player(self, name):
        if name in self.names or len(self.players) >= 6:
            return False
        color = self.PLAYER_COLORS[len(self.players)]
        self.players.append(Player(name, color))
        self.names.append(name)
        return True

    def current_player(self):
        if not self.players:
            return None
        return self.players[self.current_turn % len(self.players)]

    def roll_dice(self):
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        return d1, d2

    def get_location_info(self, position):
        loc = location[position]
        loc_type = list(loc.keys())[0]
        loc_value = loc[loc_type]
        return loc_type, loc_value

    def get_property_info(self, loc_type, loc_value):
        if loc_type in config.streets and loc_value in config.streets[loc_type]:
            return config.streets[loc_type][loc_value]
        return None

    def move_player(self):
        player = self.current_player()
        if player.in_jail:
            d1, d2 = self.roll_dice()
            if d1 == d2:
                player.in_jail = False
                player.jail_turns = 0
                self.log.append(f"{player.name} rolled doubles ({d1}+{d2}) and escaped jail!")
                new_pos = (player.position + d1 + d2) % 40
                player.position = new_pos
            else:
                player.jail_turns += 1
                if player.jail_turns >= 3:
                    player.in_jail = False
                    player.jail_turns = 0
                    player.balance -= 1000
                    self.log.append(f"{player.name} paid 1000kr to leave jail after 3 turns.")
                    new_pos = (player.position + d1 + d2) % 40
                    player.position = new_pos
                else:
                    self.log.append(f"{player.name} rolled {d1}+{d2} (no doubles) - still in jail.")
                    self.next_turn()
                    return d1, d2, player.to_dict()
        else:
            d1, d2 = self.roll_dice()
            old_pos = player.position
            new_pos = (old_pos + d1 + d2) % 40
            if new_pos < old_pos:
                player.balance += 4000
                self.log.append(f"{player.name} passed Start and collected 4000kr!")
            player.position = new_pos

        loc_type, loc_value = self.get_location_info(player.position)
        self.log.append(f"{player.name} rolled {d1}+{d2} and landed on {loc_value} (pos {player.position}).")

        # Handle special locations
        if loc_type == "Skatt":
            tax = loc_value
            player.balance -= tax
            self.log.append(f"{player.name} paid {tax}kr in tax.")
        elif loc_type == "Fängelse" and loc_value == "Fängelse":
            player.in_jail = True
            player.position = 10
            self.log.append(f"{player.name} went to jail!")

        self.next_turn()
        return d1, d2, player.to_dict()

    def buy_property(self, player_index):
        player = self.players[player_index]
        loc_type, loc_value = self.get_location_info(player.position)
        prop_info = self.get_property_info(loc_type, loc_value)
        if prop_info is None:
            return False, "Not a buyable property."
        price = prop_info["Pris"]
        # Check if already owned
        for p in self.players:
            if loc_value in p.streets:
                return False, f"{loc_value} is already owned by {p.name}."
        if player.balance < price:
            return False, "Not enough money."
        player.balance -= price
        player.streets.append(loc_value)
        self.log.append(f"{player.name} bought {loc_value} for {price}kr.")
        return True, f"Bought {loc_value} for {price}kr."

    def next_turn(self):
        self.current_turn = (self.current_turn + 1) % len(self.players)

    def to_dict(self):
        return {
            "players": [p.to_dict() for p in self.players],
            "current_turn": self.current_turn,
            "started": self.started,
            "log": self.log[-15:],
            "board": self.get_board_data(),
        }

    def get_board_data(self):
        board = []
        for pos in range(40):
            loc_type, loc_value = self.get_location_info(pos)
            prop_info = self.get_property_info(loc_type, loc_value)
            owner = None
            for p in self.players:
                if isinstance(loc_value, str) and loc_value in p.streets:
                    owner = p.name
                    break
            entry = {
                "position": pos,
                "type": loc_type,
                "name": loc_value if isinstance(loc_value, str) else loc_type,
                "price": prop_info["Pris"] if prop_info else None,
                "owner": owner,
                "color": self.get_color_hex(loc_type),
            }
            board.append(entry)
        return board

    @staticmethod
    def get_color_hex(loc_type):
        colors = {
            "Brun": "#8B4513",
            "Ljus-Blå": "#87CEEB",
            "Rosa": "#FF69B4",
            "Orange": "#FF8C00",
            "Röd": "#DC143C",
            "Gul": "#FFD700",
            "Grön": "#228B22",
            "Blå": "#0000CD",
            "Station": "#333333",
            "Statligt": "#D3D3D3",
        }
        return colors.get(loc_type, None)


def get_game():
    game_id = session.get("game_id")
    if game_id and game_id in games:
        return games[game_id]
    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/new_game", methods=["POST"])
def new_game():
    game_id = str(random.randint(10000, 99999))
    session["game_id"] = game_id
    games[game_id] = Game()
    return jsonify({"status": "ok", "game_id": game_id})


@app.route("/api/add_player", methods=["POST"])
def add_player():
    game = get_game()
    if not game:
        return jsonify({"status": "error", "message": "No active game."}), 400
    name = request.json.get("name", "").strip().capitalize()
    if not name:
        return jsonify({"status": "error", "message": "Name required."}), 400
    if game.add_player(name):
        return jsonify({"status": "ok", "game": game.to_dict()})
    return jsonify({"status": "error", "message": "Name taken or max players reached."}), 400


@app.route("/api/start_game", methods=["POST"])
def start_game():
    game = get_game()
    if not game:
        return jsonify({"status": "error", "message": "No active game."}), 400
    if len(game.players) < 2:
        return jsonify({"status": "error", "message": "Need at least 2 players."}), 400
    game.started = True
    game.log.append("Game started!")
    return jsonify({"status": "ok", "game": game.to_dict()})


@app.route("/api/roll", methods=["POST"])
def roll():
    game = get_game()
    if not game or not game.started:
        return jsonify({"status": "error", "message": "Game not started."}), 400
    d1, d2, player = game.move_player()
    return jsonify({"status": "ok", "dice": [d1, d2], "player": player, "game": game.to_dict()})


@app.route("/api/buy", methods=["POST"])
def buy():
    game = get_game()
    if not game or not game.started:
        return jsonify({"status": "error", "message": "Game not started."}), 400
    player_index = request.json.get("player_index", 0)
    success, msg = game.buy_property(player_index)
    return jsonify({"status": "ok" if success else "error", "message": msg, "game": game.to_dict()})


@app.route("/api/state", methods=["GET"])
def state():
    game = get_game()
    if not game:
        return jsonify({"status": "error", "message": "No active game."}), 400
    return jsonify({"status": "ok", "game": game.to_dict()})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
