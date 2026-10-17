output "bucket_names" {
  description = "Persistent bucket names; pass these explicitly to the compute root."
  value       = { for key, bucket in aws_s3_bucket.data : key => bucket.bucket }
}

output "bucket_arns" {
  value = { for key, bucket in aws_s3_bucket.data : key => bucket.arn }
}

output "elastic_ip_id" {
  description = "Allocation ID of the persistent Elastic IP (will not change on compute destroy/recreate)"
  value       = aws_eip.node.id
}

output "elastic_ip_address" {
  description = "Public IP address of the persistent Elastic IP"
  value       = aws_eip.node.public_ip
}
