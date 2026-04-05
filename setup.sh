#!/usr/bin/env bash
set -e

# Copy .env.example to .env if it doesn't exist
if [ -f .env ]; then
    echo ".env already exists, skipping credential setup."
else
    cp .env.example .env
    echo ".env created — fill in your credentials before running the demo."
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

  1. Fill in .env with your credentials (if not done):
       NETBOX_URL, NETBOX_TOKEN, AAP_URL, AAP_USERNAME,
       AAP_PASSWORD, EDA_STREAM_TOKEN

  2. Configure AAP and EDA (idempotent — safe to re-run):
       uv run --with requests python setup_aap.py

  3. Provision AWS infrastructure (report server + MCP VM):
       ./setup_infra.sh

  4. Reset NetBox circuits to starting state:
       ./reset.sh

  5. You're ready to run the demo!

NEXTSTEPS
