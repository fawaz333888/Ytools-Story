"""Hook generator — punchy opening lines per niche and language.

The hook is the first sentence the viewer hears; it decides whether the first
five seconds are survived. Pools are randomized and can be prepended to the
generated story so narration and subtitle both open with it.
"""

from __future__ import annotations

import random

from ..utils import rng_from_seed

HOOKS = {
    "id": {
        "horror": [
            "Jika kamu mendengar namamu dipanggil malam ini, jangan dijawab.",
            "Tiga hari setelah pindah, dia menyadari rumah itu sudah berpenghuni.",
            "Video ini mungkin terdengar mustahil, tapi semuanya terjadi di rumah biasa.",
            "Ada satu aturan di desa itu yang tidak pernah dilanggar siapa pun.",
        ],
        "motivation": [
            "Kalau kamu mau menyerah hari ini, tonton dulu video ini sampai akhir.",
            "Orang ini mengubah hidupnya hanya dalam tiga tahun, tanpa modal dan tanpa kenalan.",
            "Sebagian besar orang gagal bukan karena malas, tapi karena melewatkan satu hal kecil ini.",
            "Aku pernah berpikir sukses butuh keberuntungan. Sampai aku bertemu dia.",
        ],
        "education": [
            "Fakta ini akan mengubah cara kamu melihat hal yang kamu pakai setiap hari.",
            "Sekolah tidak pernah mengajarkan ini, padahal dampaknya kamu rasakan tiap hari.",
            "Coba teken dulu kenapa bisa begini. Jawabannya lebih aneh dari yang kamu kira.",
        ],
        "drama": [
            "Surat itu datang tanpa pengirim, dan menghancurkan semua yang dia percayai.",
            "Mereka berteman sejak kecil, sampai satu rahasia kecil mengubah segalanya.",
            "Kadang luka paling dalam datang dari kata-kata yang tidak pernah diucapkan.",
        ],
        "custom": [
            "Video ini bercerita tentang sesuatu yang jarang dibicarakan orang.",
        ],
    },
    "en": {
        "horror": [
            "If you hear your name called tonight, do not answer it.",
            "Three days after moving in, he realized the house was already occupied.",
            "This may sound impossible, but it happened in an ordinary house.",
            "There was one rule in that village that nobody ever broke.",
        ],
        "motivation": [
            "If you want to quit today, watch this video until the end first.",
            "This man changed his life in three years, with no money and no connections.",
            "Most people fail not from laziness, but from missing one small thing.",
            "I used to think success needed luck, until I met him.",
        ],
        "education": [
            "This fact will change how you see something you use every day.",
            "School never taught this, yet it affects you daily.",
            "Try to guess why this works. The answer is stranger than you think.",
        ],
        "drama": [
            "The letter arrived with no sender, and destroyed everything she believed.",
            "They had been friends since childhood, until one small secret changed it all.",
            "Sometimes the deepest wounds come from the words that were never said.",
        ],
        "custom": [
            "This video is about something people rarely talk about.",
        ],
    },
}


def generate_hook(
    niche: str,
    language: str = "id",
    seed: int | str | None = None,
) -> str:
    """Return one hook line for the niche/language."""
    pool = HOOKS.get(language, HOOKS["id"]).get(niche) or HOOKS["id"]["custom"]
    rng = rng_from_seed(seed)
    return rng.choice(pool)


def generate_hooks(
    niche: str,
    language: str = "id",
    count: int = 3,
    seed: int | str | None = None,
) -> list[str]:
    pool = HOOKS.get(language, HOOKS["id"]).get(niche) or HOOKS["id"]["custom"]
    rng = rng_from_seed(seed)
    if count >= len(pool):
        return list(pool)
    return rng.sample(pool, count)


__all__ = ["generate_hook", "generate_hooks", "HOOKS"]
