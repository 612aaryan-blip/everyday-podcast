#!/usr/bin/env python3
"""
Keep only the most recent N episodes.

Deletes old mp3s, trims episodes.json, and rewrites feed.xml so it never points at
a file that no longer exists. Exits without touching anything when there is nothing
to prune -- important, because rewriting feed.xml stamps a new lastBuildDate and
would otherwise create a pointless commit every hour.

Episode count is capped because the GitHub Pages deploy artifact contains every mp3
in the repo. It grows ~2.5 MB/day, and a bigger artifact means a slower deploy.

    PODCAST_KEEP=60 python3 prune_episodes.py
"""
import os
import sys

import build_episode as be

KEEP = int(os.environ.get("PODCAST_KEEP", "60"))

items = sorted(be.load_manifest(), key=lambda x: x["pubdate_iso"], reverse=True)
keep, drop = items[:KEEP], items[KEEP:]

if not drop:
    print(f"nothing to prune ({len(keep)} episodes, keeping {KEEP})")
    sys.exit(0)

removed = 0
for it in drop:
    path = os.path.join(be.EPISODES_DIR, it["filename"])
    if os.path.exists(path):
        os.remove(path)
        removed += 1

be.save_manifest(keep)
be.write_feed(keep)
print(f"pruned {len(drop)} episode(s), deleted {removed} file(s), kept {len(keep)}")
