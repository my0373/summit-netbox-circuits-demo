#!/usr/bin/env bash
set -e

# Copy .env.example to .env if it doesn't exist
if [ -f .env ]; then
    echo ".env already exists, skipping credential setup."
else
    cp .env.example .env
    echo ".env created — fill in your credentials before running the demo."
fi

echo ""
cat << 'NEXTSTEPS'
========================================================
  Setup complete — what to do next:
========================================================

  1. Fill in .env with your credentials:
       NETBOX_URL, NETBOX_TOKEN, AAP_URL, AAP_USERNAME,
       AAP_PASSWORD, EDA_STREAM_TOKEN

  2. Configure AAP and EDA (idempotent — safe to re-run):
       ./run-playbook.sh ansible/pb_setup_aap.yml

  3. (Optional) Provision AWS infrastructure:
       ./setup_infra.sh
     Or fill in REPORT_SERVER_HOST, ROUTER_IP, etc. in .env manually.

  4. Reset NetBox circuits to starting state:
       ./reset.sh

  5. You're ready to run the demo!

NEXTSTEPS
