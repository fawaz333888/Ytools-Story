"""FFmpeg binary discovery, encoder detection, and subprocess runner."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Optional


class FFmpegNotFound(RuntimeError):
    pass


def find_ffmpeg() -> str:
    """Resolve an ffmpeg binary path.

    Order: YTOOLS_FFMPEG env -> imageio-ffmpeg bundle -> PATH.
    imageio-ffmpeg is preferred over a random PATH install because it is a
    full GPL build (drawtext/libass/nvenc included), which is what the
    composer's filter graph needs.
    """
    env = os.environ.get("YTOOLS_FFMPEG")
    if env and os.path.isfile(env):
        return env

    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and os.path.isfile(bundled):
            return bundled
    except Exception:  # pragma: no cover - imageio not installed
        pass

    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path

    raise FFmpegNotFound(
        "no ffmpeg found. Install with: pip install imageio-ffmpeg\n"
        "or set YTOOLS_FFMPEG=/path/to/ffmpeg"
    )


def find_ffprobe() -> Optional[str]:
    env = os.environ.get("YTOOLS_FFPROBE")
    if env and os.path.isfile(env):
        return env
    return shutil.which("ffprobe") or None


class FFRunner:
    def __init__(self, ffmpeg: str | None = None, ffprobe: str | None = None):
        self.ffmpeg = ffmpeg or find_ffmpeg()
        self.ffprobe = ffprobe or find_ffprobe()

    def version(self) -> str:
        out = self._run([self.ffmpeg, "-version"])["stdout"]
        return out.splitlines()[0] if out else "unknown"

    def _run(self, cmd: list[str]) -> dict:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

    def run(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
        if check and proc.returncode != 0:
            tail = (proc.stderr or "")[-3000:]
            raise RuntimeError(
                f"ffmpeg exited {proc.returncode}\ncommand: {' '.join(map(str, cmd))}\n{tail}"
            )
        return proc

    def has(self, kind: str, name: str) -> bool:
        """Check a filter (-filters) or encoder (-encoders) by exact name."""
        flag = "-filters" if kind == "filter" else "-encoders"
        out = self._run([self.ffmpeg, "-hide_banner", flag])["stdout"]
        for line in out.splitlines():
            # ' T.C drawtext          V->V  ...'
            parts = line.split()
            if len(parts) >= 2 and parts[1] == name:
                return True
        return False

    def supports_nvenc(self) -> bool:
        try:
            return self.has("encoder", "h264_nvenc")
        except Exception:
            return False

    def probe(self, path: str) -> dict:
        """Minimal stream probe: width, height, fps, duration, has_audio.

        Falls back to parsing `ffmpeg -i` output when ffprobe is unavailable
        (e.g. when only the imageio-ffmpeg bundle is installed).
        """
        if self.ffprobe:
            return self._probe_ffprobe(path)
        return self._probe_ffmpeg(path)

    def _probe_ffprobe(self, path: str) -> dict:
        proc = self.run(
            [
                self.ffprobe, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,avg_frame_rate,duration",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1", path,
            ]
        )
        info: dict = {"width": 0, "height": 0, "fps": 0.0, "duration": 0.0}
        for line in (proc.stdout or "").splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k == "width":
                info["width"] = int(v)
            elif k == "height":
                info["height"] = int(v)
            elif k == "avg_frame_rate":
                num, _, den = v.partition("/")
                try:
                    info["fps"] = float(num) / float(den) if float(den) else 0.0
                except ValueError:
                    info["fps"] = 0.0
            elif k == "duration":
                if info["duration"] == 0.0:
                    info["duration"] = float(v)
        aproc = self.run(
            [self.ffprobe, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=index", "-of", "csv=p=0", path],
            check=False,
        )
        info["has_audio"] = (aproc.stdout or "").strip() != ""
        return info

    def _probe_ffmpeg(self, path: str) -> dict:
        # ffmpeg exits non-zero when given only an input, so don't check.
        proc = self._run([self.ffmpeg, "-hide_banner", "-i", path])
        text = proc["stderr"] or ""
        info = {"width": 0, "height": 0, "fps": 0.0, "duration": 0.0, "has_audio": False}
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", text)
        if m:
            info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        m = re.search(r"Stream #\d+:\d+.*Video:.*,\s*(\d+)x(\d+)", text)
        if m:
            info["width"], info["height"] = int(m.group(1)), int(m.group(2))
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:fps|tbr)", text)
        if m:
            info["fps"] = float(m.group(1))
        info["has_audio"] = "Audio:" in text
        return info
