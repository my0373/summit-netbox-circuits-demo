#!/usr/bin/env bash
set -e

# Copy .env.example to .env if it doesn't exist
if [ -f .env ]; then
    echo ".env already exists, skipping credential setup."
else
    cp .env.example .env
    echo ".env created — fill in your credentials before continuing."
fi

# Install Python dependencies
echo "Installing Python dependencies with uv..."
uv sync

# Create infra.yml placeholder if not present
if [ ! -f ansible/vars/infra.yml ]; then
    cp ansible/vars/infra.yml.example ansible/vars/infra.yml
    echo "ansible/vars/infra.yml created (empty — run ./setup_infra.sh to populate)."
fi

echo ""
cat << 'NEXTSTEPS'
========================================================
  Setup complete — what to do next:
========================================================

  1. Fill in .env with your credentials:
       NETBOX_URL      — NetBox Cloud instance URL
       NETBOX_TOKEN    — NetBox API token
       AAP_URL         — AAP Controller base URL
       AAP_USERNAME    — AAP username
       AAP_PASSWORD    — AAP password
       EDA_STREAM_TOKEN — Shared token for the EDA event stream

  2. Before provisioning infrastructure, accept the Cisco
     Catalyst 8000V Edge Software (BYOL) terms on AWS
     Marketplace for eu-west-2. Terraform discovers the
     AMI automatically — you just need the subscription active.

  3. Configure AAP, EDA, and NetBox webhook (idempotent — safe to re-run):
       uv run --with requests python setup_aap.py

  4. Provision AWS infrastructure (report server, MCP server, Cisco router):
       ./setup_infra.sh

  5. Install Ansible collections (first time only):
       ansible-galaxy collection install -r ansible/requirements.yml --force

  6. Reset NetBox circuits to starting state and restore router route:
       ./reset.sh

  7. You're ready to run the demo!
     Run ./howdoirun.sh at any time for a quick checklist.

NEXTSTEPS
