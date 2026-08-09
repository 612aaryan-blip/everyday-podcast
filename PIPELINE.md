# Daily audio pipeline — what we learned building this

Everything worth knowing about generating a short audio episode every day and getting it
onto a phone's podcast app. Written after building "Teach Me One Thing" and debugging its
first real production failure on 2026-08-06.

This is the reference doc. `README.md` is the setup guide; this is the *why*.

> This folder is a public GitHub repo, so this file gets published too. Keep credentials,
> tokens, and anything private out of it.

---

## 1. The shape of the system

Five stages. The interesting failures happen between them, not inside them.

```
  script ──▶ audio ──▶ manifest ──▶ feed ──▶ hosting ──▶ app
 today.txt   *.mp3   episodes.json feed.xml  GH Pages   phone
 └─── scheduled agent task ──────┘ └──── launchd on the Mac ────┘
```

**The split matters.** Generation runs as a scheduled agent task in a sandbox; publishing
runs as a launchd job on the Mac. They are separate because the sandbox can't hold git
credentials — deliberately. The agent writes files into a mounted folder; the Mac-side job
is the only thing that touches the network with your identity.

Consequence: the generator cannot confirm the episode reached the phone. Whatever verifies
publication has to live on the Mac side.

### Files and their roles

| File | Role |
|---|---|
| `today.txt` | Latest script. Overwritten daily, gitignored. |
| `episodes/<date>.mp3` | The audio. Filename is the primary key throughout. |
| `episodes.json` | **Source of truth.** Manifest of every episode. |
| `feed.xml` | *Derived* from the manifest. Never hand-edit. |
| `build_episode.py` | script → mp3 → manifest → feed |
| `prune_episodes.py` | Caps episode count, rewrites manifest + feed |
| `publish.sh` | Commit, push, **and verify it went live** |
| `com.aaryan.podcastpush.plist` | launchd job, hourly |

`episodes.json` is the source of truth and `feed.xml` is generated from it. Anything that
needs to know "what is the newest episode" must read the manifest. See lesson 3.

---

## 2. The lessons that cost something

### 1. Pushing is not publishing

The failure that started all this: `git push` succeeded, the script logged
`published, exit 0`, and the episode did not exist as far as the phone was concerned. The
GitHub Pages *deploy* job had timed out afterwards. The commit was on `main`. The repo was
perfect. The feed was a day stale for nine hours and nothing anywhere said so.

**Verify at the public URL, not at the last step you control.** The only question that
matters is "can a stranger fetch this file over HTTPS right now," and the only way to
answer it is to fetch it.

```bash
curl -fsSL "${FEED_URL}?cb=$(date +%s)" | grep -q "$EXPECTED"
```

The `?cb=` cache-buster is not optional — without it you may be reading a CDN copy and
confirming your own stale data.

### 2. "Nothing to do" and "stuck" look identical from the inside

The hourly job's most common path is *no changes to publish*. That is also exactly what a
stuck deploy looks like: local repo clean, remote up to date, nothing to commit.

So the no-op path must check external state before exiting quietly. That one change turns
a passive script into a self-healing one — a failed deploy now gets retried within the
hour, unattended, with no human noticing anything went wrong.

**If your idle path and your broken path are indistinguishable, your idle path is a bug.**

### 3. Derive expected state from the source of truth, not a convenient proxy

The verifier originally computed "newest episode" with `ls episodes/*.mp3 | tail -1`.
Reasonable, wrong. The feed is generated from `episodes.json`. If a build ever crashed
between writing the audio and saving the manifest, there'd be an mp3 on disk that is not
in the feed and never will be — and the script would wait, retrigger, and alert forever
over a file that was never supposed to be published.

Read from the manifest. A proxy that is *usually* equal to the real thing fails exactly
when you most need it to be right.

### 4. Fail fast locally, wait patiently remotely

Spending ten minutes polling a CDN is correct when the problem is remote. It's a waste
when the problem is on disk. Check the cheap local invariants first and exit immediately:

- `episodes.json` missing or empty
- `feed.xml` doesn't reference the newest manifest entry
- manifest entry whose mp3 is missing from disk

Each of these means the build didn't finish cleanly. No amount of waiting fixes them.

### 5. Silence is not success

The original script had no way to report a problem it didn't know it had. Now: `ERROR`
lines in `publish.log` plus a macOS notification via `osascript`. Notifications need
permission for the launchd process, so **the log is the authoritative signal** — the
notification is a courtesy.

### 6. Your uptime is your dependencies' uptime

The deploy timeout coincided with a GitHub-wide Actions and Pages incident. Roughly an
hour of debugging preceded anyone checking githubstatus.com.

**Check the provider's status page early.** It's the cheapest possible diagnostic and it
reframes the whole investigation. Free hosting means accepting someone else's incident
schedule; the mitigation isn't avoiding it, it's degrading loudly instead of silently.

### 7. Retry mechanisms should need no extra credentials

To retrigger a GitHub Pages deploy without the `gh` CLI, an API token, or any new auth:

```bash
git commit --allow-empty -m "retrigger pages deploy" && git push
```

Any push to the Pages source branch rebuilds and redeploys. The cheapest recovery lever is
usually one you already have.

---

## 3. Platform gotchas

### launchd (macOS)

- **Minimal PATH.** launchd does not source your shell profile. Set PATH explicitly:
  `export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"`
- **Invoke through `/bin/bash script.sh`**, not the script directly. A missing exec bit
  otherwise kills the job silently. This bit us on 2026-08-04.
- **Capture output.** Set `StandardOutPath` and `StandardErrorPath` or launchd's own errors
  go nowhere. This is how the 08-04 failure stayed invisible.
- **TCC-protected folders.** LaunchAgents are blocked from `~/Downloads`, `~/Desktop`, and
  `~/Documents`. Keep the script somewhere unprotected.
- **`&&` breaks plists.** `&` is reserved in XML, so a plist with `&&` inline fails to
  parse. Put the logic in a `.sh` and have the plist call that. Sidesteps quoting entirely.
- **`StartInterval` beats `StartCalendarInterval`.** Hourly with a quiet no-op exit is
  strictly better than once daily: a late episode publishes within the hour instead of
  waiting a full day, and retries become free. Add `RunAtLoad` to catch up after the Mac
  has been off.
- **Nothing fires while the Mac is asleep.** This is the single biggest cause of a missing
  episode, and it is not a bug in anything you wrote. launchd does not run jobs during
  sleep; it coalesces every missed `StartInterval` into one run on wake. The 2026-08-07
  gap is visible in `publish.log` as a 20-hour jump from 21:12 to 17:25 the next day. The
  Cowork scheduled task that *writes* the episode has the same constraint, and that is the
  worse half: a missed push self-heals within the hour, a missed build means there is no
  episode to push. Fix by making the Mac wake itself before the build:

  ```bash
  sudo pmset repeat wakeorpoweron MTWRFSU 07:15:00   # every day; verify with: pmset -g sched
  ```

  Day codes are `M T W R F S U`, with `R` for Thursday and `U` for Sunday. Wake an hour
  before the 08:02 build rather than ten minutes before, so the hourly publish timer
  restarts at 07:15 and its next tick at ~08:15 catches the finished episode. Waking at
  07:50 pushes that tick to 08:50 and the episode sits built-but-unpublished for most of
  an hour. Caveats: sleep, don't shut down — powering on from off stops at the FileVault
  login screen where no user agents run. Keep it on AC for reliable lid-closed wake. And
  the Claude desktop app has to be running, since it is what fires the build task.

### Sandboxes and mounted folders

- The agent's mount is **append-only** — it can create and overwrite but not delete.
- **Never run `git` from the sandbox against the mounted repo.** Git writes `index.lock`
  and removes it afterward; the removal fails, leaving a stale lock that breaks every
  later git command including the Mac-side `publish.sh`. Recovery:
  `rm -f ~/"Everyday podcast/.git/index.lock"`
- If `.git` gets badly wedged, `rm -rf .git && git init` on the Mac and re-push. Your
  actual files are never at risk; only git's bookkeeping is rebuilt.

### GitHub Pages

- **Public repo required** on the free plan. The feed is unlisted, not private. For a
  genuinely private feed use a paid podcast host (Transistor, Buzzsprout).
- **The deploy artifact is the whole repo**, so it grows with every episode. Ours hit
  ~9 MB at four episodes, growing ~2.5 MB/day. A bigger artifact is a slower, more
  timeout-prone deploy — hence `prune_episodes.py`.
- Limits: **1 GB per site**, **100 MB per file**.
- "Deploy from a branch" runs the built-in `pages-build-deployment` workflow. Healthy runs
  take 40s–1m20s. The failure was `build` green, `deploy` red at 10m 7s.
- Re-running a failed deploy needs no new commit: **Actions → the run → Re-run jobs**.

### gTTS

Free, no API key, no quota. Output is 64 kbps mono 24 kHz MP3.

Measured across four episodes:

| Words | Duration | Rate | Size |
|---|---|---|---|
| 766 | 5:18 | 144.5 wpm | 2.54 MB |
| 761 | 4:59 | 152.7 wpm | 2.40 MB |
| 772 | 5:01 | 153.9 wpm | 2.41 MB |
| 779 | 5:11 | 150.3 wpm | 2.50 MB |

**~150 wpm, ~0.5 MB per minute.** So 730–780 words lands reliably at 5:00–5:20. Budget
~2.5 MB/day of storage.

Accent via `tld` in `gTTS(...)`: `com`, `co.uk`, `com.au`, `co.in`.

### Writing for a synthetic voice

The script is heard, not read, and a TTS engine has no idea what you meant.

- **Spell out numbers.** "thirty eight microseconds", not "38 µs". Digits and symbols get
  read awkwardly or skipped.
- **No markdown, headings, bullets, or parentheses.** They become pauses in the wrong
  places or get vocalized.
- Short sentences. A sentence that needs re-reading on the page is fatal in audio.
- Structure that works: hook stating the surprising claim → correct mental model → the
  number or twist that lands it → why it matters → short sign-off.
- Count the words before building. It's the only lever on duration.

### RSS for podcast apps

Required per `<item>`: `<enclosure url= length= type=>`, `<guid>`, `<pubDate>` in RFC 2822
(`email.utils.format_datetime` gets this right). Channel needs `<itunes:image>`,
`<itunes:category>`, `<itunes:explicit>`, and an `<atom:link rel="self">`.

- **`length` must be the real byte count.** Some clients use it for seek and progress.
- Use a **stable `guid`** (we use the filename). Change it and clients re-download.
- Sort items newest-first by `pubDate`.
- A `pubDate` in the future can hide an episode in some clients.

### Podcast app refresh behaviour

Shows added by URL are **not in Apple's directory**, so they get no crawler-driven push.
The app polls on its own lazy schedule — hours is normal.

**Pull down to refresh on the show page** forces it. When an episode is missing, this is
the *last* thing to suspect, not the first. Confirm the live feed first (see below); the
app is usually telling the truth.

---

## 4. Debugging runbook

Work down the chain. Each step tells you which half of the problem you're in.

1. **Did it build?** `ls -la episodes/` and check `episodes.json`. No mp3 → the generator
   failed.
2. **Is it in the repo?** `git log --oneline -3` for today's `Episode <date>` commit.
   Missing → build or push failed; read `publish.log`.
3. **Did the push actually land?** `git ls-remote origin main` and compare to
   `git rev-parse main`. This hits the server rather than a cached ref.
4. **Is it being served?**
   `curl -s "$FEED_URL" | grep <date>` — empty means repo fine, deploy didn't land.
5. **Did the deploy fail?** Actions tab → latest `pages-build-deployment`. `build` green +
   `deploy` red is the 2026-08-06 signature. Re-run jobs, or wait for the hourly retrigger.
6. **Is the provider down?** githubstatus.com. Do this by step 2 if anything looks strange.
7. **Only now suspect the app.** Live feed has it but the phone doesn't → pull to refresh.

**Nothing below step 4 is worth investigating until step 4 passes.** The single most useful
habit: never debug the client until you've confirmed what the server is actually serving.

---

## 5. If you rebuild this somewhere else

The generic pattern, independent of this show:

1. Generate content into a **manifest** (JSON), not directly into the output format.
2. Render the distribution format (**RSS**) from the manifest, always in full, never
   incrementally. Regeneration is idempotent; patching is not.
3. Publish by pushing to static hosting.
4. **Verify by fetching the public URL**, cache-busted.
5. On failure: retrigger once with a mechanism needing no extra credentials, then alert.
6. Run the whole thing **hourly with a quiet no-op**, not daily — the retry loop comes free
   and the idle run doubles as a health check.
7. Cap total size so the deploy stays fast.

Step 4 is the one everybody skips.

---

## 6. Later: a news-driven version

Not building this now — notes for when we do.

**What doesn't change:** everything from the manifest onward. `build_episode.py`,
`prune_episodes.py`, `publish.sh`, the plist, the feed, the hosting, the verification.
The publishing layer is content-agnostic. Only script generation changes.

**What does change, and where the new failure modes are:**

- **Freshness becomes correctness.** Today's constraint is "avoid anything requiring
  current news," which makes the generator dependency-free. Remove it and the generator
  now depends on live sources, which can be down, rate-limited, or paywalled. Needs a
  defined behaviour for "no sources reachable" — probably skip the day rather than publish
  something wrong. A missing episode is much better than a confidently incorrect one.
- **Deduplication gets harder.** Uniqueness is currently checked against past episode
  *titles* in `episodes.json` — fine for evergreen topics. News needs story-level identity
  (canonical URL or a source ID) tracked across days, because the same story legitimately
  recurs with new developments. Add a `sources` array to each manifest entry.
- **Multiple items per episode.** Probably several stories rather than one idea, which
  changes the script structure and likely the target length. Re-measure against ~150 wpm.
- **Attribution.** Say the source out loud. Add source links to the `<description>` — most
  apps render basic HTML in show notes.
- **Correction path.** Evergreen explainers age well; news doesn't. Decide whether a wrong
  episode gets deleted, re-cut, or left with a follow-up. Note that changing a `guid`
  forces clients to re-download.
- **Timing.** A news episode is worth much less late. The current "publishes within the
  hour" tolerance may be too loose; consider tightening the launchd interval and the alert
  threshold.
- **Keep both shows separate.** Different feeds, different repos. One show being broken
  shouldn't take the other down, and listeners may want one and not the other.

The verification and self-healing work carries over unchanged — and matters more, since a
stale news feed is worse than a stale explainer feed.

---

*Last updated 2026-08-09, after tracing missing episodes to Mac sleep.*
