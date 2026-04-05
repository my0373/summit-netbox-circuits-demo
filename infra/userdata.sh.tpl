#!/bin/bash
set -e

# ── Move SSH to non-standard port ─────────────────────────────────────────────
sed -i 's/#Port 22$/Port ${ssh_port}/' /etc/ssh/sshd_config
sed -i 's/^Port 22$/Port ${ssh_port}/' /etc/ssh/sshd_config
echo "Port ${ssh_port}" >> /etc/ssh/sshd_config

# Apply SELinux context for non-standard SSH port
if command -v semanage &>/dev/null; then
  semanage port -a -t ssh_port_t -p tcp ${ssh_port} 2>/dev/null || true
fi

# ── Install nginx ──────────────────────────────────────────────────────────────
dnf install -y nginx

# ── Self-signed TLS certificate ───────────────────────────────────────────────
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/server.key \
  -out    /etc/nginx/ssl/server.crt \
  -subj   "/C=GB/ST=England/L=Bristol/O=NetBox Labs/CN=summit-demo"

# ── nginx config ───────────────────────────────────────────────────────────────
cat > /etc/nginx/conf.d/report.conf << 'NGINXEOF'
server {
    listen 80 default_server;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl default_server;
    server_name _;

    ssl_certificate     /etc/nginx/ssl/server.crt;
    ssl_certificate_key /etc/nginx/ssl/server.key;
    ssl_protocols       TLSv1.2 TLSv1.3;

    root  /var/www/html;
    index failover_report.html index.html;

    location / {
        try_files $uri $uri/ =404;
        add_header Cache-Control "no-store";
    }
}
NGINXEOF

# Remove default nginx config
rm -f /etc/nginx/conf.d/default.conf

# ── Web root + placeholder ─────────────────────────────────────────────────────
mkdir -p /var/www/html
cat > /var/www/html/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Summit Demo Report Server</title>
<style>
  body { font-family: sans-serif; background: #0D1B2A; color: #e2e8f0;
         display: flex; align-items: center; justify-content: center;
         height: 100vh; margin: 0; }
  .box { text-align: center; }
  h1 { color: #00C2A8; }
  p { color: #B0BCCC; }
</style>
</head>
<body>
<div class="box">
  <h1>NetBox Labs — Summit Demo</h1>
  <p>No failover report yet. Trigger a circuit failure to generate one.</p>
</div>
</body>
</html>
HTMLEOF

# ── Permissions (nginx needs to read files) ───────────────────────────────────
chown -R nginx:nginx /var/www/html
chmod -R 755 /var/www/html

# ── Start services ─────────────────────────────────────────────────────────────
systemctl enable nginx
systemctl start nginx
systemctl restart sshd
