"""Watermark overlay PNG generation (badge / plain / logo)."""

from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    # Linux (Colab / Debian)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    # Windows
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def find_font(bold: bool = True, override: str = "") -> Optional[str]:
    if override and os.path.isfile(override):
        return override
    cands = list(FONT_CANDIDATES)
    if not bold:
        nonbold = [c for c in cands if "Bold" not in c and "bd." not in c]
        cands = nonbold + cands
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def _load_font(path: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


POSITIONS = {
    "top-left": ("left", "top"),
    "top-right": ("right", "top"),
    "bottom-left": ("left", "bottom"),
    "bottom-right": ("right", "bottom"),
    "center": ("center", "center"),
}


def render_watermark(
    out_png: str,
    text: str = "@YtoolsChannel",
    style: str = "badge",
    logo_path: Optional[str] = None,
    position: str = "top-right",
    width: int = 1280,
    height: int = 720,
    font_size: int = 0,
    font_path: str = "",
    margin: int = 0,
) -> tuple[int, int, str, str]:
    """Render watermark into a full-frame transparent PNG.

    Returns (anchor_x, anchor_y, halign, valign) so the composer can place it
    deterministically regardless of badge size.
    """
    if position not in POSITIONS:
        raise ValueError(f"unknown position {position!r}; valid: {sorted(POSITIONS)}")
    halign, valign = POSITIONS[position]
    margin = margin or max(16, int(height * 0.025))

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if style == "logo":
        if not logo_path or not os.path.isfile(logo_path):
            raise FileNotFoundError(f"watermark style=logo but logo missing: {logo_path}")
        logo = Image.open(logo_path).convert("RGBA")
        max_h = int(height * 0.09)
        if logo.height > max_h:
            logo = logo.resize(
                (int(logo.width * max_h / logo.height), max_h), Image.LANCZOS
            )
        lw, lh = logo.width, logo.height
        ax = _anchor_x(halign, lw, width, margin)
        ay = _anchor_y(valign, lh, height, margin)
        img.paste(logo, (ax, ay), logo)
        img.save(out_png)
        return ax, ay, halign, valign

    if not font_size:
        font_size = max(18, int(height * 0.034))
    font = _load_font(find_font(override=font_path), font_size)

    if style == "plain":
        # dark outline + white text, no background box
        outline = 3
        tw, th = _text_size(draw, text, font)
        ax = _anchor_x(halign, tw, width, margin)
        ay = _anchor_y(valign, th, height, margin)
        for dx in range(-outline, outline + 1):
            for dy in range(-outline, outline + 1):
                if dx or dy:
                    draw.text((ax + dx, ay + dy), text, font=font, fill=(0, 0, 0, 255))
        draw.text((ax, ay), text, font=font, fill=(255, 255, 255, 255))
        img.save(out_png)
        return ax, ay, halign, valign

    # badge: rounded translucent box + accent bar + text
    pad_x, pad_y = int(font_size * 0.55), int(font_size * 0.32)
    tw, th = _text_size(draw, text, font)
    bw = tw + pad_x * 2 + int(font_size * 0.35)  # room for accent bar
    bh = th + pad_y * 2
    ax = _anchor_x(halign, bw, width, margin)
    ay = _anchor_y(valign, bh, height, margin)
    radius = int(bh * 0.28)
    draw.rounded_rectangle(
        [ax, ay, ax + bw, ay + bh], radius=radius,
        fill=(15, 15, 20, 150),
        outline=(255, 255, 255, 60), width=1,
    )
    # accent bar
    bar_w = max(3, int(font_size * 0.14))
    draw.rounded_rectangle(
        [ax + pad_x, ay + pad_y, ax + pad_x + bar_w, ay + bh - pad_y],
        radius=bar_w // 2, fill=(255, 60, 60, 255),
    )
    draw.text(
        (ax + pad_x + bar_w + int(font_size * 0.28), ay + pad_y - int(font_size * 0.06)),
        text, font=font, fill=(255, 255, 255, 255),
    )
    img.save(out_png)
    return ax, ay, halign, valign


def _anchor_x(halign: str, w: int, width: int, margin: int) -> int:
    if halign == "left":
        return margin
    if halign == "right":
        return width - w - margin
    return (width - w) // 2


def _anchor_y(valign: str, h: int, height: int, margin: int) -> int:
    if valign == "top":
        return margin
    if valign == "bottom":
        return height - h - margin
    return (height - h) // 2


__all__ = ["render_watermark", "find_font", "POSITIONS"]
