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
echo "Done. NetBox and Visual Explorer are back to starting state."
