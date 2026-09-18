import os, glob, json, importlib.util
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("be", os.path.join(HERE, "build_episode.py"))
be = importlib.util.module_from_spec(spec); spec.loader.exec_module(be)

DATE = "2026-09-18"
FN = DATE + ".mp3"
TITLE = "The jumper who goes under the bar"
SUMMARY = ("A high jumper's center of mass passes below the bar, and the technique "
           "that exploits it only became possible when foam landing pits "
           "replaced sand.")

parts = sorted(glob.glob(os.path.join(HERE, ".parts-20260918", "p*.mp3")))
out = os.path.join(HERE, "episodes", FN)
with open(out, "wb") as f:
    for p in parts:
        f.write(open(p, "rb").read())

text = open(os.path.join(HERE, "today.txt")).read().strip()
words = len(text.split())
size = os.path.getsize(out)
dur = be.mp3_duration_seconds(out)

items = [i for i in be.load_manifest() if i["filename"] != FN]
items.append({"number": len(items)+1, "title": TITLE, "summary": SUMMARY,
    "filename": FN, "bytes": size, "duration_seconds": dur,
    "duration_hhmmss": be.hhmmss(dur), "words": words,
    "pubdate_iso": datetime.now(timezone.utc).isoformat()})
be.save_manifest(items); be.write_feed(items)
print(json.dumps({"file": out, "parts": len(parts), "words": words,
    "duration": be.hhmmss(dur), "seconds": dur, "mb": round(size/1e6, 2),
    "episodes": len(items), "base_url": be.BASE_URL}, indent=2))

