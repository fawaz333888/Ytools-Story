"""Composer: build and run the final ffmpeg render.

Filter graph (per-frame, single ffmpeg pass):

  footage (looped, muted) -> cover-scale -> optional motion crop -> base
  base + watermark PNG -> base+wm
  base+wm + particle overlay (looped, alpha) -> base+fx
   base+fx + card (thumbnail + title) -> base+card
   base+card + subscribe pill (bounce-in + sway) -> base+sub
   base+sub + audio spectrum (cqt/spectrum/waves/vectorscope) -> base+spec
  base+spec + karaoke ASS (subtitles filter) -> final video
  narration wav -> asplit -> (resample -> AAC) + spectrum visualizer

Duration is driven by the narration audio (-t); the footage and particle
inputs use -stream_loop -1 so they wrap for as long as needed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..render.ffutil import FFRunner
from ..overlays.watermark import POSITIONS

POSITION_EXPR = {
    "top-left": "x={M}:y={M}",
    "top-right": "x=W-w-{M}:y={M}",
    "bottom-left": "x={M}:y=H-h-{M}",
    "bottom-right": "x=W-w-{M}:y=H-h-{M}",
    "center": "x=(W-w)/2:y=(H-h)/2",
}

# Audio spectrum palettes. "color" is the showwaves colors= name; "mix" is a
# colorchannelmixer matrix that remaps RGB (alpha untouched) for the other
# styles. Weights follow Rec.601 luma so white = grayscale of the bars.
_PALETTES = {
    "white": {
        "color": "white",
        "mix": "rr=0.299:rg=0.587:rb=0.114:gr=0.299:gg=0.587:gb=0.114:br=0.299:bg=0.587:bb=0.114",
    },
    "green": {
        "color": "green",
        "mix": "rr=0:rg=0:rb=0:gr=0.299:gg=0.587:gb=0.114:br=0:bg=0:bb=0",
    },
    "amber": {
        "color": "orange",
        "mix": "rr=0.299:rg=0.587:rb=0.114:gr=0.18:gg=0.35:gb=0.07:br=0:bg=0:bb=0",
    },
    "cyan": {
        "color": "cyan",
        "mix": "rr=0:rg=0:rb=0:gr=0.299:gg=0.587:gb=0.114:br=0.299:bg=0.587:bb=0.114",
    },
}


@dataclass
class RenderInputs:
    footage: str
    narration: str
    particles: str | None = None
    watermark: str | None = None
    card: str | None = None
    subscribe: str | None = None
    subtitle_ass: str | None = None
    out_path: str = "output.mp4"


@dataclass
class RenderOpts:
    width: int = 1280
    height: int = 720
    fps: int = 30
    motion: str = "slow_drift"      # none | slow_drift | slow_zoom
    motion_intensity: float = 1.0   # 0..3 multiplier on pan range + speed
    watermark_position: str = "top-right"
    watermark_opacity: float = 0.85
    particles_opacity: float = 1.0
    particles_enabled: bool = True
    watermark_enabled: bool = True
    subtitle_enabled: bool = True
    encoder: str = "auto"           # auto | nvenc | x264
    crf: int = 20
    preset: str = "medium"
    audio_bitrate: str = "192k"
    video_bitrate: str = "6M"         # target; nvenc vbr needs a finite cap
    video_maxrate: str = "8M"
    video_bufsize: str = "12M"
    margin: int = 0
    spectrum_enabled: bool = False
    spectrum_style: str = "cqt"       # cqt | spectrum | waves | vectorscope
    spectrum_position: str = "bottom"  # bottom | center
    spectrum_height: int = 0          # 0 = auto (20% of height)
    spectrum_opacity: float = 0.9
    spectrum_color: str = "intensity"  # showspectrum only
    card_enabled: bool = False        # thumbnail + title card overlay
    spectrum_palette: str = "white"   # white | green | amber | cyan
    subscribe_enabled: bool = False   # animated subscribe pill under watermark
    subscribe_appear: float = 3.0     # seconds in (bounce-in trigger)
    subscribe_sway_px: int = 6        # vertical sway amplitude
    subscribe_sway_period: float = 2.5  # seconds per sway cycle
    subscribe_gap: int = 10           # px below the watermark badge
    subscribe_size: tuple[int, int] | None = None  # tight-crop pill (w, h)
    watermark_geometry: tuple[int, int, int, int, str, str] | None = None
    # (ax, ay, w, h, halign, valign) from render_watermark; None = fallback


@dataclass
class RenderResult:
    path: str
    width: int = 0
    height: int = 0
    duration: float = 0.0
    has_audio: bool = False


class Composer:
    def __init__(self, ff: FFRunner | None = None):
        self.ff = ff or FFRunner()

    def build_args(
        self, inputs: RenderInputs, opts: RenderOpts, duration: float
    ) -> list[str]:
        ff = self.ff
        W, H, FPS = opts.width, opts.height, opts.fps
        args: list[str] = [ff.ffmpeg, "-y", "-v", "error", "-hide_banner"]

        # input 0: footage (infinite loop, audio discarded)
        args += ["-stream_loop", "-1", "-i", inputs.footage]
        # input 1: narration audio
        args += ["-i", inputs.narration]
        ni = 2
        # input 2: particle overlay (infinite loop, has alpha)
        if opts.particles_enabled:
            if not inputs.particles or not os.path.isfile(inputs.particles):
                raise FileNotFoundError(
                    f"particles enabled but overlay missing: {inputs.particles!r}"
                )
            args += ["-stream_loop", "-1", "-i", inputs.particles]
            part_idx = ni
            ni += 1
        else:
            part_idx = None
        # input 3: watermark PNG (looped single frame)
        if opts.watermark_enabled and inputs.watermark and os.path.isfile(inputs.watermark):
            args += ["-loop", "1", "-i", inputs.watermark]
            wm_idx = ni
            ni += 1
        else:
            wm_idx = None
        # input 4: card PNG (thumbnail + title, single frame)
        if opts.card_enabled:
            if not inputs.card or not os.path.isfile(inputs.card):
                raise FileNotFoundError(
                    f"card enabled but overlay missing: {inputs.card!r}"
                )
            args += ["-loop", "1", "-i", inputs.card]
            card_idx = ni
            ni += 1
        else:
            card_idx = None
        # input 5: subscribe pill PNG (single frame, tight-cropped)
        if opts.subscribe_enabled:
            if not inputs.subscribe or not os.path.isfile(inputs.subscribe):
                raise FileNotFoundError(
                    f"subscribe enabled but pill missing: {inputs.subscribe!r}"
                )
            args += ["-loop", "1", "-i", inputs.subscribe]
            sub_idx = ni
            ni += 1
        else:
            sub_idx = None

        # --- video chain -------------------------------------------------
        chain = []
        # filter-graph labels are handed out in fixed order so the graph is
        # identical when optional overlays are disabled
        label_n = 0

        def next_label() -> str:
            nonlocal label_n
            label_n += 1
            return f"[v{label_n}]"
        # cover-fit to target geometry
        chain.append(
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H}"
        )
        # stabilize frame rate before any motion crop (so 'n' ticks per output frame)
        chain.append(f"fps={FPS},format=yuv420p,setsar=1")

        if opts.motion in ("slow_drift", "slow_zoom"):
            # intensity scales both the pan range and the oscillation speed;
            # 1.0 reproduces the classic slow drift, 2.0 = twice as fast and
            # wider. Clamp >0: the period divides by it.
            k = max(0.05, min(opts.motion_intensity, 3.0) if opts.motion_intensity else 1.0)
            drift = opts.motion == "slow_drift"
            if drift:
                up = 1.0 + 0.15 * k
                uw, uh = int(W * up), int(H * up)
                # sinusoidal periods scale inversely with intensity
                px = max(30, round(290 / k))
                py = max(30, round(360 / k))
                x = f"(iw-{W})*(0.5+0.5*sin(n/{px}))"
                y = f"(ih-{H})*(0.5+0.5*cos(n/{py}))"
                chain.append(f"scale={uw}:{uh}:flags=lanczos,crop={W}:{H}:x='{x}':y='{y}'")
            else:
                # breathing zoom: crop box shrinks/grows around center
                up = 1.0 + 0.15 * k
                uw, uh = int(W * up), int(H * up)
                amp = round(0.25 * k, 3)
                per = max(30, round(215 / k))
                w = f"{W}*(1.0+{amp}*(1+sin(n/{per}))/2)"
                h = f"{H}*(1.0+{amp}*(1+sin(n/{per}))/2)"
                chain.append(
                    f"scale={uw}:{uh}:flags=lanczos,"
                    f"crop=w='{w}':h='{h}':x='(iw-out_w)/2':y='(ih-out_h)/2',"
                    f"scale={W}:{H}:flags=lanczos"
                )

        base_label = "[base]"
        graph_parts = [f"[0:v]{','.join(chain)}{base_label}"]
        prev = base_label

        # watermark overlay
        if wm_idx is not None:
            pos = opts.watermark_position
            if pos not in POSITIONS:
                pos = "top-right"
            margin = opts.margin or max(16, int(H * 0.025))
            expr = POSITION_EXPR[pos].format(M=margin)
            op = opts.watermark_opacity
            graph_parts.append(
                f"[{wm_idx}:v]format=rgba,colorchannelmixer=aa={op}[wm]"
            )
            lab = next_label()
            graph_parts.append(
                f"{prev}[wm]overlay={expr}:enable='gte(t,0.5)':format=auto{lab}"
            )
            prev = lab

        # particle overlay
        if part_idx is not None:
            op = opts.particles_opacity
            graph_parts.append(
                f"[{part_idx}:v]format=rgba,colorchannelmixer=aa={op}[pt]"
            )
            lab = next_label()
            graph_parts.append(f"{prev}[pt]overlay=0:0:format=auto{lab}")
            prev = lab

        # card overlay (thumbnail + title; opacity is baked into the PNG)
        if card_idx is not None:
            graph_parts.append(f"[{card_idx}:v]format=rgba[card]")
            lab = next_label()
            graph_parts.append(f"{prev}[card]overlay=0:0:format=auto{lab}")
            prev = lab

        # subscribe pill: bounce-in at t=appear, then vertical sway until end.
        # Bounce is a damped cosine from +bounce_px (below rest); sway runs
        # forever. enable= gates the whole overlay so t<appear is pixel-clean.
        if sub_idx is not None:
            if not opts.subscribe_size:
                raise ValueError("subscribe_enabled requires subscribe_size (w, h)")
            graph_parts.append(f"[{sub_idx}:v]format=rgba[sub]")
            sw, _sh = opts.subscribe_size
            sx, sy = self._subscribe_pos(opts, sw)
            A = opts.subscribe_appear
            bounce = 16  # px below rest at t=A, decays in ~2s
            y_expr = (
                f"{sy}+{bounce}*exp(-4*(t-{A}))*cos(2*PI*(t-{A})/0.5)"
                f"+{opts.subscribe_sway_px}*sin(2*PI*t/{opts.subscribe_sway_period})"
            )
            lab = next_label()
            graph_parts.append(
                f"{prev}[sub]overlay={sx}:y='{y_expr}':enable='gte(t,{A})':format=auto{lab}"
            )
            prev = lab

        # audio spectrum visualizer (drawn under the subtitles)
        if opts.spectrum_enabled:
            Hs = opts.spectrum_height or int(H * 0.2)
            style = opts.spectrum_style
            palette = opts.spectrum_palette or "white"
            if palette not in _PALETTES:
                palette = "white"
            # avectorscope renders a lissajous: square canvas keeps it round
            Ws = Hs if style == "vectorscope" else W
            # showspectrum/showcqt take fps=, showwaves/avectorscope take rate=
            rate = "fps" if style in ("cqt", "spectrum") else "rate"
            if style == "cqt":
                spec = f"showcqt=s={Ws}x{Hs}:{rate}={FPS}:axis=0"
            elif style == "spectrum":
                spec = f"showspectrum=s={Ws}x{Hs}:{rate}={FPS}"
            elif style == "waves":
                # default point mode is ~invisible in a short strip; the
                # centered line reads at low heights. colors= sets the
                # palette natively (full brightness).
                spec = f"showwaves=s={Ws}x{Hs}:{rate}={FPS}:mode=cline:colors={_PALETTES[palette]['color']}"
            else:
                spec = f"avectorscope=s={Ws}x{Hs}:{rate}={FPS}"
            # showspectrum/showcqt emit opaque RGB (no alpha plane): deriving
            # alpha from luma keeps the bars and drops the black background,
            # otherwise the overlay paints a solid box over the footage.
            # Their background luma is exactly 16, so (lum-16)*4 zeroes the
            # background while making bars solid. Forcing r=g=b=255 makes the
            # bars pure white (a lum= expr leaves chroma planes untouched and
            # tints the result). waves/avectorscope already carry an alpha
            # channel encoding the signal, so their mask reuses alpha(X,Y).
            if style in ("cqt", "spectrum"):
                spec += (
                    ",format=rgba,"
                    "geq=r='255':g='255':b='255':a='clip((r(X,Y)-16)*4,0,255)'"
                )
            else:
                spec += (
                    ",format=rgba,"
                    "geq=r='255':g='255':b='255':a='clip(alpha(X,Y)*4,0,255)'"
                )
            # remap RGB to the palette via channel weights; alpha untouched
            mix = _PALETTES[palette]["mix"]
            op = opts.spectrum_opacity
            graph_parts.append(
                f"[1:a]asplit=2[araw][spec]"
            )
            graph_parts.append(
                f"[araw]aresample=48000,volume=1.0[aout]"
            )
            graph_parts.append(
                f"[spec]{spec},colorchannelmixer={mix}:aa={op}[specv]"
            )
            sy = H - Hs if opts.spectrum_position == "bottom" else (H - Hs) // 2
            sx = (W - Ws) // 2
            lab = next_label()
            graph_parts.append(f"{prev}[specv]overlay={sx}:{sy}:format=auto{lab}")
            prev = lab

        # subtitles (karaoke ASS)
        if opts.subtitle_enabled and inputs.subtitle_ass and os.path.isfile(inputs.subtitle_ass):
            ass = inputs.subtitle_ass.replace("\\", "/").replace(":", r"\:")
            lab = next_label()
            graph_parts.append(f"{prev}subtitles='{ass}'{lab}")
            prev = lab

        # map final video label
        args += ["-filter_complex", ";".join(graph_parts), "-map", prev]

        # --- audio chain -------------------------------------------------
        if opts.spectrum_enabled:
            # -af is illegal for streams fed from filter_complex, so the
            # resample/volume moves into the graph; the spectrum takes the
            # other half of the asplit.
            args += ["-map", "[aout]"]
        else:
            args += ["-map", "1:a", "-af", "aresample=48000,volume=1.0"]

        # --- encode ------------------------------------------------------
        enc = self._pick_encoder(opts.encoder)
        if enc == "h264_nvenc":
            # vbr with -b:v 0 is quality-only and unbounded: particle overlays
            # are high-entropy, so the rate explodes without an explicit cap.
            args += [
                "-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr",
                "-cq", str(opts.crf + 2), "-b:v", opts.video_bitrate,
                "-maxrate", opts.video_maxrate, "-bufsize", opts.video_bufsize,
                "-pix_fmt", "yuv420p",
            ]
        else:
            args += [
                "-c:v", "libx264", "-preset", opts.preset, "-crf", str(opts.crf),
                "-maxrate", opts.video_maxrate, "-bufsize", opts.video_bufsize,
                "-pix_fmt", "yuv420p",
            ]
        args += ["-c:a", "aac", "-b:a", opts.audio_bitrate, "-ac", "2"]
        args += ["-t", f"{duration:.3f}", "-movflags", "+faststart"]
        args += ["-r", str(FPS)]
        args += [inputs.out_path]
        return args

    @staticmethod
    def _subscribe_pos(opts: "RenderOpts", sub_w: int) -> tuple[int, int]:
        """Pill anchor (x, y0): centered under a top watermark, else top-right."""
        W, H = opts.width, opts.height
        margin = opts.margin or max(16, int(H * 0.025))
        wg = opts.watermark_geometry
        if wg and len(wg) >= 6 and wg[5] == "top":
            ax, ay, wm_w, wm_h = wg[0], wg[1], wg[2], wg[3]
            return ax + (wm_w - sub_w) // 2, ay + wm_h + opts.subscribe_gap
        return W - sub_w - margin, margin

    def _pick_encoder(self, choice: str) -> str:
        if choice == "nvenc":
            return "h264_nvenc"
        if choice == "x264":
            return "libx264"
        # auto: only trust nvenc after a real encode smoke test — a build can
        # advertise h264_nvenc with no GPU/driver present (nvcuda.dll missing).
        return "h264_nvenc" if self._nvenc_works() else "libx264"

    _nvenc_cache: dict[str, bool] = {}

    def _nvenc_works(self) -> bool:
        key = self.ff.ffmpeg
        if key in self._nvenc_cache:
            return self._nvenc_cache[key]
        works = False
        try:
            if self.ff.supports_nvenc():
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    probe_path = tmp.name
                self.ff.run(
                    [
                        self.ff.ffmpeg, "-y", "-v", "error", "-hide_banner",
                        "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1:r=10",
                        "-c:v", "h264_nvenc", "-f", "mp4", probe_path,
                    ],
                    check=False,
                )
                works = os.path.isfile(probe_path) and os.path.getsize(probe_path) > 0
                try:
                    os.remove(probe_path)
                except OSError:
                    pass
        except Exception:
            works = False
        self._nvenc_cache[key] = works
        print(f"[composer] h264_nvenc usable: {works}", flush=True)
        return works

    def render(
        self, inputs: RenderInputs, opts: RenderOpts, duration: float
    ) -> RenderResult:
        args = self.build_args(inputs, opts, duration)
        self.ff.run(args)
        info = self.ff.probe(inputs.out_path)
        return RenderResult(
            path=inputs.out_path,
            width=info.get("width", 0),
            height=info.get("height", 0),
            duration=info.get("duration", 0.0),
            has_audio=info.get("has_audio", False),
        )


__all__ = ["Composer", "RenderInputs", "RenderOpts", "RenderResult"]
