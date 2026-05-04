#!/usr/bin/env bash
# router_connect.sh — shows how to SSH to the Cisco router and check its config

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

ROUTER_IP=""
ROUTER_PASSWORD=""
if [ -f "$SCRIPT_DIR/ansible/vars/infra.yml" ]; then
  ROUTER_IP=$(grep 'router_ip:' "$SCRIPT_DIR/ansible/vars/infra.yml" | awk '{print $2}' | tr -d '"')
  ROUTER_PASSWORD=$(grep 'router_password:' "$SCRIPT_DIR/ansible/vars/infra.yml" | awk '{print $2}' | tr -d '"')
fi
ROUTER_IP="${ROUTER_IP:-<router_ip>}"
ROUTER_PASSWORD="${ROUTER_PASSWORD:-<run setup_infra.sh first>}"

echo ""
echo "  Cisco Router — gb-brs-rtr-demo"
echo "  ──────────────────────────────────"
echo ""
echo "  Connect:"
echo "    ssh iosuser@$ROUTER_IP"
echo "    password: $ROUTER_PASSWORD"
echo ""
echo "  ── Verify demo route state ────────────────────────────────────────────"
echo ""
echo "    show running-config | include ip route"
echo ""
echo "    Expected BEFORE failover (after ./reset.sh):"
echo "      ip route 0.0.0.0 0.0.0.0 172.31.32.1   ← AWS VPC gateway (always present)"
echo "      ip route 0.0.0.0 0.0.0.0 172.16.0.1    ← demo PRIMARY route"
echo ""
echo "    Expected AFTER failover:"
echo "      ip route 0.0.0.0 0.0.0.0 172.31.32.1   ← AWS VPC gateway (always present)"
echo "      ip route 0.0.0.0 0.0.0.0 172.16.1.1    ← demo BACKUP route"
echo ""
echo "  Note: 172.31.32.1 is the AWS VPC gateway — it's always here and is"
echo "        needed for the router to reach AAP. It won't affect the demo."
echo "        Use 'show run | include ip route' (not 'show ip route 0.0.0.0')"
echo "        to verify the demo routes, as the AWS route is the active path."
echo ""
echo "  ── Other useful commands ───────────────────────────────────────────────"
echo ""
echo "    show version"
echo "      → IOS-XE version and uptime"
echo ""
echo "    show running-config"
echo "      → Full running config"
echo ""
