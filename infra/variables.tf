variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-west-2"  # London — closest to GB-Bristol demo theme
}

variable "ssh_port" {
  description = "Non-standard SSH port (used on all VMs)"
  type        = number
  default     = 2222
}

variable "instance_type" {
  description = "EC2 instance type for the report server"
  type        = string
  default     = "t3.micro"
}

variable "mcp_instance_type" {
  description = "EC2 instance type for the MCP server"
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "AWS EC2 key pair name"
  type        = string
  default     = "summit-demo-2026"
}

variable "netbox_url" {
  description = "NetBox instance URL for the MCP server"
  type        = string
  default     = "https://ryvr4514.cloud.netboxapp.com"
}

variable "netbox_token" {
  description = "NetBox API token for the MCP server (read-only)"
  type        = string
  sensitive   = true
  default     = ""
}
