data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "availability-zone"
    values = ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d", "us-east-1f"]
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  name = "${var.project}-${var.environment}"
  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "random_password" "postgres" {
  length  = 20
  special = false
}

resource "random_password" "jwt" {
  length  = 32
  special = false
}

resource "random_password" "admin" {
  length  = 24
  special = false
}

resource "aws_security_group" "node" {
  name        = "${local.name}-node"
  description = "Urban EIPP demo node"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP application ingress"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTPS application ingress"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "Jenkins CI/CD and GitHub Webhook ingress"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  dynamic "ingress" {
    for_each = var.admin_cidrs
    content {
      description = "SSH from administrator"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }
  dynamic "ingress" {
    for_each = var.admin_cidrs
    content {
      description = "Kubernetes API from administrator"
      from_port   = 6443
      to_port     = 6443
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_iam_role" "node" {
  name = "${local.name}-node-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "ec2.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "s3" {
  name = "${local.name}-s3-access"
  role = aws_iam_role.node.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = ["s3:ListBucket"],
        Resource = [for name in values(var.bucket_names) : "arn:aws:s3:::${name}"]
      },
      {
        Effect   = "Allow",
        Action   = ["s3:GetObject"],
        Resource = [for name in values(var.bucket_names) : "arn:aws:s3:::${name}/*"]
      },
      {
        Effect   = "Allow",
        Action   = ["s3:PutObject", "s3:AbortMultipartUpload"],
        Resource = flatten([for key, name in var.bucket_names : key == "models" ? [] : ["arn:aws:s3:::${name}/*"]])
      }
    ]
  })
}

resource "aws_iam_instance_profile" "node" {
  name = "${local.name}-node-profile"
  role = aws_iam_role.node.name
  tags = local.tags
}

resource "aws_eip" "node" {
  domain = "vpc"
  tags   = merge(local.tags, { Name = "${local.name}-eip" })
}

resource "aws_instance" "node" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = sort(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids      = [aws_security_group.node.id]
  key_name                    = var.key_name
  iam_instance_profile        = aws_iam_instance_profile.node.name
  associate_public_ip_address = true

  user_data = templatefile("${path.module}/templates/user_data.sh.tftpl", {
    public_ip         = aws_eip.node.public_ip
    region            = var.region
    raw_bucket        = var.bucket_names["raw"]
    processed_bucket  = var.bucket_names["processed"]
    model_bucket      = var.bucket_names["models"]
    postgres_password = random_password.postgres.result
    jwt_secret        = random_password.jwt.result
    admin_email       = var.admin_email
    admin_password    = random_password.admin.result
    openaq_api_key    = var.openaq_api_key
    docker_registry   = var.docker_registry
    docker_tag        = var.docker_tag
  })

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_size           = var.root_volume_gb
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }
  tags = merge(local.tags, { Name = "${local.name}-node" })
}

resource "aws_eip_association" "node" {
  instance_id   = aws_instance.node.id
  allocation_id = aws_eip.node.id
}
