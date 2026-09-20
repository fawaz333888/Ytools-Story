"""Karaoke subtitle generator (ASS) from word timings.

One dialogue event per line, with per-word \\k karaoke tags so libass
highlights the currently spoken word. Colors use libass BGR order
(&HAABBGGRR, alpha 00=opaque).
"""

from __future__ import annotations

import os
from typing import Optional

from ..tts.edge import Word
from ..utils import fmt_ass_time
from .watermark import find_font

# font file -> family name understood by libass/fontconfig
FONT_FAMILY = {
    "dejavusans-bold.ttf": "DejaVu Sans",
    "dejavusans.ttf": "DejaVu Sans",
    "liberationsans-bold.ttf": "Liberation Sans",
    "arialbd.ttf": "Arial",
    "arial.ttf": "Arial",
}


def _family_name(font_path: Optional[str]) -> str:
    if not font_path:
        return "DejaVu Sans"  # present on Colab/Linux; fontconfig fallback elsewhere
    base = os.path.basename(font_path).lower()
    return FONT_FAMILY.get(base, "DejaVu Sans")


def _ass_color(rgb: tuple[int, int, int], alpha: int = 0) -> str:
    """rgb(0-255) + alpha(0=opaque..255=transparent) -> &HAABBGGRR."""
    r, g, b = rgb
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _group_lines(words: list[Word], max_chars: int) -> list[list[Word]]:
    lines: list[list[Word]] = []
    cur: list[Word] = []
    cur_len = 0
    for w in words:
        wlen = len(w.text)
        add = (wlen + (1 if cur else 0))
        if cur and cur_len + add > max_chars:
            lines.append(cur)
            cur, cur_len = [w], wlen
        else:
            cur.append(w)
            cur_len += add
    if cur:
        lines.append(cur)
    return lines


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def build_karaoke_ass(
    words: list[Word],
    width: int = 1280,
    height: int = 720,
    font_size: int = 0,
    max_chars: int = 34,
    margin_v: int = 60,
    position: str = "bottom",
    font_path: str = "",
    style_name: str = "Main",
) -> str:
    """Return ASS subtitle text with karaoke-highlighted words."""
    if not words:
        raise ValueError("no words provided for subtitles")
    font_size = font_size or max(20, int(height * 0.052))
    max_chars = max_chars or 34
    family = _family_name(find_font(override=font_path) if not font_path else font_path)

    # unsung = soft white; active word (secondary) = bright amber highlight
    primary = _ass_color((245, 245, 248))
    secondary = _ass_color((255, 200, 40))
    outline = _ass_color((10, 10, 14))
    shadow = _ass_color((0, 0, 0), alpha=140)

    # position: 2=bottom-center, 8=top-center, 5=screen center
    alignment = {"bottom": 2, "top": 8, "center": 5}.get(position, 2)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 2
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: {style_name},{family},{font_size},{primary},{secondary},{outline},{shadow},-1,0,0,0,100,100,0,0,1,3,1,{alignment},48,48,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = _group_lines(words, max_chars)
    events: list[str] = []
    for line in lines:
        start = line[0].start
        end = max(w.end for w in line)
        # pad slightly so highlight does not feel clipped
        start_pad = max(0.0, start - 0.12)
        end_pad = end + 0.10

        text = "{\\k8}" + " ".join(
            rf"{{\k{max(1, int(round((w.end - w.start) * 100)))}}}" + _escape(w.text)
            for w in line
        )
        events.append(
            f"Dialogue: 0,{fmt_ass_time(start_pad)},{fmt_ass_time(end_pad)},"
            f"{style_name},,0,0,0,,{text}"
        )

    return header + "\n".join(events) + "\n"


def build_simple_ass(
    words: list[Word],
    width: int = 1280,
    height: int = 720,
    font_size: int = 0,
    max_chars: int = 34,
    margin_v: int = 60,
    position: str = "bottom",
    font_path: str = "",
    style_name: str = "Main",
) -> str:
    """Plain one-line-per-group subtitles, no per-word highlight."""
    if not words:
        raise ValueError("no words provided for subtitles")
    font_size = font_size or max(20, int(height * 0.052))
    family = _family_name(find_font(override=font_path) if not font_path else font_path)
    primary = _ass_color((255, 255, 255))
    outline = _ass_color((10, 10, 14))
    shadow = _ass_color((0, 0, 0), alpha=140)
    alignment = {"bottom": 2, "top": 8, "center": 5}.get(position, 2)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: {style_name},{family},{font_size},{primary},{primary},{outline},{shadow},0,0,0,0,100,100,0,0,1,3,1,{alignment},48,48,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    for line in _group_lines(words, max_chars):
        text = " ".join(_escape(w.text) for w in line)
        events.append(
            f"Dialogue: 0,{fmt_ass_time(line[0].start)},{fmt_ass_time(max(w.end for w in line) + 0.1)},"
            f"{style_name},,0,0,0,,{text}"
        )
    return header + "\n".join(events) + "\n"


def build_ass(
    words: list[Word],
    style: str = "karaoke",
    width: int = 1280,
    height: int = 720,
    **kw,
) -> str:
    fn = build_karaoke_ass if style == "karaoke" else build_simple_ass
    return fn(words, width=width, height=height, **kw)


__all__ = ["build_ass", "build_karaoke_ass", "build_simple_ass"]
