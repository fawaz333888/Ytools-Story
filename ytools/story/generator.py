"""Story generation dispatch by provider and language."""

from __future__ import annotations

import math

from ..utils import clean_text, split_sentences
from . import llm

VALID_NICHES = {"horror", "motivation", "education", "drama", "custom"}
VALID_LANGS = {"id", "en"}

# Above this, a single LLM call risks upstream 502 (output too long), so the
# story is split into an outline + per-section calls.
LONG_MODE_THRESHOLD = 8
DEFAULT_SECTION_MINUTES = 5
WORDS_PER_MINUTE = 130
TAIL_WORDS = 500
MIN_TOTAL_FRACTION = 0.6
# Per-section pacing guard: trim sections that overshoot, at a sentence
# boundary (never mid-sentence). The last section keeps the ending, so it gets
# more slack or a story-closing trim would eat the twist.
SECTION_MAX_WORDS_FRACTION = 1.5
LAST_SECTION_MAX_WORDS_FRACTION = 2.0
TOPIC_MAX_ATTEMPTS = 2

# Default edge-tts voice per language when none is configured.
DEFAULT_VOICE = {
    "id": "id-ID-GadisNeural",
    "en": "en-US-AvaNeural",
}

LANG_LABEL = {
    "id": "Bahasa Indonesia",
    "en": "English",
}


def generate(
    provider: str,
    niche: str,
    topic: str = "",
    minutes: int = 3,
    language: str = "id",
    model: str = "gpt-4o-mini",
    api_key_env: str = "OPENAI_API_KEY",
    base_url: str = "",
    seed: int | str | None = None,
    section_minutes: int = 0,
    perspective: str = "",
) -> str:
    """Generate a narration script in `language`."""
    if niche not in VALID_NICHES:
        raise ValueError(f"unknown niche {niche!r}; valid: {sorted(VALID_NICHES)}")
    if language not in VALID_LANGS:
        raise ValueError(f"unknown language {language!r}; valid: {sorted(VALID_LANGS)}")
    if minutes <= 0:
        raise ValueError(f"minutes must be > 0, got {minutes}")

    if provider == "manual":
        raise RuntimeError(
            "provider=manual butuh script; lewatkan --script <file> "
            "(atau config story.provider=openai|anthropic)"
        )
    elif provider in ("openai", "anthropic"):
        text = _generate_with_topic_check(
            provider, niche, topic, minutes, language, model, api_key_env,
            base_url, seed, section_minutes or DEFAULT_SECTION_MINUTES, perspective,
        )
    else:
        raise ValueError(f"unknown provider {provider!r}; valid: manual|openai|anthropic")

    text = clean_text(text)
    if not text:
        raise RuntimeError("story generation produced empty text")
    target_words = minutes * WORDS_PER_MINUTE
    if len(text.split()) < MIN_TOTAL_FRACTION * target_words:
        raise RuntimeError(
            f"story terlalu pendek: {len(text.split())} kata dari target ~{target_words}. "
            "Turunkan length_minutes atau ganti model yang lebih capable."
        )
    return text


def _call_single(
    provider: str,
    niche: str,
    topic: str,
    minutes: int,
    language: str,
    model: str,
    api_key_env: str,
    base_url: str,
    seed: int | str | None,
    perspective: str = "",
) -> str:
    if provider == "openai":
        return llm.generate_story_openai(
            niche, topic, minutes, model, api_key_env, language, base_url,
            seed if isinstance(seed, int) else None, perspective,
        )
    return llm.generate_story_anthropic(
        niche, topic, minutes, model, api_key_env, language, base_url,
        seed if isinstance(seed, int) else None, perspective,
    )


def _generate_with_topic_check(
    provider: str,
    niche: str,
    topic: str,
    minutes: int,
    language: str,
    model: str,
    api_key_env: str,
    base_url: str,
    seed: int | str | None,
    section_minutes: int,
    perspective: str = "",
) -> str:
    """Generate, regenerating once if the story drifts off-topic."""
    for attempt in range(TOPIC_MAX_ATTEMPTS):
        if minutes > LONG_MODE_THRESHOLD:
            text = _generate_long(
                provider, niche, topic, minutes, language, model, api_key_env,
                base_url, seed, section_minutes, perspective,
            )
        else:
            text = _call_single(
                provider, niche, topic, minutes, language, model, api_key_env,
                base_url, seed, perspective,
            )
        if not topic.strip() or llm.topic_relevant(text, topic):
            return text
    raise RuntimeError(
        f"story tidak relevan dengan topik {topic!r} setelah {TOPIC_MAX_ATTEMPTS} "
        "percobaan; ganti topik, perjelas, atau pakai model yang lebih capable."
    )


def _trim_section(section: str, target_words: float, max_fraction: float) -> str:
    """Trim an oversized section at a sentence boundary; never mid-sentence."""
    max_words = int(max_fraction * target_words)
    if len(section.split()) <= max_words:
        return section
    sentences = split_sentences(section)
    out: list[str] = []
    n = 0
    for s in sentences:
        w = len(s.split())
        if out and n + w > max_words:
            break
        out.append(s)
        n += w
    if not out:
        out = sentences[:1]
    text = " ".join(out).strip()
    return text or section


def _generate_long(
    provider: str,
    niche: str,
    topic: str,
    minutes: int,
    language: str,
    model: str,
    api_key_env: str,
    base_url: str,
    seed: int | str | None,
    section_minutes: int,
    perspective: str = "",
) -> str:
    n_sections = max(2, math.ceil(minutes / max(1, section_minutes)))
    words_per_section = minutes * WORDS_PER_MINUTE / float(n_sections)
    section_seed = seed if isinstance(seed, int) else None

    if provider == "openai":
        headings = llm.generate_outline_openai(
            niche, topic, n_sections, words_per_section, model, api_key_env,
            language, base_url, seed=section_seed, perspective=perspective,
        )
    else:
        headings = llm.generate_outline_anthropic(
            niche, topic, n_sections, words_per_section, model, api_key_env,
            language, base_url, perspective=perspective,
        )

    parts: list[str] = []
    for i, heading in enumerate(headings):
        tail = " ".join(parts[-1].split()[-TAIL_WORDS:]) if parts else ""
        if provider == "openai":
            section = llm.generate_section_openai(
                i, n_sections, heading, tail, words_per_section, niche, topic,
                model, api_key_env, language, base_url, seed=section_seed, perspective=perspective,
            )
        else:
            section = llm.generate_section_anthropic(
                i, n_sections, heading, tail, words_per_section, niche, topic,
                model, api_key_env, language, base_url, perspective=perspective,
            )
        section = clean_text(section)
        if not section:
            raise RuntimeError(
                f"section {i + 1}/{n_sections} kosong; story gagal di bagian ini"
            )
        section = _trim_section(
            section, words_per_section,
            LAST_SECTION_MAX_WORDS_FRACTION if i == n_sections - 1 else SECTION_MAX_WORDS_FRACTION,
        )
        parts.append(section)

    return "\n\n".join(parts)


def generate_title(
    provider: str,
    story: str,
    niche: str = "custom",
    language: str = "id",
    model: str = "gpt-4o-mini",
    api_key_env: str = "OPENAI_API_KEY",
    base_url: str = "",
    topic: str = "",
) -> str:
    """Generate a YouTube title for an already-generated story.

    Separate call so the story prompt stays untouched; the story itself is
    the context, which keeps the title accurate to the narration.
    """
    if provider == "openai":
        title = llm.generate_title_openai(story, niche, model, api_key_env, language, base_url, topic)
    elif provider == "anthropic":
        title = llm.generate_title_anthropic(story, niche, model, api_key_env, language, base_url, topic)
    else:
        raise ValueError(f"generate_title needs llm provider, got {provider!r}")

    # tolerate models that wrap the title in quotes or add a preamble line
    title = title.strip().strip('"“”').strip()
    if "\n" in title:
        title = title.splitlines()[0].strip().strip('"“”').strip()
    if len(title) > 90:
        title = title[:90].rsplit(" ", 1)[0]
    return title or ""


def default_voice(language: str) -> str:
    return DEFAULT_VOICE.get(language, DEFAULT_VOICE["id"])


__all__ = [
    "generate",
    "generate_title",
    "default_voice",
    "VALID_NICHES",
    "VALID_LANGS",
    "LANG_LABEL",
]
