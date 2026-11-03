"""Builds the production site into dist/web: bundled and minified scripts, fingerprinted assets, cache headers.
Usage: python -X utf8 -I build_site.py"""
import hashlib, os, re, shutil, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); SRC = os.path.join(ROOT, "site"); OUT = os.path.join(ROOT, "dist", "web")
shutil.rmtree(OUT, ignore_errors=True)
shutil.copytree(SRC, OUT, ignore=shutil.ignore_patterns("vendor", "capture.html", "howto.html", "steps.html", "app.js", "popup.js", "engine.js", "assets"))
NPX = shutil.which("npx") or shutil.which("npx.cmd")
def esbuild(*args): subprocess.run([NPX, "--yes", "esbuild@0.25.10", *args, "--log-level=warning"], check=True, cwd=ROOT)
esbuild("site/app.js", "--bundle", "--format=esm", "--minify", "--target=es2020", "--alias:three=./site/vendor/three.module.js", f"--outfile={OUT}/read.js")
esbuild("site/engine.js", "--minify", "--target=es2020", f"--outfile={OUT}/engine.js")

h8 = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:10]
rename = {}
for name in ("read.js", "engine.js"):
    p = os.path.join(OUT, name); stem, ext = os.path.splitext(name); new = f"{stem}.{h8(p)}{ext}"; os.rename(p, os.path.join(OUT, new)); rename[name] = new
os.makedirs(os.path.join(OUT, "assets"))
for name in os.listdir(os.path.join(SRC, "assets")):
    p = os.path.join(SRC, "assets", name); stem, ext = os.path.splitext(name); new = f"{stem}.{h8(p)}{ext}"
    shutil.copy(p, os.path.join(OUT, "assets", new)); rename["assets/" + name] = "assets/" + new

for page in ("index.html", "read.html", "watch.html"):
    p = os.path.join(OUT, page); s = open(p, encoding="utf-8").read()
    s = re.sub(r'\s*<script type="importmap">.*?</script>', "", s, flags=re.S)
    s = s.replace('src="app.js"', f'src="{rename["read.js"]}"').replace('src="engine.js"', f'src="{rename["engine.js"]}"')
    for a, b in rename.items():
        if a.startswith("assets/"): s = s.replace(a, b)
    s = s.replace('content="assets/og.', 'content="https://living-books.mikacend.xyz/assets/og.')
    open(p, "w", encoding="utf-8").write(s)

open(os.path.join(OUT, "_headers"), "w").write("""/assets/*
  Cache-Control: public, max-age=31536000, immutable
/read.*.js
  Cache-Control: public, max-age=31536000, immutable
/engine.*.js
  Cache-Control: public, max-age=31536000, immutable
/data/*
  Cache-Control: public, max-age=600
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
""")
open(os.path.join(OUT, "404.html"), "w", encoding="utf-8").write("""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Page not found · Living Books</title><link rel="stylesheet" href="/style.css"></head><body><div class="wrap" style="padding-top:18vh"><p class="eyebrow">Living Books</p><h1>This page is not in the book.</h1><p style="margin:18px 0 26px;color:var(--soft)">The link may be old or mistyped.</p><a class="btn primary" href="/">Back to the library</a></div></body></html>""")
size = lambda p: os.path.getsize(os.path.join(OUT, p)) // 1024
print("built:", {k: v for k, v in rename.items()}, "| read.js KB", size(rename["read.js"]), "| engine.js KB", size(rename["engine.js"]))
print("total MB", round(sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(OUT) for f in fs) / 1e6, 2))
