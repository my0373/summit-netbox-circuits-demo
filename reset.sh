#!/usr/bin/env bash
# Resets all demo circuits in NetBox back to 'active' status.
# Run this between demo runs to restore the Visual Explorer to its starting state.

set -e

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Run ./setup.sh first."
  exit 1
fi

set -a
source .env
set +a

echo "Resetting demo circuits to active..."
ansible-playbook ansible/pb_reset_demo.yml \
  -i ansible/inventory/localhost.yml

echo ""
cat << 'NEXTSTEPS'
========================================================
  Reset complete — you're ready to run the demo:
========================================================

  1. Open NetBox Visual Explorer and confirm both circuits
     show as active on the map.

  2. In NetBox Copilot, say something like:
       "IPLC-GB-PH-PRI has failed — set it to offline"

  3. Watch EDA and AAP fire automatically:
       - EDA rulebook picks up the webhook event
       - AAP runs the Circuit Failover job template
       - NetBox is updated: primary → offline, backup → active

  4. Refresh the Visual Explorer — the failed circuit line
     should disappear from the map.

  5. Open the failover report URL (from setup_infra.sh output)
     to see the full incident summary.

  6. Verify circuit status via the NetBox MCP server in Claude:
       "What is the current status of IPLC-GB-PH-PRI?"
       "Which circuit is now active between GB-Bristol and PH-Manila-01?"

NEXTSTEPS
