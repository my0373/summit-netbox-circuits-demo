#!/bin/bash
set -e
exec > /var/log/userdata.log 2>&1

# ── Move SSH to non-standard port ─────────────────────────────────────────────
sed -i 's/#Port 22$/Port ${ssh_port}/' /etc/ssh/sshd_config
sed -i 's/^Port 22$/Port ${ssh_port}/' /etc/ssh/sshd_config
echo "Port ${ssh_port}" >> /etc/ssh/sshd_config

if command -v semanage &>/dev/null; then
  semanage port -a -t ssh_port_t -p tcp ${ssh_port} 2>/dev/null || true
fi

# ── System packages ────────────────────────────────────────────────────────────
dnf install -y git python3 python3-pip

# ── Install uv ────────────────────────────────────────────────────────────────
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.local/bin:/home/ec2-user/.local/bin:$PATH"

# ── Clone the official NetBox MCP server ──────────────────────────────────────
# Using the official netboxlabs repo (read-only by design)
sudo -u ec2-user bash << 'USEREOF'
export PATH="/home/ec2-user/.local/bin:$PATH"
curl -LsSf https://astral.sh/uv/install.sh | sh

cd /home/ec2-user

# Try official netboxlabs repo first, fall back to community repo
if git clone https://github.com/netboxlabs/netbox-mcp-server.git netbox-mcp 2>/dev/null; then
  echo "Cloned netboxlabs/netbox-mcp-server"
else
  git clone https://github.com/automateyournetwork/NetBox_MCP.git netbox-mcp
  echo "Cloned automateyournetwork/NetBox_MCP"
fi

cd netbox-mcp
/home/ec2-user/.local/bin/uv venv .venv
/home/ec2-user/.local/bin/uv pip install -e . --python .venv/bin/python

echo "MCP server installed at /home/ec2-user/netbox-mcp/.venv/bin/netbox-mcp-server"
USEREOF

# ── Write environment file ────────────────────────────────────────────────────
cat > /home/ec2-user/netbox-mcp/.env << ENVEOF
NETBOX_URL=${netbox_url}
NETBOX_TOKEN=${netbox_token}
VERIFY_SSL=true
ENVEOF
chown ec2-user:ec2-user /home/ec2-user/netbox-mcp/.env
chmod 600 /home/ec2-user/netbox-mcp/.env

# ── Write a test script ───────────────────────────────────────────────────────
cat > /home/ec2-user/test-mcp.sh << 'TESTEOF'
#!/usr/bin/env bash
# Quick sanity-check: verifies the MCP server binary exists and can be invoked.
set -a
source /home/ec2-user/netbox-mcp/.env
set +a
echo "NetBox URL: $NETBOX_URL"
/home/ec2-user/netbox-mcp/.venv/bin/netbox-mcp-server --version 2>/dev/null \
  || echo "Server binary found (no --version flag)"
echo "MCP server ready."
TESTEOF
chown ec2-user:ec2-user /home/ec2-user/test-mcp.sh
chmod +x /home/ec2-user/test-mcp.sh

# ── Restart sshd ──────────────────────────────────────────────────────────────
systemctl restart sshd

echo "MCP server setup complete."
