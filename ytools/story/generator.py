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
        text = llm.generate_openai(niche, topic, minutes, model, api_key_env, language)
    elif provider == "anthropic":
        text = llm.generate_anthropic(niche, topic, minutes, model, api_key_env, language)
    else:
        raise ValueError(f"unknown provider {provider!r}; valid: manual|openai|anthropic")

    text = clean_text(text)
    if not text:
        raise RuntimeError("story generation produced empty text")
    return text


def default_voice(language: str) -> str:
    return DEFAULT_VOICE.get(language, DEFAULT_VOICE["id"])


__all__ = [
    "generate",
    "default_voice",
    "VALID_NICHES",
    "VALID_LANGS",
    "LANG_LABEL",
]
