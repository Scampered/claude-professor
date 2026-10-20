#!/usr/bin/env python3
"""Make an MP4: each slide image is shown while its narration plays.

Usage: python make_video.py SLIDES_DIR AUDIO_DIR --out lesson.mp4
SLIDES_DIR holds slide_NNN.png (from render_slides.py); AUDIO_DIR holds slide_NNN.wav + timings.json (from speak.py).
Needs ffmpeg on PATH (or: pip install imageio-ffmpeg).
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_ffmpeg  # noqa: E402

VF = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
      "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=white,format=yuv420p")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slides_dir")
    ap.add_argument("audio_dir")
    ap.add_argument("--out", default="lesson.mp4")
    a = ap.parse_args()

    ff = find_ffmpeg()
    if not ff:
        sys.exit("ffmpeg not found. Install it or run: pip install imageio-ffmpeg")
    timings = json.loads((Path(a.audio_dir) / "timings.json").read_text())

    tmp = Path(tempfile.mkdtemp())
    clips = []
    for t in timings:
        img = Path(a.slides_dir) / f"slide_{t['page']:03d}.png"
        clip = tmp / f"clip_{t['page']:03d}.mp4"
        subprocess.run([ff, "-y", "-loglevel", "error", "-loop", "1", "-framerate", "5", "-i", str(img),
                        "-i", t["wav"], "-vf", VF, "-c:v", "libx264", "-tune", "stillimage",
                        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest", str(clip)], check=True)
        clips.append(clip)

    listing = tmp / "list.txt"
    listing.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips))
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", a.out], check=True)
    print(a.out)


if __name__ == "__main__":
    main()
