"""Card layout overlay: thumbnail (top-left) + title text (top).

Rendered as one full-frame transparent PNG, same pattern as the watermark.
The channel tag (top-right) is the watermark overlay, not this module.
"""

from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .watermark import _load_font, _text_size, find_font


def _crop_center(img: Image.Image, ratio: float) -> Image.Image:
    """Crop to `ratio` (w/h) around the center, no upscale."""
    cur = img.width / img.height
    if cur > ratio:
        nw = int(img.height * ratio)
        x = (img.width - nw) // 2
        box = (x, 0, x + nw, img.height)
    else:
        nh = int(img.width / ratio)
        y = (img.height - nh) // 2
        box = (0, y, img.width, y + nh)
    return img.crop(box)


def _round_corners(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, img.width - 1, img.height - 1], radius=radius, fill=255
    )
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, min_lines: int = 1) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if _text_size(draw, trial, font)[0] <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    # force at least min_lines: split a single line at the word boundary nearest
    # its horizontal midpoint so both halves stay balanced (not flat 1-liner)
    while len(lines) < min_lines and len(lines[-1].split()) >= 2:
        ws = lines[-1].split()
        # pick the split k that minimizes |left width - right width|
        best = min(
            range(1, len(ws)),
            key=lambda k: abs(
                _text_size(draw, " ".join(ws[:k]), font)[0]
                - _text_size(draw, " ".join(ws[k:]), font)[0]
            ),
        )
        lines[-1:] = [" ".join(ws[:best]), " ".join(ws[best:])]

    return lines


def render_card(
    out_png: str,
    title: str = "",
    thumbnail_path: Optional[str] = None,
    width: int = 1280,
    height: int = 720,
    opacity: float = 1.0,
    title_size: int = 0,
    font_path: str = "",
    margin: int = 0,
) -> None:
    """Burn thumbnail + title into a transparent full-frame PNG."""
    if not thumbnail_path or not os.path.isfile(thumbnail_path):
        raise FileNotFoundError(f"card thumbnail missing: {thumbnail_path!r}")

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = margin or max(16, int(height * 0.025))
    alpha = int(255 * opacity)

    # thumbnail: 16:9, ~16% of frame height, rounded + white border
    thumb_h = int(height * 0.16)
    thumb_w = int(thumb_h * 16 / 9)
    th = Image.open(thumbnail_path).convert("RGBA")
    th = _crop_center(th, 16 / 9).resize((thumb_w, thumb_h), Image.LANCZOS)
    th = _round_corners(th, radius=max(6, int(thumb_h * 0.12)))
    img.paste(th, (margin, margin), th)
    ImageDraw.Draw(img).rounded_rectangle(
        [margin, margin, margin + thumb_w, margin + thumb_h],
        radius=max(6, int(thumb_h * 0.12)),
        outline=(255, 255, 255, min(255, int(220 * opacity))),
        width=3,
    )

    if title.strip():
        size = title_size or max(20, int(height * 0.038))
        font = _load_font(find_font(override=font_path), size)
        # left-aligned right of the thumbnail; right edge stays within 3/4
        # of the width so the title never runs into the channel watermark
        tx = margin + thumb_w + margin
        max_w = (width * 3 // 4) - tx
        lines = _wrap(draw, title, font, max_w, min_lines=2)[:2]
        line_h = size
        total_h = line_h * len(lines)
        ty = margin + max(0, (thumb_h - total_h) // 2)
        for line in lines:
            # no outline: plain white like the thumbnail border
            draw.text((tx, ty), line, font=font, fill=(255, 255, 255, alpha))
            ty += line_h

    img.save(out_png)


__all__ = ["render_card"]
