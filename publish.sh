#!/bin/bash
# Publishes the morning's episode to GitHub Pages.
# Run by the com.aaryan.podcastpush launchd job at 8:15 daily.

cd "$HOME/Downloads/Everyday podcast" || exit 1

# launchd runs with a minimal PATH; make sure git and gh are findable
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

LOG="$HOME/Downloads/Everyday podcast/publish.log"
echo "=== $(date) ===" >> "$LOG"

git add -A >> "$LOG" 2>&1

# Nothing new today? Exit quietly rather than erroring.
if git diff --cached --quiet; then
    echo "no changes to publish" >> "$LOG"
    exit 0
fi

git commit -m "Episode $(date +%F)" >> "$LOG" 2>&1
git push >> "$LOG" 2>&1
echo "published, exit $?" >> "$LOG"
