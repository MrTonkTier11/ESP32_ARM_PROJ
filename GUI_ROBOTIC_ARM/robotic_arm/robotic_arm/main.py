"""main.py - entry point.  Run:  python main.py"""

import tkinter as tk
from robotic_arm_app import RoboticArmApp


def main():
    root = tk.Tk()
    RoboticArmApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
