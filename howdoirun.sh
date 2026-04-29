#!/usr/bin/env bash
# howdoirun.sh — how to do a clean reset of the demo platform

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

REPORT_URL=""
if [ -f "$SCRIPT_DIR/ansible/vars/infra.yml" ]; then
  REPORT_URL=$(grep 'report_url:' "$SCRIPT_DIR/ansible/vars/infra.yml" | awk '{print $2}' | tr -d '"')
fi
REPORT_URL="${REPORT_URL:-https://<report_server_ip>/failover_report.html}"

echo ""
echo "  Clean reset (run before every demo)"
echo "  ─────────────────────────────────────"
echo ""
echo "  1. Reset circuits + router route:"
echo "       ./reset.sh"
echo ""
echo "  2. Confirm Visual Explorer shows all circuits active."
echo ""
echo "  3. Report URL (for after the demo):"
echo "       $REPORT_URL"
echo ""
echo "  ─────────────────────────────────────"
echo "  If AAP or EDA need reconfiguring:"
echo "       uv run --with requests python setup_aap.py"
echo ""
echo "  If infra needs reprovisioning:"
echo "       ./setup_infra.sh"
echo ""
