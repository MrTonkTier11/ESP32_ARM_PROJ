"""main.py - Entry point for Robotic Arm Desktop GUI."""
import sys
from pathlib import Path

# Ensure nested robotic_arm directory is in sys.path
pkg_dir = Path(__file__).resolve().parent / "robotic_arm" / "robotic_arm"
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

import tkinter as tk
from robotic_arm_app import RoboticArmApp


def main():
    root = tk.Tk()
    RoboticArmApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
