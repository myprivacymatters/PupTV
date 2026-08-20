#!/usr/bin/env python3
import subprocess, sys

LOGO_BASE = "http://plex.taila87cd9.ts.net:8899"
LOGOS = {
    "puptv.relax.yt":      "pup-relax.png",
    "puptv.enrichment.yt": "pup-enrichment.png",
    "puptv.daycare.yt":    "pup-daycare.png",
    "puptv.rescue.yt":     "pup-rescue.png",
    "puptv.service.yt":    "pup-service.png",
}

def resolve(url):
    for extra in (["--extractor-args", "youtube:player_client=android"],
                  ["--extractor-args", "youtube:player_client=web"],
                  []):
        try:
            r = subprocess.run(
                ["yt-dlp", "-g", "--no-warnings", "--no-playlist", "-f", "b/best"] + extra + [url],
                capture_output=True, text=True, timeout=120)
            urls = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("http")]
            if urls:
                for u in urls:
                    if ".m3u8" in u or "manifest" in u:
                        return u
                return urls[0]
            if r.stderr.strip():
                sys.stderr.write(r.stderr.strip().splitlines()[-1] + "\n")
        except Exception as e:
            sys.stderr.write("  err %s: %s\n" % (url, e))
    return None

def main():
    with open("youtubeLink.txt", encoding="utf-8") as f:
        raw = [l.rstrip("\n") for l in f]
    print("#EXTM3U")
    meta = None
    ok = fail = 0
    for line in raw:
        s = line.strip()
        if not s or s.startswith("##"):
            continue
        if not s.startswith("http"):
            p = s.split("||")
            meta = (p[0].strip(), p[1].strip(), p[2].strip())
        else:
            if not meta:
                continue
            name, cid, cat = meta
            url = resolve(s)
            if url:
                logo = LOGOS.get(cid, "")
                tag = ' tvg-logo="%s/%s"' % (LOGO_BASE, logo) if logo else ""
                print('\n#EXTINF:-1 tvg-id="%s" tvg-name="%s"%s group-title="%s",%s' % (cid, name, tag, cat, name))
                print(url)
                sys.stderr.write("OK    %s\n" % name); ok += 1
            else:
                sys.stderr.write("SKIP  %s  (offline or blocked)\n" % name); fail += 1
            meta = None
    sys.stderr.write("\nResolved %d, skipped %d\n" % (ok, fail))

if __name__ == "__main__":
    main()
