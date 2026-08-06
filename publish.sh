#!/bin/bash
# Publishes the morning's episode to GitHub Pages -- and then VERIFIES it went live.
#
# Why the verification exists: on 2026-08-06 the push succeeded and this script logged
# "published, exit 0", but the GitHub Pages *deploy* job afterwards died with
# "Timeout reached, aborting!". The commit sat on main, the phone served a day-old
# feed, and nothing anywhere said so. Pushing is not publishing. So now we check.
#
# Run hourly by the com.aaryan.podcastpush launchd job.
# Lives outside ~/Downloads: TCC blocks LaunchAgents from protected folders.

set -uo pipefail

cd "$HOME/Everyday podcast" || exit 1

# launchd runs with a minimal PATH; make sure git and curl are findable
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

LOG="$HOME/Everyday podcast/publish.log"
FEED_URL="https://612aaryan-blip.github.io/everyday-podcast/feed.xml"
KEEP_EPISODES=60      # cap the Pages artifact; see prune_episodes.py
VERIFY_TIMEOUT=600    # seconds to wait for Pages to serve the new episode
POLL_EVERY=20

log()    { echo "$*" >> "$LOG"; }
notify() { osascript -e "display notification \"$1\" with title \"Teach Me One Thing\"" >/dev/null 2>&1; }

log "=== $(date) ==="

log "prune: $(PODCAST_KEEP=$KEEP_EPISODES python3 prune_episodes.py 2>&1)"

# The episode we expect to see served publicly. Read from the manifest, not from
# `ls episodes/`: the feed is generated from episodes.json, so a stray mp3 on disk
# that never made it into the manifest (build crashed between writing audio and
# saving the manifest) would otherwise be something we wait forever to see live.
EXPECTED=$(python3 -c "
import json, sys
try:
    items = json.load(open('episodes.json'))
except Exception:
    sys.exit(1)
if not items:
    sys.exit(1)
print(max(items, key=lambda x: x['pubdate_iso'])['filename'])
" 2>/dev/null)

if [ -z "$EXPECTED" ]; then
    log "ERROR: episodes.json is missing or empty - nothing to publish"
    notify "Publish failed: no episode manifest"
    exit 1
fi

# Fail fast if the build never wrote this episode into the feed, rather than
# burning ten minutes waiting for Pages to serve something that isn't there.
if ! grep -q "$EXPECTED" feed.xml 2>/dev/null; then
    log "ERROR: feed.xml does not reference $EXPECTED - the build did not finish cleanly"
    notify "Publish failed: feed.xml is missing today's episode"
    exit 1
fi
if [ ! -f "episodes/$EXPECTED" ]; then
    log "ERROR: episodes/$EXPECTED is in the manifest but missing from disk"
    notify "Publish failed: episode audio missing"
    exit 1
fi

# Read the live feed, cache-busted so we see Pages rather than a stale CDN copy.
live_is_current() {
    curl -fsSL --max-time 30 "${FEED_URL}?cb=$(date +%s)" 2>/dev/null | grep -q "$EXPECTED"
}

# Poll until Pages catches up. Returns 1 if it never does.
wait_for_live() {
    local waited=0
    while [ "$waited" -lt "$VERIFY_TIMEOUT" ]; do
        if live_is_current; then
            log "VERIFIED live: $EXPECTED (after ${waited}s)"
            return 0
        fi
        sleep "$POLL_EVERY"
        waited=$((waited + POLL_EVERY))
    done
    return 1
}

# An empty commit is enough to make Pages rebuild and redeploy.
retrigger_pages() {
    log "retriggering Pages deploy"
    git commit --allow-empty -m "retrigger pages deploy $(date +%F-%H%M)" >> "$LOG" 2>&1 \
        && git push >> "$LOG" 2>&1 \
        || log "ERROR: retrigger commit/push failed"
}

give_up() {
    log "ERROR: $EXPECTED is built and pushed but Pages will not serve it."
    log "       Check https://github.com/612aaryan-blip/everyday-podcast/actions"
    notify "Episode built but NOT live - check GitHub Pages"
    exit 1
}

if ! git add -A >> "$LOG" 2>&1; then
    log "ERROR: git add failed (stale .git/index.lock?)"
    notify "Publish failed: git add"
    exit 1
fi

if git diff --cached --quiet; then
    # Nothing new to commit. Usually that just means we're up to date -- but it is
    # also exactly what a stuck Pages deploy looks like from here, which is how the
    # 2026-08-06 failure stayed invisible for nine hours. So confirm against the live
    # feed before exiting quietly. This is what makes the hourly job self-healing:
    # a failed deploy now gets noticed and retried within the hour, unattended.
    if live_is_current; then
        log "no changes to publish (live feed confirmed current)"
        exit 0
    fi
    log "WARNING: nothing to commit, but live feed is missing $EXPECTED -- Pages is stale"
    retrigger_pages
    wait_for_live || give_up
    exit 0
fi

if ! git commit -m "Episode $(date +%F)" >> "$LOG" 2>&1; then
    log "ERROR: git commit failed"
    notify "Publish failed: git commit"
    exit 1
fi
if ! git push >> "$LOG" 2>&1; then
    log "ERROR: git push failed"
    notify "Publish failed: git push"
    exit 1
fi
log "pushed $(git rev-parse --short HEAD), waiting for Pages to serve $EXPECTED"

if wait_for_live; then
    exit 0
fi

log "WARNING: $EXPECTED not live after ${VERIFY_TIMEOUT}s"
retrigger_pages
wait_for_live || give_up
