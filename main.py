import os
import config

clear = lambda: os.system('cls')

class MonopolyApp():
    """Overseeing class of the programm.
    
    Handles UI elements and all other classes."""

    def __init__(self):
        """Initiates the app and UI elements."""
        self.Monop = Monopoly()

    def main_menu(self):
        """Contains main menu to one method."""
        clear()
        print("-- Welcome to Monopoly add-on -- ")
        print("(1) Start new game")
        print("(2) Load game")
        inp = input("Input: ")
        
        return inp

    def new_game(self):
        self.create_players()
        self.start_game()
        pass

    def load_game(self):
        pass

    def create_players(self):
        print("")
        clear()
        inp = ""
        while True:
            inp = input("Add player (enter 'q' to stop): ")
            if inp == "q":
                break
            else:
                name = inp.capitalize()
                if self.Monop.create_player(name):
                    print(f"Succesfully added {name} as a player.")
                else:
                    print(f"Unable to create player.")

    def start_game(self):
        pass



class Monopoly():
    def __init__(self):
        self.players = []
        self.names = []

    def create_player(self, name):
        if name in self.names:
            return False
        else:
            self.players.append(Player(name))
            self.names.append(name)
            return True


class Player():
    
    def __init__(self, name):
        self.name = name
        self.balance = config.settings["player"]["start_balance"]
        self.streets = []

    def get_name(self):
        return self.name
    
    def get_balance(self):
        return self.balance

if __name__ == "__main__":
    app = MonopolyApp()
    usr_inp = app.main_menu()

    if usr_inp == "1":
        app.new_game()
    elif usr_inp =="2":
        app.load_game()
