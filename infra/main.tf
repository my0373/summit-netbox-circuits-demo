terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Name  = "RedhatSummitEDADemo"
      owner = "myork@netboxlabs.com"
    }
  }
}

# ── SSH Key Pair (randomly generated) ─────────────────────────────────────────

resource "tls_private_key" "summit_demo" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "summit_demo" {
  key_name   = var.key_name
  public_key = tls_private_key.summit_demo.public_key_openssh
}

# Write keys locally (gitignored)
resource "local_sensitive_file" "private_key_pem" {
  content         = tls_private_key.summit_demo.private_key_pem
  filename        = "${path.module}/keys/summit-demo.pem"
  file_permission = "0600"
}

resource "local_file" "public_key" {
  content  = tls_private_key.summit_demo.public_key_openssh
  filename = "${path.module}/keys/summit-demo.pub"
}

# ── Latest Amazon Linux 2023 AMI ──────────────────────────────────────────────

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ── Security Group ─────────────────────────────────────────────────────────────

resource "aws_security_group" "summit_demo" {
  name        = "RedhatSummitEDADemo-report-server"
  description = "Summit demo report web server — HTTP redirect, HTTPS, non-standard SSH"

  # HTTP — redirect to HTTPS
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP (redirect to HTTPS)"
  }

  # HTTPS — serve the failover report
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS report server"
  }

  # Non-standard SSH — for AAP and local access
  ingress {
    from_port   = var.ssh_port
    to_port     = var.ssh_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH on non-standard port ${var.ssh_port}"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound"
  }
}

# ── EC2 Instance ───────────────────────────────────────────────────────────────

resource "aws_instance" "summit_demo" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.summit_demo.key_name
  vpc_security_group_ids = [aws_security_group.summit_demo.id]

  user_data = templatefile("${path.module}/userdata.sh.tpl", {
    ssh_port = var.ssh_port
  })

  root_block_device {
    volume_size = 8
    volume_type = "gp3"

    tags = {
      Name  = "RedhatSummitEDADemo"
      owner = "myork@netboxlabs.com"
    }
  }
}

# ── Elastic IP (persistent public IP) ────────────────────────────────────────

resource "aws_eip" "summit_demo" {
  instance = aws_instance.summit_demo.id
  domain   = "vpc"
}
