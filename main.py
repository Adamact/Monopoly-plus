"""Entry point for Monopoly Plus GUI."""
import ctypes
import sys

from gui import start_gui

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

if __name__ == "__main__":
    start_gui()
