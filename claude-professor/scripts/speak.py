#!/usr/bin/env python3
"""Turn a narration script into speech with Kokoro-82M (open source, runs locally).

Usage:
  python speak.py --check                      # can Kokoro run here? exit 0 = yes
  python speak.py SCRIPT.md --out OUTDIR [--voice af_heart] [--speed 1.0]

Writes OUTDIR/slide_NNN.wav per slide, OUTDIR/narration.wav (+ .mp3 if ffmpeg exists)
and OUTDIR/timings.json ([{page, wav, seconds}]).
Needs: pip install kokoro-onnx soundfile numpy   (model ~300 MB is downloaded once to ~/.cache/claude-professor)
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ensure_dir, find_ffmpeg, parse_script, split_sentences  # noqa: E402

CACHE = Path.home() / ".cache" / "claude-professor"
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")


def check() -> int:
    try:
        import kokoro_onnx, soundfile, numpy  # noqa: F401,E401
    except Exception as e:
        print(f"NOT_OK: python packages missing ({e}). Try: pip install kokoro-onnx soundfile numpy")
        return 1
    if all((CACHE / f).exists() for f in FILES):
        print("OK: Kokoro ready")
        return 0
    try:
        urllib.request.urlopen(urllib.request.Request(BASE + FILES[1], method="HEAD"), timeout=8)
        print("OK: packages installed, model will download on first use")
        return 0
    except Exception as e:
        print(f"NOT_OK: cannot download the Kokoro model (no internet?): {e}")
        return 2


def download(url: str, dest: Path, retries: int = 40) -> None:
    """Resumable download: keeps a .part file and continues with a Range request after dropped connections."""
    tmp = dest.parent / (dest.name + ".part")
    for attempt in range(retries):
        have = tmp.stat().st_size if tmp.exists() else 0
        req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                total = have + int(r.headers.get("Content-Length", 0))
                if have and r.status != 206:  # server ignored Range: start over
                    have = 0
                with open(tmp, "ab" if have else "wb") as out:
                    while chunk := r.read(1 << 16):
                        out.write(chunk)
                        have += len(chunk)
                        if total:
                            print(f"\r{dest.name}: {have * 100 // total}%", end="", file=sys.stderr)
            print(file=sys.stderr)
            tmp.rename(dest)
            return
        except Exception as e:
            if hasattr(e, "code") and e.code == 416 and tmp.exists():  # already complete
                tmp.rename(dest)
                return
            print(f"\n{dest.name}: connection problem ({e}); retrying ({attempt + 1}/{retries})", file=sys.stderr)
            time.sleep(min(2 * (attempt + 1), 15))
    raise RuntimeError(f"Could not download {dest.name}. Download it manually from {url} into {dest.parent}")


def get_models() -> tuple[str, str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        dest = CACHE / f
        if not dest.exists():
            print(f"Downloading {f} (one time)...", file=sys.stderr)
            download(BASE + f, dest)
    return str(CACHE / FILES[0]), str(CACHE / FILES[1])


def chunks(text: str, limit: int = 280) -> list[str]:
    out, cur = [], ""
    for s in split_sentences(text):
        if cur and len(cur) + len(s) > limit:
            out.append(cur)
            cur = ""
        cur = f"{cur} {s}".strip()
    return out + ([cur] if cur else [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        sys.exit(check())
    if not a.script or not a.out:
        ap.error("SCRIPT and --out are required")

    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro

    sections = parse_script(Path(a.script).read_text(encoding="utf-8"))
    out = ensure_dir(a.out)
    kokoro = Kokoro(*get_models())

    timings, all_audio, sr = [], [], 24000
    gap = None
    for page, text in sections:
        parts = []
        for c in chunks(text):
            samples, sr = kokoro.create(c, voice=a.voice, speed=a.speed, lang="en-us")
            gap = np.zeros(int(sr * 0.25), dtype=samples.dtype)
            parts += [samples, gap]
        audio = np.concatenate(parts)
        wav = out / f"slide_{page:03d}.wav"
        sf.write(str(wav), audio, sr)
        all_audio.append(audio)
        timings.append({"page": page, "wav": str(wav), "seconds": round(len(audio) / sr, 2)})
        print(f"slide {page}: {timings[-1]['seconds']}s", file=sys.stderr)

    full = out / "narration.wav"
    sf.write(str(full), np.concatenate(all_audio), sr)
    result = {"wav": str(full), "timings": timings}

    ff = find_ffmpeg()
    if ff:
        mp3 = out / "narration.mp3"
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(full), "-b:a", "128k", str(mp3)], check=True)
        result["mp3"] = str(mp3)

    (out / "timings.json").write_text(json.dumps(timings, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
