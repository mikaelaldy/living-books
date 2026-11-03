"""Frame-time test of the reader in phone-sized Chrome, at normal speed and with CPU throttling.
This is a stress estimate, not a real phone. Usage: python -X utf8 -I perf.py <site url> <page>"""
import json, sys
from playwright.sync_api import sync_playwright

URL, PAGE = sys.argv[1], sys.argv[2]
JS = """()=>new Promise(res=>{let n=0,t0=performance.now(),last=t0,worst=0;function f(now){n++;worst=Math.max(worst,now-last);last=now;if(now-t0>6000)res({fps:+(n/((now-t0)/1000)).toFixed(1),worst_ms:Math.round(worst)});else requestAnimationFrame(f)}requestAnimationFrame(f)})"""
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True, args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])
    for name, rate in (("no throttle", 1), ("CPU 4x slower", 4), ("CPU 6x slower", 6)):
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        cdp = ctx.new_cdp_session(pg); cdp.send("Emulation.setCPUThrottlingRate", {"rate": rate})
        pg.goto(f"{URL}?page={PAGE}&mode=popup", wait_until="load"); pg.wait_for_timeout(2500)
        gpu = pg.evaluate("()=>{const g=document.createElement('canvas').getContext('webgl2');if(!g)return null;const e=g.getExtension('WEBGL_debug_renderer_info');return e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):'hidden'}")
        print(name, json.dumps(pg.evaluate(JS)), "errors", errs[:3], "| gpu", gpu, flush=True)
        ctx.close()
    br.close()
