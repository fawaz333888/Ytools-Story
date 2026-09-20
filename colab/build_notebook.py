"""Generate the Colab notebook JSON from cells defined here.

Run locally:  python colab/build_notebook.py
This keeps the notebook source in version control as readable text instead
of a giant opaque JSON blob.
"""

from __future__ import annotations

import json
import os

CELLS: list[dict] = [
    {
        "type": "markdown",
        "source": [
            "# Ytools-Story — YouTube Faceless Automation\n",
            "\n",
            "Loop footage + overlay (watermark, particles, karaoke subtitle) + TTS narration.\n",
            "Bawa script sendiri (wajib) atau pakai LLM (openai/anthropic, butuh API key). Bilingual ID/EN.\n",
            "\n",
            "**Cara pakai:** Run semua cell top-to-bottom (Shift+Enter).\n",
            "Upload footage di **Cell 4**, atur opsi di **Cell 5**, upload script di **Cell 7**, lalu lihat hasil di **Cell 8-9**.\n",
        ],
    },
    {
        "type": "code",
        "source": [
            "#@title 1. Install dependencies (~1 min)\n",
            "!pip install -q edge-tts ffmpeg-python imageio-ffmpeg pillow numpy pyyaml\n",
            "\n",
            "import os, sys, shutil, subprocess\n",
            "print('python', sys.version.split()[0])\n",
            "\n",
            "REPO = 'https://github.com/fawaz333888/Ytools-Story.git'\n",
            "DEST = '/content/Ytools-Story'\n",
            "\n",
            "def _have_ytools(path):\n",
            "    return os.path.isfile(os.path.join(path, 'ytools', '__init__.py'))\n",
            "\n",
            "if not _have_ytools(DEST):\n",
            "    ok = subprocess.run(['git', 'clone', '-q', REPO, DEST]).returncode == 0\n",
            "    if not ok or not _have_ytools(DEST):\n",
            "        # fallback: copy from the cwd this notebook was launched from\n",
            "        src = os.getcwd()\n",
            "        if _have_ytools(src) and os.path.abspath(src) != os.path.abspath(DEST):\n",
            "            shutil.copytree(src, DEST, dirs_exist_ok=True)\n",
            "            print('clone failed - copied local copy from', src)\n",
            "        else:\n",
            "            print('ERROR: clone gagal dan tidak ada copy lokal. Push repo ke GitHub dulu.')\n",
            "\n",
            "os.chdir(DEST)\n",
            "sys.path.insert(0, DEST)\n",
            "\n",
            "from ytools import __version__\n",
            "print('ytools', __version__)",
        ],
    },
    {
        "type": "code",
        "source": [
            "#@title 2. Cek environment (GPU / ffmpeg)\n",
            "import subprocess\n",
            "try:\n",
            "    print(subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv'],\n",
            "                         capture_output=True, text=True).stdout or 'no GPU')\n",
            "except Exception as e:\n",
            "    print('nvidia-smi error:', e)\n",
            "\n",
            "from ytools.render.ffutil import FFRunner\n",
            "ff = FFRunner()\n",
            "print('ffmpeg:', ff.version())\n",
            "print('ffprobe:', ff.ffprobe or 'tidak ada (fallback parse ffmpeg -i)')\n",
            "print('nvenc flag:', ff.supports_nvenc())",
        ],
    },
    {
        "type": "code",
        "source": [
            "#@title 3. Mount Google Drive (sekali, untuk simpan hasil)\n",
            "from google.colab import drive\n",
            "drive.mount('/content/drive')\n",
            "\n",
            "import os\n",
            "DRIVE_ROOT = '/content/drive/MyDrive/Ytools-Story'\n",
            "os.makedirs(DRIVE_ROOT, exist_ok=True)\n",
            "print('Drive siap:', DRIVE_ROOT)",
        ],
    },
    {
        "type": "code",
        "source": [
            "#@title 4. Upload footage video (minimal 30 detik)\n",
            "from google.colab import files\n",
            "import shutil, os\n",
            "\n",
            "FOOTAGE = 'footage.mp4'\n",
            "if not os.path.isfile(FOOTAGE):\n",
            "    uploaded = files.upload()\n",
            "    if uploaded:\n",
            "        name = list(uploaded.keys())[0]\n",
            "        shutil.move(name, FOOTAGE)\n",
            "        print('saved as', FOOTAGE)\n",
            "    else:\n",
            "        print('tidak ada file diupload')\n",
            "\n",
            "if os.path.isfile(FOOTAGE):\n",
            "    info = ff.probe(FOOTAGE)\n",
            "    print(f\"footage: {info['width']}x{info['height']} {info['duration']:.1f}s fps={info['fps']:.1f} audio={info['has_audio']}\")\n",
            "    if info['duration'] < 30:\n",
            "        print('WARNING: footage < 30 detik. Loop terlalu repetitif untuk YouTube.')",
        ],
    },
    {
        "type": "code",
        "source": [
            "#@title 5. Konfigurasi\n",
            "#@markdown --- **Story** ---\n",
            "niche = 'horror' #@param ['horror','motivation','education','drama','custom']\n",
            "language = 'id' #@param ['id','en']\n",
            "provider = 'manual' #@param ['manual','openai','anthropic']\n",
            "topic = '' #@param {type:'string'}\n",
            "length_minutes = 3 #@param {type:'number'}\n",
            "add_hook = True #@param {type:'boolean'}\n",
            "seed = None #@param {type:'raw'}\n",
            "\n",
            "#@markdown --- **Narration (TTS)** ---\n",
            "voice = '' #@param {type:'string'}  # kosong = auto by language\n",
            "tts_rate = '+0%' #@param {type:'string'}\n",
            "\n",
            "#@markdown --- **Video** ---\n",
            "width = 1280 #@param {type:'integer'}\n",
            "height = 720 #@param {type:'integer'}\n",
            "fps = 30 #@param {type:'integer'}\n",
            "motion = 'slow_drift' #@param ['none','slow_drift','slow_zoom']\n",
            "\n",
            "#@markdown --- **Overlays** ---\n",
            "particle_style = 'dust' #@param ['dust','snow','sparkle','fireflies','embers','fog']\n",
            "particle_density = 60 #@param {type:'integer'}\n",
            "watermark_text = '@YtoolsChannel' #@param {type:'string'}\n",
            "watermark_style = 'badge' #@param ['badge','plain','logo']\n",
            "watermark_position = 'top-right' #@param ['top-left','top-right','bottom-left','bottom-right','center']\n",
            "subtitle_style = 'karaoke' #@param ['karaoke','simple']\n",
            "\n",
            "#@markdown --- **Output** ---\n",
            "output_name = 'video.mp4' #@param {type:'string'}\n",
            "\n",
            "#@markdown --- **LLM key (hanya jika provider != manual)** ---\n",
            "os.environ.pop('OPENAI_API_KEY', None)\n",
            "if provider == 'openai':\n",
            "    from google.colab import userdata\n",
            "    os.environ['OPENAI_API_KEY'] = userdata.get('OPENAI_API_KEY', '')\n",
            "\n",
            "from ytools.config import Config\n",
            "cfg = Config()\n",
            "cfg.set('story.niche', niche); cfg.set('story.language', language)\n",
            "cfg.set('story.provider', provider); cfg.set('story.topic', topic)\n",
            "cfg.set('story.length_minutes', length_minutes); cfg.set('story.add_hook', add_hook)\n",
            "cfg.set('story.seed', seed)\n",
            "cfg.set('tts.voice', voice or None); cfg.set('tts.rate', tts_rate)\n",
            "cfg.set('video.width', width); cfg.set('video.height', height)\n",
            "cfg.set('video.fps', fps); cfg.set('video.motion', motion)\n",
            "cfg.set('overlays.particles.style', particle_style)\n",
            "cfg.set('overlays.particles.density', particle_density)\n",
            "cfg.set('overlays.watermark.text', watermark_text)\n",
            "cfg.set('overlays.watermark.style', watermark_style)\n",
            "cfg.set('overlays.watermark.position', watermark_position)\n",
            "cfg.set('overlays.subtitle.style', subtitle_style)\n",
            "cfg.set('output.encoder', 'auto')\n",
            "problems = cfg.validate()\n",
            "print('config OK' if not problems else 'config problems:', problems)",
        ],
    },
    {
        "type": "code",
        "source": [
            "#@title 6. Generate hook ideas (opsional, langsung dipakai jika add_hook=True)\n",
            "from ytools.story import hook\n",
            "for i, h in enumerate(hook.generate_hooks(niche, language, count=3), 1):\n",
            "    print(f'{i}. {h}')",
        ],
    },
    {
        "type": "code",
        "source": [
            "#@title 7. RUN pipeline (story -> tts -> overlays -> render)\n",
            "from ytools.pipeline import Pipeline\n",
            "\n",
            "workdir = '/content/ytools_work/run'\n",
            "pipe = Pipeline(workdir, cfg, ff=ff)\n",
            "\n",
            "script_arg = None\n",
            "if provider == 'manual':\n",
            "    import os\n",
            "    SCRIPT = '/content/script.txt'\n",
            "    if not os.path.isfile(SCRIPT):\n",
            "        from google.colab import files\n",
            "        up = files.upload()\n",
            "        assert up, 'provider=manual wajib upload file script .txt'\n",
            "        name = list(up.keys())[0]\n",
            "        open(SCRIPT, 'wb').write(up[name])\n",
            "    script_arg = SCRIPT\n",
            "\n",
            "art = pipe.run(footage=FOOTAGE, script_path=script_arg)\n",
            "\n",
            "from IPython.display import HTML\n",
            "print('duration:', art.duration, 'words:', len(art.words))",
        ],
    },
    {
        "type": "code",
        "source": [
            "#@title 8. Preview hasil\n",
            "from IPython.display import HTML, display\n",
            "from base64 import b64encode\n",
            "\n",
            "out = art.result.path\n",
            "mp4 = open(out, 'rb').read()\n",
            "data_url = 'data:video/mp4;base64,' + b64encode(mp4).decode()\n",
            "display(HTML(f'<video width=640 controls><source src=\"{data_url}\"></video>'))\n",
            "print('size MB:', len(mp4) / 1e6)",
        ],
    },
    {
        "type": "code",
        "source": [
            "#@title 9. Simpan hasil ke Drive\n",
            "import shutil, json, datetime\n",
            "\n",
            "run_dir = os.path.join(DRIVE_ROOT, datetime.date.today().isoformat())\n",
            "os.makedirs(run_dir, exist_ok=True)\n",
            "\n",
            "shutil.copy(art.result.path, os.path.join(run_dir, output_name))\n",
            "shutil.copy(art.script_path, os.path.join(run_dir, output_name.replace('.mp4', '_script.txt')))\n",
            "\n",
            "meta = {\n",
            "    'niche': niche,\n",
            "    'language': language,\n",
            "    'provider': provider,\n",
            "    'length_minutes': length_minutes,\n",
            "    'add_hook': add_hook,\n",
            "    'duration': art.duration,\n",
            "    'footage': FOOTAGE,\n",
            "    'created': datetime.datetime.now().isoformat(),\n",
            "}\n",
            "meta_path = os.path.join(run_dir, output_name.replace('.mp4', '_meta.json'))\n",
            "with open(meta_path, 'w', encoding='utf-8') as fh:\n",
            "    json.dump(meta, fh, ensure_ascii=False, indent=2)\n",
            "\n",
            "print('saved to', run_dir)\n",
            "for f in sorted(os.listdir(run_dir)):\n",
            "    print('  ', f)",
        ],
    },
    {
        "type": "markdown",
        "source": [
            "## Catatan\n",
            "\n",
            "- **Session Colab free** maksimal ~12 jam, idle disconnect ~90 menit. Hasil otomatis tersimpan ke Drive (cell 9) — aman berhenti kapan saja.\n",
            "- **Reuse**: cell 7 menggunakan cache — rerun cepat kalau footage/particles/watermark sudah ada.\n",
            "- **Story**: provider `manual` wajib bawa script sendiri. Untuk skrip panjang (>5 menit) gunakan `openai`/`anthropic`.\n",
            "- **Footage < 30 detik** akan terlalu repetitif; YouTube demote konten loop pendek berulang.\n",
        ],
    },
]


def build(cells: list[dict]) -> dict:
    nb_cells = []
    for c in cells:
        if c["type"] == "markdown":
            nb_cells.append(
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": c["source"],
                }
            )
        else:
            src = "".join(c["source"])
            nb_cells.append(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": src,
                }
            )
    return {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "colab": {
                "name": "Ytools-Story.ipynb",
                "provenance": [],
                "toc_visible": True,
            },
            "kernelspec": {
                "display_name": "Python 3",
                "name": "python3",
            },
            "language_info": {"name": "python"},
            "accelerator": "GPU",
        },
        "cells": nb_cells,
    }


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "Ytools-Story.ipynb")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(build(CELLS), fh, indent=1, ensure_ascii=False)
    print("wrote", out)


if __name__ == "__main__":
    main()
