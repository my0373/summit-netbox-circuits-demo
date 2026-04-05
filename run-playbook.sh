#!/usr/bin/env bash
# Wrapper that sources .env then runs an ansible-playbook command.
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

set -a
source .env
set +a

ansible-playbook "$@" -i ansible/inventory/localhost.yml
