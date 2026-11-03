"""Turns a produced book into site data: pages, book.json, replay.json (from the real recorded calls) and scorecard.json.
Usage: python -X utf8 -I export.py <slug> [title] [author]"""
import glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = sys.argv[1]; TITLE = sys.argv[2] if len(sys.argv) > 2 else SLUG; AUTHOR = sys.argv[3] if len(sys.argv) > 3 else ""
BOOK = os.path.join(ROOT, "books", SLUG); OUT = os.path.join(ROOT, "site", "data", SLUG)
os.makedirs(os.path.join(OUT, "pages"), exist_ok=True)
ld = lambda p: json.load(open(p, encoding="utf-8"))
rows = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []
cut = lambda s, n: (s or "").strip().replace("\n", " ")[:n] + ("…" if s and len(s.strip()) > n else "")

# Review notes written by the art reviewer. Older books kept them in notes files; new runs log them.
NOTES = []
for f in ("notes.json", "notes2.json"):
    p = os.path.join(BOOK, f)
    if os.path.exists(p): NOTES.append(ld(p))


def summarise(r):
    n, a, res = r["name"], r.get("args") or {}, r.get("result") or {}
    if n == "define_character":
        bad = sum(len(v.get("joint_problems", [])) for v in (res.get("poses") or {}).values() if isinstance(v, dict))
        return {"tool": n, "what": f"character {a.get('id')}", "detail": f"{res.get('bones', '?')} bones, {len(res.get('poses') or {})} poses checked, {bad} joint problems"}
    if n == "paint_scene":
        st = res.get("stats") or {}
        return {"tool": n, "what": f"{len(a.get('layers') or [])} layers painted", "detail": ", ".join(l.get("name", "") for l in (a.get("layers") or [])[:8]) + (f"; flat colour {st.get('largest_flat_colour_pct')}%, detail per band {st.get('edge_detail_pct_top_to_bottom')}" if st else "")}
    if n == "stage_scene":
        errs = res.get("errors") or []
        return {"tool": n, "what": f"{len(a.get('beats') or [])} beats over {a.get('duration')} s", "detail": ("errors: " + "; ".join(errs[:3])) if errs else "timeline accepted"}
    if n == "check_scene":
        iss = res.get("issues") or []
        return {"tool": n, "what": f"{res.get('issue_count', len(iss))} issues found", "detail": "; ".join(i.get("what", "") for i in iss[:3]) or "clean"}
    if n == "finish_scene":
        ok = res.get("ok")
        return {"tool": n, "what": ("accepted: " if ok else "refused: ") + (a.get("title") or ""), "detail": cut(a.get("director_note"), 240) if ok else "; ".join(i.get("what", "") for i in (res.get("issues") or [])[:3])}
    return {"tool": n, "what": n, "detail": ""}


def runs_of(path):
    rs, cur, last = [], None, None
    for r in rows(path):
        if cur is None or (last is not None and r["at"] - last > 400):
            cur = {"note": None, "steps": [], "calls": 0, "seconds": 0.0, "out": 0}; rs.append(cur)
        last = r["at"]
        if r["kind"] == "note": cur["note"] = r.get("note")
        elif r["kind"] == "usage": cur["calls"] += 1; cur["seconds"] += r["seconds"]; cur["out"] += r["completion"]
        elif r["kind"] == "assistant" and r.get("reasoning"): cur["steps"].append({"think": cut(r["reasoning"], 360)})
        elif r["kind"] == "tool": cur["steps"].append(summarise(r))
    for c in rs: c["seconds"] = round(c["seconds"])
    return rs


bible = ld(os.path.join(BOOK, "bible.json")); rd = rows(os.path.join(BOOK, "logs", "read.jsonl"))
read = {"seconds": round(sum(r["seconds"] for r in rd if r["kind"] == "usage")), "out": sum(r["completion"] for r in rd if r["kind"] == "usage"), "think": cut(next((r.get("reasoning") for r in rd if r["kind"] == "assistant"), ""), 900), "book_chars": sum(len(p["text"]) for p in bible["pages"])}
cast_runs = runs_of(os.path.join(BOOK, "logs", "cast.jsonl")); pages = {}; npages = 0; passed = 0; tot = {"calls": 0, "seconds": 0, "out": 0, "fix_rounds": 0}
for p in sorted(glob.glob(os.path.join(BOOK, "pages", "[0-9][0-9].json"))):
    r = ld(p); n = r["page"]; npages += 1; passed += 1 if r["gate"]["passed"] else 0
    json.dump({k: r[k] for k in ("page", "text", "feeling", "title", "director_note", "gate", "scene")}, open(os.path.join(OUT, "pages", os.path.basename(p)), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    rr = runs_of(os.path.join(BOOK, "logs", f"page{n:02d}.jsonl"))
    for i, run in enumerate(rr):
        if i and not run["note"]:
            for nf in NOTES:
                if str(n) in nf: run["note"] = nf[str(n)]; NOTES.remove(nf); break
    checks = sum(1 for run in rr for s in run["steps"] if s.get("tool") == "check_scene")
    pages[n] = {"runs": rr, "checks": checks, "final_gate": r["gate"]}
    for run in rr: tot["calls"] += run["calls"]; tot["seconds"] += run["seconds"]; tot["out"] += run["out"]
    tot["fix_rounds"] += max(0, checks - 1)
tot["calls"] += read and 1; tot["out"] += read["out"]
for run in cast_runs: tot["calls"] += run["calls"]; tot["seconds"] += run["seconds"]; tot["out"] += run["out"]
plan = [{k: x.get(k) for k in ("page", "feeling", "scene", "why", "set", "cast")} for x in bible["pages"]]
replay = {"title": TITLE, "read": read, "bible": {"world": bible["world"], "palette": bible["palette"], "arc": bible.get("emotional_arc"), "cast": [{k: c.get(k) for k in ("id", "name", "look", "personality_in_motion")} for c in bible["cast"]], "pages": plan}, "cast_runs": cast_runs, "pages": pages}
json.dump(replay, open(os.path.join(OUT, "replay.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
game = f"games/{SLUG}.html" if os.path.exists(os.path.join(ROOT, "site", "games", SLUG + ".html")) else None
json.dump({"title": TITLE, "author": AUTHOR, "pages": list(range(1, npages + 1)), "cover": 1, "game": game}, open(os.path.join(OUT, "book.json"), "w", encoding="utf-8"))
score = {"title": TITLE, "pages": npages, "pages_passed_gate": passed, "beam_calls": tot["calls"], "output_tokens": tot["out"], "minutes_in_beam_calls": round(tot["seconds"] / 60), "fix_rounds_after_first_check": tot["fix_rounds"], "characters": len(bible["cast"]), "note": "Counts describe Beam's own runs in this project. They do not rank Beam against other models."}
json.dump(score, open(os.path.join(OUT, "scorecard.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(score))
