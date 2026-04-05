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

echo ""
echo "Setup complete. Next steps:"
echo "  1. Fill in .env with your NetBox and AAP credentials (if not done)"
echo "  2. Run a playbook: ./run-playbook.sh ansible/pb_circuit_failover.yml"
echo "  3. Reset the demo:  ./reset.sh"
