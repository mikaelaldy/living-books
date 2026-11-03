import json, sys
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8123/"
FPS = """()=>new Promise(res=>{let n=0,t0=performance.now();function f(now){n++;if(now-t0>2500)res(+(n/((now-t0)/1000)).toFixed(1));else requestAnimationFrame(f)}requestAnimationFrame(f)})"""
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True, args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:220])); pg.on("console", lambda m: errs.append(m.text[:220]) if m.type == "error" else None)
    pg.goto(URL + "?page=1&mode=popup", wait_until="load"); pg.wait_for_timeout(2000)
    out = []
    for n in range(14):
        pg.evaluate("n=>reader.show(n)", n); pg.wait_for_timeout(900)
        fps = pg.evaluate(FPS); over = pg.evaluate("()=>{const t=document.getElementById('text');return [t.scrollHeight,t.clientHeight]}")
        out.append((n + 1, fps, over)); print(n + 1, fps, "text", over, flush=True)
        if n + 1 in (10, 13): pg.screenshot(path=f"../books/peter-rabbit/phone-{n+1}.png")
    print("errors", errs[:6], "mode", pg.evaluate("()=>reader.mode")); br.close()
