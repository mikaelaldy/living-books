"""Renders the five method images (site/assets/step1..5.webp) from site/steps.html, which draws them from Beam's real data for Peter Rabbit page 5.
Usage: python -X utf8 -I make_steps.py <site url>"""
import io, os, sys
from PIL import Image
from playwright.sync_api import sync_playwright
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site", "assets")
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
    pg = b.new_context(viewport={"width": 820, "height": 800}, device_scale_factor=2).new_page()
    pg.goto(sys.argv[1].rstrip("/") + "/steps.html"); pg.wait_for_function("window.ready===true", timeout=30000); pg.wait_for_timeout(500); pg.evaluate("redrawPop()")
    for i in range(1, 6):
        im = Image.open(io.BytesIO(pg.locator(f"#s{i}").screenshot())).convert("RGB")
        im = im.resize((im.width * 3 // 4, im.height * 3 // 4), Image.LANCZOS)  # 1200 px wide
        im.save(os.path.join(OUT, f"step{i}.webp"), quality=80, method=6); print(i, im.size, os.path.getsize(os.path.join(OUT, f"step{i}.webp")) // 1024, "KB")
    b.close()
