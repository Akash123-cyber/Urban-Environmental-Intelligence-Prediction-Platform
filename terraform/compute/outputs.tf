output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.node.id
}

output "public_ip" {
  description = "Elastic IP address attached to the single-node k3s cluster"
  value       = aws_eip.node.public_ip
}

output "private_ip" {
  description = "Private IP address of the EC2 instance"
  value       = aws_instance.node.private_ip
}

output "app_url" {
  description = "Public URL for React Frontend Dashboard via nip.io"
  value       = "http://app.${aws_eip.node.public_ip}.nip.io"
}

output "api_url" {
  description = "Public URL for Express API Service via nip.io"
  value       = "http://api.${aws_eip.node.public_ip}.nip.io"
}

output "api_health_url" {
  description = "Health check endpoint for Express API"
  value       = "http://api.${aws_eip.node.public_ip}.nip.io/health"
}

output "ssh_command" {
  description = "Convenience SSH command to connect to the node"
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_eip.node.public_ip}"
}

output "kubeconfig_fetch_command" {
  description = "Command to retrieve the kubeconfig and configure local kubectl"
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_eip.node.public_ip} 'sudo cat /etc/rancher/k3s/k3s.yaml' | sed 's/127.0.0.1/${aws_eip.node.public_ip}/' > kubeconfig && export KUBECONFIG=$(pwd)/kubeconfig"
}

output "database_password" {
  description = "Auto-generated PostgreSQL master password"
  value       = random_password.postgres.result
  sensitive   = true
}

output "jwt_secret" {
  description = "Auto-generated JWT secret for API token verification"
  value       = random_password.jwt.result
  sensitive   = true
}

output "admin_password" {
  description = "Auto-generated initial admin password seeded for API authentication"
  value       = random_password.admin.result
  sensitive   = true
}

