"""Story generation dispatch by provider and language."""

from __future__ import annotations

from ..utils import clean_text
from . import llm

VALID_NICHES = {"horror", "motivation", "education", "drama", "custom"}
VALID_LANGS = {"id", "en"}

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
) -> str:
    """Generate a narration script in `language`."""
    if niche not in VALID_NICHES:
        raise ValueError(f"unknown niche {niche!r}; valid: {sorted(VALID_NICHES)}")
    if language not in VALID_LANGS:
        raise ValueError(f"unknown language {language!r}; valid: {sorted(VALID_LANGS)}")

    if provider == "manual":
        raise RuntimeError(
            "provider=manual butuh script; lewatkan --script <file> "
            "(atau config story.provider=openai|anthropic)"
        )
    elif provider == "openai":
        text = llm.generate_openai(niche, topic, minutes, model, api_key_env, language, base_url)
    elif provider == "anthropic":
        text = llm.generate_anthropic(niche, topic, minutes, model, api_key_env, language, base_url)
    else:
        raise ValueError(f"unknown provider {provider!r}; valid: manual|openai|anthropic")

    text = clean_text(text)
    if not text:
        raise RuntimeError("story generation produced empty text")
    return text


def generate_title(
    provider: str,
    story: str,
    niche: str = "custom",
    language: str = "id",
    model: str = "gpt-4o-mini",
    api_key_env: str = "OPENAI_API_KEY",
    base_url: str = "",
) -> str:
    """Generate a YouTube title for an already-generated story.

    Separate call so the story prompt stays untouched; the story itself is
    the context, which keeps the title accurate to the narration.
    """
    if provider == "openai":
        title = llm.generate_title_openai(story, niche, model, api_key_env, language, base_url)
    elif provider == "anthropic":
        title = llm.generate_title_anthropic(story, niche, model, api_key_env, language, base_url)
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
