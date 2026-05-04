#!/usr/bin/env bash
# teardown_infra.sh
#
# Tears down all AWS infrastructure provisioned by setup_infra.sh:
#   - Report server EC2 instance + EIP
#   - MCP server EC2 instance + EIP
#   - Security groups, key pair
#
# Usage: ./teardown_infra.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/infra"

# ── Assume AWS role ───────────────────────────────────────────────────────────
echo "Assuming AWS credentials (eu-west-2)..."
eval "$(GRANTED_ALIAS_INSTALLED=true assume --region eu-west-2)" || {
  echo "ERROR: 'assume --region eu-west-2' failed. Check your assume configuration."
  exit 1
}

AWS_ACCOUNT=$(aws sts get-caller-identity --region eu-west-2 --query Account --output text)
echo "AWS credentials OK (account: $AWS_ACCOUNT, region: eu-west-2)"

# ── Load .env ─────────────────────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "ERROR: .env not found. Run ./setup.sh first."
  exit 1
fi
set -a; source "$SCRIPT_DIR/.env"; set +a

# ── Confirm before destroying ─────────────────────────────────────────────────
echo ""
echo "========================================================"
echo "  WARNING: This will destroy all demo infrastructure!"
echo "========================================================"
echo ""
echo "  The following will be permanently deleted:"
echo "    - Report server EC2 instance and Elastic IP"
echo "    - MCP server EC2 instance and Elastic IP"
echo "    - Associated security groups and key pair"
echo ""
read -r -p "  Type 'yes' to confirm: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted."
  exit 0
fi

echo ""
echo "========================================================"
echo "  Terraform destroy"
echo "========================================================"

cd "$INFRA_DIR"
terraform init -upgrade -input=false
terraform destroy -auto-approve -input=false \
  -var="aws_region=eu-west-2" \
  -var="netbox_url=${NETBOX_URL}" \
  -var="netbox_token=${NETBOX_TOKEN}"

cd "$SCRIPT_DIR"

# ── Clean up generated files ──────────────────────────────────────────────────
echo ""
echo "Cleaning up generated files..."

clear_env_var() {
  local key="$1" file="$SCRIPT_DIR/.env"
  if [ -f "$file" ]; then
    sed -i "s|^${key}=.*|${key}=|" "$file"
  fi
}

clear_env_var REPORT_SERVER_HOST
clear_env_var REPORT_SERVER_PORT
clear_env_var REPORT_URL
clear_env_var ROUTER_IP
clear_env_var ROUTER_PASSWORD
clear_env_var ROUTER_USERNAME
clear_env_var PRIVATE_KEY_PATH
echo "  Infrastructure variables cleared from .env."

echo ""
cat << 'NEXTSTEPS'
========================================================
  Teardown complete
========================================================

  All AWS infrastructure has been destroyed.

  To provision fresh infrastructure:
    ./setup_infra.sh

  To do a full reset from scratch:
    ./setup.sh
    ./run-playbook.sh ansible/pb_setup_aap.yml
    ./setup_infra.sh
    ./reset.sh

NEXTSTEPS
