"""Offline story generation — no API key required.

Template pools per niche. Stories are assembled from parts (hook, setup,
conflict, twist, resolution) with randomized slots (names, places, objects)
so repeated generation does not collide. Quality is obviously below an LLM,
but it costs nothing and runs offline on Colab free tier.
"""

from __future__ import annotations

import random
from typing import Optional

from ..utils import rng_from_seed

NAMES_M = ["Budi", "Ardi", "Rizky", "Dimas", "Fajar", "Hendra", "Yoga", "Bayu", "Eko", "Reza"]
NAMES_F = ["Sari", "Gadis", "Rina", "Dewi", "Lina", "Putri", "Nadia", "Sri", "Wati", "Maya"]
PLACES = [
    "sebuah desa terpencil di Jawa", "kota tua yang sepi", "sebuah gubuk di tepi hutan",
    "gang sempit di pinggiran kota", "sebuah sekolah kosong", "rumah tua di ujung jalan",
    "sebuah pabrik terbengkalai", "persawahan yang luas", "pasar tradisional yang ramai",
    "sebuah pulau kecil yang terlupakan",
]
TIMES = ["senja", "tengah malam", "subuh", "sore hari", "ketika hujan turun", "musim kemarau"]
OBJECTS = ["sebuah kotak kayu tua", "sebuah kaleng karatan", "sebuah foto pudar", "sebuah surat tak terkirim", "sebuah pisau dapur", "sebuah radio tua", "sebuah cermin retak", "sebuah buku harian"]
SOUNDS = ["suara ketukan pelan", "suara langkah di atas kayu", "bisikan halus", "suara air menetes", "gema tertawa", "suara pintu berderit"]


def _pick(rng: random.Random, items: list[str]) -> str:
    return rng.choice(items)


def _slots(rng: random.Random) -> dict[str, str]:
    male = _pick(rng, NAMES_M)
    female = _pick(rng, NAMES_F)
    return {
        "name_m": male,
        "name_f": female,
        "name": rng.choice([male, female]),
        "place": _pick(rng, PLACES),
        "time": _pick(rng, TIMES),
        "object": _pick(rng, OBJECTS),
        "sound": _pick(rng, SOUNDS),
        "they": "dia",
    }


HORROR = {
    "hook": [
        "Semua orang di {place} tahu satu aturan: jangan pernah keluar rumah saat {time}.",
        "Ada alasan kenapa rumah itu dibiarkan kosong selama bertahun-tahun.",
        "{name} tidak percaya hantu. Setidaknya, dulu.",
        "Kisah ini saya dapatkan langsung dari {name_f}, dan sampai sekarang tangannya masih gemar bercerita.",
        "Jika suatu malam kamu mendengar {sound} di luar jendela, jangan ditanggapi.",
    ],
    "setup": [
        "Begitu {time} tiba, {place} berubah menjadi sunyi yang mencekam. {name} menyadari ada yang aneh: {object} di ruang tamu sudah tidak di tempatnya semula.",
        "{name} baru pindah ke {place} seminggu yang lalu. Tetangga hanya tersenyum saat ditanya tentang rumah itu, seolah menyimpan rahasia yang terlalu berat untuk diucapkan.",
        "Semua bermula dari {object} yang {name} temukan di loteng. Kotor, tapi entah kenapa masih terasa hangat saat disentuh.",
    ],
    "build": [
        "Malam itu, {sound} terdengar dari arah dapur. {name} berdiri mematung, menahan napas, berharap itu hanya angin.",
        "Setiap malam pada pukul tepat, lampu di kamar belakang menyala sendiri. Tidak ada saklar yang tersambung ke ruangan itu.",
        "{name_f} berkata suara itu mulai berbicara memanggil nama {name}, pelan, seperti doa yang dibalik.",
        "Cermin di lorong mulai memperlihatkan hal yang tidak ada di ruangan. {name} menutupnya dengan kain, tapi kainnya selalu jatuh saat {time}.",
    ],
    "climax": [
        "Saat {name} akhirnya berani membuka pintu itu, yang terlihat hanyalah kegelapan yang bergerak. Dan dari dalam kegelapan itu, sebuah tangan — pucat dan dingin — perlahan menjulur keluar.",
        "{object} itu ternyata menyimpan sesuatu. Saat {name} membukanya, ruangan tiba-tiba dipenuhi {sound} yang memekakkan, dan semua foto di dinding menatap ke arahnya.",
        "{name} berlari keluar. Sesampainya di jalan, dia menoleh sekali — dan di jendela, seseorang yang wajahnya persis sama dengannya sedang menatap balik.",
    ],
    "resolution": [
        "Keesokan harinya, {name} pergi dari {place} dan tidak pernah kembali. Tapi kadang, saat {time}, tetangga masih mendengar {sound} dari rumah kosong itu.",
        "{name_f} menemukan {object} itu di depan pintu rumahnya, bersih seolah baru saja diusap. Tidak ada satu pun yang berani menyentuhnya.",
        "Sampai hari ini, tidak ada yang tahu apa yang sebenarnya terjadi malam itu. {name} hanya mengatakan satu hal: mereka yang dipanggil namanya, selalu menjawab.",
    ],
}

MOTIVATION = {
    "hook": [
        "Ada dua jenis orang di dunia ini: mereka yang menyerah dan mereka yang {name} sebutkan sebagai 'orang-orang beruntung'.",
        "Cerita ini tentang {name}, orang biasa dari {place} yang mengubah hidupnya hanya dalam tiga tahun.",
        "Saya bertemu {name} saat {time}, di sebuah tempat kecil di {place}. Penampilannya tidak istimewa. Tapi ceritanya, akan membuatmu berpikir dua kali tentang alasan.",
    ],
    "setup": [
        "Usianya baru dua puluh lima saat dia kehilangan segalanya. Pekerjaan, tabungan, dan kepercayaan pada diri sendiri — semua hilang dalam satu bulan.",
        "Tiap pagi sebelum {time}, {name} sudah berjalan ke {place} mencari kerja. Tiga belas kali ditolak, dan dia masih menghitung.",
        "Orang-orang di {place} mulai berbisik. Mereka bilang {name} terlalu bermimpi untuk orang dengan tangan kosong.",
    ],
    "build": [
        "Suatu malam, {name} menulis satu tujuan di {object} dan menempelkannya di dinding. Tujuan yang bagi orang lain terdengar mustahil.",
        "Dia mulai bangun dua jam lebih awal, belajar sendiri saat orang lain tidur, dan menabung uang receh yang biasanya habis untuk hal-hal kecil.",
        "Setiap kali gagal, {name} mencatat alasannya di {object} itu, lalu menulis satu baris di bawahnya: 'belum selesai'.",
    ],
    "climax": [
        "Pada hari ketika kesempatan itu datang, tangan {name} gemetar. Bukan karena takut gagal — tapi karena dia tahu ini adalah pintu yang dibukannya sendiri, satu per satu, selama bertahun-tahun.",
        "Tidak ada sorak sorai, tidak ada konfeti. Yang ada hanyalah tangangan {name} erat di atas meja dan satu kalimat: 'saya sudah bersiap untuk momen ini sejak lama.'",
    ],
    "resolution": [
        "Hari ini, jika kamu ke {place}, kamu bisa melihat {object} itu dipajang di ruangannya — dengan tulisan tujuan yang hampir pudar, dan ratusan baris 'belum selesai' di bawahnya.",
        "Pelajaran dari {name} bukan tentang keberuntungan. Tapi tentang orang yang bersedia membayar harga harian, saat semua orang lain memilih hari ini untuk berhenti.",
        "{name} sering berkata: rezeki tidak salah alamat. Ia hanya menunggu di ujung jalan yang kebanyakan orang berhenti menapakinya.",
    ],
}

EDUCATION = {
    "hook": [
        "Fakta ini mungkin akan mengubah cara kamu melihat hal yang kamu anggap biasa.",
        "Sedikit yang tahu, tapi di balik hal sehari-hari ada sejarah yang mengejutkan.",
        "Pernahkah kamu bertanya kenapa bisa begitu? Jawabannya lebih aneh dari yang kamu kira.",
    ],
    "setup": [
        "Semua bermula ratusan tahun lalu, jauh sebelum ada internet dan listrik seperti sekarang ini.",
        "Para ilmuwan waktu itu tidak punya alat canggih. Yang mereka punya hanya rasa penasaran dan keberanian untuk bertanya tentang hal yang orang anggap tabu.",
        "Awalnya, penemuan ini dianggap tidak penting. Bahkan para ahli saat itu meremehkannya.",
    ],
    "build": [
        "Yang menarik, hasilnya berbanding terbalik dengan apa yang diperkirakan semua orang.",
        "Semakin dalam diteliti, semakin banyak pertanyaan baru yang muncul — dan setiap jawaban membawa konsekuensi tak terduga.",
        "Satu eksperimen sederhana itu kemudian mengubah pemahaman manusia tentang dunia.",
    ],
    "climax": [
        "Inilah bagian paling mengejutkannya: hal yang kita anggap modern sebenarnya sudah dipahami sejak dahulu, hanya dalam bahasa yang berbeda.",
        "Dan efeknya tidak berhenti di laboratorium. Ia merembes ke kehidupan sehari-hari tanpa kita sadari.",
    ],
    "resolution": [
        "Jadi lain kali kamu melihatnya, ingat: ada sejarah panjang dan aneh di baliknya.",
        "Pengetahuan seperti ini jarang diajarkan di sekolah, padahal dampaknya bisa kamu rasakan setiap hari.",
        "Itulah sebabnya selalu ada gunanya bertanya 'kenapa?' — karena kadang jawabannya lebih aneh dari pertanyaannya.",
    ],
}

DRAMA = {
    "hook": [
        "Ada pertemuan yang mengubah segalanya, dan ada pertemuan yang justru menghancurkan. Ini adalah cerita tentang keduanya.",
        "Surat itu tiba di hari {time}, tanpa pengirim dan tanpa alamat balasan.",
        "{name_f} dan {name} bersahabat sejak kecil. Setidaknya, itulah yang selama ini mereka percayai.",
    ],
    "setup": [
        "Mereka tumbuh di {place}, berbagi rahasia, mimpi, dan satu janji yang tidak pernah ditulis di atas kertas.",
        "Sesuai janji, setiap {time} mereka bertemu di tempat yang sama. Tahun demi tahun, tidak pernah tertinggal — sampai satu tahun, {name} tidak datang.",
        "Semua berubah saat {object} itu ditemukan di laci lama, bersama dengan sesuatu yang membuat {name_f} mempertanyakan semua kenangan mereka.",
    ],
    "build": [
        "Surat demi surat dibaca ulang, dan setiap baris terasa seperti pertanyaan yang tidak pernah berani diajukan langsung.",
        "{name_f} mencari jejaknya ke {place}, bertanya kepada orang-orang yang dulu mengenal mereka berdua. Setiap jawaban malah menambah sakit.",
        "Rahasia yang terungkap bukan tentang pengkhianatan besar, melainkan tentang kata-kata kecil yang tidak perdiucapkan pada waktunya.",
    ],
    "climax": [
        "Mereka akhirnya bertemu lagi, persis di tempat dan {time} yang sama. Tapi kali ini, yang menatap {name_f} adalah orang yang sudah hidup membawa beban selama bertahun-tahun.",
        "Ketika kebenaran akhirnya terucap, tidak ada teriakan. Hanya keheningan panjang dan air mata yang jatuh ke tanah.",
    ],
    "resolution": [
        "Mereka berpisah sebagai orang yang berbeda, membawa masing-masing kepingan cerita yang tidak akan pernah utuh lagi.",
        "Hari ini, {object} itu masih tersimpan rapi. Sebagai bukti bahwa kadang, hal paling menyakitkan adalah sesuatu yang sebenarnya bisa dicegah dengan satu kejujuran kecil.",
        "Dan setiap {time}, {name_f} masih duduk di tempat itu — bukan menunggu, tapi mengingat.",
    ],
}

POOL: dict[str, dict[str, list[str]]] = {
    "horror": HORROR,
    "motivation": MOTIVATION,
    "education": EDUCATION,
    "drama": DRAMA,
}

STAGES = ["hook", "setup", "build", "climax", "resolution"]


def assemble(
    pool: dict[str, list[str]],
    topic: str = "",
    seed: int | str | None = None,
    length_hint: int = 3,
) -> str:
    """Assemble one story from a part pool dict (hook/setup/build/climax/resolution).

    Exposed so English (or custom) pools can reuse the same assembly logic.
    """
    rng = rng_from_seed(seed)
    slots = _slots(rng)

    def fill(text: str) -> str:
        return text.format(**slots)

    parts: list[str] = [fill(_pick(rng, pool["hook"]))]
    parts.append(fill(_pick(rng, pool["setup"])))

    # scale beats to requested length: narrative reads at ~130 words/min and
    # each paragraph is ~30 words, so ~4.3 paragraphs per minute total.
    # Fixed stages contribute 4 paragraphs already.
    beats = max(1, min(12, int(round(length_hint * 4.3)) - 4))
    used: set[int] = set()
    for _ in range(beats):
        avail = [i for i in range(len(pool["build"])) if i not in used] or list(range(len(pool["build"])))
        idx = _pick(rng, avail)
        used.add(idx)
        parts.append(fill(pool["build"][idx]))

    parts.append(fill(_pick(rng, pool["climax"])))
    parts.append(fill(_pick(rng, pool["resolution"])))

    if topic:
        topic = topic.strip()
        if topic and not topic.endswith((".", "!", "?")):
            topic += "."
        parts.insert(0, topic)

    return "\n\n".join(parts).strip()


def generate(
    niche: str,
    topic: str = "",
    seed: int | str | None = None,
    length_hint: int = 3,
) -> str:
    """Assemble one Indonesian story from the built-in pool for `niche`."""
    pool = POOL.get(niche, POOL["motivation"])
    return assemble(pool, topic=topic, seed=seed, length_hint=length_hint)


__all__ = ["generate", "assemble", "POOL"]
