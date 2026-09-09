import os, glob, json, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("be", os.path.join(HERE, "build_episode.py"))
be = importlib.util.module_from_spec(spec); spec.loader.exec_module(be)

parts = sorted(glob.glob(os.path.join(HERE, ".parts", "p*.mp3")))
out = os.path.join(HERE, "episodes", "2026-09-09.mp3")
with open(out, "wb") as f:
    for p in parts:
        f.write(open(p, "rb").read())

text = open(os.path.join(HERE, "today.txt")).read().strip()
words = len(text.split())
size = os.path.getsize(out); dur = be.mp3_duration_seconds(out)
from datetime import datetime, timezone
items = [i for i in be.load_manifest() if i["filename"] != "2026-09-09.mp3"]
items.append({"number": len(items)+1, "title": "The lock picks itself",
  "summary": "A pin tumbler lock has one hundred thousand combinations on paper, but manufacturing tolerances make its pins give way one at a time, turning the secret into five easy questions.",
  "filename": "2026-09-09.mp3", "bytes": size, "duration_seconds": dur,
  "duration_hhmmss": be.hhmmss(dur), "words": words,
  "pubdate_iso": datetime.now(timezone.utc).isoformat()})
be.save_manifest(items); be.write_feed(items)
print(json.dumps({"file": out, "words": words, "duration": be.hhmmss(dur),
  "mb": round(size/1e6,2), "episodes": len(items), "base_url": be.BASE_URL}, indent=2))
