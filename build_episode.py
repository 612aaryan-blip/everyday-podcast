#!/usr/bin/env python3
"""
Build one 'Teach Me One Thing' episode: text -> mp3 -> updated RSS feed.

Usage:
    python3 build_episode.py --title "Why X happens" --script-file today.txt

Writes:
    episodes/<date>.mp3      the audio
    episodes.json            manifest of all episodes
    feed.xml                 podcast RSS feed (regenerated from manifest)
"""
import argparse, json, os, sys
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
EPISODES_DIR = os.path.join(HERE, "episodes")
MANIFEST = os.path.join(HERE, "episodes.json")
FEED = os.path.join(HERE, "feed.xml")

# Public base URL where this folder is served. Overridden by PODCAST_BASE_URL env var.
BASE_URL = os.environ.get(
    "PODCAST_BASE_URL", "https://612aaryan-blip.github.io/everyday-podcast"
).rstrip("/")

SHOW_TITLE = "Teach Me One Thing"
SHOW_DESC = "A five-minute lesson on one interesting thing, every weekday morning."
SHOW_AUTHOR = "Aaryan"


def mp3_duration_seconds(path):
    """Duration via mutagen if present, else estimate from CBR bitrate."""
    try:
        from mutagen.mp3 import MP3
        return int(MP3(path).info.length)
    except Exception:
        # gTTS emits ~64kbps CBR mono
        return max(1, int(os.path.getsize(path) * 8 / 64000))


def hhmmss(total):
    h, rem = divmod(int(total), 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"


def build_audio(text, out_path):
    from gtts import gTTS
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    gTTS(text=text, lang="en", tld="com").save(out_path)
    return out_path


def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as f:
            return json.load(f)
    return []


def save_manifest(items):
    with open(MANIFEST, "w") as f:
        json.dump(items, f, indent=2)


def write_feed(items):
    now = format_datetime(datetime.now(timezone.utc))
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"'
        ' xmlns:content="http://purl.org/rss/1.0/modules/content/">',
        "<channel>",
        f"<title>{escape(SHOW_TITLE)}</title>",
        f"<description>{escape(SHOW_DESC)}</description>",
        f"<link>{escape(BASE_URL)}/</link>",
        "<language>en-us</language>",
        f"<lastBuildDate>{now}</lastBuildDate>",
        f"<itunes:author>{escape(SHOW_AUTHOR)}</itunes:author>",
        f"<itunes:summary>{escape(SHOW_DESC)}</itunes:summary>",
        "<itunes:explicit>false</itunes:explicit>",
        '<itunes:category text="Education"/>',
        f"<itunes:image href=\"{escape(BASE_URL)}/cover.jpg\"/>",
        f"<atom:link xmlns:atom=\"http://www.w3.org/2005/Atom\" href=\"{escape(BASE_URL)}/feed.xml\" rel=\"self\" type=\"application/rss+xml\"/>",
    ]
    for it in sorted(items, key=lambda x: x["pubdate_iso"], reverse=True):
        url = f"{BASE_URL}/episodes/{it['filename']}"
        pub = format_datetime(datetime.fromisoformat(it["pubdate_iso"]))
        parts += [
            "<item>",
            f"<title>{escape(it['title'])}</title>",
            f"<description>{escape(it.get('summary', it['title']))}</description>",
            f"<enclosure url=\"{escape(url)}\" length=\"{it['bytes']}\" type=\"audio/mpeg\"/>",
            f"<guid isPermaLink=\"false\">{escape(it['filename'])}</guid>",
            f"<pubDate>{pub}</pubDate>",
            f"<itunes:duration>{it['duration_hhmmss']}</itunes:duration>",
            f"<itunes:episode>{it['number']}</itunes:episode>",
            "</item>",
        ]
    parts += ["</channel>", "</rss>"]
    with open(FEED, "w") as f:
        f.write("\n".join(parts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--script-file", required=True)
    ap.add_argument("--summary", default="")
    args = ap.parse_args()

    with open(args.script_file) as f:
        text = f.read().strip()
    if not text:
        sys.exit("script file is empty")

    words = len(text.split())
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{today}.mp3"
    out_path = os.path.join(EPISODES_DIR, filename)

    build_audio(text, out_path)
    size = os.path.getsize(out_path)
    dur = mp3_duration_seconds(out_path)

    items = [i for i in load_manifest() if i["filename"] != filename]
    items.append({
        "number": len(items) + 1,
        "title": args.title,
        "summary": args.summary or args.title,
        "filename": filename,
        "bytes": size,
        "duration_seconds": dur,
        "duration_hhmmss": hhmmss(dur),
        "words": words,
        "pubdate_iso": datetime.now(timezone.utc).isoformat(),
    })
    save_manifest(items)
    write_feed(items)

    print(json.dumps({
        "file": out_path, "words": words, "duration": hhmmss(dur),
        "mb": round(size / 1e6, 2), "episodes": len(items), "base_url": BASE_URL
    }, indent=2))


if __name__ == "__main__":
    main()
