#!/usr/bin/env python3
"""
BT TV auto-maintain watcher (free, local, no external API).

Runs via cron. Tracks the Plex BT TV library's item list:
  - NEW items  -> generate title + keyword summary, write to Plex.
  - REMOVED items (deleted or removed-from-library in Plex) -> just note them.
  - ANY change (add or remove) -> refresh ONLY the BT TV channel schedule.

Safety guard: if Plex returns 0 items or is unreachable, do NOTHING (prevents a
drive unmount / server hiccup from looking like "everything was deleted").

Config: bttv-watch.conf (same dir):
  PLEX_TOKEN=...
  PLEX_URL=http://localhost:32400
  BTTV_FOLDER=/media/plex/MyBook/BTTV   (kept for reference; not required now)
  PLEX_SECTION=4
  NTV_URL=http://localhost:19850
  BTTV_CHANNEL=user_59dff7fa-26ac-4703-8768-0056ae352f56
"""
import os, re, sys, time, json, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "bttv-watch.conf")
STATE = os.path.join(HERE, "bttv-watch.state")   # JSON: {ratingKey: filename} last seen in Plex

def load_conf():
    c = {}
    with open(CONF) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                c[k.strip()] = v.strip()
    return c

def clean_title(fname):
    t = re.sub(r"\.[A-Za-z0-9]+$", "", fname)
    t = t.replace("｜", "|").replace("：", ":")
    t = re.sub(r"\s+", " ", t).strip()
    return t

def summarize(title):
    low = title.lower()
    part = ""
    m = re.search(r"\bpart\s*(\d+)\b", low)
    if m: part = f" (Part {int(m.group(1))})"
    if any(w in low for w in ["fireplace","yule","sleep sounds","cozy"]):
        return f"A cozy Boston Terrier fireside scene — crackling warmth on a gentle, relaxing loop.{part}".strip()
    if "relaxing music" in low or ("relaxing" in low and "music" in low):
        return "Calming music paired with mellow Boston Terrier company — easy, soothing background viewing."
    if any(w in low for w in ["judging","champ show","champion","breed judging","melbourne royal","club of"]):
        return "Conformation judging and breed competition showcasing Boston Terriers at their finest."
    if any(w in low for w in ["grooming","bath","give a bath"]):
        return "Grooming and care — keeping the dapper Boston Terrier clean, trimmed, and looking sharp."
    if any(w in low for w in ["training","trainer","alpha","train"]):
        return "Boston Terrier training and behavior, from basics to teaching an eager young pup."
    if any(w in low for w in ["puppy","puppies","baby","babies"]):
        return "Adorable Boston Terrier puppy antics — clumsy, playful, and impossibly cute."
    if "service dog" in low or "service dogs" in low:
        return "A look at Boston Terriers as loyal service and companion dogs."
    if any(w in low for w in ["breed information","everything you need","characteristics","breed info","101","facts","facts and information","guide to","all about","dogs 101","breed profile"]):
        return "A complete Boston Terrier breed profile — history, temperament, traits, facts, and care."
    if any(w in low for w in ["history","gentleman","origin","pit fighter","became"]):
        return "The history and heritage of the Boston Terrier — the beloved 'American Gentleman' of dogs."
    if any(w in low for w in ["dangers","prevent","ugly truths","truths about","reasons","not for everyone","aren't for","arent for","aren\u2019t for","downside","downsides","cons of","pros & cons","pros and cons","pros/cons","should you get","should i get","before you get","before you buy","don't get","dont get","things to know","what to know","regret","challenges","hard truth"]):
        return "An honest look at the realities of Boston Terrier ownership — the pros, the cons, and what to weigh before bringing one home."
    if any(w in low for w in ["watercolor","paint","draw"]):
        return "An art tutorial capturing the Boston Terrier's unmistakable markings and charm."
    if any(w in low for w in ["chew","chews","chewing","destroy","destructive","trouble","trouble-making","troublemaker","naughty","mischief","mischievous","bad behavior","behaving badly","tearing","wrecking"]):
        return "The mischief files — a Boston Terrier's talent for chaos, chewing, and getting into everything it shouldn't."
    if any(w in low for w in ["funny","funniest","hilarious","hilariously","lol","laugh","comedy","compilation","best moments","cutest","cute moments","adorable moments","fails","goofy","tea party","playdate","count their treats","snacking","family love","life with","destroyed","try not to laugh"]):
        return "A laugh-out-loud collection of Boston Terrier antics — goofy, heartwarming, and impossibly funny moments from these little companions."
    base = re.sub(r"\s*\(part\s*\d+\)\s*$", "", title, flags=re.I).strip()
    return f"A Boston Terrier feature on BT TV: {base}.{part}".strip()

def plex(path, conf, params=None, method="GET"):
    q = dict(params or {}); q["X-Plex-Token"] = conf["PLEX_TOKEN"]
    url = f"{conf['PLEX_URL']}{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, method=method, headers={"Accept": "application/xml"})
    return urllib.request.urlopen(req, timeout=60).read()

def log(msg):
    print(f"[{time.strftime('%F %T')}] {msg}")

def main():
    conf = load_conf()
    section = conf["PLEX_SECTION"]

    # --- trigger a Plex scan first, so new files get indexed (auto-scan may be off) ---
    try:
        plex(f"/library/sections/{section}/refresh", conf)
        time.sleep(30)  # give Plex a moment to index new files before we read the list
    except Exception as e:
        log(f"Plex scan trigger failed ({e}); continuing with current index.")

    # --- read current Plex item list for the BT TV library ---
    try:
        raw = plex(f"/library/sections/{section}/all", conf)
        root = ET.fromstring(raw)
    except Exception as e:
        log(f"Plex query failed ({e}); doing nothing this run.")
        return

    current = {}   # ratingKey -> filename
    for v in root.iter("Video"):
        rk = v.get("ratingKey")
        part = v.find(".//Part")
        fname = os.path.basename(part.get("file")) if (part is not None and part.get("file")) else (v.get("title") or rk)
        if rk:
            current[rk] = fname

    # SAFETY GUARD: empty library almost always means a scan-in-progress or drive/token issue.
    if not current:
        log("Plex returned 0 items for BT TV library; safety guard — doing nothing.")
        return

    # --- load last-known state ---
    prev = {}
    if os.path.exists(STATE):
        try:
            prev = json.load(open(STATE))
        except Exception:
            prev = {}

    prev_keys = set(prev.keys())
    cur_keys = set(current.keys())
    added   = cur_keys - prev_keys
    removed = prev_keys - cur_keys

    # First-ever run (no state): seed silently, no describe/refresh, so we don't
    # re-describe the existing library or false-trigger.
    if not prev:
        json.dump(current, open(STATE, "w"))
        log(f"Initialized state with {len(current)} existing items (no action).")
        return

    changed = False

    # --- describe newly added items ---
    for rk in sorted(added):
        fname = current[rk]
        title = clean_title(fname)
        summary = summarize(title)
        try:
            plex(f"/library/sections/{section}/all", conf, {
                "type": "1", "id": rk,
                "title.value": title, "title.locked": "1",
                "summary.value": summary, "summary.locked": "1",
            }, method="PUT")
            log(f"ADDED  -> {title}")
            log(f"          {summary}")
            changed = True
        except Exception as e:
            log(f"  failed to write metadata for {fname}: {e}")

    # --- note removed items (Plex already dropped them; we just refresh) ---
    for rk in sorted(removed):
        log(f"REMOVED -> {prev.get(rk)}")
        changed = True

    # --- save new state ---
    json.dump(current, open(STATE, "w"))

    # --- if anything changed, refresh ONLY the BT TV channel schedule ---
    if changed:
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"{conf['NTV_URL']}/api/schedule/refresh-channel/{conf['BTTV_CHANNEL']}",
                method="POST"), timeout=30).read()
            log(f"Refreshed BT TV schedule (+{len(added)} / -{len(removed)}).")
        except Exception as e:
            log(f"  schedule refresh error: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)
