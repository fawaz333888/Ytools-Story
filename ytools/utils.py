"""Shared helpers: time formatting, RNG, text cleaning."""

from __future__ import annotations

import random
import re
import unicodedata


def fmt_ass_time(seconds: float) -> str:
    """Seconds -> ASS timestamp 'H:MM:SS.cc'."""
    if seconds < 0:
        seconds = 0.0
    ms = int(round((seconds % 1) * 100))
    # carry on rounding to 100
    if ms >= 100:
        seconds += 1
        ms = 0
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:d}:{m:02d}:{s:02d}.{ms:02d}"


def fmt_srt_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    total = int(seconds)
    ms = int(round((seconds - total) * 1000))
    if ms >= 1000:
        seconds += 1
        total = int(seconds)
        ms = 0
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def clean_text(text: str) -> str:
    """Normalize whitespace/quotes; keep Indonesian punctuation intact."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace(" ", " ").replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def join_continuation(prev: str, cont: str) -> str:
    """Append a continuation text to `prev`, removing an echoed overlap.

    Models often repeat the last words of the context at the start of their
    continuation; drop the longest word-level overlap so the join is clean.
    The separator respects whether `prev` ended mid-sentence.
    """
    prev = (prev or "").rstrip()
    cont = (cont or "").strip()
    if not cont:
        return prev
    p_words = prev.split()
    c_words = cont.split()
    max_k = min(len(p_words), len(c_words), 12)

    def key(w: str) -> str:
        return re.sub(r"[^\w]", "", w.lower())

    for n in range(max_k, 0, -1):
        if [key(w) for w in p_words[-n:]] == [key(w) for w in c_words[:n]]:
            cont = " ".join(c_words[n:]).strip()
            break
    if not cont:
        return prev
    tail = prev.rstrip("\"'”").rstrip()
    sep = "\n\n" if tail and tail[-1] in ".!?…" else " "
    return prev + sep + cont


def split_sentences(text: str, min_len: int = 1) -> list[str]:
    """Split into sentences. Keeps punctuation. Handles '...' and abbreviations lightly."""
    text = clean_text(text)
    parts = re.split(r"(?<=[.!?…])\s+", text)
    out = [p.strip() for p in parts if len(p.strip()) >= min_len]
    return out


def rng_from_seed(seed: int | str | None) -> random.Random:
    if seed is None:
        return random.Random()
    if isinstance(seed, int):
        return random.Random(seed)
    return random.Random(hash(seed) & 0xFFFFFFFF)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
