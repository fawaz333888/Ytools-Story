"""Ytools CLI.

Usage:
  python -m ytools init                     # write example config + README notes
  python -m ytools run --footage vid.mp4    # full pipeline
  python -m ytools run --footage vid.mp4 --script story.txt
  python -m ytools run --footage vid.mp4 --niche horror --minutes 3
  python -m ytools voices                    # list Indonesian edge-tts voices
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from . import __version__
from .config import Config, example_config_yaml
from .pipeline import Pipeline
from .render.ffutil import FFmpegNotFound, FFRunner


def cmd_init(args: argparse.Namespace) -> int:
    path = args.config or "ytools_config.yaml"
    if os.path.exists(path) and not args.force:
        print(f"{path} already exists (use --force to overwrite)")
        return 1
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(example_config_yaml())
    print(f"wrote example config to {path}")
    return 0


def cmd_voices(args: argparse.Namespace) -> int:
    import edge_tts

    async def _list():
        voices = await edge_tts.list_voices()
        out = [v for v in voices if v["Locale"].startswith("id-ID")]
        if not out:
            print("no Indonesian voices found")
            return
        print("Indonesian edge-tts voices:")
        for v in out:
            cats = ",".join(v.get("VoiceTag", {}).get("ContentCategories", []))
            print(f"  {v['ShortName']:22s} {v['Gender']:6s} {cats}")

    asyncio.run(_list())
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg = _load_config(args)
    problems = cfg.validate()
    if problems and not args.allow_problems:
        print("config problems:")
        for p in problems:
            print("  -", p)
        print("fix config or pass --allow-problems")
        return 2

    footage = args.footage
    if not os.path.isfile(footage):
        print(f"footage not found: {footage}")
        return 2

    if args.script and not os.path.isfile(args.script):
        print(f"script not found: {args.script}")
        return 2

    workdir = args.workdir or os.path.join("ytools_work", "run")
    os.makedirs(workdir, exist_ok=True)

    try:
        ff = FFRunner()
        print(f"ffmpeg: {ff.version()}")
        if ff.supports_nvenc():
            print("encoder: h264_nvenc available (GPU)")
    except FFmpegNotFound as exc:
        print(str(exc))
        return 3

    pipe = Pipeline(workdir, cfg, ff=ff)
    if args.no_hook:
        cfg.set("story.add_hook", False)
    pipe.run(
        footage=footage,
        script_path=args.script,
    )
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    from .story import hook as hook_mod

    lines = hook_mod.generate_hooks(args.niche, args.language, count=args.count)
    print(f"hooks ({args.language}/{args.niche}):")
    for i, line in enumerate(lines, 1):
        print(f"  {i}. {line}")
    return 0


def _load_config(args: argparse.Namespace) -> Config:
    cfg = Config()
    if args.config and os.path.isfile(args.config):
        cfg = Config.from_file(args.config)
    # CLI overrides
    if args.niche:
        cfg.set("story.niche", args.niche)
    if args.topic:
        cfg.set("story.topic", args.topic)
    if args.language:
        cfg.set("story.language", args.language)
    if args.minutes:
        cfg.set("story.length_minutes", args.minutes)
    if args.voice:
        cfg.set("tts.voice", args.voice)
    if args.provider:
        cfg.set("story.provider", args.provider)
    if args.style:
        cfg.set("overlays.particles.style", args.style)
    if args.encoder:
        cfg.set("output.encoder", args.encoder)
    return cfg


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ytools", description="YouTube faceless automation")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="write example config")
    p_init.add_argument("--config", default="ytools_config.yaml")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="generate a video")
    p_run.add_argument("--footage", required=True, help="path to background footage video")
    p_run.add_argument("--script", help="optional ready-made narration script .txt")
    p_run.add_argument("--config", default="ytools_config.yaml")
    p_run.add_argument("--workdir", default=None)
    p_run.add_argument("--niche", choices=["horror", "motivation", "education", "drama", "custom"])
    p_run.add_argument("--language", choices=["id", "en"], default=None)
    p_run.add_argument("--topic", default=None)
    p_run.add_argument("--provider", choices=["manual", "openai", "anthropic"])
    p_run.add_argument("--no-hook", action="store_true", help="skip hook line")
    p_run.add_argument("--minutes", type=float, default=None)
    p_run.add_argument("--voice", default=None)
    p_run.add_argument("--style", default=None, help="particle style")
    p_run.add_argument("--encoder", choices=["auto", "nvenc", "x264"], default=None)
    p_run.add_argument("--allow-problems", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_voices = sub.add_parser("voices", help="list Indonesian TTS voices")
    p_voices.set_defaults(func=cmd_voices)

    p_hook = sub.add_parser("hook", help="generate hook line ideas")
    p_hook.add_argument("--niche", default="horror",
                        choices=["horror", "motivation", "education", "drama", "custom"])
    p_hook.add_argument("--language", choices=["id", "en"], default="id")
    p_hook.add_argument("--count", type=int, default=3)
    p_hook.set_defaults(func=cmd_hook)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
