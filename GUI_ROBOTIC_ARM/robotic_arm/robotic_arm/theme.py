"""theme.py - colors, constants and ttk styling (no classes)."""

from tkinter import ttk

BG_DARK = "#0d111a"
CARD_BG = "#161d2d"
CARD_BORDER = "#25324d"
ACCENT_CYAN = "#00d9ff"
ACCENT_BLUE = "#2979ff"
COLOR_GREEN = "#00e676"
COLOR_RED = "#ff3d71"
COLOR_ORANGE = "#ff9100"
COLOR_YELLOW = "#ffd54f"
TEXT_WHITE = "#ffffff"
TEXT_MUTED = "#8ea1c0"
SLIDER_TROUGH = "#0a0e16"

# Fixed ESP32 access-point address (not editable in the GUI)
ESP32_AP_IP = "192.168.4.1"


def setup_styles():
    style = ttk.Style()
    style.theme_use("clam")

    style.configure("TFrame", background=BG_DARK)
    style.configure("Card.TFrame", background=CARD_BG, relief="solid", borderwidth=1)
    style.configure("TLabel", background=BG_DARK, foreground=TEXT_WHITE, font=("Segoe UI", 10))
    style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT_WHITE, font=("Segoe UI", 10))

    style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=5, background=CARD_BORDER, foreground=TEXT_WHITE)
    style.map("TButton", background=[("active", ACCENT_CYAN)], foreground=[("active", "#000000")])

    style.configure("TRadiobutton", background=CARD_BG, foreground=TEXT_WHITE, font=("Segoe UI", 9, "bold"))
    style.map("TRadiobutton", background=[("active", CARD_BG)])
