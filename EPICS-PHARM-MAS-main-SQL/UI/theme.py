"""Design tokens and ttk styles for the desktop cabinet.

The window is a shell, like the cabinet itself, holding the four drawer fronts
and one white work surface. Two shell palettes are available and can be
switched at runtime: light (a cool-tinted shell under a teal header band) and
dark (a graphite shell). In the light shell each drawer front carries a
colored edge for its state: red when empty, blue when it holds medication, and
green while it is open; the dark shell keeps plain fronts with a teal outline
on the selected drawer. Rounded shapes are rasterized at startup with antialiased edges and
registered as nine-slice ttk image elements, so the theme needs no image files
or third-party packages and stays crisp at any display scaling. Colors match
UI/web/cabinet.css.
"""
import math
import tkinter as tk
import tkinter.font as tkfont
import tkinter.ttk as ttk

# Work surface.
SURFACE = "#ffffff"
SUBTLE = "#f6f7f9"
BG = SUBTLE
BORDER = "#e4e7ec"
BORDER_STRONG = "#cfd4dc"
TEXT = "#0f172a"
TEXT_SOFT = "#334155"
MUTED = "#64748b"
FAINT = "#94a3b8"
ACCENT = "#0d9488"
ACCENT_DARK = "#0f766e"
ACCENT_SOFT = "#f0fdfa"
ACCENT_LINE = "#99f6e4"
DANGER = "#dc2626"
DANGER_DARK = "#b91c1c"
DANGER_SOFT = "#fef2f2"
DANGER_LINE = "#fecaca"
WARNING = "#b45309"
WARNING_DARK = "#92400e"
WARNING_SOFT = "#fffbeb"
WARNING_LINE = "#fde68a"

# Status tones: (text, soft background, outline).
TONES = {
    "accent": (ACCENT_DARK, ACCENT_SOFT, ACCENT_LINE),
    "warning": (WARNING_DARK, WARNING_SOFT, WARNING_LINE),
    "danger": (DANGER_DARK, DANGER_SOFT, DANGER_LINE),
}

# Shell palettes. use_palette() copies one into the module globals below, so
# read them as T.SHELL etc. at draw time rather than binding them at import.
#   HEADER*: the band across the top of the window.
#   SHELL*: the body around the work surface; CARD_LINE outlines cards on it.
#   LOGO: (tile, drawers) colors of the brand mark in the header.
#   HEADER_BUTTON: as in _BUTTONS. HEADER_FIELD: the scan entry.
#   SHELL_HOVER, SHELL_SELECTED: plain drawer fronts (no DRAWER_TONES).
#   DRAWER_TONES: (edge and selection outline, soft fill, number text), or
#   None for plain fronts.
PALETTES = {
    "light": dict(
        HEADER="#0f766e", HEADER_TEXT="#ffffff", HEADER_MUTED="#ccfbf1", HEADER_WARNING="#fde68a",
        SHELL="#e8eff7", SHELL_RAISED="#ffffff", SHELL_LINE="#cbd7e4", SHELL_TEXT="#0f172a",
        SHELL_MUTED="#5b6b7f", SHELL_WARNING="#b45309", SHELL_DANGER="#dc2626", CARD_LINE="#cbd7e4",
        SHELL_HOVER="#f4f8fc", SHELL_SELECTED="#ffffff",
        LOGO=("#ffffff", ACCENT),
        HEADER_BUTTON=("#ffffff", ACCENT_DARK, None, ACCENT_SOFT, "#ccfbf1", "#4f9e97", "#d1e7e5", None),
        HEADER_FIELD=dict(fill=SURFACE, outline=SURFACE, text=TEXT, ring="#5eead4", hover=ACCENT_LINE,
                          placeholder=MUTED),
        DRAWER_TONES={
            "empty": ("#dc2626", "#fef2f2", "#b91c1c"),
            "stocked": ("#2563eb", "#eff6ff", "#1d4ed8"),
            "open": ("#16a34a", "#f0fdf4", "#15803d"),
        }),
    "dark": dict(
        HEADER="#161c26", HEADER_TEXT="#f1f5f9", HEADER_MUTED="#99f6e4", HEADER_WARNING="#fbbf24",
        SHELL="#161c26", SHELL_RAISED="#222a37", SHELL_LINE="#364152", SHELL_TEXT="#f1f5f9",
        SHELL_MUTED="#8b98aa", SHELL_WARNING="#fbbf24", SHELL_DANGER="#f87171", CARD_LINE=None,
        SHELL_HOVER="#29323f", SHELL_SELECTED="#25313f",
        LOGO=(ACCENT, "#ffffff"),
        HEADER_BUTTON=("#222a37", "#f1f5f9", "#364152", "#29323f", "#323d4f", "#222a37", "#8b98aa", "#364152"),
        HEADER_FIELD=dict(fill="#222a37", outline="#364152", text="#f1f5f9", ring="#134e4a", hover="#8b98aa",
                          placeholder="#8b98aa"),
        DRAWER_TONES=None),
}
PALETTE = "light"


def use_palette(name):
    """Switch the shell palette. Widgets already drawn keep their colors, so
    callers rebuild the window afterwards; ttk style names that depend on the
    palette include its name, so both palettes' styles can coexist."""
    global PALETTE
    if name not in PALETTES:
        raise ValueError(f"Unknown palette: {name}")
    PALETTE = name
    globals().update(PALETTES[name])


use_palette(PALETTE)

_UI_FAMILIES = ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter", "Noto Sans", "Cantarell", "DejaVu Sans")
_MONO_FAMILIES = ("Consolas", "Cascadia Mono", "SF Mono", "Menlo", "Noto Sans Mono", "DejaVu Sans Mono")

# Point sizes; Tk converts them using the display's real DPI.
_FONTS = {
    "display": ("strong", 24), "title": ("strong", 18), "prompt": ("strong", 17), "heading": ("strong", 14),
    "body": ("ui", 12), "strong": ("strong", 12), "small": ("ui", 11), "caption": ("strong", 10),
    "metric": ("strong", 32), "number": ("strong", 26), "button": ("strong", 12), "button_lg": ("strong", 14),
    "link": ("strong", 12), "input": ("ui", 13), "mono": ("mono", 12), "scan": ("mono", 15),
}

_BUTTONS = {
    # fill, text, outline, hover, pressed, disabled fill, disabled text, disabled outline
    "Primary": (ACCENT, "#ffffff", None, ACCENT_DARK, "#115e59", "#9fd6d0", "#ffffff", None),
    "Secondary": (SURFACE, TEXT, BORDER_STRONG, SUBTLE, BORDER, SUBTLE, FAINT, BORDER),
    "Danger": (DANGER, "#ffffff", None, DANGER_DARK, "#991b1b", "#f3b2b2", "#ffffff", None),
    "Warning": (WARNING, "#ffffff", None, WARNING_DARK, "#78350f", "#e5b98f", "#ffffff", None),
    "Ghost": (None, ACCENT_DARK, None, ACCENT_SOFT, "#ccfbf1", None, FAINT, None),
}

_UNDER_NAMES = {SURFACE: "", SUBTLE: "OnSubtle", WARNING_SOFT: "OnWarning", DANGER_SOFT: "OnDanger",
                ACCENT_SOFT: "OnAccent"}


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _suffix(under):
    if under == SHELL:
        return "OnShell" + PALETTE.title()
    if under == HEADER:
        return "OnHeader" + PALETTE.title()
    return _UNDER_NAMES.get(under, "On" + under[1:])


def _distance(box, radius):
    """Signed distance to a rounded rectangle (negative inside)."""
    x0, y0, x1, y1 = box
    hw, hh = (x1 - x0) / 2, (y1 - y0) / 2
    cx, cy = x0 + hw, y0 + hh
    radius = min(radius, hw, hh)

    def distance(x, y):
        qx = abs(x - cx) - hw + radius
        qy = abs(y - cy) - hh + radius
        return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - radius
    return distance


def rounded(box, radius):
    """Antialiased coverage of a rounded rectangle."""
    distance = _distance(box, radius)
    return lambda x, y: min(1.0, max(0.0, 0.5 - distance(x, y)))


def _stroke(points, width):
    """Coverage of a polyline with round caps (used for check marks)."""
    segments = list(zip(points, points[1:]))

    def coverage(x, y):
        best = math.inf
        for (ax, ay), (bx, by) in segments:
            dx, dy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
            best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
        return min(1.0, max(0.0, 0.5 - (best - width / 2)))
    return coverage


def _widen(image, border_x, border_y, center):
    """Grow the one-pixel middle of a nine-slice source to `center` pixels.

    ttk tiles (rather than scales) the stretchable middle, so a tiny middle
    costs one blit per pixel of widget area. Photo `copy -to` replicates the
    middle row and column natively instead.
    """
    for axis, border in ((0, border_x), (1, border_y)):
        if not border:
            continue
        w, h = image.width(), image.height()
        size = (w, h)[axis]
        grown = [w, h]
        grown[axis] = size - 1 + center
        result = tk.PhotoImage(width=grown[0], height=grown[1])

        def region(a0, a1):
            return (a0, 0, a1, h) if axis == 0 else (0, a0, w, a1)

        def target(a0, a1):
            return (a0, 0, a1, grown[1]) if axis == 0 else (0, a0, grown[0], a1)
        result.tk.call(result, "copy", image, "-from", *region(0, border), "-to", *target(0, border))
        result.tk.call(result, "copy", image, "-from", *region(border, border + 1), "-to", *target(border, border + center))
        result.tk.call(result, "copy", image, "-from", *region(border + 1, size),
                       "-to", *target(border + center, grown[axis]))
        image = result
    return image


def raster(width, height, layers, under):
    """Paint (coverage, color) layers over `under` into a PhotoImage."""
    base = _rgb(under)
    layers = [(fn, _rgb(color)) for fn, color in layers]
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            r, g, b = base
            for coverage, (cr, cg, cb) in layers:
                a = coverage(x + 0.5, y + 0.5)
                if a > 0:
                    r, g, b = r + (cr - r) * a, g + (cg - g) * a, b + (cb - b) * a
            row.append("#%02x%02x%02x" % (round(r), round(g), round(b)))
        rows.append("{" + " ".join(row) + "}")
    image = tk.PhotoImage(width=width, height=height)
    image.put(" ".join(rows))
    return image


class Theme:
    def __init__(self, root):
        self.root = root
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.style = ttk.Style(root)
        # "clam" is used because the default macOS theme ignores button colors
        self.style.theme_use("clam")
        self.images = {}
        self.styles = set()
        self.fonts = self._create_fonts()
        self._configure()

    def px(self, value):
        return int(round(value * self.scale))

    def font(self, name):
        return self.fonts[name]

    def _create_fonts(self):
        families = set(tkfont.families(self.root))
        ui = next((f for f in _UI_FAMILIES if f in families), "Helvetica")
        mono = next((f for f in _MONO_FAMILIES if f in families), "Courier")
        strong = ("Segoe UI Semibold", "normal") if ui == "Segoe UI" and "Segoe UI Semibold" in families else (ui, "bold")
        kinds = {"ui": (ui, "normal"), "strong": strong, "mono": (mono, "normal")}
        fonts = {name: tkfont.Font(self.root, family=kinds[kind][0], size=size, weight=kinds[kind][1])
                 for name, (kind, size) in _FONTS.items()}
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(name, root=self.root).configure(family=ui, size=11)
        return fonts

    # -- Rasterized shapes -------------------------------------------------

    def surface(self, fill, radius, under, outline=None, line=1, ring=None, stripe=None):
        """A square nine-slice source image and the border width to stretch.

        `stripe` paints a colored bar inside the left edge, clipped to the
        rounded shape; it sits within the fixed left border so it never tiles."""
        key = ("surface", fill, radius, under, outline, line, ring, stripe)
        if key not in self.images:
            r = self.px(radius)
            margin = self.px(3) if ring else 0
            size = 2 * (r + margin) + 3
            box = (margin, margin, size - margin, size - margin)
            layers = []
            if ring:
                layers.append((rounded((0, 0, size, size), r + margin), ring))
            width = max(1, self.px(line)) if outline else 0
            if outline:
                layers.append((rounded(box, r), outline))
            if fill:
                inner = (box[0] + width, box[1] + width, box[2] - width, box[3] - width)
                layers.append((rounded(inner, max(r - width, 0)), fill))
            if stripe:
                shape, edge = rounded(box, r), box[0] + self.px(6)
                layers.append((lambda x, y: shape(x, y) * min(1.0, max(0.0, edge - x + 0.5)), stripe))
            border = r + margin + 1
            image = _widen(raster(size, size, layers, under), border, border, self.px(48))
            self.images[key] = (image, border)
        return self.images[key]

    def logo(self, size, under=None, fill=ACCENT, mark="#ffffff"):
        """Brand mark: four drawer fronts stacked in a cabinet."""
        under = under or SHELL
        key = ("logo", size, under, fill, mark)
        if key not in self.images:
            s = size
            layers = [(rounded((0, 0, s, s), s * 0.24), fill)]
            pad, gap = s * 0.2, s * 0.06
            height = (s - 2 * pad - 3 * gap) / 4
            for index in range(4):
                y0 = pad + index * (height + gap)
                layers.append((rounded((pad, y0, s - pad, y0 + height), s * 0.04), mark))
                middle = y0 + height / 2
                layers.append((_stroke([(s * 0.42, middle), (s * 0.58, middle)], max(1.0, s * 0.04)), fill))
            self.images[key] = raster(s, s, layers, under)
        return self.images[key]

    # -- ttk styles -------------------------------------------------------

    def _element(self, name, images, border):
        default, *states = images
        # The minimum size keeps small widgets from growing to the widened
        # source image; corners still render at full radius.
        edges = border if isinstance(border, tuple) else (border, border)
        size = {"width": 2 * edges[0] + 1, "height": 2 * edges[-1] + 1} if any(edges) else {}
        self.style.element_create(name, "image", str(default),
                                  *[(spec, str(image)) for spec, image in states],
                                  border=border, padding=0, sticky="nsew", **size)

    def button_style(self, kind="Secondary", under=SURFACE, large=False):
        name = f"{kind}{'Large' if large else ''}{_suffix(under)}.TButton"
        if name in self.styles:
            return name
        fill, text, outline, hover, pressed, dis_fill, dis_text, dis_outline = (
            HEADER_BUTTON if kind == "Header" else _BUTTONS[kind])
        fill, dis_fill = fill or under, dis_fill or under
        radius = 10 if large else 8

        def shape(color, line=outline):
            return self.surface(color, radius, under, outline=line)
        normal, border = shape(fill)
        states = [("disabled", shape(dis_fill, dis_outline)[0]), ("pressed", shape(pressed)[0]),
                  ("active", shape(hover)[0])]
        if kind in ("Secondary", "Header"):
            states.append(("focus", shape(fill, ACCENT)[0]))
        element = name.replace(".TButton", "") + ".button"
        self._element(element, [normal, *states], border)
        self.style.layout(name, [(element, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})]})])
        if kind == "Ghost":
            padding, font = (self.px(10), self.px(6)), "link"
        elif large:
            padding, font = (self.px(28), self.px(14)), "button_lg"
        else:
            padding, font = (self.px(18), self.px(9)), "button"
        # width=0 sizes buttons to their label instead of clam's 11-character minimum.
        self.style.configure(name, font=self.font(font), foreground=text, padding=padding, anchor="center", width=0)
        self.style.map(name, foreground=[("disabled", dis_text)])
        self.styles.add(name)
        return name

    def frame_style(self, name, fill, under, outline=None, radius=12, line=1, stripe=None):
        """A rounded ttk.Frame style. ttk frames ignore element padding, so
        callers pass `padding=` on the widget."""
        if name not in self.styles:
            image, border = self.surface(fill, radius, under, outline=outline, line=line, stripe=stripe)
            self._element(name + ".surface", [image], border)
            self.style.layout(name, [(name + ".surface", {"sticky": "nsew"})])
            self.styles.add(name)
        return name

    @staticmethod
    def front_fill(state, tone):
        if not DRAWER_TONES:
            return {"rest": SHELL_RAISED, "hover": SHELL_HOVER, "selected": SHELL_SELECTED}[state]
        return SHELL_RAISED if state == "rest" else DRAWER_TONES[tone][1]

    def front_style(self, state, tone):
        """Drawer fronts in the cabinet: resting, hovered, selected. With
        DRAWER_TONES each carries the edge color of the drawer's tone (empty,
        stocked, open); otherwise the selected front gets an accent outline."""
        edge = DRAWER_TONES[tone][0] if DRAWER_TONES else None
        outline, line = (edge or ACCENT, 2) if state == "selected" else (CARD_LINE, 1)
        name = f"Front{state.title()}{tone.title()}{PALETTE.title()}.TFrame"
        return self.frame_style(name, self.front_fill(state, tone), SHELL, outline=outline, radius=14, line=line,
                                stripe=edge)

    def banner(self, parent, tone, under=SURFACE):
        text, soft, line = TONES[tone]
        style = self.frame_style(f"Banner{tone.title()}{_suffix(under)}.TFrame", soft, under, outline=line, radius=12)
        return ttk.Frame(parent, style=style, padding=(self.px(20), self.px(16)))

    def entry_style(self, name, under=SURFACE, fill=SURFACE, outline=BORDER_STRONG, text=TEXT, ring="#ccfbf1",
                    hover=FAINT):
        if name in self.styles:
            return name
        radius = 10

        def shape(fill_color, outline_color, ring_color=under):
            return self.surface(fill_color, radius, under, outline=outline_color, ring=ring_color)
        normal, border = shape(fill, outline)
        states = [("disabled", shape(fill, outline)[0]), ("focus", shape(fill, ACCENT, ring)[0]),
                  ("hover", shape(fill, hover)[0])]
        self._element(name + ".field", [normal, *states], border)
        self.style.layout(name, [(name + ".field", {"sticky": "nsew", "children": [
            ("Entry.padding", {"sticky": "nsew", "children": [("Entry.textarea", {"sticky": "nsew"})]})]})])
        self.style.configure(name, padding=(self.px(14), self.px(10)), foreground=text, insertcolor=text,
                             selectbackground=ACCENT_LINE, selectforeground=TEXT, insertwidth=max(1, self.px(1.5)))
        self.style.map(name, foreground=[("disabled", FAINT)])
        self.styles.add(name)
        return name

    def panel_style(self):
        """The white work panel on the shell."""
        return self.frame_style(f"Panel{PALETTE.title()}.TFrame", SURFACE, SHELL, outline=CARD_LINE, radius=16)

    def header_entry_style(self):
        """The scan field in the header band."""
        field = {k: v for k, v in HEADER_FIELD.items() if k != "placeholder"}
        return self.entry_style(f"Header{PALETTE.title()}.TEntry", under=HEADER, **field)

    def _check_style(self):
        size = self.px(22)
        gap = self.px(12)

        def box(fill, outline, mark=False):
            r = self.px(6)
            layers = [(rounded((0.5, 0.5, size - 0.5, size - 0.5), r), outline)]
            layers.append((rounded((1.5, 1.5, size - 1.5, size - 1.5), r - 1), fill))
            if mark:
                points = [(size * 0.27, size * 0.52), (size * 0.44, size * 0.68), (size * 0.74, size * 0.34)]
                layers.append((_stroke(points, max(1.6, size * 0.11)), "#ffffff"))
            return raster(size + gap, size, layers, SURFACE)
        images = [box(SURFACE, BORDER_STRONG),
                  ("disabled", box(SUBTLE, BORDER)),
                  ("selected", box(ACCENT, ACCENT, True)),
                  ("active", box(SURFACE, ACCENT))]
        for spec, image in images[1:]:
            self.images[("check", spec)] = image
        self.images[("check", "normal")] = images[0]
        self._element("Check.indicator", images, 0)
        self.style.layout("Check.TCheckbutton", [("Checkbutton.padding", {"sticky": "nsew", "children": [
            ("Check.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.label", {"side": "left", "sticky": "nsew"})]})])
        self.style.configure("Check.TCheckbutton", background=SURFACE, foreground=TEXT, font=self.font("body"),
                             padding=(0, self.px(8)), wraplength=self.px(520))
        self.style.map("Check.TCheckbutton", background=[("active", SURFACE)], foreground=[("disabled", FAINT)])

    def scrollbar_style(self, under=SURFACE):
        prefix = "Slim" + _suffix(under)
        name = prefix + ".Vertical.TScrollbar"
        if name in self.styles:
            return name
        width, radius = self.px(12), self.px(4)
        size = 2 * radius + 3
        rest, active = ("#d5dae1", FAINT) if under != SHELL else (SHELL_LINE, SHELL_MUTED)

        def thumb(color):
            x0 = (width - 2 * radius) / 2
            image = raster(width, size, [(rounded((x0, 0, x0 + 2 * radius, size), radius), color)], under)
            image = self.images[("thumb", under, color)] = _widen(image, 0, radius + 1, self.px(48))
            return image
        self._element(prefix + ".Vertical.Scrollbar.thumb", [thumb(rest), ("pressed", thumb(active)),
                                                             ("active", thumb(active))], (0, radius + 1))
        trough = self.images[("trough", under)] = raster(width, self.px(48), [], under)
        self._element(prefix + ".Vertical.Scrollbar.trough", [trough], 0)
        self.style.layout(name, [(prefix + ".Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            (prefix + ".Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        self.styles.add(name)
        return name

    def _configure(self):
        style = self.style
        style.configure(".", background=SURFACE, foreground=TEXT, font=self.font("body"),
                        bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE, troughcolor=SUBTLE,
                        focuscolor=ACCENT, selectbackground=ACCENT_LINE, selectforeground=TEXT)
        style.configure("TFrame", background=SURFACE)
        style.configure("TLabel", background=SURFACE, foreground=TEXT)
        # Unstyled buttons and entries still match the design.
        self.button_style("Primary")
        self.button_style("Secondary")
        style.layout("TButton", style.layout("Secondary.TButton"))
        style.configure("TButton", **{k: style.lookup("Secondary.TButton", k) for k in ("font", "foreground", "padding", "anchor", "width")})
        style.map("TButton", foreground=[("disabled", FAINT)])
        self.entry_style("Field.TEntry")
        style.layout("TEntry", style.layout("Field.TEntry"))
        style.configure("TEntry", **{k: style.lookup("Field.TEntry", k) for k in
                                     ("padding", "foreground", "insertcolor", "selectbackground", "selectforeground", "insertwidth")})
        self._check_style()
        self.scrollbar_style(SURFACE)
        style.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE, foreground=TEXT,
                        bordercolor=BORDER_STRONG, lightcolor=SURFACE, darkcolor=SURFACE, arrowcolor=MUTED,
                        padding=(self.px(10), self.px(6)), arrowsize=self.px(14))
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE)], bordercolor=[("focus", ACCENT)],
                  selectbackground=[("readonly", SURFACE)], selectforeground=[("readonly", TEXT)])
        self.root.option_add("*TCombobox*Listbox.font", self.font("body"))
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_SOFT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
        style.configure("Records.Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT,
                        font=self.font("mono"), rowheight=self.px(34), bordercolor=BORDER,
                        lightcolor=BORDER, darkcolor=BORDER, borderwidth=1)
        style.map("Records.Treeview", background=[("selected", ACCENT_SOFT)], foreground=[("selected", TEXT)])
        style.configure("Records.Treeview.Heading", font=self.font("caption"), background=SUBTLE, foreground=MUTED,
                        bordercolor=BORDER, lightcolor=SUBTLE, darkcolor=SUBTLE, relief="flat",
                        padding=(self.px(4), self.px(8)))
        style.map("Records.Treeview.Heading", background=[("active", SUBTLE)])


def apply_theme(window):
    """Theme a Tk root once and return its Theme; later calls reuse it."""
    root = window.nametowidget(".")
    theme = getattr(root, "pharm_theme", None)
    if theme is None:
        theme = root.pharm_theme = Theme(root)
        root.configure(bg=SHELL)
    return theme


def current(widget):
    return apply_theme(widget)
