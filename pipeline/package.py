"""Assembles dist/space (static site + README) and dist/dataset (plans, rigs, pages, transcripts) for upload.
Usage: python -X utf8 -I package.py <hf username>"""
import glob, json, os, shutil, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); USER = sys.argv[1]
DIST = os.path.join(ROOT, "dist"); SPACE = os.path.join(DIST, "space"); DATA = os.path.join(DIST, "dataset")
shutil.rmtree(SPACE, ignore_errors=True); shutil.rmtree(DATA, ignore_errors=True); os.makedirs(SPACE); os.makedirs(DATA)
ld = lambda p: json.load(open(p, encoding="utf-8"))
score = {}
for f in glob.glob(os.path.join(ROOT, "site", "data", "*", "scorecard.json")): score[os.path.basename(os.path.dirname(f))] = ld(f)
T = lambda k: sum(s[k] for s in score.values())

try:
    lic = urllib.request.urlopen("https://www.apache.org/licenses/LICENSE-2.0.txt", timeout=30).read().decode("utf-8")
except Exception:
    lic = "Apache License, Version 2.0. Full text: https://www.apache.org/licenses/LICENSE-2.0.txt\n"

WEB = os.path.join(DIST, "web")  # the built, minified site from build_site.py
for name in os.listdir(WEB):
    if name == "_headers": continue
    src = os.path.join(WEB, name); dst = os.path.join(SPACE, name)
    (shutil.copytree if os.path.isdir(src) else shutil.copy)(src, dst)
open(os.path.join(SPACE, "LICENSE"), "w", encoding="utf-8").write(lic)
shutil.copy(os.path.join(DIST, "how.gif"), os.path.join(SPACE, "how.gif"))

rows = "\n".join(f"| {s['title']} | {s['pages']} | {s['pages_passed_gate']} | {s['beam_calls']:,} | {round(s['output_tokens'] / 1000)}K | {s['characters']} |" for s in score.values())
SPACE_README = f"""---
title: Living Books
emoji: 📖
colorFrom: yellow
colorTo: red
sdk: static
pinned: false
short_description: Classic stories as living pop-up books, made by Beam
license: apache-2.0
tags:
  - beam
  - reflection-ai
  - build-with-beam
---

# Living Books: classic stories, reflected by Beam

**Unofficial.** Built with Beam by Reflection AI for the Build with Beam challenge. Not a product of Reflection AI or Hugging Face.

Read a whole classic, page by page, with every scene alive as a little paper pop-up. Beam reads each complete book, designs the characters, paints each page's world, performs the scene against the words, and fixes what its measurement tools report. Two books are finished:

| Book | Pages | Passed the scene checks | Beam calls | Tokens Beam wrote | Characters |
|---|---|---|---|---|---|
{rows}

Also live at **https://living-books.mikacend.xyz** (Cloudflare Pages), which loads faster on phones.

![How it works: Beam reads the book, paints the page in layers, stages the puppets, fixes what the checker reports, and the page becomes a pop-up](how.gif)

*Real calls from Beam's log for The Tale of Peter Rabbit, page 5.*

## Try, test, replicate

- **Try:** open this Space, or https://living-books.mikacend.xyz on a phone. Swipe pages, tilt to look into the pop-up, and tap the ⓘ button to see Beam's calls for that page.
- **Test without a key:** the code is at https://github.com/mikaelaldy/living-books. Run `pip install -r requirements.txt`, `python -m playwright install chromium`, then `python -X utf8 pipeline/verify.py`. It re-runs the scene check on all 33 pages.
- **Make your own book:** with a Reflection API key (or a Hugging Face token), `pipeline/produce.py read`, `cast` and `pages` take any public-domain text through the same tools. The GitHub README has the full steps.

Open the Space, pick a book, swipe through the pages, and press **How Beam made this page** to see the recorded calls. **Watch Beam read** replays everything from the transcripts in the [dataset](https://huggingface.co/datasets/{USER}/living-books-data).

## How Beam was used

Model: `Beam-1.0-501B-A23B`, with `reasoning_effort` set explicitly on every call (the account default is `max`). Most calls went through the Reflection API; some review-round calls ran through Hugging Face Inference Providers using the challenge credit.

1. **Read the whole book.** One request with the entire text at `high` effort. Beam returns a story plan: world, palette, emotional arc, cast, locations, and where each page starts and ends. The plan is checked so that every word of the book lands on exactly one page.
2. **Cast.** Beam designs each character with the `define_character` tool at `xhigh` effort: a tree of bones with Beam-written Canvas drawing code, and a set of named poses. The tool returns joint gaps, pose bounds and a letter-map silhouette, because Beam cannot see images.
3. **Paint.** `paint_scene` at `xhigh`: depth-sorted layers of Beam-written drawing code, a ground line and anchors. The tool returns colour statistics, detail per band and a letter map of the frame.
4. **Perform.** `stage_scene` and `check_scene` at `high`: a timeline of beats tied to phrases of the text. `check_scene` renders the scene and reports actors out of frame, feet off the ground, overlaps, hidden characters, dead time and empty bands. Beam fixes what it reports, and `finish_scene` refuses the page while issues remain.
5. **Game.** Beam wrote the *Peter Rabbit* mini-game, "Home Before Dark", in one call, then fixed two issues from review notes.

Tool calling uses `reasoning_content` echoed back on every assistant message, as Beam requires. Loops stop when the same error repeats, and a reply that ends with `finish_reason: length` counts as a failed call.

## Who did what

- **Beam** wrote the story plans, the characters and their poses, every background, every animation timeline, and the game, and made every fix.
- **A coding agent** wrote the puppet engine, the production pipeline, the reader and these pages. It did not edit Beam's art.
- **Visual review.** Beam cannot see images, so a third-party multimodal model looked at frames of each page and wrote review notes. Any model with image input, or a person, can fill this role. The notes are recorded in the transcripts and labelled on the Watch Beam read pages; Beam made every fix.
- The scene checks measure geometry. They cannot judge storytelling, so some pages still have weak staging; the review notes exist for that reason.

## Things to know

- Reading mode keeps no accounts, cookies or analytics of its own.
- Source texts are public domain, from Project Gutenberg, with the Gutenberg licence header removed.
- The pop-up depth effect uses WebGL and falls back to flat 2D on slow devices or without WebGL.
- Counts above describe Beam's own runs in this project. They are not a benchmark and do not rank Beam against any other model.

Code: Apache-2.0. Derived data in the dataset: CC-BY-4.0.
"""
open(os.path.join(SPACE, "README.md"), "w", encoding="utf-8").write(SPACE_README)

for slug in score:
    src = os.path.join(ROOT, "books", slug); dst = os.path.join(DATA, "books", slug); os.makedirs(dst)
    for f in ("bible.json", "cast.json", "report.json", "notes.json", "notes2.json", "cast-brief.txt", "art-note.txt"):
        if os.path.exists(os.path.join(src, f)): shutil.copy(os.path.join(src, f), dst)
    for d in ("pages", "logs", "game"):
        if os.path.isdir(os.path.join(src, d)):
            shutil.copytree(os.path.join(src, d), os.path.join(dst, d), ignore=shutil.ignore_patterns("*.log", "*.jpg", "*.png", "check*"))
shutil.copytree(os.path.join(ROOT, "pipeline"), os.path.join(DATA, "pipeline"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
shutil.copy(os.path.join(ROOT, "engine", "engine.js"), os.path.join(DATA, "pipeline", "engine.js"))
CARD = f"""---
license: cc-by-4.0
pretty_name: Living Books data
language:
  - en
tags:
  - beam
  - reflection-ai
  - build-with-beam
  - tool-use
  - animation
---

# Living Books data

Everything behind [Living Books](https://huggingface.co/spaces/{USER}/living-books): for each book, Beam's story plan (`bible.json`), its character rigs (`cast.json`), the finished pages with their scenes and timelines (`pages/`), and the full record of every call Beam made while producing it (`logs/*.jsonl`: requests' outcomes, token counts, Beam's reasoning, every tool call and result). `books/peter-rabbit/game/` holds the prompt, reasoning and review rounds for the mini-game.

`pipeline/` has the production scripts and the puppet engine. Review notes written by the reviewing agent are in `notes*.json`, in `cast-note-*.txt` where present, and as `note` rows in the logs.

Counts are Beam's own runs in this project, not a benchmark. Source texts are public domain from Project Gutenberg. Data: CC-BY-4.0. Code: Apache-2.0.
"""
open(os.path.join(DATA, "README.md"), "w", encoding="utf-8").write(CARD)
open(os.path.join(DATA, "pipeline", "LICENSE"), "w", encoding="utf-8").write(lic)
tot = lambda d: sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(d) for f in fs)
print("space MB", round(tot(SPACE) / 1e6, 1), "dataset MB", round(tot(DATA) / 1e6, 1), "totals", T("beam_calls"), "calls")
