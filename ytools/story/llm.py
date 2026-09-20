"""LLM-based story generation (optional, needs API key)."""

from __future__ import annotations

import os
from typing import Optional

NICHE_PROMPTS = {
    "horror": "cerita horor Indonesia yang mencekam dengan twist akhir, gaya narasi faceless YouTube",
    "motivation": "cerita motivasi Indonesia yang mengangkat semangat, gaya narasi faceless YouTube",
    "education": "narasi edukasi Indonesia tentang fakta unik, gaya narasi faceless YouTube",
    "drama": "cerita drama Indonesia yang emosional, gaya narasi faceless YouTube",
    "custom": "cerita narasi faceless YouTube",
}


def _system_prompt(niche: str, topic: str, minutes: int, language: str = "id") -> str:
    base = NICHE_PROMPTS.get(niche, NICHE_PROMPTS["custom"])
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    topic_line = f" Tema spesifik: {topic}." if topic.strip() else ""
    return (
        f"Tulis {base} dalam {lang_name}.{topic_line}\n"
        f"Target durasi narasi sekitar {minutes} menit (sekitar {minutes * 130} kata).\n"
        "Aturan:\n"
        "- Tulis dalam paragraf narasi murni (bukan dialog skrip, tidak ada label adegan).\n"
        "- Mulai dengan kalimat hook yang langsung memikat di 3 detik pertama.\n"
        "- Tidak ada kata pembuka seperti 'Halo' atau 'Selamat datang'.\n"
        "- Tidak menyebutkan bahwa ini dibuat oleh AI.\n"
        "- Gunakan tata bahasa yang alami dan benar untuk bahasa tersebut.\n"
        "- Akhiri dengan kalimat penutup yang membuat penonton ingin subscribe.\n"
    )


def generate_openai(
    niche: str,
    topic: str,
    minutes: int,
    model: str,
    api_key_env: str,
    language: str = "id",
    base_url: str = "",
) -> str:
    from openai import OpenAI

    key = os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"env {api_key_env} not set; cannot use openai provider")
    client = OpenAI(api_key=key, base_url=base_url or None)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _system_prompt(niche, topic, minutes, language)},
            {"role": "user", "content": "Tulis ceritanya sekarang."},
        ],
        temperature=0.9,
    )
    return (resp.choices[0].message.content or "").strip()


def generate_anthropic(
    niche: str,
    topic: str,
    minutes: int,
    model: str,
    api_key_env: str,
    language: str = "id",
    base_url: str = "",
) -> str:
    import anthropic

    key = os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"env {api_key_env} not set; cannot use anthropic provider")
    client = anthropic.Anthropic(api_key=key, base_url=base_url or None)
    resp = client.messages.create(
        model=model or "claude-3-5-sonnet-20241022",
        max_tokens=4000,
        system=_system_prompt(niche, topic, minutes, language),
        messages=[{"role": "user", "content": "Tulis ceritanya sekarang."}],
    )
    return resp.content[0].text.strip()


__all__ = ["generate_openai", "generate_anthropic", "NICHE_PROMPTS"]
