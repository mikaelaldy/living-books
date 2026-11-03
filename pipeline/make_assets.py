"""Renders the landing assets from Beam's real scenes: a pop-up hero montage video, its poster, book covers and a social card.
Usage: python -X utf8 -I make_assets.py <site url>"""
import io, math, os, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

URL = sys.argv[1].rstrip("/") + "/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "site", "assets"); os.makedirs(OUT, exist_ok=True)
SHOTS = [("peter-rabbit", 5, 1.2), ("happy-prince", 15, 0.6), ("peter-rabbit", 13, 1.0)]  # book, page, start time
FPS, SEG = 30, 4.0
tmp = tempfile.mkdtemp(prefix="lb_frames_")

with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True, args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
    pg = br.new_context(viewport={"width": 600, "height": 800}, device_scale_factor=1).new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    pg.goto(URL + "capture.html", wait_until="load"); pg.wait_for_function("window.ready===true", timeout=20000)
    for si, (book, page, t0) in enumerate(SHOTS):
        dur = pg.evaluate("a=>cap.load(a[0],a[1])", [book, page]); pg.wait_for_timeout(300)
        os.makedirs(os.path.join(tmp, f"s{si}"))
        for k in range(int(SEG * FPS)):
            u = k / (SEG * FPS); t = (t0 + k / FPS) % dur
            cx = 1.1 * math.sin(2 * math.pi * (u * 0.5 - 0.25)); cy = 0.35 * math.sin(2 * math.pi * u * 0.5)
            pg.evaluate("a=>cap.show(a[0],a[1],a[2])", [t, cx, cy])
            pg.locator("#c").screenshot(path=os.path.join(tmp, f"s{si}", f"{k:04d}.png"))
    # covers: still pop-up frames, centred camera
    for book, page in (("peter-rabbit", 1), ("happy-prince", 3)):
        pg.evaluate("a=>cap.load(a[0],a[1])", [book, page]); pg.wait_for_timeout(300); pg.evaluate("()=>cap.show(2.5,0,0)")
        im = Image.open(io.BytesIO(pg.locator("#c").screenshot())).convert("RGB").resize((300, 400), Image.LANCZOS)
        im.save(os.path.join(OUT, f"cover-{book}.webp"), quality=82, method=6)
    print("render errors:", errs[:3]); br.close()

# Encode each segment, then crossfade them into one loop.
segs = []
for si in range(len(SHOTS)):
    seg = os.path.join(tmp, f"seg{si}.mp4"); segs.append(seg)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, f"s{si}", "%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", seg], check=True)
fade = 0.6; filt = []; last = "[0:v]"; off = SEG - fade
for i in range(1, len(segs)):
    filt.append(f"{last}[{i}:v]xfade=transition=fade:duration={fade}:offset={off:.2f}[v{i}]"); last = f"[v{i}]"; off += SEG - fade
cmd = ["ffmpeg", "-y", "-loglevel", "error"]
for s in segs: cmd += ["-i", s]
cmd += ["-filter_complex", ";".join(filt), "-map", last, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "29", "-preset", "slow", "-movflags", "+faststart", "-an", os.path.join(OUT, "hero.mp4")]
subprocess.run(cmd, check=True)
Image.open(os.path.join(tmp, "s0", "0000.png")).convert("RGB").save(os.path.join(OUT, "hero.jpg"), quality=80, optimize=True, progressive=True)

# Social card, 1200 x 630.
card = Image.new("RGB", (1200, 630), "#f4eadb"); d = ImageDraw.Draw(card)
f = lambda n: ImageFont.truetype(r"C:\Windows\Fonts\georgia.ttf", n)
d.text((70, 120), "Living Books", font=f(78), fill="#2b2420")
d.text((72, 230), "Classic stories, reflected by Beam", font=f(36), fill="#6d6055")
d.text((72, 330), "Whole books as living paper pop-ups.", font=f(30), fill="#2b2420")
d.text((72, 375), "Beam reads, designs, paints and animates", font=f(30), fill="#2b2420")
d.text((72, 420), "every page through tools.", font=f(30), fill="#2b2420")
d.text((72, 530), "Unofficial. Built with Beam by Reflection AI.", font=f(22), fill="#6d6055")
hero = Image.open(os.path.join(tmp, "s0", "0060.png")).convert("RGB").resize((390, 520), Image.LANCZOS)
card.paste(hero, (760, 55)); card.save(os.path.join(OUT, "og.jpg"), quality=84, optimize=True)
shutil.rmtree(tmp, ignore_errors=True)
for n in sorted(os.listdir(OUT)): print(n, round(os.path.getsize(os.path.join(OUT, n)) / 1024), "KB")
