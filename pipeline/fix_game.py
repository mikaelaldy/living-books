import os, json, re, sys, time, urllib.request
KEY = open(sys.argv[1], encoding="utf-8").read().strip(); NOTE = sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); path = os.path.join(ROOT, "books", "peter-rabbit", "game", "game.html")
html = open(path, encoding="utf-8").read(); rec = json.load(open(os.path.join(ROOT, "books", "peter-rabbit", "game", "record.json"), encoding="utf-8"))
msgs = [{"role": "user", "content": rec["prompt"]}, {"role": "assistant", "content": "```html\n" + html + "\n```", "reasoning_content": rec["reasoning"]},
        {"role": "user", "content": "REVIEW NOTES from the art director, who played the game in a phone-sized browser:\n" + NOTE + "\n\nReply with the COMPLETE updated HTML document in a single ```html code block and nothing else."}]
body = {"model": "Beam-1.0-501B-A23B", "reasoning_effort": "high", "temperature": 0.7, "max_completion_tokens": 48000, "messages": msgs}
t = time.time()
r = urllib.request.urlopen(urllib.request.Request("https://api.reflection.ai/openai/v1/chat/completions", data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}), timeout=590)
d = json.load(r); c = d["choices"][0]; s = c["message"].get("content") or ""; m = re.search(r"```html\s*(.*?)```", s, re.S); h = m.group(1) if m else s
open(path, "w", encoding="utf-8").write(h)
rec.setdefault("rounds", []).append({"note": NOTE, "usage": d["usage"], "seconds": round(time.time() - t, 1), "reasoning": c["message"].get("reasoning_content")}); json.dump(rec, open(os.path.join(ROOT, "books", "peter-rabbit", "game", "record.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("seconds", round(time.time() - t), "finish", c.get("finish_reason"), "out", d["usage"]["completion_tokens"], "KB", round(len(h) / 1024, 1))
