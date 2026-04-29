#!/usr/bin/env bash
# teardown_infra.sh
#
# Tears down all AWS infrastructure provisioned by setup_infra.sh:
#   - Report server EC2 instance + EIP
#   - MCP server EC2 instance + EIP
#   - Cisco router (C8000V) EC2 instance + EIP
#   - Security groups, key pair
#
# Also cleans up in NetBox:
#   - Removes the router EC2 Elastic IP address object
#   - Resets gb-brs-rtr-01 primary_ip4 to the original simulated IP (10.150.0.1/24)
#
# Usage: ./teardown_infra.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/infra"

# ── Assume AWS role ───────────────────────────────────────────────────────────
echo "Assuming AWS credentials (eu-west-3)..."
eval "$(GRANTED_ALIAS_INSTALLED=true assume --region eu-west-3)" || {
  echo "ERROR: 'assume --region eu-west-3' failed. Check your assume configuration."
  exit 1
}

AWS_ACCOUNT=$(aws sts get-caller-identity --region eu-west-3 --query Account --output text)
echo "AWS credentials OK (account: $AWS_ACCOUNT, region: eu-west-3)"

# ── Load .env ─────────────────────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "ERROR: .env not found. Run ./setup.sh first."
  exit 1
fi
set -a; source "$SCRIPT_DIR/.env"; set +a

# ── Read current router IP from infra.yml ────────────────────────────────────
ROUTER_IP=""
if [ -f "$SCRIPT_DIR/ansible/vars/infra.yml" ]; then
  ROUTER_IP=$(grep 'router_ip:' "$SCRIPT_DIR/ansible/vars/infra.yml" | awk '{print $2}' | tr -d '"')
fi

# ── Confirm before destroying ─────────────────────────────────────────────────
echo ""
echo "========================================================"
echo "  WARNING: This will destroy all demo infrastructure!"
echo "========================================================"
echo ""
echo "  The following AWS resources will be permanently deleted:"
echo "    - Report server EC2 instance and Elastic IP"
echo "    - MCP server EC2 instance and Elastic IP"
echo "    - Cisco router (C8000V) EC2 instance and Elastic IP"
echo "    - Security groups (report, MCP, router)"
echo "    - EC2 key pair (summit-demo-2026)"
echo ""
if [ -n "$ROUTER_IP" ]; then
  echo "  NetBox cleanup:"
  echo "    - Remove IP $ROUTER_IP/32 from NetBox IPAM"
  echo "    - Reset gb-brs-rtr-01 primary_ip4 to 10.150.0.1/24"
  echo ""
fi
read -r -p "  Type 'yes' to confirm: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted."
  exit 0
fi

# ── Terraform destroy ─────────────────────────────────────────────────────────
echo ""
echo "========================================================"
echo "  Step 1: Terraform destroy"
echo "========================================================"

cd "$INFRA_DIR"
terraform init -upgrade -input=false

# router_password is required by the variable definition but not used during destroy.
# Read from infra.yml if available, otherwise pass a dummy value to satisfy Terraform.
_ROUTER_PW=""
if [ -f "$SCRIPT_DIR/ansible/vars/infra.yml" ]; then
  _ROUTER_PW=$(grep 'router_password:' "$SCRIPT_DIR/ansible/vars/infra.yml" 2>/dev/null | awk '{print $2}' | tr -d '"' || true)
fi
_ROUTER_PW="${_ROUTER_PW:-unused-destroy-placeholder}"

terraform destroy -auto-approve -input=false \
  -var="aws_region=eu-west-3" \
  -var="netbox_url=${NETBOX_URL}" \
  -var="netbox_token=${NETBOX_TOKEN}" \
  -var="router_password=${_ROUTER_PW}"

cd "$SCRIPT_DIR"

# ── NetBox cleanup ────────────────────────────────────────────────────────────
if [ -n "$ROUTER_IP" ]; then
  echo ""
  echo "========================================================"
  echo "  Step 2: NetBox cleanup"
  echo "========================================================"

  # Reset gb-brs-rtr-01 primary_ip4 to original simulated IP (id=22, 10.150.0.1/24)
  echo "  Resetting gb-brs-rtr-01 primary_ip4 to 10.150.0.1/24..."
  PATCH_RESULT=$(curl -s -w "\n%{http_code}" -X PATCH \
    -H "Authorization: Token $NETBOX_TOKEN" \
    -H "Content-Type: application/json" \
    "$NETBOX_URL/api/dcim/devices/22/" \
    -d '{"primary_ip4": 22}')
  HTTP_CODE=$(echo "$PATCH_RESULT" | tail -1)
  if [ "$HTTP_CODE" = "200" ]; then
    echo "  OK — primary_ip4 restored to 10.150.0.1/24"
  else
    echo "  WARNING — PATCH returned HTTP $HTTP_CODE (may need manual cleanup)"
  fi

  # Delete the EC2 Elastic IP object from NetBox IPAM
  ROUTER_CIDR="${ROUTER_IP}%2F32"
  IP_ID=$(curl -s -H "Authorization: Token $NETBOX_TOKEN" \
    "$NETBOX_URL/api/ipam/ip-addresses/?address=${ROUTER_CIDR}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); ids=[r['id'] for r in d.get('results',[]) if r['description']=='Cisco demo router EC2 Elastic IP']; print(ids[0] if ids else '')" 2>/dev/null)

  if [ -n "$IP_ID" ]; then
    DEL_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
      -H "Authorization: Token $NETBOX_TOKEN" \
      "$NETBOX_URL/api/ipam/ip-addresses/$IP_ID/")
    if [ "$DEL_CODE" = "204" ]; then
      echo "  OK — removed $ROUTER_IP/32 from NetBox IPAM (id=$IP_ID)"
    else
      echo "  WARNING — DELETE returned HTTP $DEL_CODE for IP id=$IP_ID"
    fi
  else
    echo "  No router IP found in NetBox IPAM — skipping"
  fi
fi

# ── Clean up generated files ──────────────────────────────────────────────────
echo ""
echo "========================================================"
echo "  Step 3: Clean up generated files"
echo "========================================================"

if [ -f "$SCRIPT_DIR/ansible/vars/infra.yml" ]; then
  cp "$SCRIPT_DIR/ansible/vars/infra.yml.example" "$SCRIPT_DIR/ansible/vars/infra.yml"
  echo "  ansible/vars/infra.yml reset to empty placeholder."
fi

if [ -f "$SCRIPT_DIR/ansible/vars/network_creds.yml" ]; then
  cp "$SCRIPT_DIR/ansible/vars/network_creds.yml.example" "$SCRIPT_DIR/ansible/vars/network_creds.yml"
  echo "  ansible/vars/network_creds.yml reset to empty placeholder."
fi

echo ""
cat << 'NEXTSTEPS'
========================================================
  Teardown complete
========================================================

  All AWS infrastructure has been destroyed.
  NetBox router IP has been reset.

  To provision fresh infrastructure:
    ./setup_infra.sh

  To do a full reset from scratch:
    ./setup.sh
    uv run --with requests python setup_aap.py
    ./setup_infra.sh
    ./reset.sh

NEXTSTEPS
