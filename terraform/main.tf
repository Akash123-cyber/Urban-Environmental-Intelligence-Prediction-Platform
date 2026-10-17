provider "aws" {
  region = var.region
}

# ==============================================================================
# Persistent Infrastructure: S3 Data Lake Buckets & Persistent Elastic IP
# ==============================================================================
module "persistent" {
  source                   = "./modules/persistent"
  project                  = var.project
  environment              = var.environment
  raw_retention_days       = var.raw_retention_days
  processed_retention_days = var.processed_retention_days
}

# ==============================================================================
# Ephemeral Compute Node: EC2, IAM, K3s, Ingress, CI/CD, Observability
# ==============================================================================
module "compute" {
  source              = "./modules/compute"
  project             = var.project
  environment         = var.environment
  region              = var.region
  key_name            = var.key_name
  instance_type       = var.instance_type
  root_volume_gb      = var.root_volume_gb
  admin_cidrs         = var.admin_cidrs
  elastic_ip_id       = var.elastic_ip_id != "" ? var.elastic_ip_id : module.persistent.elastic_ip_id
  bucket_names        = module.persistent.bucket_names
  docker_registry     = var.docker_registry
  docker_tag          = var.docker_tag
  admin_email         = var.admin_email
  openaq_api_key      = var.openaq_api_key
  dashboard_json_file = "${path.module}/../monitoring/dashboards/urban-health.json"

  depends_on = [module.persistent]
}
