output "elastic_ip_address" {
  description = "Fixed Elastic Public IP address for the cluster node"
  value       = module.compute.public_ip
}

output "web_dashboard_url" {
  description = "Urban Environmental Intelligence Web Application URL (nip.io)"
  value       = module.compute.app_url
}

output "api_gateway_url" {
  description = "REST API Gateway URL (nip.io)"
  value       = module.compute.api_url
}

output "api_health_url" {
  description = "API Health Check URL"
  value       = module.compute.api_health_url
}

output "jenkins_ci_cd_url" {
  description = "Jenkins CI/CD Automation Web Console"
  value       = module.compute.jenkins_url
}

output "github_webhook_url" {
  description = "GitHub Webhook Target URL for automated pipeline triggers"
  value       = module.compute.github_webhook_url
}

output "grafana_monitoring_url" {
  description = "Grafana Observability & Metrics Dashboard URL"
  value       = module.compute.grafana_url
}

output "s3_buckets" {
  description = "Persistent S3 Data Lake and Model Registry bucket names"
  value       = module.persistent.bucket_names
}

output "s3_bucket_arns" {
  description = "ARNs of persistent S3 Data Lake buckets"
  value       = module.persistent.bucket_arns
}

output "ssh_command" {
  description = "Convenience SSH command to connect to the node"
  value       = module.compute.ssh_command
}

output "kubeconfig_fetch_command" {
  description = "Command to retrieve the kubeconfig and configure local kubectl"
  value       = module.compute.kubeconfig_fetch_command
}
