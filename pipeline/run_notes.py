"""Runs page review notes four at a time. Usage: python -X utf8 -I run_notes.py <notes.json>"""
import json, os, subprocess, sys, time
notes = json.load(open(sys.argv[1], encoding="utf-8")); q = list(notes.items()); live = []
logs = os.path.join(os.path.dirname(sys.argv[1]), "logs")
while q or live:
    while q and len(live) < 4:
        n, note = q.pop(0); f = open(os.path.join(logs, f"page{int(n):02d}.log"), "a", encoding="utf-8")
        live.append((n, subprocess.Popen([sys.executable, "-X", "utf8", "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "produce.py"), "page", n, note], stdout=f, stderr=subprocess.STDOUT), time.time()))
    time.sleep(3)
    for it in list(live):
        n, pr, t = it
        if pr.poll() is not None:
            print("page", n, "exit", pr.returncode, round(time.time() - t), "s", flush=True); live.remove(it)
        elif time.time() - t > 1500:
            pr.kill(); print("page", n, "killed", flush=True); live.remove(it)
