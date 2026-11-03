"""Checks every published page without an API key: loads each scene into the puppet engine in headless Chrome,
runs the same scene check Beam had to pass, and fails if any page has an issue or a drawing error.
Usage: python -X utf8 -I pipeline/verify.py [book-slug ...]"""
import json, os, sys
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "site", "data")
ENGINE = open(os.path.join(ROOT, "engine", "engine.js"), encoding="utf-8").read()
books = sys.argv[1:] or sorted(d for d in os.listdir(DATA) if os.path.isdir(os.path.join(DATA, d)))

failed = 0; total = 0
with sync_playwright() as p:
    try: br = p.chromium.launch(channel="chrome", headless=True)
    except Exception: br = p.chromium.launch(headless=True)  # bundled Chromium: `python -m playwright install chromium`
    pg = br.new_context(viewport={"width": 390, "height": 520}, offline=True).new_page()
    pg.set_content("<!doctype html><html><body></body></html>"); pg.add_script_tag(content=ENGINE)
    for slug in books:
        meta = json.load(open(os.path.join(DATA, slug, "book.json"), encoding="utf-8"))
        print(f"\n{meta['title']} ({len(meta['pages'])} pages)")
        for i in range(len(meta["pages"])):
            rec = json.load(open(os.path.join(DATA, slug, "pages", f"{i + 1:02d}.json"), encoding="utf-8"))
            res = pg.evaluate("s=>{LB.reset();LB.load(s);const c=LB.toolCheck({});return {issues:c.issues.map(i=>i.what),errors:LB.errors()}}", rec["scene"])
            ok = not res["issues"] and not res["errors"]; total += 1; failed += not ok
            print(f"  page {i + 1:2d}  {'pass' if ok else 'FAIL'}  {rec.get('title') or ''}" + ("" if ok else f"  {res['issues'] + res['errors']}"))
    br.close()
print(f"\n{total - failed} of {total} pages pass the scene check.")
sys.exit(1 if failed else 0)
