"""LLM-based story generation (optional, needs API key)."""

from __future__ import annotations

import os
import re
import time
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
        "- Buka cerita dengan 1-2 kalimat yang membangkitkan rasa penasaran: beri petunjuk "
        "kejutan atau paradoks kecil yang baru terjawab menjelang akhir. Jangan spoil twist-nya.\n"
        "- Gunakan bahasa Indonesia sehari-hari yang mudah dipahami semua orang, termasuk "
        "pemirsa awam (seperti ibu rumah tangga): kalimat pendek, kata-kata umum, ungkapan "
        "yang akrab di telinga. Hindari kata baku, istilah rumit, dan struktur kalimat panjang "
        "yang berbelit.\n"
        "- Tidak ada kata pembuka seperti 'Halo' atau 'Selamat datang'.\n"
        "- Tidak menyebutkan bahwa ini dibuat oleh AI.\n"
        "- Gunakan tata bahasa yang alami dan benar untuk bahasa tersebut.\n"        "- Akhiri dengan kalimat penutup yang membuat penonton ingin subscribe.\n"
    )


def _retryable(exc: Exception) -> bool:
    name = type(exc).__name__
    if name in ("APITimeoutError", "APIConnectionError", "InternalServerError", "RateLimitError"):
        return True
    status = getattr(exc, "status_code", None)
    return status in (500, 502, 503, 529)


def _with_retry(fn, attempts: int = 3):
    last: Optional[Exception] = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if not _retryable(exc) or i == attempts - 1:
                raise
            time.sleep(5 * (2**i))
    raise RuntimeError("unreachable") from last


def _outline_prompt(niche: str, topic: str, n_sections: int, words_per_section: int, language: str = "id") -> str:
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    base = NICHE_PROMPTS.get(niche, NICHE_PROMPTS["custom"])
    topic_line = f" Tema spesifik: {topic}." if topic.strip() else ""
    return (
        f"Kamu akan menulis {base} dalam {lang_name}.{topic_line}\n"
        f"Cerita ini dibagi menjadi tepat {n_sections} bagian, masing-masing sekitar "
        f"{int(words_per_section)} kata (~5 menit narasi).\n"
        "Aturan:\n"
        "- Cetak HANYA kerangka cerita: 1 baris per bagian, total tepat "
        f"{n_sections} baris.\n"
        "- Tiap baris = 1-2 kalimat singkat: peristiwa inti bagian itu.\n"
        "- Urutan baris = urutan jalan cerita (pembuka di baris 1, penutup di baris terakhir).\n"
        "- Tanpa penomoran, tanpa bullet, tanpa penjelasan, tanpa judul.\n"
    )


def _parse_outline(text: str, n_sections: int) -> list[str]:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        s = re.sub(r"^\s*\d+\s*[.)]?\s*", "", s)
        s = s.strip().lstrip("-•").strip().strip('"“”').strip()
        if s:
            lines.append(s)
    if len(lines) < 2:
        return [f"Bagian {i + 1}" for i in range(n_sections)]
    if len(lines) > n_sections:
        lines = lines[:n_sections]
    while len(lines) < n_sections:
        lines.append(f"Bagian {len(lines) + 1}")
    return lines


def _section_prompt(niche: str, language: str = "id") -> str:
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    base = NICHE_PROMPTS.get(niche, NICHE_PROMPTS["custom"])
    return (
        f"Lanjutkan menulis {base} dalam {lang_name}, sebagai narasi YouTube faceless.\n"
        "Aturan:\n"
        "- Tulis HANYA paragraf narasi bagian ini (sesuai kerangka yang diberikan).\n"
        "- Jangan ulangi bagian sebelumnya, jangan rangkum, jangan tulis heading/judul bagian.\n"
        "- Jangan mulai dengan pembuka seperti 'Selanjutnya' atau 'Di bagian ini'.\n"
        "- Kalimat pendek, bahasa sehari-hari, mudah dipahami pemirsa umum.\n"
        "- Tidak ada label adegan, tidak ada dialog skrip, tidak menyebut AI.\n"
    )


def generate_openai(
    niche: str,
    topic: str,
    minutes: int,
    model: str,
    api_key_env: str,
    language: str = "id",
    base_url: str = "",
    system_prompt: str = "",
    user_prompt: str = "",
    max_tokens: int = 0,
    seed: int | None = None,
) -> str:
    from openai import OpenAI

    key = os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"env {api_key_env} not set; cannot use openai provider")
    client = OpenAI(api_key=key, base_url=base_url or None)
    sys_msg = system_prompt or _system_prompt(niche, topic, minutes, language)
    usr_msg = user_prompt or "Tulis ceritanya sekarang."
    kwargs: dict = {}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    if seed is not None:
        kwargs["seed"] = seed
    resp = _with_retry(
        lambda: client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": usr_msg},
            ],
            temperature=0.9,
            **kwargs,
        )
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
    system_prompt: str = "",
    user_prompt: str = "",
    max_tokens: int = 0,
    seed: int | None = None,
) -> str:
    import anthropic

    key = os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"env {api_key_env} not set; cannot use anthropic provider")
    client = anthropic.Anthropic(api_key=key, base_url=base_url or None)
    sys_msg = system_prompt or _system_prompt(niche, topic, minutes, language)
    usr_msg = user_prompt or "Tulis ceritanya sekarang."
    resp = _with_retry(
        lambda: client.messages.create(
            model=model or "claude-3-5-sonnet-20241022",
            max_tokens=max_tokens or 4000,
            system=sys_msg,
            messages=[{"role": "user", "content": usr_msg}],
        )
    )
    return resp.content[0].text.strip()


def _title_prompt(niche: str, language: str = "id") -> str:
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    return (
        f"Berikan satu judul YouTube yang menarik dan clickbait-modarat untuk "
        f"cerita narasi berikut, dalam {lang_name}.\n"
        "Aturan:\n"
        "- Maksimal 60 karakter, satu baris saja.\n"
        "- Judul harus nyambung dan akurat dengan isi cerita (bukan menambah "
        "detail baru atau kontradiksi).\n"
        "- Tanpa tanda kutip, tanpa emoji, tanpa kata 'YouTube' atau 'Video'.\n"
        "- Tidak menyebutkan bahwa ini dibuat oleh AI.\n"
        "- Balas HANYA judulnya, tanpa kata pengantar.\n"
    )


def generate_title_openai(
    story: str,
    niche: str,
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
            {"role": "system", "content": _title_prompt(niche, language)},
            {"role": "user", "content": f"Ceritanya:\n\n{story}\n\nJudulnya:"},
        ],
        temperature=0.8,
    )
    return (resp.choices[0].message.content or "").strip()


def generate_title_anthropic(
    story: str,
    niche: str,
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
        max_tokens=120,
        system=_title_prompt(niche, language),
        messages=[{"role": "user", "content": f"Ceritanya:\n\n{story}\n\nJudulnya:"}],
    )
    return resp.content[0].text.strip()


def generate_outline_openai(
    niche: str,
    topic: str,
    n_sections: int,
    words_per_section: float,
    model: str,
    api_key_env: str,
    language: str = "id",
    base_url: str = "",
    seed: int | None = None,
) -> list[str]:
    text = generate_openai(
        niche, topic, 0, model, api_key_env, language, base_url,
        system_prompt=_outline_prompt(niche, topic, n_sections, words_per_section, language),
        user_prompt=f"Cetak tepat {n_sections} baris kerangka sekarang.",
        max_tokens=max(300, int(n_sections * 25)),
        seed=seed,
    )
    return _parse_outline(text, n_sections)


def generate_section_openai(
    section_idx: int,
    n_sections: int,
    heading: str,
    prev_tail: str,
    target_words: float,
    niche: str,
    topic: str,
    model: str,
    api_key_env: str,
    language: str = "id",
    base_url: str = "",
    seed: int | None = None,
) -> str:
    tail = (prev_tail or "").strip()
    user = (
        f"Kerangka bagian {section_idx + 1}/{n_sections}: {heading}\n"
        f"Target: sekitar {int(target_words)} kata.\n\n"
        + ("(Ini bagian pertama.)" if not tail else f"Bagian sebelumnya (akhiran):\n{tail}")
        + "\n\nTulis bagian ini sekarang."
    )
    return generate_openai(
        niche, topic, 0, model, api_key_env, language, base_url,
        system_prompt=_section_prompt(niche, language),
        user_prompt=user,
        max_tokens=int(target_words * 1.6) + 250,
        seed=seed,
    )


def generate_outline_anthropic(
    niche: str,
    topic: str,
    n_sections: int,
    words_per_section: float,
    model: str,
    api_key_env: str,
    language: str = "id",
    base_url: str = "",
    seed: int | None = None,
) -> list[str]:
    text = generate_anthropic(
        niche, topic, 0, model, api_key_env, language, base_url,
        system_prompt=_outline_prompt(niche, topic, n_sections, words_per_section, language),
        user_prompt=f"Cetak tepat {n_sections} baris kerangka sekarang.",
        max_tokens=max(300, int(n_sections * 25)),
    )
    return _parse_outline(text, n_sections)


def generate_section_anthropic(
    section_idx: int,
    n_sections: int,
    heading: str,
    prev_tail: str,
    target_words: float,
    niche: str,
    topic: str,
    model: str,
    api_key_env: str,
    language: str = "id",
    base_url: str = "",
    seed: int | None = None,
) -> str:
    tail = (prev_tail or "").strip()
    user = (
        f"Kerangka bagian {section_idx + 1}/{n_sections}: {heading}\n"
        f"Target: sekitar {int(target_words)} kata.\n\n"
        + ("(Ini bagian pertama.)" if not tail else f"Bagian sebelumnya (akhiran):\n{tail}")
        + "\n\nTulis bagian ini sekarang."
    )
    return generate_anthropic(
        niche, topic, 0, model, api_key_env, language, base_url,
        system_prompt=_section_prompt(niche, language),
        user_prompt=user,
        max_tokens=int(target_words * 1.6) + 250,
    )


__all__ = [
    "generate_openai", "generate_anthropic", "generate_title_openai", "generate_title_anthropic",
    "generate_outline_openai", "generate_outline_anthropic",
    "generate_section_openai", "generate_section_anthropic",
    "NICHE_PROMPTS",
]
