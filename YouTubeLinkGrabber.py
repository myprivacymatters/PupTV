#!/usr/bin/env python3
# yt-dlp based resolver for PUP TV.
# Reads youtubeLink.txt ("Name || id || Category" then a URL line),
# resolves each YouTube live URL to a real HLS manifest, prints an M3U to stdout.
# Channels that don't resolve (offline / blocked) are skipped, not faked.
import subprocess, sys

def resolve(url):
    # Try the android client first (usually dodges the datacenter bot-wall), then web.
    for extra in (["--extractor-args", "youtube:player_client=android"],
                  ["--extractor-args", "youtube:player_client=web"],
                  []):
        try:
            r = subprocess.run(
                ["yt-dlp", "-g", "--no-warnings", "--no-playlist", "-f", "b/best"] + extra + [url],
                capture_output=True, text=True, timeout=120)
            urls = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("http")]
            if urls:
                for u in urls:                       # prefer an HLS manifest
                    if ".m3u8" in u or "manifest" in u:
                        return u
                return urls[0]
            if r.stderr.strip():
                sys.stderr.write(r.stderr.strip().splitlines()[-1] + "\n")
        except Exception as e:
            sys.stderr.write(f"  err {url}: {e}\n")
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
                print(f'\n#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" group-title="{cat}",{name}')
                print(url)
                sys.stderr.write(f"OK    {name}\n"); ok += 1
            else:
                sys.stderr.write(f"SKIP  {name}  (offline or blocked)\n"); fail += 1
            meta = None
    sys.stderr.write(f"\nResolved {ok}, skipped {fail}\n")

if __name__ == "__main__":
    main()
