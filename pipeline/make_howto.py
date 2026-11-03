"""Records the "how it works" clip from site/howto.html (Beam's real record of Peter Rabbit page 5) into site/assets: how.mp4, how.jpg and how.gif.
Usage: python -X utf8 -I make_howto.py <site url>"""
import os, shutil, subprocess, sys, tempfile
from playwright.sync_api import sync_playwright
URL = sys.argv[1].rstrip("/") + "/howto.html"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "site", "assets"); FPS = 25
tmp = tempfile.mkdtemp(prefix="lb_how_")
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
    pg = br.new_page(viewport={"width": 1280, "height": 720}); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    pg.goto(URL); pg.wait_for_function("window.ready===true", timeout=30000); dur = pg.evaluate("DUR")
    for k in range(int(dur * FPS)):
        pg.evaluate(f"frame({k / FPS})"); pg.locator("#f").screenshot(path=os.path.join(tmp, f"{k:04d}.png"))
    print("errors", errs); br.close()
fr = os.path.join(tmp, "%04d.png")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", fr, "-vf", "fade=in:st=0:d=0.4,fade=out:st=%.2f:d=0.5" % (dur - 0.5), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "28", "-preset", "slow", "-movflags", "+faststart", "-an", os.path.join(OUT, "how.mp4")], check=True)
shutil.copy(os.path.join(tmp, f"{int(19 * FPS):04d}.png"), os.path.join(tmp, "poster.png"))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(tmp, "poster.png"), "-q:v", "4", os.path.join(OUT, "how.jpg")], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", fr, "-vf", "fps=10,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle", os.path.join(ROOT, "dist", "how.gif")], check=True)
shutil.rmtree(tmp, ignore_errors=True)
for f in (os.path.join(OUT, "how.mp4"), os.path.join(OUT, "how.jpg"), os.path.join(ROOT, "dist", "how.gif")): print(f, round(os.path.getsize(f) / 1024), "KB")
