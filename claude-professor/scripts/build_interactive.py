#!/usr/bin/env python3
"""Build a single-file interactive lesson: recreated slides with clickable parts that explain themselves out loud.

Usage: python build_interactive.py LESSON.json --out lesson.html [--slides SLIDES_DIR]
                                   [--voice af_heart --speed 1.0] [--no-audio]

LESSON.json (written by Claude):
{
  "title": "Lecture 5: Descriptive statistics",
  "audience": "Cambridge A Level Mathematics",      // level/curriculum the explanations are written for (shown as a badge, also sent with in-page questions)
  "slides": [{
    "page": 90,
    "title": "Standardization",
    "syllabus": "Statistics: the normal distribution",   // optional: where this sits in the syllabus (only if you are sure)
    "html": "<ul class='s-list'><li data-e='def'>A sample is <b>standardized</b> if ...</li></ul> <div class='s-formula' data-e='f'>$$z_i = \\frac{x_i-\\bar x}{s_x}$$</div>",
    "intro": "Spoken overview of the whole slide (what it is about and why it matters).",
    "notes": {
      "def": {"title": "What 'standardized' means", "say": "Spoken explanation...", "extra": ["worked example step 1", "step 2 (list items are revealed progressively while it is spoken)"], "exam_tip": "optional"},
      "f":   {"title": "The z-score formula",       "say": "..."}
    },
    "steps": ["def", "f"]      // order for the 'Play slide' walkthrough (after the intro)
  }]
}
Every element with data-e="ID" becomes clickable and needs notes["ID"]. Math uses KaTeX ($$...$$ block, \\(...\\) inline).

Audio: with Kokoro available each spoken text is synthesized and embedded (mp3 if ffmpeg exists, else wav),
so the file works offline with a consistent, natural voice. Without it the page falls back to browser voices.
"""
import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_ffmpeg  # noqa: E402

KATEX = "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9"


def b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


class Voice:
    """Kokoro synthesis -> data URI. Returns None for everything if Kokoro isn't usable."""

    def __init__(self, voice: str, speed: float):
        self.voice, self.speed, self.ff = voice, speed, find_ffmpeg()
        self.k = None
        try:
            from kokoro_onnx import Kokoro
            from speak import get_models
            self.k = Kokoro(*get_models())
        except Exception as e:
            print(f"[audio] Kokoro unavailable ({e}); page will use browser voices.", file=sys.stderr)

    def __call__(self, text: str) -> str | None:
        if not self.k or not text.strip():
            return None
        import numpy as np
        import soundfile as sf
        from speak import chunks
        parts, sr = [], 24000
        for c in chunks(text):
            s, sr = self.k.create(c, voice=self.voice, speed=self.speed, lang="en-us")
            parts += [s, np.zeros(int(sr * 0.2), dtype=s.dtype)]
        tmp = Path(tempfile.mkdtemp())
        wav = tmp / "a.wav"
        sf.write(str(wav), np.concatenate(parts), sr)
        if self.ff:
            mp3 = tmp / "a.mp3"
            subprocess.run([self.ff, "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-b:a", "64k", str(mp3)], check=True)
            return b64(mp3, "audio/mpeg")
        return b64(wav, "audio/wav")


def crop(slides_dir: Path, m) -> str:
    """<img src="crop:97:0.35,0.55,0.65,0.9"> -> that fractional region (x0,y0,x1,y1) of slide 97 as a data URI.
    Use it to reuse a photo/figure from the original slide. Render with --zoom 2.5 for sharp crops."""
    from PIL import Image
    import io
    im = Image.open(slides_dir / f"slide_{int(m.group(1)):03d}.png").convert("RGB")
    x0, y0, x1, y1 = (float(m.group(i)) for i in range(2, 6))
    w, h = im.size
    buf = io.BytesIO()
    im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))).save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def build(lesson: dict, slides_dir: Path | None, voice: Voice | None) -> dict:
    for s in lesson["slides"]:
        s.setdefault("notes", {})
        s.setdefault("steps", list(s["notes"].keys()))
        ids = set(re.findall(r"data-e=['\"]([^'\"]+)['\"]", s["html"]))
        missing = ids - set(s["notes"])
        if missing:
            raise SystemExit(f"Slide {s['page']}: data-e ids without notes: {sorted(missing)}")
        if slides_dir:
            s["html"] = re.sub(r"crop:(\d+):([\d.]+),([\d.]+),([\d.]+),([\d.]+)",
                               lambda m: crop(slides_dir, m), s["html"])
            img = slides_dir / f"slide_{s['page']:03d}.png"
            if img.exists():
                s["original"] = b64(img, "image/png")
        if voice:
            print(f"[audio] slide {s['page']}", file=sys.stderr)
            if s.get("intro"):
                s["intro_audio"] = voice(s["intro"])
            for n in s["notes"].values():
                n["audio"] = voice(n["say"])
    return lesson


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="__KATEX__/katex.min.css">
<style>
:root{--bg:#f3f4f8;--fg:#1b1c22;--card:#fff;--muted:#6b6d78;--accent:#3b5bdb;--line:#e3e4ec;--hot:#3b5bdb17;--blue:#274690;--ok:#2f9e6b}
@media (prefers-color-scheme:dark){:root{--bg:#121316;--fg:#ececf1;--card:#1b1c21;--muted:#9a9cab;--line:#2c2e37;--hot:#7391ff26;--blue:#9db6ff;--accent:#7391ff;--ok:#5fd19b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,"Segoe UI",sans-serif}
main{max-width:1240px;margin:0 auto;padding:18px 16px 30px}
header{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;margin-bottom:14px}
header h1{font-size:18px;margin:0;font-weight:650;letter-spacing:-.01em}
.badge{font-size:12px;padding:3px 10px;border-radius:99px;background:var(--hot);color:var(--accent);font-weight:600}
.sp{flex:1}
button,select,input{font:inherit;font-size:14px;color:var(--fg)}
button,select{padding:7px 13px;border-radius:9px;border:1px solid var(--line);background:var(--card);cursor:pointer;transition:border-color .15s,transform .05s}
button:hover,select:hover{border-color:var(--accent)}button:active{transform:scale(.98)}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
button.on{border-color:var(--accent);color:var(--accent)}
label{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:6px}
.grid{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(300px,1fr);gap:16px;align-items:start}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
.slide{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:30px 36px 34px;min-height:440px;position:relative;font-size:19px;line-height:1.62;box-shadow:0 1px 2px #0000000a,0 8px 28px #0000000a}
.slide .meta{position:absolute;top:12px;right:18px;font-size:12.5px;color:var(--muted);display:flex;gap:10px;align-items:center}
.slide h2{font-weight:450;color:var(--blue);font-size:30px;margin:6px 0 20px;letter-spacing:-.01em;animation:rise .45s both}
.slide img.orig{max-width:100%;display:block;margin:0 auto;border-radius:8px}
.s-list{list-style:none;padding:0;margin:0}
.s-list>li{position:relative;padding:6px 10px 6px 28px;margin:5px 0}
.s-list>li::before{content:"";position:absolute;left:9px;top:.82em;border-left:8px solid var(--blue);border-top:5px solid transparent;border-bottom:5px solid transparent}
.s-formula{text-align:center;margin:12px auto;padding:10px 22px;border-radius:10px;width:fit-content;max-width:100%;overflow-x:auto;background:color-mix(in srgb,var(--blue) 11%,transparent)}
.s-table{border-collapse:collapse;width:100%;font-size:17px}
.s-table th{text-align:left;border-bottom:1.5px solid var(--fg);padding:7px 12px;font-weight:550}
.s-table td{padding:8px 12px}
.s-table th:first-child,.s-table td:first-child{border-right:1.5px solid var(--fg)}
[data-e]{cursor:pointer;border-radius:10px;transition:background .18s,opacity .35s,box-shadow .2s}
[data-e]:hover{background:var(--hot)}
tr[data-e]:hover td{background:var(--hot)}
[data-e].active{background:var(--hot);box-shadow:0 0 0 2px var(--accent)}
tr[data-e].active td{background:var(--hot)}
tr[data-e].active{outline:2px solid var(--accent);outline-offset:-2px;border-radius:6px}
.presenting [data-e].pending{opacity:.16;filter:saturate(0)}
.presenting [data-e].reveal{animation:pop .5s cubic-bezier(.2,.9,.3,1.2)}
@keyframes pop{0%{transform:translateY(8px) scale(.97);opacity:.1}100%{transform:none;opacity:1}}
@keyframes rise{0%{transform:translateY(8px);opacity:0}100%{transform:none;opacity:1}}
.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:14px}
.dots{display:flex;gap:6px;flex:1;flex-wrap:wrap;align-items:center;justify-content:flex-end}
.dots i{width:8px;height:8px;border-radius:50%;background:var(--line);cursor:pointer;transition:.2s}
.dots i.cur{background:var(--accent);transform:scale(1.4)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;position:sticky;top:12px;max-height:calc(100vh - 24px);display:flex;flex-direction:column;box-shadow:0 1px 2px #0000000a,0 8px 28px #0000000a}
#pc{padding:20px 22px 8px;overflow:auto;flex:1;min-height:200px}
.panel h3{margin:0 0 10px;font-size:17px;letter-spacing:-.01em;animation:rise .35s both}
.say{font-size:16px;line-height:1.65}
.snt{transition:color .25s,background .25s;border-radius:4px}
.snt.done{color:var(--muted)}
.snt.cur{background:var(--hot);color:var(--fg)}
.ex{margin-top:12px;padding:10px 14px;border-left:3px solid var(--accent);background:var(--hot);border-radius:0 10px 10px 0;font-size:15px;opacity:0;transform:translateY(8px);transition:opacity .45s,transform .45s}
.ex.in{opacity:1;transform:none}
.tip{margin-top:12px;padding:10px 14px;border-radius:10px;background:color-mix(in srgb,var(--ok) 14%,transparent);font-size:14.5px}
.hint{color:var(--muted);font-size:15px}
.row{display:flex;gap:8px;margin:14px 0 8px;flex-wrap:wrap}
.qs{margin-top:14px;display:flex;flex-direction:column;gap:6px}
.qs button{text-align:left;font-size:14px}
.ask{border-top:1px solid var(--line);padding:12px 14px 14px}
.ask form{display:flex;gap:8px}
.ask input[type=text],.ask input[type=password]{flex:1;min-width:0;padding:9px 12px;border-radius:9px;border:1px solid var(--line);background:var(--bg)}
.ask input:focus{outline:2px solid var(--accent);outline-offset:-1px}
#st{font-size:13px;color:var(--muted);margin-top:6px;min-height:1.2em}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.chips button{font-size:12.5px;padding:4px 10px;border-radius:99px;color:var(--muted)}
.katex{font-size:1.07em}
</style></head><body><main>
<header><h1>__TITLE__</h1><span class="badge" id="aud"></span><span class="sp"></span>
 <label>Voice <select id="voice" style="max-width:210px"></select></label>
 <label>Speed <select id="rate"><option value="0.85">0.85×</option><option value="1" selected>1×</option><option value="1.15">1.15×</option><option value="1.3">1.3×</option></select></label>
 <button id="orig">Original slide</button><button id="dl" title="Download this lesson including your questions">Save</button></header>
<div class="grid">
 <div><div class="slide" id="slide"></div>
  <div class="bar"><button id="prev">◀</button><button class="primary" id="play">▶ Play slide</button><button id="next">▶</button><span class="dots" id="dots"></span></div></div>
 <aside class="panel"><div id="pc"></div>
  <div class="ask"><div class="chips" id="chips"></div>
   <form id="askf"><input type="text" id="q" placeholder="Ask a question about this slide…" autocomplete="off"><button class="primary" id="send">Ask</button></form>
   <div id="st"></div><form id="keyf" style="display:none;gap:8px;margin-top:8px"><input type="password" id="key" placeholder="Anthropic API key (stored in this browser only)"><button>Save key</button></form></div></aside>
</div></main>
<script defer src="__KATEX__/katex.min.js"></script>
<script defer src="__KATEX__/contrib/auto-render.min.js"></script>
<script>
const LESSON=__DATA__;
const $=id=>document.getElementById(id), synth=window.speechSynthesis, SKEY="cp:"+LESSON.title;
const MODEL="claude-sonnet-5-5";
let si=0,token=0,audio=null,playing=false,showOrig=false,resolveCur=null,sampleFn=undefined;

/* ---------- data helpers ---------- */
function norm(n){ if(n.extra_html&&!n.extra) n.extra=[n.extra_html]; if(typeof n.extra==="string") n.extra=[n.extra]; n.extra=n.extra||[]; return n; }
LESSON.slides.forEach(s=>{ Object.values(s.notes).forEach(norm); });
try{ const sv=JSON.parse(localStorage.getItem(SKEY)||"{}");
  LESSON.slides.forEach(s=>{ const p=sv[s.page]; if(!p) return;
    if(p.html){ s.html=p.html; s.htmlChanged=true; }
    Object.entries(p.notes||{}).forEach(([id,n])=>{ s.notes[id]=norm(n); });
    if(p.steps) s.steps=p.steps; }); }catch(e){}
function persist(){ try{ const o={}; LESSON.slides.forEach(s=>{ const ch={}; Object.entries(s.notes).forEach(([id,n])=>{ if(n.user) ch[id]=n; });
    if(Object.keys(ch).length||s.htmlChanged) o[s.page]={notes:ch,html:s.htmlChanged?s.html:undefined,steps:s.steps}; });
  localStorage.setItem(SKEY,JSON.stringify(o)); }catch(e){} }
const esc=s=>String(s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
function math(el){ if(window.renderMathInElement) renderMathInElement(el,{delimiters:[{left:"$$",right:"$$",display:true},{left:"\\(",right:"\\)",display:false}],throwOnError:false}); }
const sleep=ms=>new Promise(r=>setTimeout(r,ms));

/* ---------- voices ---------- */
function enVoices(){ return synth?synth.getVoices().filter(v=>/^en/i.test(v.lang)):[]; }
function score(v){ const n=v.name; let s=0;
  if(/google/i.test(n)) s+=50; if(/natural|neural|online/i.test(n)) s+=60;
  if(/samantha|serena|daniel|karen|jenny|aria|sonia|libby|ryan|guy/i.test(n)) s+=20;
  if(/en-(GB|US)/i.test(v.lang)) s+=5; if(/espeak|zira|david|mark|hazel/i.test(n)) s-=10; return s; }
function fillVoices(){ const vs=enVoices().sort((a,b)=>score(b)-score(a)); if(!vs.length) return;
  let pref=null; try{pref=localStorage.getItem("cp:voice");}catch(e){}
  $("voice").innerHTML=vs.map(v=>`<option>${esc(v.name)}</option>`).join("");
  $("voice").value=vs.some(v=>v.name===pref)?pref:vs[0].name; }
if(synth){ fillVoices(); synth.onvoiceschanged=fillVoices; }
$("voice").onchange=()=>{ try{localStorage.setItem("cp:voice",$("voice").value);}catch(e){} };

/* ---------- speech ---------- */
function stop(){ token++; playing=false; $("play").textContent="▶ Play slide"; if(audio){audio.pause();audio=null;} if(synth) synth.cancel();
  if(resolveCur){const r=resolveCur;resolveCur=null;r();} document.body.classList.remove("presenting"); document.querySelectorAll(".pending").forEach(e=>e.classList.remove("pending")); }

function speakItem(src,text,my,prog){
  return new Promise(res=>{ resolveCur=res; const rate=parseFloat($("rate").value);
    if(src){ audio=new Audio(src); audio.playbackRate=rate;
      audio.ontimeupdate=()=>{ if(audio&&audio.duration) prog(audio.currentTime/audio.duration); };
      audio.onended=()=>res(); audio.onerror=()=>res(); audio.play().catch(()=>res()); return; }
    if(!synth) return res();
    const sents=text.replace(/\s+/g," ").split(/(?<=[.!?])\s+/), total=text.length; let k=0,off=0;
    const next=()=>{ if(my!==token||k>=sents.length) return res();
      const s=sents[k], base=off; prog(base/total);
      const u=new SpeechSynthesisUtterance(s); u.rate=rate;
      const v=enVoices().find(x=>x.name===$("voice").value); if(v) u.voice=v;
      u.onboundary=e=>prog((base+e.charIndex)/total);
      u.onend=()=>{ off+=s.length+1; k++; next(); }; u.onerror=()=>res(); synth.speak(u); };
    next(); });
}

/* ---------- panel ---------- */
function showNote(id,live){
  const s=LESSON.slides[si], n=id==="_intro"?{title:"Overview",say:s.intro,extra:[]}:s.notes[id];
  const sents=n.say.replace(/\s+/g," ").split(/(?<=[.!?])\s+/);
  $("pc").innerHTML=`<h3>${esc(n.title)}</h3><div class="say">${sents.map(x=>`<span class="snt">${esc(x)}</span>`).join(" ")}</div>`
   +n.extra.map(x=>`<div class="ex${live?"":" in"}">${x}</div>`).join("")
   +(n.exam_tip?`<div class="tip"><b>Exam tip.</b> ${n.exam_tip}</div>`:"")
   +`<div class="row"><button id="replay">↻ Replay</button><button id="stopb">■ Stop</button></div>`;
  math($("pc")); document.querySelectorAll("#slide [data-e]").forEach(e=>e.classList.toggle("active",e.dataset.e===id));
  $("replay").onclick=()=>say(id); $("stopb").onclick=stop;
  const sp=[...$("pc").querySelectorAll(".snt")], ex=[...$("pc").querySelectorAll(".ex")];
  const cum=[]; let c=0; sents.forEach(x=>{ c+=x.length+1; cum.push(c/(n.say.length+1)); });
  return p=>{ p=Math.min(1,Math.max(0,p)); const cur=Math.min(sp.length-1,cum.findIndex(v=>v>=p-1e-9)<0?sp.length-1:cum.findIndex(v=>v>=p-1e-9));
    sp.forEach((e,i)=>{ e.classList.toggle("cur",p<1&&i===cur); e.classList.toggle("done",p>=1||i<cur); });
    ex.forEach((e,i)=>{ if(p>=(i+1)/(ex.length+1)||p>=1) e.classList.add("in"); }); };
}
function home(){ const s=LESSON.slides[si]; const qs=Object.entries(s.notes).filter(([id,n])=>n.user);
  $("pc").innerHTML=`<h3>${esc(s.title)}</h3><p class="hint">Click any sentence, formula or table row to hear it explained. Press <b>Play slide</b> for a guided walkthrough, or ask your own question below.</p>`
   +(s.syllabus?`<p class="hint"><b>Syllabus link:</b> ${esc(s.syllabus)}</p>`:"")
   +(s.intro?`<div class="row"><button id="ov">🔊 Overview</button></div>`:"")
   +(qs.length?`<div class="qs"><b style="font-size:14px">Your questions</b>${qs.map(([id,n])=>`<button data-q="${id}">💬 ${esc(n.title)}</button>`).join("")}</div>`:"");
  if($("ov")) $("ov").onclick=()=>say("_intro");
  $("pc").querySelectorAll("[data-q]").forEach(b=>b.onclick=()=>say(b.dataset.q)); }

async function say(id){ stop(); const my=token, s=LESSON.slides[si]; const prog=showNote(id,true);
  const n=id==="_intro"?{say:s.intro,audio:s.intro_audio}:s.notes[id];
  await speakItem(n.audio,n.say,my,prog); if(my===token) prog(1); }

async function playSlide(){ stop(); const my=token; playing=true; $("play").textContent="❚❚ Pause";
  while(my===token){ const s=LESSON.slides[si]; const seq=(s.intro?["_intro"]:[]).concat(s.steps);
    document.body.classList.add("presenting"); document.querySelectorAll("#slide [data-e]").forEach(e=>e.classList.add("pending"));
    for(const id of seq){ if(my!==token) return; const prog=showNote(id,true);
      const el=id==="_intro"?null:document.querySelector(`#slide [data-e="${id}"]`);
      if(el){ el.classList.remove("pending"); el.classList.add("reveal"); }
      const n=id==="_intro"?{say:s.intro,audio:s.intro_audio}:s.notes[id];
      await speakItem(n.audio,n.say,my,prog); if(my!==token) return; prog(1); await sleep(450); }
    if(my!==token) return; document.querySelectorAll(".pending").forEach(e=>e.classList.remove("pending"));
    if(si+1<LESSON.slides.length){ render(si+1); await sleep(600); } else break; }
  if(my===token) stop(); }

/* ---------- slide ---------- */
function render(n){ si=Math.max(0,Math.min(LESSON.slides.length-1,n)); const s=LESSON.slides[si];
  $("slide").innerHTML=`<div class="meta">${s.syllabus?`<span class="badge">${esc(s.syllabus)}</span>`:""}<span>${s.page}</span></div><h2>${esc(s.title)}</h2>`+(showOrig&&s.original?`<img class="orig" src="${s.original}">`:s.html);
  math($("slide")); $("slide").querySelectorAll("[data-e]").forEach(el=>el.onclick=()=>say(el.dataset.e));
  $("orig").classList.toggle("on",showOrig); $("orig").style.display=LESSON.slides.some(x=>x.original)?"":"none";
  $("dots").innerHTML=LESSON.slides.map((x,i)=>`<i class="${i===si?"cur":""}" title="Slide ${x.page}" data-i="${i}"></i>`).join("");
  $("dots").querySelectorAll("i").forEach(d=>d.onclick=()=>{ stop(); render(+d.dataset.i); });
  $("chips").innerHTML=["Explain this more simply","Give me another example","Why does this matter?","How is this tested in exams?"].map(t=>`<button type="button">${t}</button>`).join("");
  $("chips").querySelectorAll("button").forEach(b=>b.onclick=()=>{ $("q").value=b.textContent; ask(); });
  home(); }

/* ---------- ask Claude ---------- */
async function getSample(){ if(sampleFn!==undefined) return sampleFn; try{ sampleFn=(window.claude&&claude.use)?await claude.use("sample"):null; }catch(e){ sampleFn=null; } return sampleFn; }
function slideText(s){ const d=document.createElement("div"); d.innerHTML=s.html; return d.textContent.replace(/\s+/g," ").trim(); }
function buildPrompt(q){ const s=LESSON.slides[si]; const cur=document.querySelector("#slide .active"); const cid=cur?cur.dataset.e:null;
  const list=Object.entries(s.notes).map(([id,n])=>`${id}: ${n.title}`).join("; ");
  return `You are a patient tutor inside an interactive lesson. Audience / level: ${LESSON.audience||"a student who is learning this for the first time"}.
Slide ${s.page}: "${s.title}"${s.syllabus?` (syllabus: ${s.syllabus})`:""}
Slide text: ${slideText(s)}
Existing explanations (id: title): ${list}
${cid?`The student currently has "${cid}" selected. Its explanation: ${s.notes[cid].say}`:""}
Student's question: ${q}

Answer for that audience. Reply with ONLY one JSON object, no code fences:
{"title":"short heading","say":"spoken explanation, 50-150 words, friendly, no LaTeX or symbols, formulas said in words","extra":["optional HTML snippets with a worked example or derivation steps, math as \\\\( ... \\\\)"],"exam_tip":"optional one-liner","replaces":"id of an existing explanation to REPLACE if the student asked to re-explain it, else null"}`; }
async function callClaude(prompt){
  const sm=await getSample(); if(sm){ const r=await sm(prompt,{cache:false}); return r.text; }
  let key=null; try{key=localStorage.getItem("cp:key");}catch(e){}
  if(key){ const r=await fetch("https://api.anthropic.com/v1/messages",{method:"POST",headers:{"content-type":"application/json","x-api-key":key,"anthropic-version":"2023-06-01","anthropic-dangerous-direct-browser-access":"true"},
      body:JSON.stringify({model:MODEL,max_tokens:1500,messages:[{role:"user",content:prompt}]})});
    if(!r.ok) throw new Error("API error "+r.status); const j=await r.json(); return j.content.map(b=>b.text||"").join(""); }
  return null; }
async function ask(){ const q=$("q").value.trim(); if(!q) return; const s=LESSON.slides[si]; const prompt=buildPrompt(q);
  $("send").disabled=true; $("st").textContent="Thinking…";
  try{ const txt=await callClaude(prompt);
    if(txt===null){ try{ await navigator.clipboard.writeText(prompt+"\n\n(Update this slide's explanations in lesson.json accordingly and rebuild the lesson.)"); $("st").textContent="No Claude connection here. I copied the question with full context; paste it into Claude."; }catch(e){ $("st").textContent="No Claude connection here. Paste an API key below, or ask in your Claude chat."; }
      $("keyf").style.display="flex"; return; }
    const m=txt.match(/\{[\s\S]*\}/); if(!m) throw new Error("Unexpected reply"); const a=JSON.parse(m[0]);
    const note=norm({title:a.title||q,say:a.say,extra:a.extra||[],exam_tip:a.exam_tip||"",user:true});
    let id=a.replaces&&s.notes[a.replaces]?a.replaces:null; if(!id){ id="q"+Date.now().toString(36); }
    s.notes[id]=note; if(!s.steps.includes(id)) s.steps.push(id); persist(); $("q").value=""; $("st").textContent=id.startsWith("q")?"Added to “Your questions”.":"Explanation updated.";
    say(id);
  }catch(e){ $("st").textContent="Couldn't get an answer: "+(e.message||e); }
  finally{ $("send").disabled=false; } }
$("askf").onsubmit=e=>{ e.preventDefault(); ask(); };
$("keyf").onsubmit=e=>{ e.preventDefault(); try{localStorage.setItem("cp:key",$("key").value.trim());}catch(x){} $("key").value=""; $("keyf").style.display="none"; $("st").textContent="Key saved. Ask again."; };

/* ---------- controls ---------- */
$("prev").onclick=()=>{stop();render(si-1)}; $("next").onclick=()=>{stop();render(si+1)};
$("play").onclick=()=>playing?stop():playSlide();
$("orig").onclick=()=>{showOrig=!showOrig;stop();render(si)};
$("dl").onclick=()=>{ const copy=JSON.parse(JSON.stringify(LESSON,(k,v)=>(k==="audio"||k==="intro_audio"||k==="original")?undefined:v));
  const a=document.createElement("a"); a.href=URL.createObjectURL(new Blob([JSON.stringify(copy,null,2)],{type:"application/json"})); a.download="lesson.json"; a.click(); };
document.addEventListener("keydown",e=>{ if(/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
  if(e.code==="Space"){e.preventDefault();playing?stop():playSlide();} if(e.key==="ArrowRight"){stop();render(si+1);} if(e.key==="ArrowLeft"){stop();render(si-1);} });
$("aud").textContent=LESSON.audience||""; $("aud").style.display=LESSON.audience?"":"none";
render(0); window.addEventListener("load",()=>render(si));
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lesson")
    ap.add_argument("--out", default="lesson.html")
    ap.add_argument("--slides", help="dir with slide_NNN.png from render_slides.py (enables 'Original slide' toggle)")
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--no-audio", action="store_true", help="skip Kokoro; page uses browser voices")
    a = ap.parse_args()

    lesson = json.loads(Path(a.lesson).read_text(encoding="utf-8"))
    voice = None if a.no_audio else Voice(a.voice, a.speed)
    if voice and not voice.k:
        voice = None
    lesson = build(lesson, Path(a.slides) if a.slides else None, voice)

    html = (TEMPLATE.replace("__TITLE__", lesson.get("title", "Lesson"))
            .replace("__KATEX__", KATEX)
            .replace("__DATA__", json.dumps(lesson, ensure_ascii=False).replace("</", "<\\/")))
    Path(a.out).write_text(html, encoding="utf-8")
    print(f"{a.out}  ({'Kokoro audio embedded' if voice else 'browser voices'}, {Path(a.out).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
