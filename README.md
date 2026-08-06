# Teach Me One Thing — private podcast

A 5-minute lesson, generated automatically every morning at 8:00.

Episode 1 is already built. Everything works except the last mile: the audio needs a
public HTTPS address before a phone can play it. That's the one-time setup below.

---

## What runs automatically

Daily at 8:00 the scheduled task `teach-me-one-thing`:

1. Reads `episodes.json` so it never repeats a topic
2. Writes a ~750-word script to `today.txt`
3. Renders `episodes/YYYY-MM-DD.mp3` with gTTS (free, no quota, no API key)
4. Regenerates `feed.xml`
5. Checks the duration landed between 4:30 and 5:45

Cost per episode: zero. Roughly 2.5 MB of audio per day.

---

## One-time setup: publishing

Podcast apps need an RSS feed at a stable public URL. GitHub Pages is free and works well.

### 1. Create the repo

On github.com, create a new **public** repository called `everyday-podcast`.
Leave it empty — no README, no .gitignore.

> Note: GitHub Pages requires a public repo on the free plan. The feed is *unlisted*
> rather than truly private — nobody can find it without the URL, but it isn't
> access-controlled. If you want real privacy, use a paid podcast host
> (Transistor and Buzzsprout both offer genuine private feeds) and skip to step 5.

### 2. Push this folder

In Terminal:

```bash
cd ~/Downloads/Everyday\ podcast
rm -rf .git
git init -b main
git add -A
git commit -m "Teach Me One Thing: episode 1"
git remote add origin https://github.com/612aaryan-blip/everyday-podcast.git
git push -u origin main
```

Git will ask you to authenticate. Handle that yourself — I deliberately don't touch
tokens or passwords, so this step stays entirely on your machine.

> **Why `rm -rf .git` first:** the repo was originally initialised from a sandbox that
> mounts this folder append-only — it can create files but not delete them. Git writes
> lock files during a commit and removes them afterward; those removals failed, leaving
> stale `index.lock`, `HEAD.lock` and `maintenance.lock` files that make every later git
> command fail with "cannot lock ref 'HEAD'". Rebuilding `.git` from scratch on your Mac
> clears all of it at once. Your actual files — episodes, feed, scripts — are never
> touched; only git's internal bookkeeping is recreated.

### 3. Turn on Pages

Repo → **Settings** → **Pages** → Source: `Deploy from a branch`, Branch: `main`, folder `/ (root)` → Save.

After a minute your feed is live at:

```
https://612aaryan-blip.github.io/everyday-podcast/feed.xml
```

### 4. Point the feed at that URL

Already done — the URL is baked into `build_episode.py` and `feed.xml`, so you can skip
this. Kept here only in case you ever move the feed:

```bash
cd ~/Downloads/Everyday\ podcast
echo 'export PODCAST_BASE_URL="https://612aaryan-blip.github.io/everyday-podcast"' >> ~/.zshrc
source ~/.zshrc
python3 build_episode.py --title "Why your GPS needs Einstein" \
  --summary "GPS satellite clocks are built deliberately wrong so relativity makes them right." \
  --script-file today.txt
git add -A && git commit -m "set base url" && git push
```

Or just tell me the URL and I'll set it for you.

### 5. Subscribe on your phone

- **Apple Podcasts:** Library → top-right `...` → Add a Show by URL → paste the feed URL
- **Overcast:** `+` → Add URL
- **Pocket Casts:** Profile → Add Podcast → Add by URL

Turn **on** new-episode notifications for the show. That gives you exactly the loop you
wanted: push notification at 8am → tap → press play → 5 minutes.

---

## Getting each morning's episode pushed up

The daily task writes the new mp3 into this folder, but it can't push to GitHub for you
(that would mean handling your credentials). Add a tiny job on your Mac that publishes
a few minutes after the episode is built:

`publish.sh` in this folder does the commit-and-push. Register it with launchd to run at 8:15:

```bash
cat > ~/Library/LaunchAgents/com.aaryan.podcastpush.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.aaryan.podcastpush</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/aaryan/Downloads/Everyday podcast/publish.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>8</integer>
    <key>Minute</key><integer>15</integer>
  </dict>
</dict>
</plist>
PLIST
launchctl load ~/Library/LaunchAgents/com.aaryan.podcastpush.plist
```

The logic lives in `publish.sh` rather than inline in the plist because `&&` contains `&`,
which is a reserved character in XML and makes the plist fail to parse.

`publish.sh` writes to `publish.log` (gitignored) so you can see what happened on any given
morning. It exits quietly when there's nothing new, and sets an explicit PATH because
launchd runs with a minimal environment that wouldn't otherwise find `git`.

### Publishing is verified, not assumed

**Pushing is not publishing.** On 2026-08-06 the push succeeded and the log said
`published, exit 0`, but the GitHub Pages *deploy* job afterwards died with
`Timeout reached, aborting!`. The commit was on `main`, the episode was in the repo, and
the phone served a day-old feed for nine hours with nothing anywhere reporting a problem.

So `publish.sh` now confirms the episode is actually being served before it calls the job
done. After pushing it polls the live `feed.xml` (cache-busted, so it reads Pages rather
than a stale CDN copy) for up to ten minutes, looking for today's filename. If it never
shows up, it pushes an empty commit to retrigger the Pages deploy and polls again. If
*that* fails it writes a loud `ERROR` to the log and fires a macOS notification.

The important part is what happens on an ordinary hourly run with nothing new to publish.
It doesn't just exit — it checks the live feed first. A stuck deploy therefore gets
noticed and retried within the hour, unattended, which is exactly the case that went
undetected before.

It also fails fast rather than waiting ten minutes when the problem is local: an empty or
missing `episodes.json`, a `feed.xml` that doesn't reference the newest episode, or a
manifest entry whose mp3 is missing from disk. The expected filename is read from
`episodes.json`, not from `ls episodes/`, because the feed is generated from the manifest —
a stray mp3 that never made it into the manifest would otherwise be something the script
waits forever to see go live.

### Keeping the deploy artifact small

The Pages deploy artifact contains every mp3 in the repo and grows ~2.5 MB/day. A bigger
artifact means a slower deploy and more timeout risk, so `publish.sh` runs
`prune_episodes.py` first, which caps the feed at the most recent `KEEP_EPISODES` (default
60, about 150 MB). It deletes the old mp3s, trims `episodes.json`, and rewrites `feed.xml`
so it never points at a file that no longer exists. It exits without touching anything when
there's nothing to prune — rewriting `feed.xml` stamps a fresh `lastBuildDate` and would
otherwise create a pointless commit every hour.

Lower the cap by editing `KEEP_EPISODES` at the top of `publish.sh`.

### When the episode isn't on your phone

Work down the chain — each step tells you which half of the problem to look at:

1. **Is it in the repo?** `git log --oneline -3` should show today's `Episode <date>` commit.
   If not, the build or the push failed; check `publish.log`.
2. **Is Pages serving it?**
   `curl -s https://612aaryan-blip.github.io/everyday-podcast/feed.xml | grep <date>`
   Empty output means the repo is fine but the deploy didn't land.
3. **Did the deploy fail?** github.com/612aaryan-blip/everyday-podcast/actions — look at
   the latest `pages-build-deployment`. `build` green + `deploy` red is the 2026-08-06
   failure. Fix: **Re-run jobs**, or just wait for the next hourly `publish.sh`, which now
   retriggers on its own.
4. **Only then suspect the app.** If the live feed has the episode but your phone doesn't,
   it's client-side caching — pull down to refresh on the show page. Shows added by URL
   aren't in Apple's index, so they refresh on the app's own lazy schedule.

Alternative if you'd rather not touch launchd: run `bash ~/Downloads/Everyday\ podcast/publish.sh`
whenever you want to publish, or open GitHub Desktop and hit "Push origin".

---

## Housekeeping

Episodes accumulate at ~75 MB/month. To keep the repo small, prune old ones every so often:

```bash
cd ~/Downloads/Everyday\ podcast
ls episodes/*.mp3 | head -n -60 | xargs rm -f   # keep the most recent 60
```

`episodes.json` and `feed.xml` are regenerated on each build, so stale entries clear
themselves once the files are gone.

## Changing the show

- **Different time:** ask me to reschedule `teach-me-one-thing`
- **Weekdays only:** ask me to switch the cron to `0 8 * * 1-5`
- **Different length:** the word count in the task prompt drives it — ~145 words per minute
- **Different voice:** gTTS accents via `tld` (`co.uk`, `com.au`, `co.in`) in `build_episode.py`;
  for a much better voice, ElevenLabs works but a 5-min daily episode needs a paid plan
