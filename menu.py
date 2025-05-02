import os

clear = lambda: os.system('cls')

def main_menu():
    clear()
    print("-- Välkommen till Monopol tillägg -- ")
    print("(1) Starta nytt spel")
    print("(2) Ladda tidigare spel")
    inp = ("Input: ")
    return inp

def add_player():
    clear()
    player_name = input("Lägg till spelare: ")
    return player_name