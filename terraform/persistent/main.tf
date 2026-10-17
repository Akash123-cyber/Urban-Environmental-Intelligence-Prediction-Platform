data "aws_caller_identity" "current" {}

locals {
  prefix = lower("${var.project}-${data.aws_caller_identity.current.account_id}")
  buckets = {
    raw       = "${local.prefix}-raw"
    processed = "${local.prefix}-processed"
    models    = "${local.prefix}-models"
  }
}

resource "aws_s3_bucket" "data" {
  for_each      = local.buckets
  bucket        = each.value
  force_destroy = true

  lifecycle {
    prevent_destroy = false
  }

  tags = {
    Project     = var.project
    Environment = var.environment
    DataClass   = each.key
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  for_each                = aws_s3_bucket.data
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  for_each = aws_s3_bucket.data
  bucket   = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "data" {
  for_each = aws_s3_bucket.data
  bucket   = each.value.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.data["raw"].id
  rule {
    id     = "expire-old-raw-objects"
    status = "Enabled"
    filter {}
    expiration { days = var.raw_retention_days }
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "processed" {
  bucket = aws_s3_bucket.data["processed"].id
  rule {
    id     = "expire-old-processed-objects"
    status = "Enabled"
    filter {}
    expiration { days = var.processed_retention_days }
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}
