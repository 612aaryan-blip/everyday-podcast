#!/bin/bash
# Publishes the morning's episode to GitHub Pages.
# Run hourly by the com.aaryan.podcastpush launchd job.
# Lives outside ~/Downloads: TCC blocks LaunchAgents from protected folders.

cd "$HOME/Everyday podcast" || exit 1

# launchd runs with a minimal PATH; make sure git and gh are findable
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

LOG="$HOME/Everyday podcast/publish.log"
echo "=== $(date) ===" >> "$LOG"

if ! git add -A >> "$LOG" 2>&1; then
    echo "ERROR: git add failed (stale .git/index.lock?)" >> "$LOG"
    exit 1
fi

# Nothing new today? Exit quietly rather than erroring.
if git diff --cached --quiet; then
    echo "no changes to publish" >> "$LOG"
    exit 0
fi

git commit -m "Episode $(date +%F)" >> "$LOG" 2>&1
git push >> "$LOG" 2>&1
echo "published, exit $?" >> "$LOG"
