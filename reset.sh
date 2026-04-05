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

  1. Open NetBox Visual Explorer and confirm IPLC-GB-AT-PRI
     shows as active between GB-Bristol and US-Atlanta.

  2. In NetBox Copilot, say:
       "IPLC-GB-AT-PRI has failed — set it to offline"

  3. Watch AAP fire automatically:
       - NetBox event rule sends webhook to AAP
       - AAP runs the Circuit Failover Workflow:
           Step 1: primary → offline, backup → active
           Step 2: HTML incident report deployed to report server

  4. Refresh the Visual Explorer — IPLC-GB-AT-PRI disappears
     and the backup circuit appears active.

  5. Open the incident report:
       https://13.41.146.206/failover_report.html

  6. Ask Claude (via NetBox MCP):
       "What is the current status of IPLC-GB-AT-PRI?"
       "Which circuit is now active between GB-Bristol and US-Atlanta?"

NEXTSTEPS
