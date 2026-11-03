"""Records a ~75 s demo video of the live site with Playwright, then joins the parts with ffmpeg.
Usage: python -X utf8 -I make_video.py <site url>    Output: dist/video/living-books.mp4"""
import os, shutil, subprocess, sys, time
from playwright.sync_api import sync_playwright

URL = sys.argv[1].rstrip("/") + "/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dist", "video"); TMP = os.path.join(OUT, "parts")
shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
W, H = 1280, 720
CAP = """(t)=>{let c=document.getElementById('__cap');if(!c){c=document.createElement('div');c.id='__cap';c.style.cssText='position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;background:rgba(43,36,32,.88);color:#fff;font:600 22px/1.35 system-ui,sans-serif;padding:12px 22px;border-radius:14px;max-width:1000px;text-align:center;transition:opacity .3s';document.body.append(c)}c.style.opacity=t?1:0;if(t)c.textContent=t}"""
CARD = """<!doctype html><html style="background:#f4eadb;height:100%"><body style="margin:0;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#f4eadb;color:#2b2420;font-family:Georgia,serif;text-align:center">{}</body></html>"""
parts = []

def record(name, fn):
    """Runs fn(page, mark) in a fresh recorded context; mark() sets where the kept footage starts."""
    ctx = br.new_context(viewport={"width": W, "height": H}, record_video_dir=TMP, record_video_size={"width": W, "height": H})
    pg = ctx.new_page(); t0 = time.monotonic(); start = [0.0]
    def mark(): start[0] = time.monotonic() - t0
    fn(pg, mark); dur = time.monotonic() - t0 - start[0]
    path = pg.video.path(); ctx.close()
    out = os.path.join(TMP, f"{len(parts):02d}-{name}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start[0]:.2f}", "-i", path, "-t", f"{dur:.2f}", "-vf", f"fps=30,scale={W}:{H}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-an", out], check=True)
    parts.append(out); print(name, round(dur, 1), "s")

def still(name, html, secs):
    """Title and end cards are still images, held for secs seconds."""
    pg = br.new_page(viewport={"width": W, "height": H}); pg.set_content(CARD.format(html)); pg.wait_for_timeout(300)
    png = os.path.join(TMP, f"{name}.png"); pg.screenshot(path=png); pg.close()
    out = os.path.join(TMP, f"{len(parts):02d}-{name}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-i", png, "-t", str(secs), "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "20", out], check=True)
    parts.append(out); print(name, secs, "s")

def sway(pg, secs, box="#stage"):
    """Moves the mouse slowly across the scene for secs seconds of wall time, so the pop-up layers shift."""
    import math
    b = pg.locator(box).bounding_box(); t0 = time.monotonic()
    while (u := (time.monotonic() - t0) / secs) < 1:
        pg.mouse.move(b["x"] + b["width"] * (0.5 + 0.42 * math.sin(u * 2 * math.pi)), b["y"] + b["height"] * (0.5 + 0.2 * math.sin(u * 4 * math.pi)))
        pg.wait_for_timeout(30)

def reader(book, pages):
    def f(pg, mark):
        pg.goto(URL + f"read.html?book={book}&page={pages[0][0]}", wait_until="networkidle"); pg.wait_for_timeout(2500); mark()
        for i, (n, secs, cap) in enumerate(pages):
            if i: pg.evaluate("n=>reader.show(n-1)", n); pg.wait_for_timeout(400)
            pg.evaluate(CAP, cap); sway(pg, secs)
        pg.evaluate(CAP, "")
    return f

def landing(pg, mark):
    pg.goto(URL, wait_until="networkidle"); pg.wait_for_timeout(1500); mark()
    pg.evaluate(CAP, "Whole classic books as paper pop-ups. Beam made every page."); pg.wait_for_timeout(3500)
    for _ in range(12): pg.mouse.wheel(0, 90); pg.wait_for_timeout(60)
    pg.wait_for_timeout(1200)

def howto(pg, mark):
    pg.goto(URL + "assets/" + [n for n in os.listdir(os.path.join(ROOT, "dist", "web", "assets")) if n.startswith("how.") and n.endswith(".mp4")][0], wait_until="load")
    pg.evaluate("()=>{const v=document.querySelector('video');v.muted=true;v.pause();v.currentTime=0;document.body.style.margin=0;document.body.style.background='#f4eadb';v.style.cssText='width:100vw;height:100vh;object-fit:contain'}")
    pg.wait_for_timeout(500); mark(); pg.evaluate("()=>document.querySelector('video').play()"); pg.wait_for_timeout(21500)

def watch(pg, mark):
    pg.goto(URL + "watch.html?book=peter-rabbit", wait_until="networkidle"); pg.wait_for_timeout(1500)
    pg.evaluate("()=>{const b=[...document.querySelectorAll('.tabs button')].find(x=>x.textContent.trim()==='5');b&&b.click()}"); pg.wait_for_timeout(1500); mark()
    pg.evaluate(CAP, "Watch Beam read: every real call and every fix, replayed from the transcripts")
    for _ in range(30): pg.mouse.wheel(0, 70); pg.wait_for_timeout(110)
    pg.wait_for_timeout(1500)

def game(pg, mark):
    pg.goto(URL + "games/peter-rabbit.html", wait_until="networkidle"); pg.evaluate("()=>{document.documentElement.style.background=getComputedStyle(document.body).backgroundColor||'#f4eadb'}"); pg.wait_for_timeout(1200); mark()
    pg.evaluate(CAP, "After the last page: a small game Beam wrote in one call"); pg.wait_for_timeout(2500)
    pg.keyboard.press("Enter")
    for k, ms in (("ArrowUp", 700), ("ArrowRight", 500), ("ArrowUp", 600)):
        pg.keyboard.down(k); pg.wait_for_timeout(ms); pg.keyboard.up(k)
    pg.wait_for_timeout(500)

with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
    still("title", '<div style="font:600 15px system-ui;letter-spacing:.14em;color:#c8743a">BUILD WITH BEAM</div><h1 style="font-size:76px;font-weight:normal;margin:14px 0 10px">Living Books</h1><p style="font-size:28px;color:#6d6055;margin:0">Whole classic books as moving paper pop-ups,<br>read, designed and animated by Beam through tool calls.</p>', 3.5)
    record("landing", landing)
    record("peter", reader("peter-rabbit", [
        (1, 5, "The Tale of Peter Rabbit: 14 pages, every scene alive"),
        (5, 7, "Each move is tied to a phrase of the text. Move the mouse or tilt a phone to look in."),
        (8, 5, "Every character is a jointed paper puppet Beam drew in code"),
        (11, 4, "Every page is layers of canvas code standing at different depths")]))
    record("how", howto)
    record("watch", watch)
    record("prince", reader("happy-prince", [
        (3, 5, "The Happy Prince: 19 pages, for older readers"),
        (15, 5, "670 Beam calls across both books. All 33 pages pass the scene check.")]))
    record("game", game)
    still("end", '<div style="font:600 15px system-ui;letter-spacing:.14em;color:#c8743a">LIVING BOOKS</div><h1 style="font-size:60px;font-weight:normal;margin:14px 0 18px">Made by Mika</h1><p style="font-size:28px;color:#3b5f8a;margin:0">Try it yourself: the links are in the description.</p>', 5)
    br.close()

lst = os.path.join(TMP, "list.txt"); open(lst, "w").write("".join(f"file '{p.replace(chr(92), '/')}'\n" for p in parts))
final = os.path.join(OUT, "living-books.mp4")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", "-preset", "slow", "-movflags", "+faststart", "-an", final], check=True)
d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", final], capture_output=True, text=True).stdout.strip()
print("video", final, round(float(d), 1), "s", os.path.getsize(final) // 1024, "KB")
