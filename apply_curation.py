#!/usr/bin/env python3
# Replay onn default-channel curation onto the Docker server, scoped to a profile.
# Usage:  python3 apply_curation.py <PROFILE_ID>
#   renames+settings -> POST /api/channels/{id}/override?profileId=...
#   logos            -> POST /api/channels/{id}/logo?profileId=...   (multipart PNG)
#   hidden           -> POST /api/channels/{id}/visibility?profileId=...
import json, base64, io, sys, urllib.request, urllib.parse

BASE="http://localhost:19850"
SRC="/tmp/onn.json"
PROFILE = sys.argv[1] if len(sys.argv)>1 else ""
Q = f"?profileId={urllib.parse.quote(PROFILE)}" if PROFILE else ""

def post_json(path, payload):
    data=json.dumps(payload).encode()
    req=urllib.request.Request(BASE+path, data=data, method="POST",
        headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read(300).decode("utf-8","replace")

def post_multipart(path, filename, raw, field="file"):
    b="----ntvB0undary7351"; body=io.BytesIO()
    def w(s): body.write(s if isinstance(s,bytes) else s.encode())
    w(f"--{b}\r\n"); w(f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n')
    w("Content-Type: image/png\r\n\r\n"); w(raw); w("\r\n"); w(f"--{b}--\r\n")
    req=urllib.request.Request(BASE+path, data=body.getvalue(), method="POST",
        headers={"Content-Type":f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read(300).decode("utf-8","replace")

def main():
    d=json.load(open(SRC))
    ov=d.get("defaultChannelOverrides",{}); logos=d.get("defaultChannelLogos",{})
    hidden=d.get("defaultHiddenChannels",[])
    ro=re=lo=le=ho=he=0
    PASS=("customName","customNumberText","customNumber","sortingMethod","marathonsEnabled",
          "allowSpecials","isKidChannel","watchedOnly","deduplicateContent","rentModeEnabled",
          "enabled","algorithm")
    for cid,v in ov.items():
        body={k:v[k] for k in PASS if k in v}
        if not body: continue
        try:
            st,_=post_json(f"/api/channels/{urllib.parse.quote(cid)}/override{Q}", body)
            ro+=1 if st<300 else 0; re+=0 if st<300 else 1
            if st>=300: print("rename FAIL",cid,st)
        except Exception as e: re+=1; print("rename ERR",cid,str(e)[:80])
    for key,b64 in logos.items():
        cid=key[:-4] if key.endswith(".png") else key
        try:
            raw=base64.b64decode(b64)
            st,_=post_multipart(f"/api/channels/{urllib.parse.quote(cid)}/logo{Q}", cid+".png", raw)
            lo+=1 if st<300 else 0; le+=0 if st<300 else 1
            if st>=300: print("logo FAIL",cid,st)
        except Exception as e: le+=1; print("logo ERR",cid,str(e)[:80])
    for cid in hidden:
        try:
            st,_=post_json(f"/api/channels/{urllib.parse.quote(cid)}/visibility{Q}", {"visible":False})
            ho+=1 if st<300 else 0; he+=0 if st<300 else 1
            if st>=300: print("hide FAIL",cid,st)
        except Exception as e: he+=1; print("hide ERR",cid,str(e)[:80])
    print(f"\nRENAMES: {ro} ok / {re} fail")
    print(f"LOGOS:   {lo} ok / {le} fail")
    print(f"HIDDEN:  {ho} ok / {he} fail")

if __name__=="__main__": main()
