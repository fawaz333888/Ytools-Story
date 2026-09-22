"""Pipeline: story -> tts -> overlays -> compose."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable

from .config import Config
from .overlays import card as card_mod
from .overlays import particles as particles_mod
from .overlays import subtitle as subtitle_mod
from .overlays import watermark as watermark_mod
from .render.composer import Composer, RenderInputs, RenderOpts, RenderResult
from .render.ffutil import FFRunner
from .story import generator as story_gen
from .tts import edge as tts_edge


@dataclass
class PipelineArtifacts:
    script_path: str = ""
    narration_path: str = ""
    words: list = field(default_factory=list)
    duration: float = 0.0
    particles_path: str = ""
    watermark_path: str = ""
    card_path: str = ""
    title: str = ""
    subtitle_path: str = ""
    result: RenderResult | None = None


class Pipeline:
    def __init__(
        self,
        workdir: str,
        config: Config,
        ff: FFRunner | None = None,
        on_stage: Callable[[str], None] | None = None,
    ):
        self.workdir = workdir
        self.cfg = config
        self.ff = ff or FFRunner()
        self.artifacts = PipelineArtifacts()
        self._stage = on_stage or (lambda msg: None)
        os.makedirs(workdir, exist_ok=True)

    def stage(self, msg: str) -> None:
        print(f"[pipeline] {msg}", flush=True)
        self._stage(msg)

    def run(
        self,
        footage: str,
        script_path: str | None = None,
        skip_particles: bool = False,
    ) -> PipelineArtifacts:
        a = self.artifacts

        # 1. script
        if script_path and os.path.isfile(script_path):
            with open(script_path, encoding="utf-8") as fh:
                story = fh.read()
            self.stage(f"script loaded from {script_path}")
        else:
            language = self.cfg.get("story.language", "id")
            self.stage(
                f"generating story (provider={self.cfg.get('story.provider')}, "
                f"niche={self.cfg.get('story.niche')}, lang={language})"
            )
            story = story_gen.generate(
                provider=self.cfg.get("story.provider"),
                niche=self.cfg.get("story.niche"),
                topic=self.cfg.get("story.topic", ""),
                minutes=self.cfg.get("story.length_minutes", 3),
                language=language,
                model=self.cfg.get("story.model"),
                api_key_env=self.cfg.get("story.api_key_env"),
                base_url=self.cfg.get("story.base_url", "") or "",
                seed=self.cfg.get("story.seed"),
            )
        a.script_path = os.path.join(self.workdir, "script.txt")
        with open(a.script_path, "w", encoding="utf-8") as fh:
            fh.write(story)

        # 2. tts
        # voice must match the story language; otherwise auto-pick the default.
        language = self.cfg.get("story.language", "id")
        voice = self.cfg.get("tts.voice") or ""
        if not voice or not voice.lower().startswith(f"{language}-"):
            voice = story_gen.default_voice(language)
        self.stage(
            f"tts (voice={voice}, {len(story.split())} words)"
        )
        tts_dir = os.path.join(self.workdir, "tts")
        res = tts_edge.synthesize(
            story,
            tts_dir,
            voice=voice,
            rate=self.cfg.get("tts.rate", "+0%"),
            volume=self.cfg.get("tts.volume", "+0%"),
            pitch=self.cfg.get("tts.pitch", "+0Hz"),
            on_progress=lambda i, n: self._stage(f"  tts chunk {i}/{n}"),
        )
        a.narration_path = res.audio_path
        a.words = res.words
        a.duration = res.duration
        self.stage(f"narration {a.duration:.1f}s, {len(a.words)} words")

        W = self.cfg.get("video.width")
        H = self.cfg.get("video.height")
        FPS = self.cfg.get("video.fps")

        # 3. particles
        if not skip_particles and self.cfg.get("overlays.particles.enabled"):
            style = self.cfg.get("overlays.particles.style", "dust")
            density = self.cfg.get("overlays.particles.density", 120)
            part_opacity = self.cfg.get("overlays.particles.opacity", 1.0)
            part_size = self.cfg.get("overlays.particles.size", 1.0)
            loop_seconds = self.cfg.get("overlays.particles.loop_seconds", 8.0)
            # cache key must include every param that changes the render,
            # otherwise a density/size tweak silently reuses the stale overlay.
            # opacity is applied by the composer (colorchannelmixer), not baked
            # into the mov, so changing it reuses this cache without a re-render
            part_name = (
                f"particles_{style}_{W}x{H}_{FPS}fps_{loop_seconds}s"
                f"_n{density}_s{part_size}.mov"
            )
            a.particles_path = os.path.join(self.workdir, part_name)
            if not os.path.isfile(a.particles_path):
                self._prune_cache("particles_", style, part_name)
                self.stage(f"rendering particles ({style}, n={density}, size={part_size})")
                particles_mod.render_particles(
                    a.particles_path,
                    style=style,
                    width=W,
                    height=H,
                    fps=FPS,
                    loop_seconds=loop_seconds,
                    density=density,
                    size_mult=part_size,
                    workdir=os.path.join(self.workdir, "pframes"),
                    ff=self.ff,
                )
            else:
                self.stage("particles cached")

        # 4. watermark
        if self.cfg.get("overlays.watermark.enabled"):
            wm_style = self.cfg.get("overlays.watermark.style", "badge")
            wm_text = self.cfg.get("overlays.watermark.text", "@channel")
            wm_position = self.cfg.get("overlays.watermark.position", "top-right")
            wm_opacity = self.cfg.get("overlays.watermark.opacity", 0.85)
            wm_font_size = self.cfg.get("overlays.watermark.font_size", 0)
            wm_logo = self.cfg.get("overlays.watermark.logo_path")
            safe_text = "".join(c if c.isalnum() or c in "-_." else "_" for c in wm_text)[:24]
            logo_tag = os.path.splitext(os.path.basename(wm_logo or ""))[0][:20] or "nologo"
            wm_name = (
                f"watermark_{wm_style}_{safe_text}_{wm_position}"
                f"_o{wm_opacity}_f{wm_font_size}_{logo_tag}_{W}x{H}.png"
            )
            a.watermark_path = os.path.join(self.workdir, wm_name)
            if not os.path.isfile(a.watermark_path):
                self._prune_cache("watermark_", wm_style, wm_name)
                self.stage(f"rendering watermark ({wm_style})")
                watermark_mod.render_watermark(
                    a.watermark_path,
                    text=wm_text,
                    style=wm_style,
                    logo_path=wm_logo,
                    position=wm_position,
                    width=W,
                    height=H,
                    opacity=wm_opacity,
                    font_size=wm_font_size,
                    font_path=self.cfg.get("overlays.watermark.font", ""),
                )
            else:
                self.stage("watermark cached")

        # 5. card (thumbnail + title)
        if self.cfg.get("overlays.card.enabled"):
            thumb = self.cfg.get("overlays.card.thumbnail_path")
            if not thumb or not os.path.isfile(thumb):
                raise FileNotFoundError(f"card enabled but thumbnail missing: {thumb!r}")
            title = (self.cfg.get("overlays.card.title") or "").strip()
            if not title and self.cfg.get("story.provider") != "manual":
                # LLM title uses the finished story as context so it stays
                # accurate to the narration
                self.stage("generating title (LLM)")
                title = story_gen.generate_title(
                    provider=self.cfg.get("story.provider"),
                    story=story,
                    niche=self.cfg.get("story.niche", "custom"),
                    language=language,
                    model=self.cfg.get("story.model"),
                    api_key_env=self.cfg.get("story.api_key_env"),
                    base_url=self.cfg.get("story.base_url", "") or "",
                )
            a.title = title
            card_opacity = self.cfg.get("overlays.card.opacity", 1.0)
            safe_title = (
                "".join(c if c.isalnum() or c in "-_." else "_" for c in title)[:40]
                or "notitle"
            )
            thumb_tag = os.path.splitext(os.path.basename(thumb))[0][:20]
            card_name = (
                f"card_{safe_title}_{W}x{H}_o{card_opacity}_{thumb_tag}.png"
            )
            a.card_path = os.path.join(self.workdir, card_name)
            if not os.path.isfile(a.card_path):
                self._prune_cache("card_", "", card_name)
                self.stage(f"rendering card (title={title[:40]!r})")
                card_mod.render_card(
                    a.card_path,
                    title=title,
                    thumbnail_path=thumb,
                    width=W,
                    height=H,
                    opacity=card_opacity,
                    title_size=self.cfg.get("overlays.card.title_size", 0),
                    font_path=self.cfg.get("overlays.card.font", ""),
                )
            else:
                self.stage("card cached")

        # 6. subtitles
        if self.cfg.get("overlays.subtitle.enabled"):
            self.stage("building karaoke subtitles")
            sub_style = self.cfg.get("overlays.subtitle.style", "karaoke")
            ass_text = subtitle_mod.build_ass(
                a.words,
                style=sub_style,
                width=W,
                height=H,
                font_size=self.cfg.get("overlays.subtitle.font_size", 0),
                max_chars=self.cfg.get("overlays.subtitle.max_chars", 34),
                margin_v=self.cfg.get("overlays.subtitle.margin_v", 60),
                position=self.cfg.get("overlays.subtitle.position", "bottom"),
                font_path=self.cfg.get("overlays.subtitle.font", ""),
            )
            a.subtitle_path = os.path.join(self.workdir, "subtitle.ass")
            with open(a.subtitle_path, "w", encoding="utf-8") as fh:
                fh.write(ass_text)

        # 7. compose
        self.stage("composing final video")
        composer = Composer(self.ff)
        inputs = RenderInputs(
            footage=footage,
            narration=a.narration_path,
            particles=a.particles_path,
            watermark=a.watermark_path,
            card=a.card_path,
            subtitle_ass=a.subtitle_path,
            out_path=self._out_path(),
        )
        opts = RenderOpts(
            width=W,
            height=H,
            fps=FPS,
            motion=self.cfg.get("video.motion", "slow_drift"),
            watermark_position=self.cfg.get("overlays.watermark.position", "top-right"),
            watermark_opacity=self.cfg.get("overlays.watermark.opacity", 0.85),
            particles_opacity=self.cfg.get("overlays.particles.opacity", 1.0),
            particles_enabled=self.cfg.get("overlays.particles.enabled", True),
            watermark_enabled=self.cfg.get("overlays.watermark.enabled", True),
            subtitle_enabled=self.cfg.get("overlays.subtitle.enabled", True),
            encoder=self.cfg.get("output.encoder", "auto"),
            crf=self.cfg.get("output.crf", 20),
            preset=self.cfg.get("output.preset", "medium"),
            audio_bitrate=self.cfg.get("output.audio_bitrate", "192k"),
            video_bitrate=self.cfg.get("output.video_bitrate", "6M"),
            video_maxrate=self.cfg.get("output.video_maxrate", "8M"),
            video_bufsize=self.cfg.get("output.video_bufsize", "12M"),
            spectrum_enabled=self.cfg.get("overlays.spectrum.enabled", False),
            spectrum_style=self.cfg.get("overlays.spectrum.style", "cqt"),
            spectrum_position=self.cfg.get("overlays.spectrum.position", "bottom"),
            spectrum_height=self.cfg.get("overlays.spectrum.height", 0),
            spectrum_opacity=self.cfg.get("overlays.spectrum.opacity", 0.9),
            spectrum_palette=self.cfg.get("overlays.spectrum.palette", "white"),
            card_enabled=self.cfg.get("overlays.card.enabled", False),
        )
        a.result = composer.render(inputs, opts, a.duration)
        self.stage(
            f"done: {a.result.path} {a.result.width}x{a.result.height} "
            f"{a.result.duration:.1f}s audio={a.result.has_audio}"
        )
        return a

    def _out_path(self) -> str:
        outdir = self.cfg.get("output.dir", "output")
        os.makedirs(outdir, exist_ok=True)
        return os.path.join(outdir, "video.mp4")

    def _prune_cache(self, prefix: str, style: str, current: str) -> None:
        """Delete stale cached overlays of the same style that no longer match
        the current parameters, so the workdir does not accumulate old renders
        (matters on Colab where disk is limited)."""
        try:
            for fname in os.listdir(self.workdir):
                if fname.startswith(f"{prefix}{style}_") and fname != current:
                    os.remove(os.path.join(self.workdir, fname))
        except OSError:
            pass


__all__ = ["Pipeline", "PipelineArtifacts"]
