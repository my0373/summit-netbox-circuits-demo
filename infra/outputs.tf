output "public_ip" {
  description = "Public IP address of the report server"
  value       = aws_eip.summit_demo.public_ip
}

output "ssh_port" {
  description = "SSH port"
  value       = var.ssh_port
}

output "ssh_connect" {
  description = "SSH command to connect to the report server"
  value       = "ssh -i infra/keys/summit-demo.pem -p ${var.ssh_port} ec2-user@${aws_eip.summit_demo.public_ip}"
}

output "report_url" {
  description = "URL of the failover report"
  value       = "https://${aws_eip.summit_demo.public_ip}/failover_report.html"
}

output "private_key_path" {
  description = "Path to the generated private key"
  value       = "${path.module}/keys/summit-demo.pem"
}
