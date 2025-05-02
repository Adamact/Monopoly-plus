"""Main file. Manages players and their interactions"""

import menu # type: ignore

class Player:
    
    def __init__(self, name):
        self._name = name
        self._currency = 0
        self.streets = []
        pass

class MonopolyApp:
    """Manages GUI"""

    def __init__(self):
        self.main()

    def main(self):
        decision = menu.main_menu()

class PlayerHandler:
    """Handles player decision and exchanges. 
    
    Calls other classes to change the dynamic of the game.
    Effects the stockmarket."""

    def __init__(self, players):
        self._players = players

    def add_player(self, player):
        pass

    def remove_player(self, player):
        pass

    def sell_street(self, street, buyer, seller):
        pass

    def buy_street(self, street, buyer, seller):
        pass

    def add_currency(self, amount):
        pass

    def remove_currency(self, amount):
        pass

if __name__ == "__main__":
    monopoly = MonopolyApp()