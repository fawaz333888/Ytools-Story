"""LLM-based story generation (optional, needs API key)."""

from __future__ import annotations

import os
import re
import time
from typing import Optional

from ..utils import join_continuation

# Indonesian needs more tokens per word than English (~2.7 tok/kata), so the
# per-section cap uses this factor to avoid sections dying mid-sentence.
SECTION_TOKENS_PER_WORD = 3.0
SECTION_CONTINUATION_MAX = 2
SECTION_PAD_MIN_FRACTION = 0.8
SECTION_PAD_MAX_ITER = 1
CONTINUATION_TAIL_WORDS = 300
WORDS_PER_MINUTE = 130

NICHE_PROMPTS = {
    "horror": "cerita horor Indonesia yang mencekam dengan twist akhir, gaya narasi faceless YouTube",
    "motivation": "cerita motivasi Indonesia yang mengangkat semangat, gaya narasi faceless YouTube",
    "education": "narasi edukasi Indonesia tentang fakta unik, gaya narasi faceless YouTube",
    "drama": "cerita drama Indonesia yang emosional, gaya narasi faceless YouTube",
    "custom": "cerita narasi faceless YouTube",
}


PERSPECTIVE_LINES = {
    "first_person": (
        "Gunakan narasi orang pertama (AKU): pencerita menceritakan dirinya sendiri, "
        "sudut pandang tokoh utama."
    ),
    "second_person": (
        "Gunakan narasi orang kedua (KAMU): cerita seakan menyindir langsung ke pembaca/"
        "penonton, efektif untuk ketegangan."
    ),
    "third_person": (
        "Gunakan narasi orang ketiga terbatas (DIA atau nama tokoh): pencerita menceritakan "
        "orang lain, fokus batin satu tokoh."
    ),
    "omniscient": (
        "Gunakan narator serba tahu: bebas berpindah sudut pandang antar tokoh sesuai kebutuhan."
    ),
}


def _perspective_line(perspective: str = "") -> str:
    return PERSPECTIVE_LINES.get(perspective or "third_person", PERSPECTIVE_LINES["third_person"])


def _topic_line(topic: str) -> str:
    topic = (topic or "").strip()
    if not topic:
        return ""
    return f"\nTOPIK WAJIB: seluruh cerita harus berpusat pada '{topic}'. Jangan keluar dari topik ini.\n"


def _system_prompt(niche: str, topic: str, minutes: int, language: str = "id", perspective: str = "") -> str:
    base = NICHE_PROMPTS.get(niche, NICHE_PROMPTS["custom"])
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    return (
        f"Tulis {base} dalam {lang_name}.{_topic_line(topic)}\n"
        f"{_perspective_line(perspective)}\n"
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


def _continuation_prompt(niche: str, topic: str, language: str = "id", perspective: str = "") -> str:
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    base = NICHE_PROMPTS.get(niche, NICHE_PROMPTS["custom"])
    return (
        f"Lanjutkan {base} dalam {lang_name} sebagai narasi YouTube faceless.{_topic_line(topic)}\n"
        f"{_perspective_line(perspective)}\n"
        "Aturan:\n"
        "- Lanjutkan TEPAT dari titik terakhir teks yang diberikan.\n"
        "- Jangan ulangi bagian yang sudah ada, jangan rangkum, jangan beri pengantar "
        "seperti 'Selanjutnya' atau 'Berikut lanjutannya'.\n"
        "- Tetap satu alur cerita; tidak ada heading, label adegan, atau dialog skrip.\n"
        "- Kalimat pendek, bahasa sehari-hari, tidak menyebut AI.\n"
    )


def _pad_prompt(niche: str, topic: str, target_words: int, language: str = "id", perspective: str = "") -> str:
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    base = NICHE_PROMPTS.get(niche, NICHE_PROMPTS["custom"])
    return (
        f"Cerita {base} dalam {lang_name} di bawah ini terlalu pendek. Kembangkan menjadi "
        f"sekitar {int(target_words)} kata: tambahkan detail, emosi, atau adegan baru. "
        f"JANGAN ulangi isi yang sudah ada.{_topic_line(topic)}\n"
        f"{_perspective_line(perspective)}\n"
        "Aturan:\n"
        "- Tetap pada satu alur dan gaya yang sama, sebagai satu cerita yang utuh.\n"
        "- Balas HANYA cerita lengkapnya (versi panjang), tanpa pengantar, heading, atau label adegan.\n"
        "- Kalimat pendek, bahasa sehari-hari, tidak menyebut AI.\n"
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


def _outline_prompt(niche: str, topic: str, n_sections: int, words_per_section: int, language: str = "id", perspective: str = "") -> str:
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    base = NICHE_PROMPTS.get(niche, NICHE_PROMPTS["custom"])
    return (
        f"Kamu akan menulis {base} dalam {lang_name}.{_topic_line(topic)}\n"
        f"{_perspective_line(perspective)}\n"
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


def _section_prompt(niche: str, language: str = "id", perspective: str = "", topic: str = "") -> str:
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    base = NICHE_PROMPTS.get(niche, NICHE_PROMPTS["custom"])
    topic_line = ""
    if (topic or "").strip():
        topic_line = f"\nCerita ini berpusat pada topik: '{topic}'. Tetap relevan, jangan keluar dari topik ini.\n"
    return (
        f"Lanjutkan menulis {base} dalam {lang_name}, sebagai narasi YouTube faceless.{topic_line}\n"
        f"{_perspective_line(perspective)}\n"
        "Aturan:\n"
        "- Tulis HANYA paragraf narasi bagian ini (sesuai kerangka yang diberikan).\n"
        "- Jangan ulangi bagian sebelumnya, jangan rangkum, jangan tulis heading/judul bagian.\n"
        "- Jangan mulai dengan pembuka seperti 'Selanjutnya' atau 'Di bagian ini'.\n"
        "- Kalimat pendek, bahasa sehari-hari, mudah dipahami pemirsa umum.\n"
        "- Tidak ada label adegan, tidak ada dialog skrip, tidak menyebut AI.\n"
    )


def _chat_openai(
    model: str,
    sys_msg: str,
    usr_msg: str,
    api_key_env: str,
    base_url: str,
    max_tokens: int = 0,
    seed: int | None = None,
    temperature: float = 0.9,
) -> tuple[str, Optional[str]]:
    from openai import OpenAI

    key = os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"env {api_key_env} not set; cannot use openai provider")
    client = OpenAI(api_key=key, base_url=base_url or None)
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
            temperature=temperature,
            **kwargs,
        )
    )
    choice = resp.choices[0]
    text = (choice.message.content or "").strip()
    return text, getattr(choice, "finish_reason", None)


def _chat_anthropic(
    model: str,
    sys_msg: str,
    usr_msg: str,
    api_key_env: str,
    base_url: str,
    max_tokens: int = 0,
    temperature: float = 0.9,
) -> tuple[str, Optional[str]]:
    import anthropic

    key = os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"env {api_key_env} not set; cannot use anthropic provider")
    client = anthropic.Anthropic(api_key=key, base_url=base_url or None)
    resp = _with_retry(
        lambda: client.messages.create(
            model=model or "claude-3-5-sonnet-20241022",
            max_tokens=max_tokens or 4000,
            system=sys_msg,
            messages=[{"role": "user", "content": usr_msg}],
            temperature=temperature,
        )
    )
    text = resp.content[0].text.strip()
    return text, getattr(resp, "stop_reason", None)


def _truncated(reason: Optional[str]) -> bool:
    return reason in ("length", "max_tokens")


def _continue_and_pad_openai(
    text: str,
    reason: Optional[str],
    target_words: float,
    niche: str,
    topic: str,
    language: str,
    model: str,
    api_key_env: str,
    base_url: str,
    seed: int | None = None,
    perspective: str = "",
) -> tuple[str, Optional[str]]:
    """Repair a truncated/under-length story piece with follow-up LLM calls."""
    cap = int(target_words * SECTION_TOKENS_PER_WORD) + 400
    it = 0
    while _truncated(reason) and it < SECTION_CONTINUATION_MAX and text.strip():
        tail = " ".join(text.split()[-CONTINUATION_TAIL_WORDS:])
        cont, reason = _chat_openai(
            model,
            _continuation_prompt(niche, topic, language, perspective),
            f"Teks sebelumnya (akhiran):\n{tail}\n\nTulis kelanjutannya sekarang.",
            api_key_env, base_url, max_tokens=cap, seed=seed,
        )
        cont = (cont or "").strip()
        if cont:
            text = join_continuation(text, cont)
        it += 1

    pad_it = 0
    while (
        not _truncated(reason)
        and len(text.split()) < SECTION_PAD_MIN_FRACTION * target_words
        and pad_it < SECTION_PAD_MAX_ITER
        and text.strip()
    ):
        padded, _ = _chat_openai(
            model,
            _pad_prompt(niche, topic, target_words, language, perspective),
            f"Ceritanya:\n\n{text}\n\nTulis versi yang lebih panjang sekarang.",
            api_key_env, base_url, max_tokens=cap, seed=seed,
        )
        padded = (padded or "").strip()
        if padded and len(padded.split()) > len(text.split()):
            text = padded
        pad_it += 1

    return text, reason


def _continue_and_pad_anthropic(
    text: str,
    reason: Optional[str],
    target_words: float,
    niche: str,
    topic: str,
    language: str,
    model: str,
    api_key_env: str,
    base_url: str,
    seed: int | None = None,
    perspective: str = "",
) -> tuple[str, Optional[str]]:
    cap = int(target_words * SECTION_TOKENS_PER_WORD) + 400
    it = 0
    while _truncated(reason) and it < SECTION_CONTINUATION_MAX and text.strip():
        tail = " ".join(text.split()[-CONTINUATION_TAIL_WORDS:])
        cont, reason = _chat_anthropic(
            model,
            _continuation_prompt(niche, topic, language, perspective),
            f"Teks sebelumnya (akhiran):\n{tail}\n\nTulis kelanjutannya sekarang.",
            api_key_env, base_url, max_tokens=cap,
        )
        cont = (cont or "").strip()
        if cont:
            text = join_continuation(text, cont)
        it += 1

    pad_it = 0
    while (
        not _truncated(reason)
        and len(text.split()) < SECTION_PAD_MIN_FRACTION * target_words
        and pad_it < SECTION_PAD_MAX_ITER
        and text.strip()
    ):
        padded, _ = _chat_anthropic(
            model,
            _pad_prompt(niche, topic, target_words, language, perspective),
            f"Ceritanya:\n\n{text}\n\nTulis versi yang lebih panjang sekarang.",
            api_key_env, base_url, max_tokens=cap,
        )
        padded = (padded or "").strip()
        if padded and len(padded.split()) > len(text.split()):
            text = padded
        pad_it += 1

    return text, reason


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
    perspective: str = "",
) -> str:
    from openai import OpenAI

    key = os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"env {api_key_env} not set; cannot use openai provider")
    sys_msg = system_prompt or _system_prompt(niche, topic, minutes, language, perspective)
    usr_msg = user_prompt or "Tulis ceritanya sekarang."
    text, _ = _chat_openai(model, sys_msg, usr_msg, api_key_env, base_url, max_tokens, seed=seed)
    return text


def generate_story_openai(
    niche: str,
    topic: str,
    minutes: int,
    model: str,
    api_key_env: str,
    language: str = "id",
    base_url: str = "",
    seed: int | None = None,
    perspective: str = "",
) -> str:
    """Single-call story for minutes <= LONG_MODE_THRESHOLD, with auto-repair."""
    text, reason = _chat_openai(
        model,
        _system_prompt(niche, topic, minutes, language, perspective),
        "Tulis ceritanya sekarang.",
        api_key_env, base_url, 0, seed=seed,
    )
    text, _ = _continue_and_pad_openai(
        text, reason, minutes * WORDS_PER_MINUTE, niche, topic, language,
        model, api_key_env, base_url, seed, perspective,
    )
    return text


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
    perspective: str = "",
) -> str:
    import anthropic

    key = os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"env {api_key_env} not set; cannot use anthropic provider")
    sys_msg = system_prompt or _system_prompt(niche, topic, minutes, language, perspective)
    usr_msg = user_prompt or "Tulis ceritanya sekarang."
    text, _ = _chat_anthropic(model, sys_msg, usr_msg, api_key_env, base_url, max_tokens)
    return text


def generate_story_anthropic(
    niche: str,
    topic: str,
    minutes: int,
    model: str,
    api_key_env: str,
    language: str = "id",
    base_url: str = "",
    seed: int | None = None,
    perspective: str = "",
) -> str:
    """Single-call story for minutes <= LONG_MODE_THRESHOLD, with auto-repair."""
    text, reason = _chat_anthropic(
        model,
        _system_prompt(niche, topic, minutes, language, perspective),
        "Tulis ceritanya sekarang.",
        api_key_env, base_url, 0,
    )
    text, _ = _continue_and_pad_anthropic(
        text, reason, minutes * WORDS_PER_MINUTE, niche, topic, language,
        model, api_key_env, base_url, seed, perspective,
    )
    return text


def _title_prompt(niche: str, language: str = "id", topic: str = "") -> str:
    lang_name = "Bahasa Indonesia" if language == "id" else "English"
    topic_line = ""
    if (topic or "").strip():
        topic_line = f"\nTopik cerita: '{topic}'. Judul harus nyambung dengan topik ini DAN isi cerita.\n"
    return (
        f"Berikan satu judul YouTube yang menarik dan clickbait-modarat untuk "
        f"cerita narasi berikut, dalam {lang_name}.{topic_line}\n"
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
    topic: str = "",
) -> str:
    from openai import OpenAI

    key = os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"env {api_key_env} not set; cannot use openai provider")
    client = OpenAI(api_key=key, base_url=base_url or None)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _title_prompt(niche, language, topic)},
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
    topic: str = "",
) -> str:
    import anthropic

    key = os.environ.get(api_key_env, "")
    if not key:
        raise RuntimeError(f"env {api_key_env} not set; cannot use anthropic provider")
    client = anthropic.Anthropic(api_key=key, base_url=base_url or None)
    resp = client.messages.create(
        model=model or "claude-3-5-sonnet-20241022",
        max_tokens=120,
        system=_title_prompt(niche, language, topic),
        messages=[{"role": "user", "content": f"Ceritanya:\n\n{story}\n\nJudulnya:"}],
    )
    return resp.content[0].text.strip()


def topic_relevant(text: str, topic: str) -> bool:
    """Heuristic: does `text` stay on `topic`?

    Matches content tokens of the topic (len > 3) as substrings, so
    inflections still count ("mertua" in "mertuaku"). Multi-word topics need
    >= 60% of their tokens present. Empty topic = always relevant.
    """
    topic = (topic or "").strip()
    if not topic:
        return True

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

    haystack = norm(text)
    if not haystack:
        return False
    tokens = [t for t in norm(topic).split() if len(t) > 3]
    if not tokens:
        tokens = norm(topic).split()
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in haystack)
    return hits >= max(1, int(0.6 * len(tokens)))



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
    perspective: str = "",
) -> list[str]:
    text = generate_openai(
        niche, topic, 0, model, api_key_env, language, base_url,
        system_prompt=_outline_prompt(niche, topic, n_sections, words_per_section, language, perspective),
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
    perspective: str = "",
) -> str:
    tail = (prev_tail or "").strip()
    user = (
        f"Kerangka bagian {section_idx + 1}/{n_sections}: {heading}\n"
        f"Target: sekitar {int(target_words)} kata.\n\n"
        + ("(Ini bagian pertama.)" if not tail else f"Bagian sebelumnya (akhiran):\n{tail}")
        + "\n\nTulis bagian ini sekarang."
    )
    text, reason = _chat_openai(
        model,
        _section_prompt(niche, language, perspective, topic),
        user,
        api_key_env, base_url,
        int(target_words * SECTION_TOKENS_PER_WORD) + 400,
        seed=seed,
    )
    text, _ = _continue_and_pad_openai(
        text, reason, target_words, niche, topic, language,
        model, api_key_env, base_url, seed, perspective,
    )
    return text


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
    perspective: str = "",
) -> list[str]:
    text = generate_anthropic(
        niche, topic, 0, model, api_key_env, language, base_url,
        system_prompt=_outline_prompt(niche, topic, n_sections, words_per_section, language, perspective),
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
    perspective: str = "",
) -> str:
    tail = (prev_tail or "").strip()
    user = (
        f"Kerangka bagian {section_idx + 1}/{n_sections}: {heading}\n"
        f"Target: sekitar {int(target_words)} kata.\n\n"
        + ("(Ini bagian pertama.)" if not tail else f"Bagian sebelumnya (akhiran):\n{tail}")
        + "\n\nTulis bagian ini sekarang."
    )
    text, reason = _chat_anthropic(
        model,
        _section_prompt(niche, language, perspective, topic),
        user,
        api_key_env, base_url,
        int(target_words * SECTION_TOKENS_PER_WORD) + 400,
    )
    text, _ = _continue_and_pad_anthropic(
        text, reason, target_words, niche, topic, language,
        model, api_key_env, base_url, seed, perspective,
    )
    return text


__all__ = [
    "generate_openai", "generate_anthropic", "generate_title_openai", "generate_title_anthropic",
    "generate_story_openai", "generate_story_anthropic",
    "generate_outline_openai", "generate_outline_anthropic",
    "generate_section_openai", "generate_section_anthropic",
    "topic_relevant",
    "NICHE_PROMPTS",
]
