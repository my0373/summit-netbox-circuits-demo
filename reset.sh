#!/usr/bin/env bash
# Resets the demo to its starting state:
#   - All dd-tagged circuits → active (except IPLC-GB-AT-SEC → offline)
#   - Cisco router (gb-brs-rtr-01) primary route restored to 172.16.0.1

set -e

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Run ./setup.sh first."
  exit 1
fi

set -a
source .env
set +a

# Export router credentials as ANSIBLE_NET_* env vars so the reset playbook
# can authenticate to the Cisco router. These match the env vars AAP injects
# from its Network credential, so the playbook works the same locally and
# under AAP without any vars-file dependency.
if [ -f ansible/vars/infra.yml ]; then
  export ANSIBLE_NET_USERNAME=iosuser
  export ANSIBLE_NET_PASSWORD="$(grep '^router_password:' ansible/vars/infra.yml | awk '{print $2}' | tr -d '"')"
fi

echo "Resetting demo circuits and router route..."
ansible-playbook ansible/pb_reset_demo.yml \
  -i ansible/inventory/localhost.yml

# Read report URL from generated infra vars (if available)
REPORT_URL=""
if [ -f ansible/vars/infra.yml ]; then
  REPORT_URL=$(grep 'report_url:' ansible/vars/infra.yml | awk '{print $2}' | tr -d '"')
fi
REPORT_URL="${REPORT_URL:-https://<report_server_ip>/failover_report.html}"

echo ""
cat << NEXTSTEPS
========================================================
  Reset complete — you're ready to run the demo:
========================================================

  1. Open NetBox Visual Explorer and confirm IPLC-GB-AT-PRI
     shows as active between GB-Bristol and US-Atlanta.

  2. In NetBox Copilot, say:
       "IPLC-GB-AT-PRI has failed — set it to offline"

  3. Watch AAP fire automatically:
       - NetBox event rule sends webhook to EDA event stream
       - EDA rulebook triggers Circuit Failover Workflow in AAP:
           Step 1: push IOS config to router, primary → offline, backup → active
           Step 2: HTML incident report deployed to report server

  4. Refresh the Visual Explorer — IPLC-GB-AT-PRI disappears
     and the backup circuit appears active.

  5. Open the incident report:
       $REPORT_URL

  6. Ask Claude (via NetBox MCP):
       "What is the current status of IPLC-GB-AT-PRI?"
       "Which circuit is now active between GB-Bristol and US-Atlanta?"

NEXTSTEPS
