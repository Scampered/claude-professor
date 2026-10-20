# Claude Professor

A Claude skill that explains your lecture slides out loud.

Give it a PDF or PowerPoint, tell it which pages (`all`, `80`, `89-100`, `80, 89-100`), and Claude reads the slides (formulas and diagrams included) and builds:

- an **interactive lesson** (one HTML file): each slide is recreated in crisp HTML with real math, and you can **click any sentence, formula or table row** to read and hear it explained, with worked examples. Or press *Play slide* for a guided walkthrough. The voice is the open-source [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), embedded in the file so it works offline.
- an **ask box** inside the lesson: type a question ("why divide by s?", "explain more simply") and Claude adds an explanation to that slide or rewrites the one you selected, then speaks it
- an optional **style**: tell it how you want things explained ("like I'm new to maths", "Cambridge A Level", "IB HL", "with football examples"), or leave it out for a clear default
- a **voice recording** (MP3/WAV) of the whole explanation
- a **video** (MP4) that shows each slide while it is explained
- where Kokoro can't run (e.g. the claude.ai sandbox has no internet), the same interactive lesson using your browser's voices instead

No API keys needed. Claude itself does the reading and writing.

## Install

**Claude Code**
```bash
git clone https://github.com/<you>/claude-professor
cp -r claude-professor/claude-professor ~/.claude/skills/        # macOS/Linux
# Windows PowerShell: Copy-Item -Recurse claude-professor\claude-professor $HOME\.claude\skills\
```

**claude.ai (web / desktop)**
Zip the inner `claude-professor/` folder (the one containing `SKILL.md`) and upload it under *Settings → Capabilities → Skills*. Requires code execution to be enabled.

## Use

Just say: *"Explain pages 89-100 of this deck"* and attach the file, or *"use claude-professor on lectures/cai.pdf"*. Claude asks which pages, which output, and the level, then does the rest.

## What works where

| | Claude Code (your PC) | claude.ai web |
|---|---|---|
| Read PDF / PPTX, write script | yes | yes |
| Kokoro voice, MP3/WAV | yes | only if the sandbox has internet |
| MP4 video | yes (ffmpeg or `pip install imageio-ffmpeg`) | only if Kokoro works |
| Interactive lesson, browser voices | yes | yes (fallback) |
| Interactive lesson, Kokoro voice embedded | yes | only if the sandbox has internet |

On the web, you can always take the `lesson.json` Claude gives you and rebuild with the better voice on your own computer:

```bash
pip install kokoro-onnx soundfile imageio-ffmpeg
python claude-professor/scripts/build_interactive.py lesson.json --out lesson.html
```

See `claude-professor/examples/lesson.example.json` for the format.

## Requirements
Python 3.10+, `pymupdf`, `pillow`. For voice: `kokoro-onnx`, `soundfile`, `numpy` (~300 MB model downloaded on first use). For PPTX files: LibreOffice or PowerPoint (otherwise text-only). For video: ffmpeg.

## License
MIT
