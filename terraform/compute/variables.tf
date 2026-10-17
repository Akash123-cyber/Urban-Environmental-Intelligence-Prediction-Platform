variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "project" {
  type    = string
  default = "urban-eipp"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "admin_cidrs" {
  description = "Trusted CIDR ranges for SSH and Kubernetes API access."
  type        = list(string)
  validation {
    condition     = length(var.admin_cidrs) > 0 && alltrue([for cidr in var.admin_cidrs : can(cidrhost(cidr, 0))])
    error_message = "Set one or more valid admin CIDRs."
  }
}

variable "bucket_names" {
  description = "Map from persistent root output: raw, processed, models."
  type        = map(string)
  validation {
    condition     = alltrue([for key in ["raw", "processed", "models"] : contains(keys(var.bucket_names), key)])
    error_message = "bucket_names must contain raw, processed, and models."
  }
}

variable "instance_type" {
  type    = string
  default = "t3.medium"
}

variable "root_volume_gb" {
  type    = number
  default = 30
}

variable "key_name" {
  type = string
}

variable "docker_registry" {
  description = "Docker Hub repository / registry prefix (e.g., docker.io/yourusername)"
  type        = string
  default     = "docker.io/urbanplatform"
}

variable "docker_tag" {
  description = "Docker image tag to pull from Docker Hub (e.g., git commit SHA or v1.0.0)"
  type        = string
  default     = "latest"
}

variable "admin_email" {
  description = "Default admin user email for the platform"
  type        = string
  default     = "admin@example.com"
}

variable "openaq_api_key" {
  description = "Optional OpenAQ API key (leave empty if not using OpenAQ)"
  type        = string
  default     = ""
}

variable "elastic_ip_id" {
  description = "Optional Allocation ID of an existing persistent Elastic IP (e.g. from terraform/persistent). If set, compute attaches this EIP so the IP address remains fixed across compute destruction and re-creation."
  type        = string
  default     = ""
}
