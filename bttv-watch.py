#!/usr/bin/env python3
"""
BT TV auto-add watcher (free, local, no external API).
On each run (via cron): finds NEW .mkv files in the BT TV folder, generates a
title + keyword-based summary, triggers a Plex scan of the BT TV library,
writes the metadata to Plex, and refreshes ONLY the BT TV channel schedule.

Config is read from bttv-watch.conf in the same directory:
  PLEX_TOKEN=...
  PLEX_URL=http://localhost:32400
  BTTV_FOLDER=/media/plex/MyBook/BTTV
  PLEX_SECTION=4
  NTV_URL=http://localhost:19850
  BTTV_CHANNEL=user_59dff7fa-26ac-4703-8768-0056ae352f56
"""
import os, re, sys, time, json, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "bttv-watch.conf")
SEEN = os.path.join(HERE, "bttv-watch.seen")   # list of already-processed filenames

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
    t = re.sub(r"\.[A-Za-z0-9]+$", "", fname)          # drop extension
    t = t.replace("｜", "|").replace("：", ":")          # fix fullwidth junk
    t = re.sub(r"\s+", " ", t).strip()
    return t

def summarize(title):
    """Keyword-based topical summary. Tuned to BT TV content."""
    low = title.lower()
    # Part N (ambient loops) -> note the part
    part = ""
    m = re.search(r"\bpart\s*(\d+)\b", low)
    if m: part = f" (Part {int(m.group(1))})"

    if any(w in low for w in ["fireplace", "yule", "sleep sounds", "cozy"]):
        return f"A cozy Boston Terrier fireside scene — crackling warmth on a gentle, relaxing loop.{part}".strip()
    if "relaxing music" in low or ("relaxing" in low and "music" in low):
        return "Calming music paired with mellow Boston Terrier company — easy, soothing background viewing."
    if any(w in low for w in ["judging", "champ show", "champion", "breed judging", "melbourne royal", "club of"]):
        return "Conformation judging and breed competition showcasing Boston Terriers at their finest."
    if any(w in low for w in ["grooming", "bath", "give a bath"]):
        return "Grooming and care — keeping the dapper Boston Terrier clean, trimmed, and looking sharp."
    if any(w in low for w in ["training", "alpha", "train"]):
        return "Boston Terrier training and behavior, from basics to teaching an eager young pup."
    if any(w in low for w in ["puppy", "puppies", "baby", "babies"]):
        return "Adorable Boston Terrier puppy antics — clumsy, playful, and impossibly cute."
    if "service dog" in low or "service dogs" in low:
        return "A look at Boston Terriers as loyal service and companion dogs."
    if any(w in low for w in ["breed information", "everything you need", "characteristics", "breed info"]):
        return "A complete Boston Terrier breed profile — history, temperament, traits, and care."
    if any(w in low for w in ["history", "gentleman", "origin", "pit fighter", "became"]):
        return "The history and heritage of the Boston Terrier — the beloved 'American Gentleman' of dogs."
    if any(w in low for w in ["dangers", "prevent", "ugly truths", "truths about"]):
        return "The honest realities of Boston Terrier ownership — what to watch for and how to prepare."
    if any(w in low for w in ["watercolor", "paint", "draw"]):
        return "An art tutorial capturing the Boston Terrier's unmistakable markings and charm."
    if any(w in low for w in ["tea party", "playdate", "count their treats", "snacking", "funniest", "family love", "life with", "destroyed"]):
        return "Everyday Boston Terrier joy — the funny, heartwarming moments of life with these little companions."
    # default
    base = re.sub(r"\s*\(part\s*\d+\)\s*$", "", title, flags=re.I).strip()
    return f"A Boston Terrier feature on BT TV: {base}.{part}".strip()

def api_get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/xml"})
    return urllib.request.urlopen(req, timeout=30).read()

def plex(path, conf, params=None, method="GET"):
    q = dict(params or {}); q["X-Plex-Token"] = conf["PLEX_TOKEN"]
    url = f"{conf['PLEX_URL']}{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, method=method, headers={"Accept": "application/xml"})
    return urllib.request.urlopen(req, timeout=60).read()

def main():
    conf = load_conf()
    folder = conf["BTTV_FOLDER"]; section = conf["PLEX_SECTION"]

    current = {f for f in os.listdir(folder) if f.lower().endswith(".mkv")}
    seen = set()
    if os.path.exists(SEEN):
        seen = set(open(SEEN).read().splitlines())
    new = sorted(current - seen)
    if not new:
        return  # nothing to do; stay quiet for cron

    print(f"[{time.strftime('%F %T')}] {len(new)} new file(s): {new}")

    # 1) trigger a Plex scan of the BT TV library, wait for it to index
    plex(f"/library/sections/{section}/refresh", conf)
    time.sleep(45)  # give Plex time to scan the new items

    # 2) pull the section's items, match new files by their Part file path, write metadata
    items = ET.fromstring(plex(f"/library/sections/{section}/all", conf))
    by_file = {}
    for v in items.iter("Video"):
        rk = v.get("ratingKey")
        part = v.find(".//Part")
        if part is not None and part.get("file"):
            by_file[os.path.basename(part.get("file"))] = rk

    wrote = 0
    for fname in new:
        rk = by_file.get(fname)
        if not rk:
            print(f"  (not indexed yet, will retry next run): {fname}")
            continue  # don't mark seen; picked up next run
        title = clean_title(fname)
        summary = summarize(title)
        plex(f"/library/sections/{section}/all", conf, {
            "type": "1", "id": rk,
            "title.value": title, "title.locked": "1",
            "summary.value": summary, "summary.locked": "1",
        }, method="PUT")
        print(f"  wrote: {title}\n         {summary}")
        wrote += 1
        seen.add(fname)

    # persist processed list (only the ones we actually wrote + already-seen)
    open(SEEN, "w").write("\n".join(sorted(seen)))

    # 3) if we added anything, refresh ONLY the BT TV channel schedule
    if wrote:
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"{conf['NTV_URL']}/api/schedule/refresh-channel/{conf['BTTV_CHANNEL']}",
                method="POST"), timeout=30).read()
            print(f"  refreshed BT TV schedule ({wrote} new).")
        except Exception as e:
            print(f"  schedule refresh error: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[{time.strftime('%F %T')}] ERROR: {e}")
        sys.exit(1)
