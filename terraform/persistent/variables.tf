variable "region" {
  description = "AWS region for persistent data buckets."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  type    = string
  default = "urban-eipp"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "raw_retention_days" {
  type    = number
  default = 90
}

variable "processed_retention_days" {
  type    = number
  default = 365
}
