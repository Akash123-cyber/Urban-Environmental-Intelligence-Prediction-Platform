#!/usr/bin/env bash
# ==============================================================================
# Urban EIPP — One-Click Automated Provisioning
# Provisions S3 Data Lake, EIP, EC2 Node, K3s, Jenkins, Grafana, Microservices
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

echo "=========================================================="
echo "Urban EIPP — One-Click Infrastructure Provisioning"
echo "=========================================================="
cd "$TERRAFORM_DIR"

echo "[1/4] Initializing Terraform root module..."
terraform init -upgrade

echo "[2/4] Applying Infrastructure Plan..."
terraform apply -auto-approve

echo "[3/4] Fetching Infrastructure Outputs..."
PUBLIC_IP=$(terraform output -raw elastic_ip_address)
APP_URL=$(terraform output -raw web_dashboard_url)
API_URL=$(terraform output -raw api_gateway_url)
JENKINS_URL=$(terraform output -raw jenkins_ci_cd_url)
WEBHOOK_URL=$(terraform output -raw github_webhook_url)
GRAFANA_URL=$(terraform output -raw grafana_monitoring_url)

echo "=========================================================="
echo "Infrastructure Provisioned Successfully!"
echo "Fixed Elastic IP:      $PUBLIC_IP"
echo "Web Dashboard:         $APP_URL"
echo "REST API Gateway:      $API_URL"
echo "Jenkins CI/CD:         $JENKINS_URL"
echo "GitHub Webhook Target: $WEBHOOK_URL"
echo "Grafana Monitoring:    $GRAFANA_URL"
echo "=========================================================="
echo "Note: Cloud-Init is now bootstrapping K3s, Ingress-Nginx, Jenkins, and Grafana."
echo "You can tail the bootstrap progress via:"
echo "  ssh -i ~/.ssh/urban-eipp-key.pem ubuntu@$PUBLIC_IP 'sudo tail -f /var/log/user-data.log'"
