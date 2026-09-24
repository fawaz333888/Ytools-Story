"""Subscribe button overlay (solid red pill, tight-cropped PNG).

Rendered at exact pill size (not full-frame): the composer positions it under
the channel watermark, so a small input keeps the bounce/sway overlay cheap.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

from .watermark import _load_font, _text_size, find_font

RED = (204, 0, 0, 255)


def render_subscribe(
    out_png: str,
    text: str = "SUBSCRIBE",
    width: int = 1280,
    height: int = 720,
    font_size: int = 0,
    font_path: str = "",
) -> tuple[int, int]:
    """Render the subscribe pill into a tight-cropped transparent PNG.

    Returns (w, h) of the pill so the pipeline/composer can place it without
    probing the file.
    """
    if not text.strip():
        text = "SUBSCRIBE"
    if not font_size:
        font_size = max(18, int(height * 0.034))
    font = _load_font(find_font(override=font_path), font_size)

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    tw, th = _text_size(draw, text, font)
    pad_x, pad_y = int(font_size * 0.7), int(font_size * 0.34)
    bw, bh = tw + pad_x * 2, th + pad_y * 2
    x0, y0 = (width - bw) // 2, (height - bh) // 2

    draw.rounded_rectangle(
        [x0, y0, x0 + bw, y0 + bh], radius=bh // 2, fill=RED
    )
    draw.text(
        (x0 + pad_x, y0 + pad_y - int(font_size * 0.06)),
        text, font=font, fill=(255, 255, 255, 255),
    )

    canvas.crop((x0, y0, x0 + bw, y0 + bh)).save(out_png)
    return bw, bh


def subscribe_size(path: str) -> tuple[int, int]:
    """Read a rendered pill's (w, h) — used on cache hits."""
    with Image.open(path) as img:
        return img.size


__all__ = ["render_subscribe", "subscribe_size", "RED"]
