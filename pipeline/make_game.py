"""Beam writes the Peter Rabbit mini-game in one call. Usage: python -X utf8 -I make_game.py <keyfile>"""
import os, json, re, sys, time, urllib.request
KEY = open(sys.argv[1], encoding="utf-8").read().strip()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bible = json.load(open(os.path.join(ROOT, "books", "peter-rabbit", "bible.json"), encoding="utf-8"))
PROMPT = f"""You are the game designer and programmer of Living Books, animated pop-up editions of classic children's books. Make the small reward game that follows the last page of The Tale of Peter Rabbit.

THE GAME, "Home Before Dark": Peter has squeezed back under the gate of Mr. McGregor's garden and must run home across the garden. Seen from above, a 390 by 520 pixel garden with rows of cabbages, a cucumber frame, a watering can and a scarecrow. Peter starts at the bottom, the gate is at the top left, and Mr. McGregor patrols and chases with his rake, getting slightly faster each time Peter picks up a leaf of parsley. Peter must grab 3 sprigs of parsley and reach the gate before McGregor catches him. Peter is slowed in the muddy puddles and hides behind cabbages (McGregor cannot see him while he is still inside a cabbage patch, and loses him for two seconds). Winning shows a gentle message tied to the book (he gets home and is put to bed with camomile tea), and losing is soft and kind: "Peter squeezes under the gate again. Try once more!" with a Try again button.

CONTROLS: touch or mouse: drag anywhere to steer Peter toward the finger; keyboard: arrow keys and WASD. It must be playable on a phone with one thumb.

LOOK: cut-paper style: flat filled shapes with soft drop shadows, no outlines, warm afternoon colours from this palette: {json.dumps(bible['palette'])}. Peter is a small tawny rabbit with a blue jacket and brass buttons, seen from above; McGregor wears a straw hat and brown waistcoat. Keep everything drawn in code with Canvas 2D. A large readable title screen and a "Start" button. Include a small sound-free design: no audio at all. Respect prefers-reduced-motion by removing screen shake.

TECHNICAL: reply with ONE complete self-contained HTML document in a single ```html code block and nothing else. No external files, no network, no libraries, no text in image files. The canvas is exactly 390 by 520 CSS pixels, placed at the top-left, scaled with CSS to fit the window while keeping its aspect ratio (use width: min(100vw, 75vh)) and centered, with the page background #f4eadb. Use requestAnimationFrame with a time-step so speed is independent of frame rate. Expose window.livingGame = {{ state() {{ return {{ phase, sprigs, caught }} }}, start() }} where phase is one of 'title', 'playing', 'won', 'lost'. Make the game robust: never throw, clamp positions to the garden, and keep every number finite."""
body = {"model": "Beam-1.0-501B-A23B", "reasoning_effort": "high", "temperature": 0.7, "max_completion_tokens": 48000, "messages": [{"role": "user", "content": PROMPT}]}
t = time.time()
r = urllib.request.urlopen(urllib.request.Request("https://api.reflection.ai/openai/v1/chat/completions", data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}), timeout=590)
d = json.load(r); c = d["choices"][0]; s = c["message"].get("content") or ""; u = d["usage"]
m = re.search(r"```html\s*(.*?)```", s, re.S); h = m.group(1) if m else s
open(os.path.join(ROOT, "books", "peter-rabbit", "game", "game.html"), "w", encoding="utf-8").write(h)
json.dump({"prompt": PROMPT, "reasoning": c["message"].get("reasoning_content"), "usage": u, "finish": c.get("finish_reason"), "seconds": round(time.time() - t, 1)}, open(os.path.join(ROOT, "books", "peter-rabbit", "game", "record.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("seconds", round(time.time() - t), "finish", c.get("finish_reason"), "out", u["completion_tokens"], "html KB", round(len(h) / 1024, 1))
