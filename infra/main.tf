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

# ── SSH Key Pair (single key pair shared across both VMs) ─────────────────────

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

# ── Security Group: Report Server ──────────────────────────────────────────────

resource "aws_security_group" "report_server" {
  name        = "RedhatSummitEDADemo-report-server"
  description = "Summit demo report web server - HTTP redirect, HTTPS, non-standard SSH"

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP (redirect to HTTPS)"
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS report server"
  }

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

# ── Security Group: MCP Server ─────────────────────────────────────────────────

resource "aws_security_group" "mcp_server" {
  name        = "RedhatSummitEDADemo-mcp-server"
  description = "Summit demo NetBox MCP server - non-standard SSH only (stdio over SSH)"

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
    description = "All outbound (NetBox API calls)"
  }
}

# ── EC2 Instance: Report Server ────────────────────────────────────────────────

resource "aws_instance" "report_server" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.summit_demo.key_name
  vpc_security_group_ids = [aws_security_group.report_server.id]

  user_data = templatefile("${path.module}/userdata.sh.tpl", {
    ssh_port = var.ssh_port
  })

  root_block_device {
    volume_size = 30
    volume_type = "gp3"

    tags = {
      Name  = "RedhatSummitEDADemo-report"
      owner = "myork@netboxlabs.com"
    }
  }
}

# ── EC2 Instance: MCP Server ───────────────────────────────────────────────────

resource "aws_instance" "mcp_server" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.mcp_instance_type
  key_name               = aws_key_pair.summit_demo.key_name
  vpc_security_group_ids = [aws_security_group.mcp_server.id]

  user_data = templatefile("${path.module}/userdata_mcp.sh.tpl", {
    ssh_port      = var.ssh_port
    netbox_url    = var.netbox_url
    netbox_token  = var.netbox_token
  })

  root_block_device {
    volume_size = 30
    volume_type = "gp3"

    tags = {
      Name  = "RedhatSummitEDADemo-mcp"
      owner = "myork@netboxlabs.com"
    }
  }
}

# ── Elastic IPs ────────────────────────────────────────────────────────────────

resource "aws_eip" "report_server" {
  instance = aws_instance.report_server.id
  domain   = "vpc"
}

resource "aws_eip" "mcp_server" {
  instance = aws_instance.mcp_server.id
  domain   = "vpc"
}
