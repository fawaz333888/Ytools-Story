"""Particle overlay engine — renders a seamlessly looping transparent video.

Motion is fully parametric (sine/mod based) so frame 0 and frame N match
exactly, giving a loopable overlay. Frames are drawn with PIL using
pre-built radial glow stamps, then encoded to a QuickTime Animation (qtrle)
video with an alpha channel, which the composer overlays on the footage.

Styles: dust, snow, sparkle, fireflies, embers, fog
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass

import numpy as np
from PIL import Image

from ..render.ffutil import FFRunner
from ..utils import clamp, rng_from_seed

STYLE_COLORS = {
    "dust": (255, 248, 220),
    "snow": (255, 255, 255),
    "sparkle": (255, 255, 240),
    "fireflies": (190, 255, 120),
    "embers": (255, 140, 40),
    "fog": (200, 205, 215),
}


@dataclass
class Particle:
    bx: float       # base x (fractional 0..1)
    by: float       # base y
    amp_x: float    # horizontal sway amplitude (px)
    amp_y: float
    freq_x: float   # cycles per loop
    freq_y: float
    phase: float
    size: float     # stamp radius px
    alpha: float    # peak alpha
    pulse_freq: float
    pulse_depth: float


def _make_stamp(radius: int, color: tuple[int, int, int], soft: float = 2.0) -> Image.Image:
    """Radial-gradient glow stamp as RGBA PIL image."""
    r = max(1, int(radius))
    yy, xx = np.mgrid[0 : 2 * r, 0 : 2 * r]
    dist = np.sqrt((xx - r) ** 2 + (yy - r) ** 2) / float(r)
    falloff = np.clip(1.0 - dist, 0.0, 1.0) ** soft
    alpha = (np.clip(falloff, 0.0, 1.0) * 255).astype(np.uint8)
    rgb = np.zeros((2 * r, 2 * r, 3), dtype=np.uint8)
    rgb[..., 0], rgb[..., 1], rgb[..., 2] = color
    rgba = np.dstack([rgb, alpha])
    return Image.fromarray(rgba, "RGBA")


def _spawn(rng: random.Random, style: str, width: int, height: int) -> Particle:
    if style == "dust":
        return Particle(
            bx=rng.random(), by=rng.random(),
            amp_x=rng.uniform(10, 40), amp_y=rng.uniform(8, 30),
            freq_x=rng.uniform(0.5, 2.0), freq_y=rng.uniform(0.5, 2.0),
            phase=rng.uniform(0, 2 * math.pi),
            size=rng.uniform(1.5, 3.5), alpha=rng.uniform(0.65, 0.95),
            pulse_freq=rng.uniform(1, 3), pulse_depth=rng.uniform(0.15, 0.4),
        )
    if style == "snow":
        return Particle(
            bx=rng.random(), by=rng.random(),
            amp_x=rng.uniform(15, 60), amp_y=0.0,
            freq_x=rng.uniform(0.3, 1.2), freq_y=1.0,
            phase=rng.uniform(0, 2 * math.pi),
            size=rng.uniform(1.8, 4.0), alpha=rng.uniform(0.7, 1.0),
            pulse_freq=rng.uniform(0.3, 1.0), pulse_depth=0.15,
        )
    if style == "sparkle":
        return Particle(
            bx=rng.random(), by=rng.random(),
            amp_x=0.0, amp_y=0.0,
            freq_x=1.0, freq_y=1.0,
            phase=rng.uniform(0, 2 * math.pi),
            size=rng.uniform(1.2, 3.0), alpha=rng.uniform(0.6, 1.0),
            pulse_freq=rng.uniform(2, 6), pulse_depth=1.0,
        )
    if style == "fireflies":
        return Particle(
            bx=rng.random(), by=rng.random(),
            amp_x=rng.uniform(30, 110), amp_y=rng.uniform(20, 80),
            freq_x=rng.uniform(0.3, 1.0), freq_y=rng.uniform(0.3, 1.0),
            phase=rng.uniform(0, 2 * math.pi),
            size=rng.uniform(2.5, 5.5), alpha=rng.uniform(0.7, 1.0),
            pulse_freq=rng.uniform(0.8, 2.5), pulse_depth=rng.uniform(0.3, 0.7),
        )
    if style == "embers":
        return Particle(
            bx=rng.uniform(0.15, 0.85), by=rng.uniform(0.3, 1.0),
            amp_x=rng.uniform(5, 25), amp_y=0.0,
            freq_x=rng.uniform(1.0, 3.0), freq_y=1.0,
            phase=rng.uniform(0, 2 * math.pi),
            size=rng.uniform(1.2, 3.0), alpha=rng.uniform(0.7, 1.0),
            pulse_freq=rng.uniform(1, 4), pulse_depth=0.4,
        )
    if style == "fog":
        return Particle(
            bx=rng.random(), by=rng.uniform(0.35, 1.0),
            amp_x=rng.uniform(120, 320), amp_y=rng.uniform(10, 40),
            freq_x=rng.uniform(0.2, 0.6), freq_y=rng.uniform(0.2, 0.5),
            phase=rng.uniform(0, 2 * math.pi),
            size=rng.uniform(60, 160), alpha=rng.uniform(0.5, 0.8),
            pulse_freq=rng.uniform(0.2, 0.6), pulse_depth=0.3,
        )
    raise ValueError(f"unknown particle style {style!r}")


def _position(p: Particle, t_frac: float, width: int, height: int) -> tuple[float, float]:
    """Parametric position; embers/snow drift globally and wrap via mod."""
    ang_x = 2 * math.pi * p.freq_x * t_frac + p.phase
    ang_y = 2 * math.pi * p.freq_y * t_frac + p.phase * 1.3
    x = p.bx * width + math.sin(ang_x) * p.amp_x
    y = p.by * height + math.sin(ang_y) * p.amp_y
    return x, y


def _drift(style: str, p: Particle, t_frac: float, width: int, height: int) -> tuple[float, float]:
    """Global directional drift (wrap-around) for snow/embers."""
    if style in ("snow",):
        speed = height * 0.9  # full-height fall over one loop
        y = (p.by * height + speed * t_frac) % height
        x = p.bx * width + math.sin(2 * math.pi * p.freq_x * t_frac + p.phase) * p.amp_x
        return x, y
    if style == "embers":
        speed = height * 1.4
        y = (p.by * height - speed * t_frac) % height
        x = p.bx * width + math.sin(2 * math.pi * p.freq_x * t_frac + p.phase) * p.amp_x
        return x, y
    return _position(p, t_frac, width, height)


def render_particles(
    out_mov: str,
    style: str = "dust",
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    loop_seconds: float = 8.0,
    density: int = 60,
    size_mult: float = 1.0,
    seed: int | None = None,
    workdir: str | None = None,
    ff: FFRunner | None = None,
) -> str:
    """Render a looping transparent particle overlay video (qtrle + alpha)."""
    if style not in STYLE_COLORS:
        raise ValueError(f"unknown particle style {style!r}; valid: {sorted(STYLE_COLORS)}")
    ff = ff or FFRunner()
    rng = rng_from_seed(seed if seed is not None else random.SystemRandom().randint(0, 2**31))
    frames = max(1, int(round(loop_seconds * fps)))
    workdir = workdir or os.path.splitext(out_mov)[0] + "_frames"
    os.makedirs(workdir, exist_ok=True)

    color = STYLE_COLORS[style]
    particles = [_spawn(rng, style, width, height) for _ in range(int(density))]
    if size_mult != 1.0:
        for p in particles:
            p.size = p.size * size_mult
    stamps = {}
    # group particles by rounded size to limit stamp count
    for p in particles:
        key = max(1, int(round(p.size)))
        if key not in stamps:
            stamps[key] = _make_stamp(key, color, soft=1.2 if style in ("sparkle", "embers") else 1.5)

    for f in range(frames):
        t_frac = f / float(frames)
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for p in particles:
            x, y = _drift(style, p, t_frac, width, height)
            # alpha pulse (sine, periodic)
            pulse = 1.0 - p.pulse_depth + p.pulse_depth * (
                0.5 + 0.5 * math.sin(2 * math.pi * p.pulse_freq * t_frac + p.phase)
            )
            a = int(clamp(p.alpha * pulse, 0.0, 1.0) * 255)
            if a <= 1:
                continue
            stamp = stamps[max(1, int(round(p.size)))]
            # apply per-particle alpha by re-tinting the stamp channel
            sx, sy = int(round(x - stamp.width / 2)), int(round(y - stamp.height / 2))
            if sx + stamp.width < 0 or sy + stamp.height < 0 or sx > width or sy > height:
                continue
            tinted = stamp.copy()
            alpha_ch = tinted.split()[3].point(lambda v: int(v * a / 255))
            tinted.putalpha(alpha_ch)
            canvas.paste(tinted, (sx, sy), tinted)
        canvas.save(os.path.join(workdir, f"f_{f:05d}.png"))

    pattern = os.path.join(workdir, "f_%05d.png")
    ff.run(
        [ff.ffmpeg, "-y", "-v", "error", "-f", "image2", "-framerate", str(fps),
         "-i", pattern, "-c:v", "qtrle", "-pix_fmt", "argb", out_mov]
    )
    # clean up frames to save disk (important on Colab)
    for f in range(frames):
        try:
            os.remove(os.path.join(workdir, f"f_{f:05d}.png"))
        except OSError:
            pass
    return out_mov


__all__ = ["render_particles", "STYLE_COLORS"]
