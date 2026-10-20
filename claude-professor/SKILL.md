---
name: claude-professor
description: Explains lecture slides out loud. Takes a PDF or PowerPoint (uploaded or on disk), asks which pages (all, or e.g. "80, 89-100"), then builds an interactive lesson where each slide is recreated in crisp HTML with real math and every sentence, formula and table row is clickable to hear (and read) a clear explanation in a natural open-source voice (Kokoro-82M). Can also export a voice recording (MP3) or an MP4 video. Use when the user wants slides explained, summarised, narrated, turned into audio/video, or "taught to me" like a professor.
---

# Claude Professor

Turn slides into an interactive spoken lesson. You do the understanding, the writing and the slide recreation; scripts do the rendering, the speech and the packaging. Scripts are in `scripts/` next to this file.

## Step 1: Get the file and the choices

If not already stated, ask (AskUserQuestion if available, else one chat message):

1. **File?** An upload (usually `/mnt/user-data/uploads/` or `/mnt/data/`) or a path.
2. **Pages?** `all`, one page, a range (`89-100`, `89 to 100`) or a mix (`80, 89-100`). PDF page numbers (the number printed on the slide may differ).
3. **Output?** Interactive lesson (default, recommended), voice recording (MP3), or video (MP4), or several.
4. **Style / level (optional, free text):** do NOT insist on this. Offer it as an open question ("any particular way you want it explained?"). Examples the user might say: "like I'm new to maths", "Cambridge A Level", "IB HL", "exam revision", "use football examples", "short recap". If they give nothing, default to a clear study explanation for a first-time learner and leave `audience` out.

## Step 2: Render and read the slides

```bash
pip install pymupdf pillow
python scripts/render_slides.py FILE --pages "89-100" --out work/slides
```
Prints JSON with each page's PNG and extracted text. **Look at every PNG** (formulas, tables, diagrams are often missing from the text layer); use the text to get exact wording and symbols right.
- `.pptx/.ppt` needs LibreOffice (`soffice`) or PowerPoint for images; otherwise you get text only plus a `warning`, so tell the user and suggest exporting to PDF.
- More than ~15 slides: work in batches and keep tone consistent.

## Step 3: Write `work/lesson.json`

See `examples/lesson.example.json` (real slides 89-90) and the docstring in `scripts/build_interactive.py`. Per slide:

- `html`: **recreate the slide faithfully** (same title, bullets, formulas, tables, diagram as simple HTML/SVG). Use the provided classes: `ul.s-list > li`, `div.s-formula`, `table.s-table`. Math is KaTeX: `\\( inline \\)` and `$$ block $$` (remember JSON escaping: every backslash doubled).
- Put `data-e="id"` on **every meaningful unit**: each bullet, each formula, each table row, each diagram part. This is what the user clicks.
- Top-level `audience` (optional): the user's style/level wording, verbatim-ish (e.g. "Cambridge A Level Mathematics"). Shown as a badge and sent along with in-page questions. Omit if they gave none.
- `syllabus` (optional, per slide): where the slide sits in the named curriculum. Only include it if the user named a curriculum **and** you are confident of the topic. Never invent syllabus codes or paper numbers.
- `exam_tip` (optional, per note): a short exam-style tip, useful when the user asked for an exam board or revision.
- `intro`: spoken overview of the whole slide: what it's about, why it matters (2-4 sentences).
- `notes[id]`: `title` (short heading), `say` (spoken explanation), optional `extra` (list of HTML snippets: worked example or derivation steps with math; they are revealed one by one while the explanation is spoken), optional `exam_tip`.
- `steps`: order for the "Play slide" walkthrough.

Writing rules for `say` (it is read aloud by TTS):
- **Explain, don't repeat.** Define terms, give the intuition, say why it matters, add a tiny concrete example. For formulas: what each symbol means, what the formula does step by step, one worked number example (in `extra_html`).
- Spoken style: short sentences, friendly teacher tone, no bullets, no markdown, no LaTeX or symbols. Say math in words ("y bar equals a times x bar, plus b").
- Cover the **whole** slide: every bullet and formula gets its own note; connect them. Roughly 40-100 words per note.
- Only explain what the slides support. If something is ambiguous, tell the user in chat.

Show the user a short outline of what you'll build unless they said to just go.

## Step 4: Build

```bash
python scripts/speak.py --check            # OK / NOT_OK for the Kokoro voice
```
If `NOT_OK` because of missing packages, try `pip install kokoro-onnx soundfile imageio-ffmpeg` and re-check. In a no-internet sandbox it stays `NOT_OK`.

```bash
python scripts/build_interactive.py work/lesson.json --out lesson.html --slides work/slides
```
- With Kokoro available, every explanation is synthesized and **embedded** in `lesson.html` (works offline, same voice everywhere). Options: `--voice af_heart|af_bella|af_nicole|am_michael|am_adam|bf_emma|bm_george`, `--speed 1.0`.
- Without Kokoro it still builds, and the page uses the viewer's browser voices (lower quality). Say so honestly and tell the user how to get the better voice: run the skill in Claude Code, or run the same command on their own computer with `lesson.json`.
- `--slides` adds an "Original slide" toggle so the user can compare with the real slide.

**In-page questions.** The lesson has an "Ask a question" box; Claude answers, and the answer is added to that slide (or rewrites the selected explanation) and spoken. It works in three ways: published as a claude.ai artifact with `capabilities: {"sample": {}}` (load the `artifact-capabilities` skill first; no key needed); opened as a local file after the user pastes their own Anthropic API key into the page (stored only in their browser); otherwise it copies the question plus slide context to the clipboard to paste into Claude chat. Answers fall back to browser voices because they have no pre-rendered audio; users can pick the best voice in the Voice menu (Chrome's "Google" voices and Edge's "Natural" voices sound best).

Deliver `lesson.html` (publish as an artifact if you can, passing `capabilities: {"sample": {}}`; browser-voice mode works there. Embedded audio may make large files, keep it under the size limit by splitting very long lessons). Always also give `lesson.json` so the user can edit and rebuild.

### Optional exports (Claude Code / any environment with Kokoro)

Linear voice recording or video, from a plain script in `work/script.md` (`## Slide 89` header + narration for each slide; concatenate each slide's `intro` and notes `say` text in `steps` order):

```bash
python scripts/speak.py work/script.md --out work/audio --voice af_heart     # narration.mp3/.wav + timings.json
python scripts/make_video.py work/slides work/audio --out lesson.mp4        # needs ffmpeg or imageio-ffmpeg
```
Deliver via SendUserFile (Claude Code) or the outputs folder (claude.ai, `/mnt/user-data/outputs/`).

## Notes
- First Kokoro run downloads ~300 MB to `~/.cache/claude-professor/` once.
- No API keys needed. Claude does the reading and writing.
