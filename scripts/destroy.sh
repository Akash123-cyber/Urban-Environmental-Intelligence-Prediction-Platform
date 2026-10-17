#!/usr/bin/env bash
# ==============================================================================
# Urban EIPP — Safe Compute Infrastructure Teardown
# Destroys ephemeral EC2 compute node while preserving Elastic IP & S3 Data Lake
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

echo "=========================================================="
echo "Urban EIPP — Safe Compute Teardown"
echo "Preserving Static Elastic IP and S3 Data Lake Buckets"
echo "=========================================================="
cd "$TERRAFORM_DIR"

echo "Tearing down compute module resources (EC2, SG, IAM, EIP association)..."
terraform destroy -target=module.compute -auto-approve

echo "=========================================================="
echo "Compute resources destroyed successfully."
echo "Elastic IP address and S3 Data Lake remain 100% intact."
echo "Run ./scripts/provision.sh to re-provision the compute node."
echo "=========================================================="
