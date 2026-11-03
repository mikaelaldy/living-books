"""Living Books production pipeline. Beam reads, casts, paints and performs a book through tools.

  python -X utf8 -I produce.py read
  python -X utf8 -I produce.py cast [note]
  python -X utf8 -I produce.py pages [n n n]        runs up to 4 pages at once
  python -X utf8 -I produce.py page N [note]
  python -X utf8 -I produce.py sheet

Env: LB_KEY (key file), LB_BOOK (text file), LB_SLUG, LB_ROUTE (reflection or hf).
The browser is offline and Beam's code runs only inside it."""
import io, json, os, re, subprocess, sys, time, urllib.error, urllib.request

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = os.environ.get("LB_SLUG", "peter-rabbit")
# Absolute paths, so the page runs started from do_pages find the same files.
for _v in ("LB_KEY", "LB_BOOK"): os.environ[_v] = os.path.abspath(os.path.expanduser(os.environ[_v]))
KEY = open(os.environ["LB_KEY"], encoding="utf-8").read().strip()
RAW = open(os.environ["LB_BOOK"], encoding="utf-8", errors="ignore").read().replace("\r\n", "\n")
ROUTE = os.environ.get("LB_ROUTE", "reflection")
URL, MODEL = ("https://router.huggingface.co/v1/chat/completions", "reflection/Beam-1.0-501B-A23B") if ROUTE == "hf" else ("https://api.reflection.ai/openai/v1/chat/completions", "Beam-1.0-501B-A23B")
BOOKDIR = os.path.join(ROOT, "books", SLUG); PAGES = os.path.join(BOOKDIR, "pages"); LOGS = os.path.join(BOOKDIR, "logs")
ENGINE = open(os.path.join(ROOT, "engine", "engine.js"), encoding="utf-8").read()
for d in (PAGES, LOGS): os.makedirs(d, exist_ok=True)

a = RAW.index("*** START OF"); a = RAW.index("\n", a) + 1
BOOK = RAW[a:RAW.index("*** END OF")].strip()
if SLUG == "peter-rabbit" and "Once upon a time" in BOOK: BOOK = BOOK[BOOK.index("Once upon a time"):]
CLEAN = re.sub(r"[ \t]+", " ", re.sub(r"\[Illustration\]\s*", "", BOOK)).strip()


class Run:
    def __init__(self, name):
        self.log = open(os.path.join(LOGS, name + ".jsonl"), "a", encoding="utf-8"); self.name = name
        self.tot = {"prompt": 0, "cached": 0, "completion": 0, "reasoning": 0, "seconds": 0.0, "calls": 0, "route": ROUTE}

    def write(self, kind, **kw):
        self.log.write(json.dumps({"kind": kind, "at": round(time.time()), **kw}, ensure_ascii=False) + "\n"); self.log.flush()

    def beam(self, messages, effort, tools=None, max_tokens=64000):
        body = {"model": MODEL, "reasoning_effort": effort, "temperature": 0.7, "max_completion_tokens": max_tokens, "messages": messages}
        if tools:
            body["tools"] = tools; body["tool_choice"] = "auto"
        data = json.dumps(body).encode(); head = {}
        for attempt in range(5):
            t = time.time()
            req = urllib.request.Request(URL, data=data, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=590) as r:
                    d = json.load(r); head = {k.lower(): v for k, v in r.headers.items()}
                break
            except urllib.error.HTTPError as e:
                msg = e.read().decode()[:300]; print(self.name, "http", e.code, msg, flush=True)
                if e.code not in (429, 500, 502, 503, 504) or attempt == 4: raise
                time.sleep(15 * (attempt + 1))
            except Exception as e:
                print(self.name, "net", repr(e), flush=True)
                if attempt == 4: raise
                time.sleep(15)
        secs = time.time() - t; u = d["usage"]; c = d["choices"][0]
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0; reason = (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        for k, v in (("prompt", u["prompt_tokens"]), ("cached", cached), ("completion", u["completion_tokens"]), ("reasoning", reason), ("seconds", secs), ("calls", 1)): self.tot[k] += v
        left = {k.replace("x-ratelimit-remaining-", ""): v for k, v in head.items() if "remaining" in k}
        print(f"{self.name} call {self.tot['calls']} [{effort}] {secs:.0f}s in={u['prompt_tokens']} cached={cached} out={u['completion_tokens']} reasoning={reason} finish={c.get('finish_reason')} left={left}", flush=True)
        self.write("usage", seconds=round(secs, 1), effort=effort, prompt=u["prompt_tokens"], cached=cached, completion=u["completion_tokens"], reasoning=reason, finish=c.get("finish_reason"))
        return c


def j(path, data=None):
    if data is None: return json.load(open(path, encoding="utf-8"))
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def fence(s):
    m = re.search(r"```json\s*(.*?)```", s, re.S)
    return json.loads(m.group(1) if m else s)


READ = f"""You are about to adapt a whole short book into a living, animated pop-up edition for families. Read all of it first, as a reader.

Return ONE JSON object in a ```json fence and nothing else:
{{
 "world": "2 sentences on the visual world",
 "palette": ["6 to 8 hex colours"],
 "emotional_arc": ["one line per stage of the story"],
 "cast": [{{"id": "short_id", "name": "...", "look": "concrete drawable details from the text", "personality_in_motion": "how this character moves", "states": "visible changes during the book"}}],
 "sets": [{{"id": "short_id", "description": "a recurring location, with details that must stay the same on every page"}}],
 "pages": [{{"page": 1, "first_words": "the exact first 6 words of the page", "last_words": "the exact last 6 words", "set": "set id", "cast": ["ids on stage"], "scene": "what the animation shows", "feeling": "one word", "why": "why this moment deserves this staging", "needs_animation": true}}]
}}

Split the whole story into natural spreads a child would turn, with no words left out and none repeated: each page starts exactly where the last one ended. The [Illustration] marks show where the author paused. Set needs_animation to false for a page that works better as a quiet held picture.

--- BOOK ---
{BOOK}"""

SYSTEM = """You are the director, character designer, painter and animator of Living Books, animated pop-up editions of classic stories. You work only through tools on a Canvas 2D puppet engine.

You cannot see images. define_character, paint_scene and check_scene return measurements and letter maps; these are your only eyes, so read them closely and fix what they report.

FRAME: 390 wide, 520 tall, y grows downward. A card on a phone beside the book's text.

CHARACTERS (define_character): a tree of bones. Character origin (0,0) is the ground point under the feet, facing right, so the body lives in negative y. One root bone with a pivot such as [0,-90]. Each child's pivot is in its parent's coordinates, and each bone's drawing code runs with the origin AT ITS OWN PIVOT, so draw limbs extending away from (0,0): a thigh draws from (0,0) down to (0,40), and the shin's pivot is [0,40]. Code is the body of function(ctx, f); f has blink (0 open, 1 closed), mouth ('smile','open','flat','frown'), look (-1 to 1), brow (-1 to 1), t (seconds, for small secondary motion such as ear flutter), and any custom field set through a beat's face, such as f.prop === 'rake' or f.jacket === false. z sets draw order. poses maps a pose name to bone angles in degrees, added to rest. Reserved keys _x and _y shift the root, so a sitting or crouching pose needs a positive _y to keep the feet on the ground. Calling define_character again with the same id replaces only the bones and poses you send.

BACKGROUND (paint_scene): layers painted far to near. Code is the body of function(ctx, W, H, t, rand), W=390, H=520, rand() is seeded. Paint x from -30 to 420 because layers shift in depth. depth: 0 is far and 1 is near; each layer becomes a real sheet of a pop-up book at that depth, so give each a clear outline with transparent areas, not a full rectangle, except the farthest. front:true layers draw over the actors, for framing plants, and must stay low or at the edges. animated:true layers repaint every frame using t; static layers are cached, so put heavy detail in static layers. Soft paper shadows are added for you. ground is a polyline [[x,y],...] from x=-30 to x=420 where feet land. anchors are named ellipses {x,y,rx,ry}. Calling paint_scene again replaces only the layers you send, by name.

STAGE (stage_scene): replaces the whole timeline. start is an ARRAY with one object per actor: {actor, char (rig id, when several actors share a rig), x, pose, facing (1 right, -1 left), scale, lift, z, opacity, face, exiting (true while the actor is deliberately offstage or hidden at the start)}. Each beat has actor, at, dur, ease ('inOut','out','in','back','anticipate','linear'), phrase (the exact words being performed), and any of: move_to, lift_to, arc (hop height), scale_to, opacity_to, facing, pose (blend to it), cycle ([poseA,poseB]), hz, bob, squash (pulse: 0.15 stretches, -0.15 squashes), face ({mouth, look, blink, brow, prop, jacket, shoes, variant}), clip (anchor name), exiting (true when leaving or hidden is intended, false once fully on stage), z.
Use anticipation before big moves, follow-through after, and let a pause land. The scene must feel performed, not slid. Moves should cover real distance. Write every beat out in full, and never send an empty beat."""

ART = """ART DIRECTION FOR THE WHOLE BOOK: a layered cut-paper pop-up diorama with warm afternoon light and long shadows, in the spirit of an award-winning picture book. Rich, limited palette taken from the story bible. Every part of the frame holds something: no empty sky, no flat ground. Clear foreground, midground and background, with foreground plants framing the action.
Keep the ground under the actors calm enough that the characters read instantly: large shapes, furrows and leaves, never a scatter of tiny coloured dots.
SKY AND LIGHT: warm cream, peach and pale gold skies with soft paper clouds and a low sun, never blue and never dark. Blue belongs to Peter's jacket and small accents only. Warm amber light lies on everything; shadows are warm brown, never black.
RICHNESS: each static layer draws at least 60 individual shapes using loops: leaves on stems, climbing ivy across walls, rows of cabbages built from overlapping leaves, bricks, planks, flowers. Sheets overlap in depth so nothing looks like a flat stripe.
SCALE: actors keep scale between 0.9 and 1.1. Mr. McGregor is about 1.3 times Peter's height, and never a giant.
Characters are big, clean and instantly readable, with strong simple silhouettes and appealing proportions. They are NOT chibi: the head is about a quarter to a third of total height, with real limbs, paws or hands, and expressive eyes. People stand 190 to 230 px tall. Rabbits stand 140 to 180 px tall. Small creatures such as birds and mice are at least 70 px across, since they are small in the story."""

CAST_STYLE = """CUT-PAPER CHARACTER RULES, which override everything else:
- No outlines. Never stroke a body, limb or face edge. Every shape is a flat paper fill, with one darker and one lighter paper shape on top for shading, plus small details.
- Limbs are thick tapered filled paths with rounded overlapping ends, so a joint never looks like a doll's hinge. Never draw circles or dots at joints.
- Rabbits are soft real animals in clothes: a plump pear-shaped body, short thick limbs, big hind feet, long tapered ears with pink inners, a round tail. Legs are at most a third of the height. Warm tawny fur, not dark brown.
- Peter's bright blue jacket covers his whole torso and upper arms, with four large brass buttons. His hero look must read at a glance.
- Mrs. Rabbit is a RABBIT too, larger than her children: rabbit head and ears, long full dress, white apron, shawl, small bonnet between the ears.
- The three sisters are small rabbits in red hooded cloaks, like the book's; f.variant changes small details.
- Mr. McGregor is a thick-set old gardener: straw hat, white beard, brown waistcoat over rolled blue shirtsleeves, stout boots. His kneel pose is truly on hands and knees: torso level, head low and forward, palms and knees on the ground.
- The cat sits upright with a smooth white silhouette and a thick curling tail. Sparrows are plump and round. The mouse is small and neat with a bonnet.
- Sitting, lying and crouching poses fold the legs naturally, with no stiff straight limbs.

Reference: this is the art director's favourite Peter so far, and his shading approach and body language are what they liked. Match that fill-based style, while following the rules above:
"""

PEOPLE_GUIDE = """For each character, read the pages and design EVERY pose the book needs, plus two walk or run poses to alternate. Examples of what must really read: a gardener on hands and knees has his head low, hips up, palms and knees on the ground, and bounds top no higher than -130; sitting, lying in bed, crying, eating, peeping and running on four legs are all distinct body shapes, not small changes.
State changes are drawn conditionally: f.jacket === false removes Peter's jacket, f.shoes === false removes his shoes. Props are bones drawn only when f.prop names them, such as the rake, hoe, sieve, basket and umbrella."""

CODE = "Body of a JavaScript function"
FACE = {"type": "object", "properties": {"mouth": {"type": "string"}, "look": {"type": "number"}, "blink": {"type": "number"}, "brow": {"type": "number"}, "prop": {"type": "string"}, "jacket": {"type": "boolean"}, "shoes": {"type": "boolean"}, "variant": {"type": "number"}}}
BEAT = {"type": "object", "required": ["actor", "at"], "properties": {
    "actor": {"type": "string"}, "at": {"type": "number"}, "dur": {"type": "number"}, "ease": {"type": "string"}, "phrase": {"type": "string"},
    "move_to": {"type": "number"}, "lift_to": {"type": "number"}, "arc": {"type": "number"}, "scale_to": {"type": "number"}, "opacity_to": {"type": "number"}, "facing": {"type": "number"},
    "pose": {"type": "string"}, "cycle": {"type": "array", "items": {"type": "string"}}, "hz": {"type": "number"}, "bob": {"type": "number"}, "squash": {"type": "number"}, "face": FACE, "clip": {"type": "string"}, "exiting": {"type": "boolean"}, "z": {"type": "number"}}}
START = {"type": "object", "required": ["actor", "x", "pose"], "properties": {"actor": {"type": "string"}, "char": {"type": "string"}, "x": {"type": "number"}, "pose": {"type": "string"}, "facing": {"type": "number"}, "scale": {"type": "number"}, "lift": {"type": "number"}, "z": {"type": "number"}, "opacity": {"type": "number"}, "face": FACE, "exiting": {"type": "boolean"}}}
TOOLS = {
    "define_character": {"description": "Create or patch a jointed character. Returns joint problems per pose, pose bounds and a letter-map silhouette.", "parameters": {"type": "object", "required": ["id"], "properties": {
        "id": {"type": "string"},
        "bones": {"type": "array", "items": {"type": "object", "required": ["name", "pivot"], "properties": {"name": {"type": "string"}, "parent": {"type": ["string", "null"]}, "pivot": {"type": "array", "items": {"type": "number"}}, "rest": {"type": "number"}, "z": {"type": "number"}, "code": {"type": "string", "description": CODE + " (ctx, f)"}}}},
        "poses": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": {"type": "number"}}}}}},
    "paint_scene": {"description": "Create or patch background layers, the ground line and anchors. Returns colour stats and a letter map of the frame.", "parameters": {"type": "object", "properties": {
        "layers": {"type": "array", "items": {"type": "object", "required": ["name", "code"], "properties": {"name": {"type": "string"}, "depth": {"type": "number"}, "front": {"type": "boolean"}, "animated": {"type": "boolean"}, "code": {"type": "string", "description": CODE + " (ctx, W, H, t, rand)"}}}},
        "ground": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
        "anchors": {"type": "array", "items": {"type": "object", "required": ["name", "x", "y", "rx", "ry"], "properties": {"name": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"}, "rx": {"type": "number"}, "ry": {"type": "number"}}}}}}},
    "stage_scene": {"description": "Replace the timeline. Write every beat in full.", "parameters": {"type": "object", "required": ["duration", "start", "beats"], "properties": {"duration": {"type": "number"}, "start": {"type": "array", "items": START}, "beats": {"type": "array", "items": BEAT}}}},
    "check_scene": {"description": "Render the scene and report issues, per-actor measurements every second, and letter maps of key frames. Letters: k black, w white, a grey, r red, o orange, y yellow, l light green, g green, d dark green, b blue, s pale blue, p pink, n brown, t tan. UPPERCASE cells belong to an actor.", "parameters": {"type": "object", "properties": {"times": {"type": "array", "items": {"type": "number"}, "description": "Up to 3 seconds to view as letter maps"}}}},
    "finish_scene": {"description": "Submit the page. The scene gate runs and refuses the page if issues remain.", "parameters": {"type": "object", "required": ["title", "director_note"], "properties": {"title": {"type": "string"}, "director_note": {"type": "string", "description": "2 sentences on the emotional choice you staged"}}}},
}
FN = {"define_character": "a=>LB.toolDefine(a)", "paint_scene": "a=>LB.toolPaint(a)", "stage_scene": "a=>LB.toolStage(a)", "check_scene": "a=>LB.toolCheck(a)"}


def tools_for(names):
    return [{"type": "function", "function": {"name": n, **TOOLS[n]}} for n in names]


def browser(p):
    br = p.chromium.launch(channel="chrome", headless=True)
    pg = br.new_context(viewport={"width": 390, "height": 520}, offline=True).new_page()
    pg.set_content("<!doctype html><html><body></body></html>"); pg.add_script_tag(content=ENGINE)
    return br, pg


def fix_args(name, args):
    if name == "stage_scene" and isinstance(args.get("start"), list):
        args["start"] = {s["actor"]: {k: v for k, v in s.items() if k != "actor"} for s in args["start"] if s.get("actor")}
    if name == "paint_scene" and isinstance(args.get("anchors"), list):
        args["anchors"] = {x["name"]: {k: v for k, v in x.items() if k != "name"} for x in args["anchors"] if x.get("name")}
    return args


def assistant_entry(m):
    e = {"role": "assistant", "content": m.get("content") or ""}
    if m.get("reasoning_content") is not None: e["reasoning_content"] = m["reasoning_content"]
    if m.get("tool_calls"):
        for tc in m["tool_calls"]:
            try: json.loads(tc["function"]["arguments"] or "{}")
            except Exception: tc["function"]["arguments"] = "{}"
        e["tool_calls"] = m["tool_calls"]
    return e


def short(res):
    s = {k: v for k, v in res.items() if k not in ("frames", "frame", "samples", "silhouette_rest", "poses")}
    if "poses" in res: s["joint_problems"] = {k: v["joint_problems"] for k, v in res["poses"].items() if v.get("joint_problems")}
    return json.dumps(s, ensure_ascii=False)[:800]


def do_read():
    run = Run("read")
    print("reading", len(BOOK), "chars", flush=True)
    c = run.beam([{"role": "user", "content": READ}], "high", max_tokens=40000)
    run.write("assistant", content=c["message"].get("content"), reasoning=c["message"].get("reasoning_content"))
    bible = fence(c["message"]["content"]); pos = 0; gaps = []
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    flat = norm(CLEAN)
    for pg_ in bible["pages"]:
        st = flat.find(norm(pg_["first_words"]), pos); en = flat.find(norm(pg_["last_words"]), st)
        if st < 0 or en < 0: raise SystemExit(f"page {pg_['page']} words not found: {pg_['first_words']} / {pg_['last_words']}")
        en += len(norm(pg_["last_words"]))
        if flat[pos:st].strip(): gaps.append((pg_["page"], flat[pos:st]))
        pg_["text"] = flat[st:en]; pos = en
    if flat[pos:].strip(): gaps.append(("end", flat[pos:]))
    j(os.path.join(BOOKDIR, "bible.json"), bible)
    print("pages", len(bible["pages"]), "gaps", gaps, "cast", [x["id"] for x in bible["cast"]], "sets", [x["id"] for x in bible["sets"]], json.dumps(run.tot), flush=True)


def cast_sheet(pg, cast):
    chars = list(cast.values()); rows = []
    for c in chars:
        pg.evaluate("c=>LB.addChars([c])", {k: v for k, v in c.items()})
    html = "<canvas id=s></canvas>"
    size = 150; cols = 8; poses = [(c["id"], n) for c in chars for n in c["poses"]]
    data = pg.evaluate("""([poses,size,cols])=>{const r=Math.ceil(poses.length/cols),c=document.createElement('canvas');c.width=cols*size;c.height=r*(size*1.3+14);const x=c.getContext('2d');x.fillStyle='#e9dcc3';x.fillRect(0,0,c.width,c.height);
      poses.forEach(([id,n],i)=>{const gx=i%cols*size,gy=Math.floor(i/cols)*(size*1.3+14);x.save();x.translate(gx+size/2,gy+size*1.25);x.scale(.62,.62);LB.poseSheet(x,id,n);x.restore();x.fillStyle='#333';x.font='11px sans-serif';x.fillText(id+':'+n,gx+4,gy+size*1.3+10);});return c.toDataURL('image/png')}""", [poses, size, cols])
    import base64
    open(os.path.join(BOOKDIR, "cast-sheet.png"), "wb").write(base64.b64decode(data.split(",")[1]))


def do_cast(note=None):
    bible = j(os.path.join(BOOKDIR, "bible.json")); run = Run("cast"); path = os.path.join(BOOKDIR, "cast.json")
    pages = [{"page": p["page"], "cast": p.get("cast"), "scene": p["scene"]} for p in bible["pages"]]
    brief = {"world": bible["world"], "palette": bible["palette"], "cast": bible["cast"], "pages": pages}
    bp = os.path.join(BOOKDIR, "cast-brief.txt"); custom = open(bp, encoding="utf-8").read() if os.path.exists(bp) else None
    posegu = custom.split("=====")[1].strip() if custom else PEOPLE_GUIDE
    ask = f"""Your story bible, from your own reading of the whole book:
{json.dumps(brief, ensure_ascii=False, indent=1)}

{ART}

CAST PHASE. Design every character in the bible with define_character, one call per character, starting with the hero. Use the exact bible ids. Share one drawing language: the same outline weight, shading shapes and eye style, so that they belong to one book. Each main character has at least 12 bones with jointed limbs. Give costumes layered detail: shading shapes, trim, buttons, fur tufts. Each group such as the siblings is ONE rig; three actors will share it and f.variant (0, 1, 2) changes its colours and small details.

{posegu}

After each call read joint_problems, bounds and silhouette, and fix them. When every character is clean, stop calling tools and reply with one sentence."""
    if note and os.path.exists(path):
        ask = f"Your cast for this book is already designed. Here is the complete rig data, with every bone's name, pivot, code, and every pose: {json.dumps(j(path), ensure_ascii=False)}.\n\n{ART}\n\nREVIEW NOTES from the art review: {note}\n\nFix these with define_character patches: send only the bones and poses that change. When done, stop calling tools and reply with one sentence."
    seed = os.path.join(ROOT, "experiments", "puppet-stage", "run3", "scene.json")
    if not note and os.path.exists(seed):
        ref = j(seed)["chars"]["peter"]["bones"]
        intro = (custom.split("=====")[0].strip() + chr(10) + "Style reference only, a rabbit rig from the same book family: reuse its technique of flat fills with a darker and lighter shape on top, not the animal. Here are its bones:" + chr(10)) if custom else CAST_STYLE
        ask = intro + json.dumps([{k: x.get(k) for k in ("name", "parent", "pivot", "z", "code")} for x in ref], ensure_ascii=False) + 2 * chr(10) + ask
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": ask}]
    with sync_playwright() as p:
        br, pg = browser(p)
        if os.path.exists(path): pg.evaluate("c=>LB.addChars(c)", list(j(path).values()))
        last = None
        for turn in range(1, 31):
            c = run.beam(msgs, "xhigh", tools_for(["define_character"])); m = c["message"]; msgs.append(assistant_entry(m))
            run.write("assistant", content=m.get("content"), reasoning=m.get("reasoning_content"), calls=[x["function"]["name"] for x in (m.get("tool_calls") or [])])
            if not m.get("tool_calls"):
                if c.get("finish_reason") == "length":
                    msgs.append({"role": "user", "content": "That ran out of tokens. Continue with one character at a time."}); continue
                break
            for tc in m["tool_calls"]:
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}"); res = pg.evaluate(FN["define_character"], args)
                except Exception as e:
                    res = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}; args = {}
                msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(res, ensure_ascii=False)})
                print("  ", args.get("id"), len(tc["function"]["arguments"]), short(res), flush=True); run.write("tool", name="define_character", args=args, result=res)
            sc = pg.evaluate("()=>LB.exportScene()")["chars"]; j(path, sc)
        cast_sheet(pg, j(path)); br.close()
    print("cast done", list(j(path)), json.dumps(run.tot), flush=True)


def page_sheet(br, sc, n):
    html = "<!doctype html><canvas id=c width=390 height=520></canvas>"
    pg = br.new_context(viewport={"width": 390, "height": 520}, offline=True).new_page(); pg.set_content(html); pg.add_script_tag(content=ENGINE)
    errs = pg.evaluate("s=>LB.load(s)", sc); dur = pg.evaluate("()=>LB.duration()"); frames = []
    for q in range(6):
        d = pg.evaluate("t=>{const c=document.getElementById('c');LB.render(c.getContext('2d'),t,{scale:1});return c.toDataURL('image/jpeg',.85)}", dur * (q + .4) / 6)
        import base64
        frames.append(Image.open(io.BytesIO(base64.b64decode(d.split(",")[1]))).convert("RGB"))
    sh = Image.new("RGB", (6 * 262, 346), "white")
    for q, f in enumerate(frames): sh.paste(f.resize((260, 346)), (q * 262, 0))
    sh.save(os.path.join(PAGES, f"{n:02d}-sheet.jpg"), quality=86); pg.context.close()
    return errs


def do_page(n, note=None):
    bible = j(os.path.join(BOOKDIR, "bible.json")); cast = j(os.path.join(BOOKDIR, "cast.json")); P = next(x for x in bible["pages"] if x["page"] == n)
    run = Run(f"page{n:02d}"); out = os.path.join(PAGES, f"{n:02d}.json")
    prior = j(out) if note and os.path.exists(out) else None
    if note: run.write("note", note=note)
    sets = [s for s in bible.get("sets", []) if s["id"] == P.get("set")]
    idx = bible["pages"].index(P); prev = bible["pages"][idx - 1]["scene"] if idx else None; nxt = bible["pages"][idx + 1]["scene"] if idx + 1 < len(bible["pages"]) else None
    poses = {k: list(v["poses"]) for k, v in cast.items() if k in (P.get("cast") or list(cast))}
    brief = {"world": bible["world"], "palette": bible["palette"], "emotional_arc": bible["emotional_arc"], "set": sets}
    anp = os.path.join(BOOKDIR, "art-note.txt"); artnote = open(anp, encoding="utf-8").read().strip() if os.path.exists(anp) else ""
    head = f"""Your story bible, from your own reading of the whole book:
{json.dumps(brief, ensure_ascii=False, indent=1)}

{ART}
{artnote}

PAGE {n} of {len(bible['pages'])}. Feeling: {P.get('feeling')}. Why it matters: {P.get('why')}
Staging from your plan: {P['scene']}
Previous page: {prev}
Next page: {nxt}

--- THE PAGE'S TEXT ---
{P['text']}
---

Your finished characters, with their poses: {json.dumps(poses)}
Custom face fields: prop (draws a named prop), jacket, shoes, variant."""
    paint = "\n\nPHASE 1, WORLD. Paint this page's world with paint_scene in one call. Use at least 6 static layers plus one animated layer. Each layer is a separate sheet of the pop-up at its own depth, so the near sheets need transparent areas that reveal the sheets behind. The set description lists the whole location, but this page shows ONE corner of it: paint only what this page's text mentions plus simple surroundings, so never put every prop in one view. Keep colours and materials consistent with the set. Draw many individual shapes using loops: leaves, bricks, furrows, planks. Expect a long program, 15 KB of code or more; thin backgrounds fail. Each value in edge_detail_pct_top_to_bottom must be at least 3, and largest_flat_colour_pct at most 30. Keep at least the central 250 px wide, 130 to 460 px tall zone free of front layers for the actors."
    stagep = "PHASE 2, PERFORMANCE. Stage this page as an 8 to 14 second scene, with each beat's phrase copied from the text. Call stage_scene, then check_scene, and fix what it reports. Add a pose with define_character if the page needs one. Mark actors that start hidden or offstage with exiting:true and set exiting:false once they are on stage. Finish with finish_scene: the gate refuses the page while issues remain."
    state = "paint"
    if prior:
        state = "stage"
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"{head}\n\nThis page is already painted and staged. Layers: {[l['name'] for l in prior['scene']['layers']]}.\nCurrent timeline: {json.dumps(prior['scene']['stage'], ensure_ascii=False)}\n\nREVIEW NOTES from the art review: {note}\n\nFix these, using patches: paint_scene for named layers, define_character for poses, stage_scene for the timeline. Then check_scene and finish_scene."}]
    else:
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": head + paint}]
    done = None; gate = None; turn = 0; repeat = 0; lastsig = None
    with sync_playwright() as p:
        br, pg = browser(p)
        if prior:
            pg.evaluate("s=>LB.load(s)", prior["scene"])
        else:
            pg.evaluate("c=>LB.addChars(c)", list(cast.values()))
        for turn in range(1, 19):
            names = ["paint_scene"] if state == "paint" else ["stage_scene", "check_scene", "define_character", "paint_scene", "finish_scene"]
            c = run.beam(msgs, "xhigh" if state == "paint" else "high", tools_for(names)); m = c["message"]; msgs.append(assistant_entry(m))
            run.write("assistant", phase=state, content=m.get("content"), reasoning=m.get("reasoning_content"), calls=[x["function"]["name"] for x in (m.get("tool_calls") or [])])
            if not m.get("tool_calls"):
                msgs.append({"role": "user", "content": "Your message ran out of tokens; be shorter." if c.get("finish_reason") == "length" else "Continue with tools."}); continue
            advance = False
            for tc in m["tool_calls"]:
                name = tc["function"]["name"]; raw = tc["function"]["arguments"] or "{}"
                try:
                    args = fix_args(name, json.loads(raw))
                    if name == "finish_scene":
                        chk = pg.evaluate(FN["check_scene"], {}); bad = [i for i in chk["issues"]]
                        gate = {"passed": not bad, "issues": [i["what"] for i in bad]}
                        res = {"ok": True} if not bad else {"ok": False, "refused": "the scene gate found issues", "issues": chk["issues"]}
                        if not bad or turn >= 16: done = args
                    elif name not in names:
                        res = {"ok": False, "error": f"{name} is not available now"}
                    else:
                        res = pg.evaluate(FN[name], args)
                        if state == "paint" and name == "paint_scene":
                            st = res.get("stats", {}); bands = st.get("edge_detail_pct_top_to_bottom", [0]); statics = len([x for x in res.get("layers", []) if "animated" not in x])
                            if res.get("ok") and min(bands) >= 3 and st.get("largest_flat_colour_pct", 100) <= 30 and statics >= 5: advance = True
                            else: res["not_yet"] = "This fails phase 1: need every band >= 3, largest flat colour <= 30, at least 5 static layers. Patch the weak layers."
                except Exception as e:
                    res = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}; args = {}
                msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(res, ensure_ascii=False)})
                print(f"p{n}", name, len(raw), short(res), flush=True); run.write("tool", name=name, args=args, result=res)
                sig = name + raw; repeat = repeat + 1 if sig == lastsig else 0; lastsig = sig
            if advance:
                state = "stage"; msgs.append({"role": "user", "content": stagep})
            if done or repeat >= 2: break
        final = pg.evaluate(FN["check_scene"], {}); sc = pg.evaluate("()=>LB.exportScene()")
        used = {(s.get("char") or a) for a, s in sc["stage"]["start"].items()}; sc["chars"] = {k: v for k, v in sc["chars"].items() if k in used}
        rec = {"page": n, "text": P["text"], "feeling": P.get("feeling"), "title": (done or {}).get("title"), "director_note": (done or {}).get("director_note"), "gate": {"passed": not final["issues"], "issues": [i["what"] for i in final["issues"]]}, "turns": turn, "usage": run.tot, "scene": sc}
        j(out, rec); errs = page_sheet(br, sc, n); br.close()
    print(f"p{n} DONE gate={rec['gate']} turns={turn} sheet_errs={errs} {json.dumps(run.tot)}", flush=True)


def do_pages(nums):
    q = list(nums); live = []; env = dict(os.environ)
    while q or live:
        while q and len(live) < 4:
            n = q.pop(0); f = open(os.path.join(LOGS, f"page{n:02d}.log"), "a", encoding="utf-8")
            live.append((n, subprocess.Popen([sys.executable, "-X", "utf8", "-I", os.path.abspath(__file__), "page", str(n)], stdout=f, stderr=subprocess.STDOUT, env=env, cwd=os.path.dirname(os.path.abspath(__file__))), time.time()))
        time.sleep(3)
        for it in list(live):
            n, pr, t = it
            if pr.poll() is not None:
                print("page", n, "exit", pr.returncode, round(time.time() - t), "s", flush=True); live.remove(it)
            elif time.time() - t > 1500:
                pr.kill(); print("page", n, "killed", flush=True); live.remove(it)


def do_sheet():
    files = sorted(x for x in os.listdir(PAGES) if x.endswith("-sheet.jpg")); ims = [Image.open(os.path.join(PAGES, x)) for x in files]
    for part in range(0, len(ims), 7):
        chunk = ims[part:part + 7]; sh = Image.new("RGB", (ims[0].width + 40, len(chunk) * 350), "white"); d = ImageDraw.Draw(sh)
        for i, im in enumerate(chunk):
            sh.paste(im, (40, i * 350)); d.text((6, i * 350 + 160), files[part + i][:2], fill="black")
        sh.save(os.path.join(BOOKDIR, f"review-{part // 7 + 1}.jpg"), quality=84)
    tot = {}; rows = []
    for x in sorted(x for x in os.listdir(PAGES) if x.endswith(".json")):
        r = j(os.path.join(PAGES, x)); rows.append({"page": r["page"], "passed": r["gate"]["passed"], "issues": r["gate"]["issues"], "turns": r["turns"], "out": r["usage"]["completion"]})
        for k in ("prompt", "cached", "completion", "reasoning", "seconds", "calls"): tot[k] = tot.get(k, 0) + r["usage"][k]
    j(os.path.join(BOOKDIR, "report.json"), {"pages": rows, "totals": tot}); print(json.dumps(rows, ensure_ascii=False)[:1500]); print(tot)


cmd = sys.argv[1]
if cmd == "read": do_read()
elif cmd == "cast": do_cast(sys.argv[2] if len(sys.argv) > 2 else None)
elif cmd == "page": do_page(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
elif cmd == "pages": do_pages([int(x) for x in sys.argv[2:]] or [p["page"] for p in j(os.path.join(BOOKDIR, "bible.json"))["pages"]])
elif cmd == "sheet": do_sheet()
elif cmd == "regate":
    with sync_playwright() as p:
        br, pg = browser(p)
        for x in sorted(x for x in os.listdir(PAGES) if x.endswith(".json")):
            r = j(os.path.join(PAGES, x)); pg.evaluate("s=>{LB.reset();LB.load(s)}", r["scene"]); c = pg.evaluate(FN["check_scene"], {})
            r["gate"] = {"passed": not c["issues"], "issues": [i["what"] for i in c["issues"]]}; j(os.path.join(PAGES, x), r); print(x, r["gate"], flush=True)
        br.close()
