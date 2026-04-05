variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-west-2"  # London — closest to GB-Bristol demo theme
}

variable "ssh_port" {
  description = "Non-standard SSH port"
  type        = number
  default     = 2222
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "AWS EC2 key pair name"
  type        = string
  default     = "summit-demo-2026"
}
