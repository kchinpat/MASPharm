"""Optional local image display. Network scraping is retired; images never identify stock."""
from pathlib import Path

IMAGE_DIR = Path(__file__).resolve().parent / "images"

def load_medicine_image(parent_frame, ndc, width=300):
    if not isinstance(ndc, str) or not ndc or any(c not in "0123456789-" for c in ndc):
        return None
    try:
        from PIL import Image, ImageTk
        import tkinter as tk
        with Image.open(IMAGE_DIR / f"{ndc}.jpg") as original:
            original.thumbnail((width, width))
            photo = ImageTk.PhotoImage(original.copy())
        label = tk.Label(parent_frame, image=photo)
        label.image = photo
        label.pack()
        return label
    except (ImportError, OSError, ValueError):
        return None

def download_image(ndc):
    # Optional curated local assets only. Loading inventory never waits for a remote image.
    return None

def update_medicine_image(img_label, parent_frame, new_ndc, width=200):
    if img_label is not None:
        img_label.destroy()
    return load_medicine_image(parent_frame, new_ndc, width)
