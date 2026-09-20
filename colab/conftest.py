"""Pytest conftest so the Colab notebook can be executed locally with nbval.

On real Colab, google.colab exists and the repo is cloned into /content.
Locally neither is true, so this conftest installs a tiny google.colab shim
into site-packages and puts the repo on sys.path.
"""

import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

SHIM_BODY = '''"""Local test shim for google.colab (installed by nbval conftest)."""

import os


class _Files:
    def upload(self):
        return {}

    def download(self, path):
        print("shim download", path)


class _UserData:
    def get(self, key, default=""):
        return os.environ.get(key, default)


class _Drive:
    def mount(self, mountpoint, quiet=False):
        os.makedirs(mountpoint, exist_ok=True)


files = _Files()
userdata = _UserData()
drive = _Drive()
'''


def _install_shim() -> None:
    """Drop a fake google.colab package next to the real google namespace."""
    import google  # noqa: PLC0415  (import here: nbval shells may differ)

    target = None
    for p in google.__path__:
        if "site-packages" in os.path.normcase(p):
            target = os.path.join(p, "colab")
            break
    if target is None:
        return
    os.makedirs(target, exist_ok=True)
    init = os.path.join(target, "__init__.py")
    with open(init, "w", encoding="utf-8") as fh:
        fh.write(SHIM_BODY)


def _seed_footage() -> None:
    """Copy the test fixture to ./footage.mp4 so notebook cell 3 can probe it."""
    src = os.path.join(_REPO, "tests", "fixtures", "footage_test.mp4")
    dst = os.path.join(_REPO, "footage.mp4")
    if os.path.isfile(src) and not os.path.isfile(dst):
        shutil.copy(src, dst)


if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

# cell 1 falls back to copying from cwd, so run from the repo root
os.chdir(_REPO)

_install_shim()
_seed_footage()
