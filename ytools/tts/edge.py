"""Edge-TTS narration with word-level timing capture.

The Communicate stream emits WordBoundary events (offset/duration in 100ns
ticks) which drive the karaoke subtitle overlay downstream. Long scripts are
split into sentence chunks because edge-tts degrades on very long requests,
then chunk timings are offset-stitched into a single timeline.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from ..utils import split_sentences

TICKS_PER_SECOND = 10_000_000
# edge-tts serves 24kHz mono mp3; we re-encode to wav for exact concat.
SAMPLE_RATE = 24000


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class NarrationResult:
    audio_path: str
    words: list[Word] = field(default_factory=list)
    duration: float = 0.0
    sample_rate: int = SAMPLE_RATE


class TTSError(RuntimeError):
    pass


async def _synthesize_chunk(
    text: str,
    voice: str,
    rate: str,
    volume: str,
    pitch: str,
    out_mp3: str,
) -> tuple[list[Word], int]:
    """Synthesize one chunk; returns (words, byte size)."""
    import edge_tts

    words: list[Word] = []
    communicate = edge_tts.Communicate(
        text, voice, rate=rate, volume=volume, pitch=pitch,
        boundary="WordBoundary",
    )
    size = 0
    with open(out_mp3, "wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                data = chunk["data"]
                fh.write(data)
                size += len(data)
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / TICKS_PER_SECOND
                end = start + chunk["duration"] / TICKS_PER_SECOND
                wtext = chunk["text"].strip()
                if wtext:
                    words.append(Word(text=wtext, start=start, end=end))
    if not os.path.isfile(out_mp3) or os.path.getsize(out_mp3) == 0:
        raise TTSError(f"no audio produced for chunk: {text[:60]!r}")
    return words, size


async def synthesize_async(
    script: str,
    out_dir: str,
    voice: str = "id-ID-GadisNeural",
    rate: str = "+0%",
    volume: str = "+0%",
    pitch: str = "+0Hz",
    max_chars: int = 1800,
    on_progress=None,
) -> NarrationResult:
    """Synthesize full script; returns NarrationResult with stitched timings."""
    import edge_tts

    os.makedirs(out_dir, exist_ok=True)

    # chunk by sentences under max_chars
    chunks: list[str] = []
    buf = ""
    for sent in split_sentences(script):
        if len(buf) + len(sent) + 1 <= max_chars:
            buf = (buf + " " + sent).strip()
        else:
            if buf:
                chunks.append(buf)
            buf = sent
            while len(buf) > max_chars:  # hard-wrap overlong sentence
                chunks.append(buf[:max_chars])
                buf = buf[max_chars:].strip()
    if buf:
        chunks.append(buf)
    if not chunks:
        raise TTSError("script produced no speakable chunks")

    # verify voice exists (fail fast with a helpful message)
    try:
        voices = await edge_tts.list_voices()
        known = {v["ShortName"] for v in voices}
    except Exception as exc:  # pragma: no cover - network quirks
        raise TTSError(f"cannot list edge-tts voices: {exc}") from exc
    if voice not in known:
        raise TTSError(
            f"voice {voice!r} not found. Indonesian options: "
            + ", ".join(sorted(v for v in known if v.startswith("id-ID")))
        )

    words_per_chunk: list[list[Word]] = []
    mp3_paths: list[str] = []
    for i, chunk in enumerate(chunks):
        mp3 = os.path.join(out_dir, f"chunk_{i:04d}.mp3")
        words, _ = await _synthesize_chunk(
            chunk, voice, rate, volume, pitch, mp3
        )
        mp3_paths.append(mp3)
        words_per_chunk.append(words)
        if on_progress:
            on_progress(i + 1, len(chunks))

    # Decode each chunk to sample-exact wav and measure duration, so chunk-local
    # word timings can be offset-stitched onto the absolute timeline.
    wav_paths: list[str] = []
    chunk_durs: list[float] = []
    for i, mp3 in enumerate(mp3_paths):
        wav = os.path.join(out_dir, f"chunk_{i:04d}.wav")
        _to_wav(mp3, wav)
        chunk_durs.append(_wav_duration(wav))
        wav_paths.append(wav)

    stitched: list[Word] = []
    abs_t = 0.0
    for dur, cwords in zip(chunk_durs, words_per_chunk):
        for w in cwords:
            stitched.append(Word(text=w.text, start=w.start + abs_t, end=w.end + abs_t))
        abs_t += dur

    final_wav = os.path.join(out_dir, "narration.wav")
    _concat_wav(wav_paths, final_wav)
    total_dur = _wav_duration(final_wav)

    return NarrationResult(
        audio_path=final_wav, words=stitched, duration=total_dur
    )


def _to_wav(mp3: str, wav: str) -> None:
    from ..render.ffutil import FFRunner

    ff = FFRunner()
    ff.run([ff.ffmpeg, "-y", "-v", "error", "-i", mp3,
            "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", wav])


def _wav_duration(wav: str) -> float:
    import wave

    with wave.open(wav, "rb") as fh:
        frames = fh.getnframes()
        rate = fh.getframerate()
        return frames / float(rate)


def _concat_wav(wavs: list[str], out: str) -> None:
    """Concat same-format wavs by raw PCM joining (sample-exact)."""
    import wave

    if not wavs:
        raise TTSError("no wav chunks to concat")
    with wave.open(wavs[0], "rb") as fh:
        params = fh.getparams()
    with wave.open(out, "wb") as out_fh:
        out_fh.setparams(params)
        for w in wavs:
            with wave.open(w, "rb") as fh:
                if fh.getparams()[:3] != params[:3]:
                    raise TTSError(f"format mismatch in {w}")
                out_fh.writeframes(fh.readframes(fh.getnframes()))


def synthesize(
    script: str,
    out_dir: str,
    voice: str = "id-ID-GadisNeural",
    rate: str = "+0%",
    volume: str = "+0%",
    pitch: str = "+0Hz",
    on_progress=None,
) -> NarrationResult:
    """Sync entry point. Handles being called inside a running event loop
    (Jupyter / IPython kernels already run one)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            synthesize_async(script, out_dir, voice, rate, volume, pitch,
                             on_progress=on_progress)
        )
    # We are inside a running loop (notebook kernel): run the coroutine on a
    # private loop in a worker thread instead of nesting asyncio.run().
    return _run_on_loop(
        synthesize_async(script, out_dir, voice, rate, volume, pitch,
                         on_progress=on_progress)
    )


def _run_on_loop(coro):
    """Run a coroutine to completion when the current thread already runs a loop.

    IPython/Jupyter kernels own a running event loop, so asyncio.run() raises.
    We spin up a private loop on a worker thread and block until the coroutine
    finishes; the caller's loop is never entered re-entrantly.
    """
    import concurrent.futures
    import threading

    result: dict = {}

    def _worker() -> None:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result["value"] = loop.run_until_complete(coro)
        except BaseException as exc:  # noqa: BLE001 - propagate to caller
            result["error"] = exc
        finally:
            loop.close()

    # run in a daemon thread; the TTS work is network-bound I/O, not CPU-bound
    th = threading.Thread(target=_worker, daemon=True)
    th.start()
    th.join()
    if "error" in result:
        raise result["error"]
    return result["value"]


__all__ = ["synthesize", "synthesize_async", "NarrationResult", "Word", "TTSError"]
