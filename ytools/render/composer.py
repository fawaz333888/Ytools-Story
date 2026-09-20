"""Composer: build and run the final ffmpeg render.

Filter graph (per-frame, single ffmpeg pass):

  footage (looped, muted) -> cover-scale -> optional motion crop -> base
  base + watermark PNG -> base+wm
  base+wm + particle overlay (looped, alpha) -> base+fx
  base+fx + karaoke ASS (subtitles filter) -> final video
  narration wav -> resample -> AAC

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


@dataclass
class RenderInputs:
    footage: str
    narration: str
    particles: str | None = None
    watermark: str | None = None
    subtitle_ass: str | None = None
    out_path: str = "output.mp4"


@dataclass
class RenderOpts:
    width: int = 1280
    height: int = 720
    fps: int = 30
    motion: str = "slow_drift"      # none | slow_drift | slow_zoom
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
    margin: int = 0


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
        if opts.particles_enabled and inputs.particles and os.path.isfile(inputs.particles):
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

        # --- video chain -------------------------------------------------
        chain = []
        # cover-fit to target geometry
        chain.append(
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H}"
        )
        # stabilize frame rate before any motion crop (so 'n' ticks per output frame)
        chain.append(f"fps={FPS},format=yuv420p,setsar=1")

        if opts.motion in ("slow_drift", "slow_zoom"):
            # upscale 15%, then animate the crop box with frame counter 'n'
            up = 1.15
            uw, uh = int(W * up), int(H * up)
            drift = opts.motion == "slow_drift"
            # slow sinusoidal periods (~16s and ~20s at 30fps)
            if drift:
                x = f"(iw-{W})*(0.5+0.5*sin(n/290))"
                y = f"(ih-{H})*(0.5+0.5*cos(n/360))"
                chain.append(f"scale={uw}:{uh}:flags=lanczos,crop={W}:{H}:x='{x}':y='{y}'")
            else:
                # breathing zoom: crop box shrinks/grows around center
                w = f"{W}*(1.0+0.13*(1+sin(n/430))/2)"
                h = f"{H}*(1.0+0.13*(1+sin(n/430))/2)"
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
            graph_parts.append(
                f"{prev}[wm]overlay={expr}:enable='gte(t,0.5)':format=auto[v1]"
            )
            prev = "[v1]"

        # particle overlay
        if part_idx is not None:
            op = opts.particles_opacity
            graph_parts.append(
                f"[{part_idx}:v]format=rgba,colorchannelmixer=aa={op}[pt]"
            )
            graph_parts.append(f"{prev}[pt]overlay=0:0:format=auto[v2]")
            prev = "[v2]"

        # subtitles (karaoke ASS)
        if opts.subtitle_enabled and inputs.subtitle_ass and os.path.isfile(inputs.subtitle_ass):
            ass = inputs.subtitle_ass.replace("\\", "/").replace(":", r"\:")
            graph_parts.append(f"{prev}subtitles='{ass}'[v3]")
            prev = "[v3]"

        # map final video label
        args += ["-filter_complex", ";".join(graph_parts), "-map", prev]

        # --- audio chain -------------------------------------------------
        args += ["-map", "1:a", "-af", "aresample=48000,volume=1.0"]

        # --- encode ------------------------------------------------------
        enc = self._pick_encoder(opts.encoder)
        if enc == "h264_nvenc":
            args += [
                "-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr",
                "-cq", str(opts.crf + 2), "-b:v", "0",
                "-pix_fmt", "yuv420p",
            ]
        else:
            args += [
                "-c:v", "libx264", "-preset", opts.preset, "-crf", str(opts.crf),
                "-pix_fmt", "yuv420p",
            ]
        args += ["-c:a", "aac", "-b:a", opts.audio_bitrate, "-ac", "2"]
        args += ["-t", f"{duration:.3f}", "-movflags", "+faststart"]
        args += ["-r", str(FPS)]
        args += [inputs.out_path]
        return args

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
