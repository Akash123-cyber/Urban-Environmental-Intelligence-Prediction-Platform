variable "region" {
  description = "AWS region for infrastructure deployment"
  type        = string
  default     = "ap-south-1"
}

variable "project" {
  description = "Project name identifier for resource tagging and naming"
  type        = string
  default     = "urban-eipp"
}

variable "environment" {
  description = "Target deployment environment (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "key_name" {
  description = "Name of the AWS EC2 SSH KeyPair"
  type        = string
  default     = "urban-eipp-key"
}

variable "instance_type" {
  description = "EC2 instance type for single-node K3s cluster"
  type        = string
  default     = "t3.medium"
}

variable "root_volume_gb" {
  description = "Size of EBS root volume in GB"
  type        = number
  default     = 16
}

variable "admin_cidrs" {
  description = "Allowed CIDR blocks for administrative access (SSH 22 & K8s API 6443)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "elastic_ip_id" {
  description = "Allocation ID of persistent Elastic IP. If empty, the persistent module creates or reuses the tagged EIP."
  type        = string
  default     = "eipalloc-0af00b69e28da8468"
}

variable "docker_registry" {
  description = "Docker Hub repository / registry prefix (e.g. docker.io/akash123cyber)"
  type        = string
  default     = "docker.io/akash123cyber"
}

variable "docker_tag" {
  description = "Docker image tag to pull from Docker Hub"
  type        = string
  default     = "latest"
}

variable "admin_email" {
  description = "Default admin user email for initial platform seeding"
  type        = string
  default     = "admin@example.com"
}

variable "openaq_api_key" {
  description = "Optional OpenAQ API key for enhanced rate limits"
  type        = string
  default     = ""
}

variable "raw_retention_days" {
  description = "Lifecycle retention days for raw telemetry in S3"
  type        = number
  default     = 90
}

variable "processed_retention_days" {
  description = "Lifecycle retention days for harmonized parquet in S3"
  type        = number
  default     = 365
}
