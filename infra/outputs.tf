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

# ── MCP Server ─────────────────────────────────────────────────────────────────

output "mcp_server_ip" {
  description = "Public IP of the MCP server"
  value       = aws_eip.mcp_server.public_ip
}

output "mcp_server_ssh" {
  description = "SSH command for the MCP server"
  value       = "ssh -i infra/keys/summit-demo.pem -p ${var.ssh_port} ec2-user@${aws_eip.mcp_server.public_ip}"
}

output "mcp_claude_add_command" {
  description = "Command to register the NetBox MCP server with Claude Code"
  value       = <<-EOT
    claude mcp add netbox-mcp \
      -e NETBOX_URL=${var.netbox_url} \
      -e NETBOX_TOKEN=<your-token> \
      -e VERIFY_SSL=true \
      -- ssh -o StrictHostKeyChecking=no \
             -i ${path.module}/keys/summit-demo.pem \
             -p ${var.ssh_port} \
             ec2-user@${aws_eip.mcp_server.public_ip} \
             /home/ec2-user/netbox-mcp/.venv/bin/netbox-mcp-server
  EOT
}

# ── Shared ─────────────────────────────────────────────────────────────────────

output "ssh_port" {
  description = "SSH port used on all VMs"
  value       = var.ssh_port
}

output "private_key_path" {
  description = "Path to the generated SSH private key"
  value       = "${path.module}/keys/summit-demo.pem"
}
