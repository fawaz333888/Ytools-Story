# Ytools-V1

YouTube faceless automation: loop footage + overlays + TTS narration, bilingual ID/EN, Colab-ready.

## Quick start (local)

```bash
pip install -r requirements.txt
python -m ytools run --footage your_video.mp4 --niche horror --language id --minutes 3
```

Output: `output/video.mp4` (720p, H.264 + AAC, looped to narration length).

## Pipeline

1. **Story** — manual script file (default, wajib `--script`) atau LLM (`openai`/`anthropic`). Niche: `horror` / `motivation` / `education` / `drama` / `custom`.
2. **TTS** — `edge-tts`, word-level timestamps via `WordBoundary` events. Indonesian: `id-ID-GadisNeural`, `id-ID-ArdiNeural`. English: `en-US-AvaNeural` etc.
3. **Overlays** (all optional, ≥2 burned in by default):
   - Karaoke **subtitles** (ASS, per-word highlight from TTS word timings)
   - **Particles** — dust / snow / sparkle / fireflies / embers / fog (seamless loop, alpha video)
   - **Watermark** — badge / plain / logo, 5 anchor positions
   - **Audio spectrum** — optional visualizer for the narration: `cqt` (bar graph, default) / `spectrum` / `waves` / `vectorscope`, bottom or center
4. **Compose** — single ffmpeg pass: footage cover-scaled + optional motion crop (slow drift / breathing zoom), overlays burned, original audio **muted**, narration muxed, looped to exact narration duration.

## Commands

```bash
python -m ytools init                  # write example config
python -m ytools voices                # list Indonesian edge-tts voices
python -m ytools run --footage v.mp4 --script my_story.txt          # skip generation
python -m ytools run --footage v.mp4 --provider openai --topic "..." # needs OPENAI_API_KEY
```

Provider `openai` juga mendukung endpoint **OpenAI-compatible** (OpenRouter, Groq, vLLM lokal, dll) — set `story.base_url` di config atau `llm_base_url` di notebook Colab. `base_url` kosong = endpoint OpenAI resmi.

## Colab

Run `colab/Ytools-V1.ipynb` (GPU runtime recommended). All cells validated via `jupyter nbconvert --execute`. Source of the notebook is `colab/build_notebook.py` — regenerate with `python colab/build_notebook.py` after edits.

Notes:
- Colab free session: ~12h max, idle disconnect ~90 min — save to Drive before stopping.
- Provider `manual` butuh file `--script`; gunakan LLM untuk skrip panjang.
- Footage ≥30s recommended; shorter loops get flagged as repetitive content.

## Layout

```
ytools/
  story/    generator, LLM wrappers
  tts/      edge-tts synthesis + word timings (chunked, offset-stitched)
  overlays/ particles, watermark, karaoke subtitles
  render/   ffmpeg binary discovery, encoder smoke test, filter-graph composer
  pipeline.py, main.py (CLI), config.py
colab/      notebook builder + generated .ipynb
tests/      fixtures
```

Requirements: `edge-tts`, `ffmpeg-python`, `imageio-ffmpeg` (bundles a full ffmpeg), `pillow`, `numpy`, `pyyaml`. Optional: `openai`, `anthropic`.
