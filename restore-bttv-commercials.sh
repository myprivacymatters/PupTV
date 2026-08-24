#!/bin/bash
# Re-applies BT TV commercial config if a device reset wipes it.
# Run AFTER all devices are settled (a freshly-reset device syncs blank config up and wipes this).
BASE="http://localhost:19850"
PROFILE="3e3721a1-0348-47a3-a9e0-fb68a2a35a3f"
BTTV="user_59dff7fa-26ac-4703-8768-0056ae352f56"
LIB="5"
SERVER="06efe57f0d3e55a813b2bd67c034ae314967b7fd"

echo "Setting global commercial config (BTTV-Bumpers, align off)..."
curl -sS -X POST "$BASE/api/commercials/global?profileId=$PROFILE" \
  -H "Content-Type: application/json" \
  -d "{\"commercialLibraryId\":\"$LIB\",\"commercialServerId\":\"$SERVER\",\"sourceFromOneLibrary\":true,\"alignToQuarterHour\":false,\"alignmentMinutes\":0,\"countBetweenShows\":1}" | head -c 200; echo

echo "Enabling commercials on BT TV..."
curl -sS -X POST "$BASE/api/commercials/channel/$BTTV?profileId=$PROFILE" \
  -H "Content-Type: application/json" \
  -d '{"isEnabled":true,"midBreakMode":"NONE","midBreakCommercialCount":1,"rentModeEnabled":false}' | head -c 200; echo

echo "Refreshing BT TV schedule..."
curl -sS -X POST "$BASE/api/schedule/refresh-channel/$BTTV" | head -c 200; echo

echo ""
echo "Verifying..."
curl -sS "$BASE/api/commercials/?profileId=$PROFILE" | python3 -c "
import sys,json
d=json.load(sys.stdin); g=d['globalConfig']
print('  libraryId:', g.get('commercialLibraryId'), '| align:', g.get('alignToQuarterHour'))
bt=d['channelConfigs'].get('$BTTV')
print('  BT TV enabled:', bt.get('isEnabled') if bt else 'NOT FOUND')
"
echo "Done. Expect: libraryId: 5 | align: False | BT TV enabled: True"
