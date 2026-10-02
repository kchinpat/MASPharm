import tkinter.ttk as ttk

BG = "#f3f4f6"
CARD = "#ffffff"
BORDER = "#d1d5db"
PHOTO_BG = "#f9fafb"
TEXT = "#111827"
MUTED = "#6b7280"
ACCENT = "#2563eb"
ACCENT_DARK = "#1d4ed8"
DANGER = "#dc2626"
DANGER_LIGHT = "#fef2f2"

FAMILY = "Helvetica"
TITLE = (FAMILY, 26, "bold")
HEADING = (FAMILY, 16, "bold")
BODY = (FAMILY, 13)
BODY_BOLD = (FAMILY, 13, "bold")
SMALL = (FAMILY, 11)
INPUT = (FAMILY, 16)


def apply_theme(window):
    window.configure(bg=BG)
    style = ttk.Style(window)
    # "clam" is used because the default macOS theme ignores button colors
    style.theme_use("clam")

    style.configure("TButton", font=BODY, padding=(14, 8), borderwidth=1)
    style.configure("TEntry", padding=6, fieldbackground=CARD, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)

    style.configure("Primary.TButton", background=ACCENT, foreground="white",
                    bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT, focuscolor=ACCENT)
    style.map("Primary.TButton",
              background=[("disabled", BORDER), ("active", ACCENT_DARK)],
              lightcolor=[("disabled", BORDER), ("active", ACCENT_DARK)],
              darkcolor=[("disabled", BORDER), ("active", ACCENT_DARK)],
              bordercolor=[("disabled", BORDER)],
              foreground=[("disabled", "white")])

    style.configure("Secondary.TButton", background=CARD, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, focuscolor=CARD)
    style.map("Secondary.TButton",
              background=[("active", PHOTO_BG)],
              lightcolor=[("active", PHOTO_BG)],
              darkcolor=[("active", PHOTO_BG)])

    style.configure("Danger.TButton", background=CARD, foreground=DANGER,
                    bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, focuscolor=CARD)
    style.map("Danger.TButton",
              background=[("active", DANGER_LIGHT)],
              lightcolor=[("active", DANGER_LIGHT)],
              darkcolor=[("active", DANGER_LIGHT)],
              foreground=[("disabled", BORDER)])
