#!/usr/bin/env python3
# Writes titles + summaries to BT TV items in Plex (NostalgiaTV reads them from there).
# Usage:  PLEX_TOKEN=xxxx python3 set_descriptions.py --dry     (preview)
#         PLEX_TOKEN=xxxx python3 set_descriptions.py --apply   (write)
import os, sys, re, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

PLEX_URL   = os.environ.get("PLEX_URL", "http://localhost:32400")
PLEX_TOKEN = os.environ.get("PLEX_TOKEN", "")
LIBRARY    = os.environ.get("PLEX_LIBRARY", "BT TV")

def slug(s):
    s = s.rsplit("/", 1)[-1]
    s = re.sub(r"\.[A-Za-z0-9]+$", "", s)
    s = s.lower().replace("｜", " ").replace("：", " ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

# base slug -> (clean title, plot)
DESC = {
 "2025 boston terrier judging at melbourne royal": ("Boston Terrier Judging \u2014 Melbourne Royal 2025", "Conformation judging of Boston Terriers at Australia's Melbourne Royal show."),
 "2022 boston terrier club of vic champ show": ("Boston Terrier Club of Victoria \u2014 2022 Champ Show", "The Boston Terrier Club of Victoria's 2022 championship conformation show."),
 "2025 boston terrier breed judging day doswell va": ("Boston Terrier Breed Judging \u2014 Doswell, VA 2025", "A full day of Boston Terrier breed judging from Doswell, Virginia."),
 "boston terrier dogs relaxing music for dogs": ("Relaxing Music for Boston Terriers", "Calming music paired with mellow Boston Terrier company \u2014 easy background viewing."),
 "what it s like to give a bath to 7 boston terrier dogs": ("Bath Day: Seven Boston Terriers", "Sudsy, slippery chaos as seven Boston Terriers get their baths."),
 "my boston has a playdate": ("My Boston Has a Playdate", "A Boston Terrier meets up with a friend for an afternoon of play."),
 "their home was destroyed by two boston terriers": ("Home Wrecked by Two Boston Terriers", "The delightful destruction two determined Boston Terriers can cause when left to their own devices."),
 "boston terrier dog breed information everything you need to know": ("Boston Terrier: Everything You Need to Know", "A complete breed profile \u2014 history, temperament, care, and what to expect from a Boston."),
 "the ugly truths about owning a boston terrier": ("The Ugly Truths About Owning a Boston Terrier", "An honest look at the snorts, stubbornness, and challenges that come with the breed."),
 "alpha boston terrier training her pup": ("Alpha Boston Terrier Trains Her Pup", "An older Boston Terrier shows a youngster how it's done."),
 "how to paint a realistic boston terrier in watercolor": ("Painting a Boston Terrier in Watercolor", "A step-by-step watercolor tutorial capturing a Boston Terrier's markings."),
 "boston terriers these small dogs give us big family love": ("Big Family Love, Small Dogs", "A heartfelt feature on how Boston Terriers become the heart of a family."),
 "our boston terriers count their treats": ("Our Boston Terriers Count Their Treats", "A playful bit of counting \u2014 with very food-motivated Bostons."),
 "basics of dog grooming boston terrier edition": ("Grooming Basics \u2014 Boston Terrier Edition", "The essentials of keeping a Boston Terrier clean, trimmed, and comfortable."),
 "the funniest moments with our baby boston terriers": ("Funniest Baby Boston Terrier Moments", "A greatest-hits reel of clumsy, hilarious Boston Terrier puppy antics."),
 "everyday dangers for boston terriers how to spot and prevent them": ("Everyday Dangers for Boston Terriers", "How to spot and prevent common household and outdoor hazards for the breed."),
 "mula the boston terrier dog": ("Mula, the Boston Terrier", "A day in the life of Mula, one very expressive Boston Terrier."),
 "life with three boston terriers": ("Life with Three Boston Terriers", "The joyful, chaotic reality of sharing a home with a trio of Bostons."),
 "boston terrier breed information and characteristics": ("Boston Terrier: Breed Traits", "A rundown of the Boston Terrier's defining characteristics and temperament."),
 "5th annual boston terrier tea party": ("5th Annual Boston Terrier Tea Party", "Bostons gather for the fifth annual tea party meetup \u2014 tiny hats encouraged."),
 "snacking with 7 boston terriers": ("Snacking with Seven Boston Terriers", "Snack time descends into happy pandemonium with a pack of seven."),
 "do boston terriers make good service dogs": ("Do Boston Terriers Make Good Service Dogs?", "A look at whether the breed's size and temperament suit service work."),
}

# ambient loops that were split into parts: base slug -> plot template
PARTS = {
 "cozy by the fireplace with your boston terrier": "A cozy fireplace scene with a Boston Terrier \u2014 a calm, continuous loop to relax to.",
 "cozy boston terrier holiday yule log": "A festive Boston Terrier Yule log \u2014 crackling holiday warmth on a gentle loop.",
 "4 hour boston terrier puppy fireplace sleep sounds": "Boston Terrier puppies by a soft fire \u2014 soothing sleep-sound ambience.",
}

def lookup(base):
    if base in DESC: return DESC[base]
    m = re.match(r"^(.*?) part (\d+)$", base)
    if m:
        b, n = m.group(1).strip(), int(m.group(2))
        for k, plot in PARTS.items():
            if b == k:
                title = DESC.get(k, (b.title(),))[0] if k in DESC else b.title()
                pretty = {
                 "cozy by the fireplace with your boston terrier": "Cozy Fireplace with a Boston Terrier",
                 "cozy boston terrier holiday yule log": "Boston Terrier Holiday Yule Log",
                 "4 hour boston terrier puppy fireplace sleep sounds": "Boston Terrier Puppy Fireplace \u2014 Sleep Sounds",
                }[k]
                return (f"{pretty} (Part {n})", plot)
    return None

def api(path, method="GET", params=None):
    q = dict(params or {}); q["X-Plex-Token"] = PLEX_TOKEN
    url = f"{PLEX_URL}{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, method=method, headers={"Accept":"application/xml"})
    return urllib.request.urlopen(req, timeout=20).read()

def main():
    if not PLEX_TOKEN:
        sys.exit("Set PLEX_TOKEN env var first (see instructions).")
    mode = "--dry" if "--apply" not in sys.argv else "--apply"
    # find section
    secs = ET.fromstring(api("/library/sections"))
    key = None
    for d in secs.iter("Directory"):
        if d.get("title") == LIBRARY: key = d.get("key")
    if not key: sys.exit(f'Library "{LIBRARY}" not found.')
    items = ET.fromstring(api(f"/library/sections/{key}/all"))
    hit = miss = 0
    for v in items.iter("Video"):
        rk = v.get("ratingKey")
        part = v.find(".//Part")
        fname = part.get("file") if part is not None else v.get("title","")
        base = slug(fname)
        d = lookup(base)
        if not d:
            miss += 1; print("  NO MATCH:", base); continue
        title, plot = d; hit += 1
        print(f"[{mode}] {title}\n         {plot}")
        if mode == "--apply":
            api(f"/library/sections/{key}/all", "PUT", {
                "type": "1",
                "id": rk,
                "title.value": title, "title.locked": "1",
                "summary.value": plot, "summary.locked": "1",
            })
    print(f"\n{hit} matched, {miss} unmatched.  Mode: {mode}")

if __name__ == "__main__":
    main()
