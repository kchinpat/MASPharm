"""Build the four launchers beside the app folder, each with its own icon.

The icons are the app's cabinet mark (UI/theme.py's logo), with a corner badge on
each launcher other than the main one. Launcher.cs is compiled by the C# compiler
that comes with Windows' .NET Framework. Drawing the icons needs Pillow.

    python -B app/launcher/build.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # where the launchers go, beside the app folder
TOP, BOTTOM = (20, 168, 153), (15, 118, 110)  # the brand teal, #0d9488, lit from above
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
SCALE = 8  # supersampling for smooth edges

# (file name, C# define, console window, badge: (color, glyph) or None)
LAUNCHERS = (
    ("Pharmacy Drawer", "DESKTOP", False, None),
    ("Browser Cabinet", "BROWSER", True, ((37, 99, 235), "globe")),
    ("USB Bench", "USB", True, ((71, 85, 105), "plug")),
    ("Team USB Bench", "TEAM_USB", True, ((234, 88, 12), "plug")),
)


def mark(size, badge):
    s = size * SCALE
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    tile = Image.new("RGBA", (s, s))
    shade = ImageDraw.Draw(tile)
    for y in range(s):
        t = y / (s - 1)
        shade.line([(0, y), (s, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)) + (255,))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=s * 0.24, fill=255)
    image.paste(tile, (0, 0), mask)

    draw = ImageDraw.Draw(image)
    pad, gap = s * 0.2, s * 0.06
    height = (s - 2 * pad - 3 * gap) / 4
    for index in range(4):
        y0 = pad + index * (height + gap)
        draw.rounded_rectangle((pad, y0, s - pad, y0 + height), radius=s * 0.04, fill="white")
        if size >= 32:  # handles blur away below this, as in the window icon
            middle = y0 + height / 2
            draw.line([(s * 0.42, middle), (s * 0.58, middle)], fill=BOTTOM, width=max(SCALE, round(s * 0.04)))

    if badge:
        color, glyph = badge
        cx = cy = s * 0.765
        r, ring = s * 0.225, s * 0.05
        cut = Image.new("L", (s, s), 0)
        ImageDraw.Draw(cut).ellipse((cx - r - ring, cy - r - ring, cx + r + ring, cy + r + ring), fill=255)
        image.paste((0, 0, 0, 0), (0, 0), cut)
        draw = ImageDraw.Draw(image)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
        if size >= 24:
            line = max(SCALE, round(s * 0.028))
            if glyph == "globe":
                g = r * 0.62
                draw.ellipse((cx - g, cy - g, cx + g, cy + g), outline="white", width=line)
                draw.ellipse((cx - g * 0.45, cy - g, cx + g * 0.45, cy + g), outline="white", width=line)
                draw.line([(cx - g, cy), (cx + g, cy)], fill="white", width=line)
            else:  # a USB plug: two prongs, the plug body and its cable
                w, top = r * 0.62, cy - r * 0.18
                prong = r * 0.14
                for x in (cx - w * 0.38, cx + w * 0.38):
                    draw.rectangle((x - prong / 2, top - r * 0.38, x + prong / 2, top), fill="white")
                draw.rounded_rectangle((cx - w / 2, top, cx + w / 2, top + r * 0.5), radius=r * 0.1, fill="white")
                draw.rectangle((cx - prong / 2, top + r * 0.5, cx + prong / 2, cy + r * 0.66), fill="white")
    return image.resize((size, size), Image.LANCZOS)


def compiler():
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    for framework in ("Framework64", "Framework"):
        csc = windows / "Microsoft.NET" / framework / "v4.0.30319" / "csc.exe"
        if csc.is_file():
            return csc
    sys.exit("The .NET Framework 4 C# compiler (csc.exe) was not found.")


def main():
    csc = compiler()
    with tempfile.TemporaryDirectory() as scratch:
        for name, define, console, badge in LAUNCHERS:
            icon = Path(scratch) / f"{define}.ico"
            frames = [mark(size, badge) for size in SIZES]
            frames[-1].save(icon, format="ICO", sizes=[(n, n) for n in SIZES], append_images=frames[:-1])
            target = ROOT / f"{name}.exe"
            subprocess.run([str(csc), "/nologo", "/optimize+", "/warn:0", f"/define:{define}",
                            "/target:" + ("exe" if console else "winexe"), f"/win32icon:{icon}",
                            f"/out:{target}", str(HERE / "Launcher.cs")], check=True)
            print(f"Built {target.name} ({target.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
