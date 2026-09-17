import os, glob, json, importlib.util
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("be", os.path.join(HERE, "build_episode.py"))
be = importlib.util.module_from_spec(spec); spec.loader.exec_module(be)

DATE = "2026-09-17"
FN = DATE + ".mp3"
TITLE = "The cat that turns without spinning"
SUMMARY = ("A falling cat rights itself with zero angular momentum the whole way down, "
           "and the shape-changing trick it uses is the same one astronauts and "
           "fuel-free satellites rely on.")

parts = sorted(glob.glob(os.path.join(HERE, ".parts-20260917", "p*.mp3")))
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
