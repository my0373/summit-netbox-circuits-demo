#!/usr/bin/env bash
# setup_infra.sh
#
# Provisions the Summit Demo infrastructure on AWS via Terraform:
#   - Report server: nginx HTTPS, serves the AAP-generated failover report
#   - MCP server: NetBox read-only MCP server accessed via SSH stdio
#   - Cisco router: C8000v/CSR1000v for real IOS config demo (A-side)
#
# Then registers VMs with AAP and updates gb-brs-rtr-01 primary IP in NetBox.
#
# Prerequisites:
#   1. Run ./setup.sh (creates .env)
#   2. Run: uv run --with requests python setup_aap.py (configures AAP)
#   3. Accept the Cisco C8000V (product: Cisco Catalyst 8000V Edge Software BYOL)
#      terms on AWS Marketplace for eu-west-3 — no AMI ID needed, Terraform
#      discovers it automatically by product code.
#
# Usage: ./setup_infra.sh

set -euo pipefail

# ── Assume AWS role ───────────────────────────────────────────────────────────
echo "Assuming AWS credentials (eu-west-3)..."
eval "$(GRANTED_ALIAS_INSTALLED=true assume --region eu-west-3)" || {
  echo "ERROR: 'assume --region eu-west-3' failed. Check your assume configuration."
  exit 1
}

AWS_ACCOUNT=$(aws sts get-caller-identity --region eu-west-3 --query Account --output text)
echo "AWS credentials OK (account: $AWS_ACCOUNT, region: eu-west-3)"

# ── EIP headroom check ────────────────────────────────────────────────────────
# List EIPs tagged owner=myork@netboxlabs.com so we can spot ones to release.
# This demo needs 3 EIPs; the default AWS limit is 5 per region.
echo ""
echo "Checking existing EIPs tagged owner=myork@netboxlabs.com in eu-west-3..."
OWNED_COUNT=$(aws ec2 describe-addresses --region eu-west-3 \
  --filters "Name=tag:owner,Values=myork@netboxlabs.com" \
  --query 'length(Addresses)' --output text 2>/dev/null || echo 0)

ALL_COUNT=$(aws ec2 describe-addresses --region eu-west-3 \
  --query 'length(Addresses)' --output text 2>/dev/null || echo 0)

AVAILABLE=$((5 - ALL_COUNT))

echo "  $ALL_COUNT/5 EIPs in use, $OWNED_COUNT tagged as yours. This demo needs 3."
echo ""

# Always show all EIPs with their tags so untagged/foreign ones are visible
ALL_EIPS=$(aws ec2 describe-addresses --region eu-west-3 \
  --query 'Addresses[*].{
    IP:PublicIp,
    ID:AllocationId,
    Instance:InstanceId,
    Name:Tags[?Key==`Name`]|[0].Value,
    Owner:Tags[?Key==`owner`]|[0].Value,
    Project:Tags[?Key==`Project`]|[0].Value
  }' --output table 2>/dev/null)
echo "$ALL_EIPS"

if [ "$AVAILABLE" -lt 3 ]; then
  echo ""
  echo "  WARNING: Only $AVAILABLE EIP slot(s) free — this run needs 3 and will fail."
  echo "  Release an unneeded EIP with:"
  echo "    aws ec2 release-address --region eu-west-3 --allocation-id <ID>"
  echo ""
  read -r -p "  Press ENTER to continue anyway, or Ctrl-C to abort..."
fi
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/infra"
KEYS_DIR="$INFRA_DIR/keys"

# Load credentials
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "ERROR: .env not found. Run ./setup.sh first."
  exit 1
fi
set -a; source "$SCRIPT_DIR/.env"; set +a

echo "========================================================"
echo "  Step 1: Terraform — provision VMs"
echo "========================================================"

# Generate a fresh secure router password for every provisioning run.
# Alphanumeric only (IOS-XE compatible), 24 characters.
ROUTER_PASSWORD=$(openssl rand -base64 32 | tr -d '+/=\n' | cut -c1-24)

cd "$INFRA_DIR"
terraform init -upgrade -input=false

# Cisco C8000V AMI is discovered automatically by product code — no ROUTER_AMI_ID needed.
# You must accept the Marketplace terms for eu-west-2 before running this script.
terraform apply -auto-approve -input=false \
  -var="aws_region=eu-west-3" \
  -var="netbox_url=${NETBOX_URL}" \
  -var="netbox_token=${NETBOX_TOKEN}" \
  -var="router_password=${ROUTER_PASSWORD}"

# Capture outputs
REPORT_IP=$(terraform output -raw report_server_ip)
MCP_IP=$(terraform output -raw mcp_server_ip)
ROUTER_IP=$(terraform output -raw router_ip)
SSH_PORT=$(terraform output -raw ssh_port)
PRIVATE_KEY_PATH=$(realpath "$KEYS_DIR/summit-demo.pem")
REPORT_URL=$(terraform output -raw report_url)

echo ""
echo "  Report server:  $REPORT_IP  ($REPORT_URL)"
echo "  MCP server:     $MCP_IP"
echo "  Cisco router:   $ROUTER_IP"
echo "  SSH port:       $SSH_PORT (Linux VMs) / 22 (router)"
echo "  Private key:    $PRIVATE_KEY_PATH"

cd "$SCRIPT_DIR"

echo ""
echo "========================================================"
echo "  Step 2: Wait for SSH on all VMs"
echo "========================================================"

wait_for_ssh() {
  local ip=$1
  local label=$2
  local port=${3:-$SSH_PORT}
  echo -n "  Waiting for SSH on $label ($ip:$port)..."
  for i in $(seq 1 48); do
    if ssh -o StrictHostKeyChecking=no \
           -o ConnectTimeout=5 \
           -o BatchMode=yes \
           -i "$PRIVATE_KEY_PATH" \
           -p "$port" \
           "ec2-user@$ip" "echo ok" &>/dev/null; then
      echo " ready."
      return 0
    fi
    echo -n "."
    sleep 5
  done
  echo " TIMEOUT (VM may still be initialising — check manually)"
}

wait_for_cisco_ssh() {
  local ip=$1
  # IOS-XE takes 5–10 minutes to boot and start accepting SSH.
  # Use a port check (nc) — password auth makes BatchMode SSH impractical here.
  # 36 attempts × 15s = 9 minutes maximum wait.
  echo -n "  Waiting for Cisco router port 22 ($ip) — IOS-XE boot takes ~5–8 min..."
  for i in $(seq 1 36); do
    if nc -z -w5 "$ip" 22 &>/dev/null; then
      echo " ready."
      return 0
    fi
    echo -n "."
    sleep 15
  done
  echo " TIMEOUT (router may still be booting — check manually with: ssh iosuser@$ip)"
}

wait_for_ssh "$REPORT_IP" "report-server"
wait_for_ssh "$MCP_IP" "mcp-server"
wait_for_cisco_ssh "$ROUTER_IP"

echo ""
echo "========================================================"
echo "  Step 3: Write infra vars for Ansible"
echo "========================================================"

cat > "$SCRIPT_DIR/ansible/vars/infra.yml" << VARSEOF
---
# Generated by setup_infra.sh — do not commit (gitignored)
report_server_host: "$REPORT_IP"
report_server_port: $SSH_PORT
report_server_user: "ec2-user"
report_server_path: "/var/www/html/failover_report.html"
report_url: "$REPORT_URL"
router_ip: "$ROUTER_IP"
router_password: "$ROUTER_PASSWORD"
infra_key_path: "$PRIVATE_KEY_PATH"
VARSEOF

cat > "$SCRIPT_DIR/ansible/vars/network_creds.yml" << VARSEOF
---
# Generated by setup_infra.sh — do not commit (gitignored)
router_username: iosuser
router_password: "$ROUTER_PASSWORD"
router_primary_gw: "172.16.0.1"
router_backup_gw: "172.16.1.1"
VARSEOF

echo "  Written: ansible/vars/infra.yml"
echo "  Written: ansible/vars/network_creds.yml"

echo ""
echo "========================================================"
echo "  Step 4: Register VMs with AAP + update NetBox"
echo "========================================================"

uv run --with requests python setup_aap.py \
  --report-server-ip "$REPORT_IP" \
  --report-server-port "$SSH_PORT" \
  --private-key-path "$PRIVATE_KEY_PATH" \
  --update-router-ip "$ROUTER_IP" \
  --router-password "$ROUTER_PASSWORD"

echo ""
echo "========================================================"
echo "  Done!"
echo "========================================================"

MCP_CMD=$(terraform -chdir="$INFRA_DIR" output -raw mcp_claude_add_command 2>/dev/null || echo "")

cat << SUMMARY

  ┌─────────────────────────────────────────────────────────────┐
  │  Infrastructure Ready                                       │
  ├─────────────────────────────────────────────────────────────┤
  │  Report server                                              │
  │    URL:  $REPORT_URL
  │    SSH:  ssh -i infra/keys/summit-demo.pem -p $SSH_PORT ec2-user@$REPORT_IP
  │                                                             │
  │  MCP server                                                 │
  │    SSH:  ssh -i infra/keys/summit-demo.pem -p $SSH_PORT ec2-user@$MCP_IP
  │                                                             │
  │  Cisco router (gb-brs-rtr-demo)                             │
  │    SSH:  ssh iosuser@$ROUTER_IP
  │    Creds: see ansible/vars/infra.yml (or run ./router_connect.sh)
  │    Note: NetBox gb-brs-rtr-01 primary IP updated to $ROUTER_IP
  └─────────────────────────────────────────────────────────────┘

  To register the NetBox MCP server with Claude Code, run:

  claude mcp add netbox-mcp \\
    -e NETBOX_URL=${NETBOX_URL} \\
    -e NETBOX_TOKEN=${NETBOX_TOKEN} \\
    -e VERIFY_SSL=true \\
    -- ssh -o StrictHostKeyChecking=no \\
           -i $PRIVATE_KEY_PATH \\
           -p $SSH_PORT \\
           ec2-user@$MCP_IP \\
           /home/ec2-user/netbox-mcp/.venv/bin/netbox-mcp-server

  Then restart Claude Code and verify with: claude mcp list

  To tear down all infrastructure: cd infra && terraform destroy
SUMMARY
