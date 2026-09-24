"""Config loading/validation with defaults."""

from __future__ import annotations

import copy
import os
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "story": {
        "provider": "manual",       # manual | openai | anthropic
        "niche": "horror",           # horror | motivation | education | drama | custom
        "topic": "",
        "language": "id",            # id | en
        "length_minutes": 3,
        "model": "gpt-4o-mini",
        "base_url": "",            # kosong = endpoint resmi; isi untuk OpenAI-compatible
        "api_key_env": "OPENAI_API_KEY",
        "seed": None,
    },
    "tts": {
        "voice": "",                 # "" = auto by story.language
        "rate": "+0%",
        "volume": "+0%",
        "pitch": "+0Hz",
    },
    "video": {
        "width": 1280,
        "height": 720,
        "fps": 30,
        "motion": "slow_drift",      # none | slow_drift | slow_zoom
        "motion_intensity": 1.0,     # 0..2 multiplier
    },
    "overlays": {
        "watermark": {
            "enabled": True,
            "text": "@YtoolsChannel",
            "style": "badge",        # badge | plain | logo
            "logo_path": None,       # PNG with alpha, used when style=logo
            "position": "top-right", # top-left|top-right|bottom-left|bottom-right|center
            "opacity": 0.85,
            "font_size": 0,          # 0 = autoscale from height
        },
        "particles": {
            "enabled": True,
            "style": "dust",         # dust|snow|sparkle|fireflies|embers|fog
            "density": 120,          # jumlah titik per frame
            "size": 1.0,             # ukuran titik multiplier (1.0 = default; 3.0 = 3x lebih besar)
            "loop_seconds": 8.0,
            "opacity": 1.0,
        },
        "subtitle": {
            "enabled": True,
            "style": "karaoke",      # karaoke | simple
            "font": "",              # path to .ttf; "" = autodetect
            "font_size": 0,          # 0 = autoscale
            "position": "bottom",    # bottom | center
            "max_chars": 34,         # wrap width
            "margin_v": 60,
        },
        "spectrum": {
            "enabled": False,
            "style": "cqt",          # cqt | spectrum | waves | vectorscope
            "position": "bottom",    # bottom | center
            "height": 0,             # 0 = auto (20% of video height)
            "opacity": 0.9,
            "palette": "white",      # white | green | amber | cyan
        },
        "card": {
            "enabled": False,
            "title": "",             # kosong + provider LLM = judul dari LLM
            "thumbnail_path": None,  # wajib diisi (path image) kalau enabled
            "opacity": 1.0,
            "title_size": 0,         # 0 = auto
        },
        "subscribe": {
            "enabled": False,
            "text": "SUBSCRIBE",     # teks pill
            "appear": 3.0,           # detik muncul (bounce-in)
            "sway_px": 6,            # amplitudo goyangan vertikal
            "sway_period": 2.5,      # detik per siklus goyangan
            "gap": 10,               # jarak ke bawah watermark (px)
            "font_size": 0,          # 0 = autoscale dari height
        },
    },
    "output": {
        "dir": "output",
        "encoder": "auto",           # auto | nvenc | x264
        "crf": 20,
        "preset": "medium",
        "audio_bitrate": "192k",
        "video_bitrate": "6M",        # target video bitrate; ~135MB per 3 min
        "video_maxrate": "8M",
        "video_bufsize": "12M",
    },
}


def _deep_merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


class Config:
    def __init__(self, data: dict | None = None):
        self.data = copy.deepcopy(DEFAULTS)
        if data:
            _deep_merge(self.data, data)

    @classmethod
    def from_file(cls, path: str) -> "Config":
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        return cls(raw)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value: Any) -> None:
        node = self.data
        parts = dotted.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.get("story.provider") not in {"manual", "openai", "anthropic"}:
            problems.append("story.provider must be manual|openai|anthropic")
        if self.get("story.provider") == "openai" and not os.environ.get(
            self.get("story.api_key_env"), ""
        ):
            problems.append(
                f"story.provider=openai but env {self.get('story.api_key_env')} is unset"
            )
        w, h = self.get("video.width"), self.get("video.height")
        if not (128 <= w <= 7680) or not (128 <= h <= 4320):
            problems.append(f"implausible video size {w}x{h}")
        if self.get("video.fps") not in (24, 25, 30, 48, 50, 60):
            problems.append(f"video.fps={self.get('video.fps')} unusual (24/30/60 typical)")
        mi = self.get("video.motion_intensity")
        if not isinstance(mi, (int, float)) or not (0 <= float(mi) <= 3):
            problems.append(f"video.motion_intensity={mi} must be a number in 0..3")
        if self.get("overlays.spectrum.enabled"):
            if self.get("overlays.spectrum.style") not in {"cqt", "spectrum", "waves", "vectorscope"}:
                problems.append(
                    "overlays.spectrum.style must be cqt|spectrum|waves|vectorscope"
                )
            if self.get("overlays.spectrum.position") not in {"bottom", "center"}:
                problems.append("overlays.spectrum.position must be bottom|center")
            if self.get("overlays.spectrum.palette") not in {"white", "green", "amber", "cyan"}:
                problems.append("overlays.spectrum.palette must be white|green|amber|cyan")
        if self.get("overlays.subscribe.enabled"):
            sub_text = self.get("overlays.subscribe.text", "")
            if not isinstance(sub_text, str) or not sub_text.strip():
                problems.append("overlays.subscribe.text must be a non-empty string")
            ap = self.get("overlays.subscribe.appear", 3.0)
            if not isinstance(ap, (int, float)) or float(ap) < 0:
                problems.append(f"overlays.subscribe.appear={ap} must be a number >= 0")
            sp = self.get("overlays.subscribe.sway_period", 2.5)
            if not isinstance(sp, (int, float)) or float(sp) <= 0:
                problems.append(f"overlays.subscribe.sway_period={sp} must be > 0")
            sw = self.get("overlays.subscribe.sway_px", 6)
            if not isinstance(sw, (int, float)) or float(sw) < 0:
                problems.append(f"overlays.subscribe.sway_px={sw} must be >= 0")
        return problems

    def __repr__(self) -> str:  # pragma: no cover
        return f"Config({self.data!r})"


def example_config_yaml() -> str:
    return yaml.safe_dump(DEFAULTS, sort_keys=False, allow_unicode=True)
