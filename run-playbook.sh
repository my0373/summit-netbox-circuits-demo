#!/usr/bin/env bash
# Wrapper that runs a playbook inside the project EE via ansible-navigator.
# All settings (EE image, env injection, mode) come from ansible-navigator.yml.
#
# Usage: ./run-playbook.sh ansible/pb_circuit_failover.yml [extra args]
#        ./run-playbook.sh ansible/pb_circuit_failover.yml --extra-vars "failed_circuit=IPLC-GB-JP-PRI"

set -e

if [ -z "$1" ]; then
  echo "Usage: ./run-playbook.sh <playbook> [ansible-playbook args...]"
  exit 1
fi

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Run ./setup.sh first."
  exit 1
fi

ansible-navigator run "$@" -i ansible/inventory/localhost.yml
