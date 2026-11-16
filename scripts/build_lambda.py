"""B4 - Build the Lambda zip without Docker: Linux wheels downloaded by pip + our code.

    python scripts/build_lambda.py          # -> .build/lambda.zip

Choice (see docs/AWS.md): a zip with manylinux wheels instead of a container image
(no Docker on the team's machines) and instead of the managed "AWS SDK for pandas"
layer (its version number would have to be pinned by hand per region). pandas and
numpy fit well under the 250 MB unzipped limit once their test suites are stripped.

Data is NOT in the zip: the function reads it from the S3 data bucket at cold
start (api/bootstrap.py). Rules (rules/, or the reference examples in contracts/)
and contracts are bundled because they are versioned with the code.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / ".build"
PKG = BUILD / "lambda"
ZIP = BUILD / "lambda.zip"
CODE_DIRS = ["api", "core", "agents", "services", "ingest", "contracts", "rules"]
STRIP_DIRS = {"tests", "test", "__pycache__", "benchmarks"}
LIMIT_UNZIPPED = 250 * 1024 * 1024


def _size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def build() -> Path:
    shutil.rmtree(PKG, ignore_errors=True)
    PKG.mkdir(parents=True)
    print("1/3 Linux wheels (python 3.12, x86_64)...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
        "--target", str(PKG), "--implementation", "cp", "--python-version", "3.12",
        "--platform", "manylinux_2_28_x86_64", "--platform", "manylinux2014_x86_64",
        "--only-binary=:all:", "-r", str(ROOT / "api" / "requirements-lambda.txt"),
    ], check=True)

    print("2/3 Code: " + ", ".join(d for d in CODE_DIRS if (ROOT / d).exists()))
    for d in CODE_DIRS:
        src = ROOT / d
        if src.exists():
            shutil.copytree(src, PKG / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests"))

    for p in sorted(PKG.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if p.is_dir() and p.name in STRIP_DIRS and p.parent.name != "api":
            shutil.rmtree(p, ignore_errors=True)
    unzipped = _size(PKG)
    if unzipped > LIMIT_UNZIPPED:
        raise SystemExit(f"Package too large: {unzipped / 2**20:.0f} MB > 250 MB unzipped")

    print("3/3 Zip...")
    ZIP.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in sorted(PKG.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(PKG).as_posix())
    print(f"OK {ZIP.relative_to(ROOT)}: {ZIP.stat().st_size / 2**20:.1f} MB zipped, {unzipped / 2**20:.0f} MB unzipped")
    return ZIP


if __name__ == "__main__":
    build()
