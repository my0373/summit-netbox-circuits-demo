# ── Report Server ──────────────────────────────────────────────────────────────

output "report_server_ip" {
  description = "Public IP of the report server"
  value       = aws_eip.report_server.public_ip
}

output "report_url" {
  description = "URL of the failover report"
  value       = "https://${aws_eip.report_server.public_ip}/failover_report.html"
}

output "report_server_ssh" {
  description = "SSH command for the report server"
  value       = "ssh -i infra/keys/summit-demo.pem -p ${var.ssh_port} ec2-user@${aws_eip.report_server.public_ip}"
}

# ── Cisco Router ───────────────────────────────────────────────────────────────

output "router_ip" {
  description = "Public IP of the Cisco demo router"
  value       = aws_eip.cisco_router.public_ip
}

output "router_ssh" {
  description = "SSH command for the Cisco router (local IOS user — no key pair)"
  value       = "ssh iosuser@${aws_eip.cisco_router.public_ip}  # password: iospass"
}

# ── Shared ─────────────────────────────────────────────────────────────────────

output "ssh_port" {
  description = "SSH port used on all Linux VMs (router uses standard port 22)"
  value       = var.ssh_port
}

output "private_key_path" {
  description = "Path to the generated SSH private key"
  value       = "${path.module}/keys/summit-demo.pem"
}
