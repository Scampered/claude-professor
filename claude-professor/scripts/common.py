"""Shared helpers for claude-professor scripts."""
import re
import shutil
from pathlib import Path


def parse_pages(spec: str, count: int) -> list[int]:
    """'all' | '80, 89-100' | '89 to 100' -> sorted unique 1-based page numbers."""
    spec = spec.strip().lower()
    if spec in ("", "all", "*"):
        return list(range(1, count + 1))
    spec = re.sub(r"\s*(to|–|—|until|through)\s*", "-", spec)
    pages: set[int] = set()
    for part in re.split(r"[,;\s]+", spec):
        if not part:
            continue
        lo, _, hi = part.partition("-")
        a, b = int(lo), int(hi or lo)
        if a > b:
            a, b = b, a
        pages.update(range(a, b + 1))
    bad = [p for p in pages if p < 1 or p > count]
    if not pages or bad:
        raise ValueError(f"Pages out of range (document has {count} pages): {sorted(bad) or spec}")
    return sorted(pages)


SECTION = re.compile(r"^##\s*Slide\s+(\d+)\s*$", re.M)


def parse_script(text: str) -> list[tuple[int, str]]:
    """Split a script into [(page, narration)] using '## Slide N' headers."""
    marks = list(SECTION.finditer(text))
    if not marks:
        raise ValueError("Script needs '## Slide N' headers, one per slide.")
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end():end].strip()
        if body:
            out.append((int(m.group(1)), body))
    return out


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s]


def find_ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def ensure_dir(p) -> Path:
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p
