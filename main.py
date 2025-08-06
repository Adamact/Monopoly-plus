import os

clear = lambda: os.system('cls')

class MonopolyApp():
    """Overseeing class of the programm."""

    def __init__(self):
        self.Monop = Monopoly()

    def main_menu(self):
        clear()
        print("-- Welcome to Monopoly add-on -- ")
        print("(1) Start new game")
        print("(2) Load game")
        inp = input("Input: ")
        
        return inp

    def new_game(self):
        self.create_players()
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
                    print(f"Unable to create.")



class Monopoly():
    def __init__(self):
        self.players = []

    def create_player(self, name="Test"):
        self.players.append(Player(name))
        return True


class Player():
    
    def __init__(self, name):
        self.name = name

if __name__ == "__main__":
    app = MonopolyApp()
    usr_inp = app.main_menu()

    if usr_inp == "1":
        app.new_game()
    elif usr_inp =="2":
        app.load_game()
