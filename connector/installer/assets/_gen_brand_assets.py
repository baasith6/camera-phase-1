"""Generate wizard BMPs from the original onevo.ico (not the new mark)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent
FONTS = ASSETS / "fonts"
BG = (245, 244, 241)
SURFACE = (250, 250, 249)
INK = (41, 37, 36)
MUTED = (120, 113, 108)
ACCENT = (37, 99, 235)
BORDER = (224, 222, 217)


def load_font(name: str, size: int) -> ImageFont.ImageFont:
    path = FONTS / name
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def load_logo(max_side: int) -> Image.Image:
    ico = Image.open(ASSETS / "onevo.ico")
    # Pillow picks best size from multi-res ICO
    ico = ico.convert("RGBA")
    ico.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return ico


def paste_centered(base: Image.Image, overlay: Image.Image, cx: int, cy: int) -> None:
    x = cx - overlay.width // 2
    y = cy - overlay.height // 2
    base.paste(overlay, (x, y), overlay)


def make_side() -> None:
    w, h = 164, 314
    side = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(side)
    d.rectangle([0, 0, w, 4], fill=ACCENT)
    d.rounded_rectangle([12, 40, w - 12, 200], radius=12, fill=SURFACE, outline=BORDER)
    logo = load_logo(96)
    paste_centered(side, logo, w // 2, 100)
    font_brand = load_font("IBMPlexSans-SemiBold.ttf", 26)
    font_sub = load_font("IBMPlexSans-Medium.ttf", 12)
    one_w = d.textbbox((0, 0), "one", font=font_brand)[2]
    tw = d.textbbox((0, 0), "onetix", font=font_brand)[2]
    x0 = (w - tw) // 2
    d.text((x0, 160), "one", font=font_brand, fill=INK)
    d.text((x0 + one_w, 160), "tix", font=font_brand, fill=ACCENT)
    for y, label in ((220, "Local connector"), (240, "Camera pairing")):
        sb = d.textbbox((0, 0), label, font=font_sub)
        d.text(((w - (sb[2] - sb[0])) // 2, y), label, font=font_sub, fill=MUTED)
    small = load_logo(28)
    paste_centered(side, small, w // 2, 280)
    path = ASSETS / "wizard-side.bmp"
    side.save(path, format="BMP")
    print("wrote", path)


def make_small() -> None:
    sw, sh = 55, 55
    small = Image.new("RGB", (sw, sh), BG)
    ds = ImageDraw.Draw(small)
    ds.rounded_rectangle([2, 2, sw - 3, sh - 3], radius=10, fill=SURFACE, outline=BORDER)
    logo = load_logo(40)
    paste_centered(small, logo, sw // 2, sh // 2)
    path = ASSETS / "wizard-small.bmp"
    small.save(path, format="BMP")
    print("wrote", path)


if __name__ == "__main__":
    make_side()
    make_small()
