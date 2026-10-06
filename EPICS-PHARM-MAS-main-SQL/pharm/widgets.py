"""Composite Tk widgets for the desktop cabinet, built on UI/theme.py."""
import base64
import struct
import tkinter as tk
from tkinter import ttk
import zlib

from UI import theme as T


def label(parent, text="", font="body", fg=T.TEXT, bg=T.SURFACE, **options):
    theme = T.apply_theme(parent)
    options.setdefault("anchor", "w")
    options.setdefault("justify", "left")
    return tk.Label(parent, text=text, font=theme.font(font), fg=fg, bg=bg, **options)


def divider(parent, color=T.BORDER):
    return tk.Frame(parent, height=1, bg=color)


def icon_png(size, layers):
    """Encode antialiased layers as a transparent PNG PhotoImage (window icons)."""
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            r = g = b = a = 0.0
            for coverage, color in layers:
                alpha = coverage(x + 0.5, y + 0.5)
                if alpha <= 0:
                    continue
                cr, cg, cb = (int(color[i:i + 2], 16) for i in (1, 3, 5))
                out = alpha + a * (1 - alpha)
                r = (cr * alpha + r * a * (1 - alpha)) / out
                g = (cg * alpha + g * a * (1 - alpha)) / out
                b = (cb * alpha + b * a * (1 - alpha)) / out
                a = out
            row += bytes((round(r), round(g), round(b), round(a * 255)))
        rows.append(bytes(row))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))
    return tk.PhotoImage(data=base64.b64encode(png))


def set_window_icon(root):
    """Replace the Tk feather with the cabinet mark, keeping transparent corners."""
    theme = T.apply_theme(root)
    icons = []
    for size in (16, 32, 48, 64):
        layers = [(T.rounded((0, 0, size, size), size * 0.24), T.ACCENT)]
        pad, gap = size * 0.2, size * 0.06
        height = (size - 2 * pad - 3 * gap) / 4
        for index in range(4):
            y0 = pad + index * (height + gap)
            layers.append((T.rounded((pad, y0, size - pad, y0 + height), size * 0.04), "#ffffff"))
        icons.append(icon_png(size, layers))
    theme.images["window-icons"] = icons
    root.iconphoto(True, *reversed(icons))


class ScrollFrame(tk.Frame):
    """Vertical scroll area for `.body`.

    The body fills the viewport width and is at least the viewport height, so
    cards can stretch on large windows and scroll on small ones. Its height is
    never pinned: the minimum comes from a grid row minsize, so content changes
    always re-measure. The scrollbar gutter is reserved, which avoids the
    reflow loop that auto-hiding scrollbars cause."""

    def __init__(self, parent, bg=T.SURFACE):
        super().__init__(parent, bg=bg)
        theme = T.apply_theme(self)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, yscrollincrement=theme.px(24))
        self.bar = ttk.Scrollbar(self, orient="vertical", style=theme.scrollbar_style(bg), command=self.canvas.yview)
        self.viewport = tk.Frame(self.canvas, bg=bg)
        self.viewport.columnconfigure(0, weight=1)
        self.viewport.rowconfigure(0, weight=1)
        self.body = tk.Frame(self.viewport, bg=bg)
        self.body.grid(row=0, column=0, sticky="nsew")
        self.window = self.canvas.create_window(0, 0, window=self.viewport, anchor="nw")
        self.canvas.configure(yscrollcommand=self._scrolled)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.bar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, minsize=theme.px(12))
        self.rowconfigure(0, weight=1)
        self.viewport.bind("<Configure>", self._measure)
        self.canvas.bind("<Configure>", self._resize)
        root = self.nametowidget(".")
        if not getattr(root, "pharm_wheel", False):
            root.pharm_wheel = True
            root.bind_all("<MouseWheel>", _wheel, add="+")
            root.bind_all("<Button-4>", _wheel, add="+")
            root.bind_all("<Button-5>", _wheel, add="+")

    def _resize(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        self.viewport.rowconfigure(0, minsize=event.height)

    def _measure(self, event):
        self.canvas.configure(scrollregion=(0, 0, event.width, event.height))

    def _scrolled(self, first, last):
        if float(first) <= 0 and float(last) >= 1:
            self.bar.grid_remove()
        else:
            self.bar.grid()
        self.bar.set(first, last)

    def scroll(self, steps):
        if self.bar.winfo_ismapped():
            self.canvas.yview_scroll(steps, "units")

    def top(self):
        self.canvas.yview_moveto(0)


def _wheel(event):
    try:
        widget = event.widget.winfo_containing(event.x_root, event.y_root)
    except (AttributeError, KeyError, tk.TclError):
        return
    while widget is not None and not isinstance(widget, ScrollFrame):
        widget = widget.master
    if widget is not None:
        steps = -3 if getattr(event, "num", None) == 4 else 3 if getattr(event, "num", None) == 5 else -round(event.delta / 40)
        widget.scroll(steps)


class Splash(tk.Frame):
    """Shown while the package catalog loads, so launch never looks frozen."""

    def __init__(self, root):
        super().__init__(root, bg=T.SHELL)
        theme = T.apply_theme(root)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        center = tk.Frame(self, bg=T.SHELL)
        center.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(center, image=theme.logo(theme.px(64), T.SHELL), bg=T.SHELL).pack()
        label(center, "Pharmacy Drawer", "display", T.SHELL_TEXT, T.SHELL, anchor="center").pack(pady=(theme.px(18), 0))
        label(center, "Loading...", "body", T.SHELL_MUTED, T.SHELL, anchor="center").pack(pady=(theme.px(4), 0))
