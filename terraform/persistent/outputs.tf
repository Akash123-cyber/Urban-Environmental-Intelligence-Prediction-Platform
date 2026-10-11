output "bucket_names" {
  description = "Persistent bucket names; pass these explicitly to the compute root."
  value       = { for key, bucket in aws_s3_bucket.data : key => bucket.bucket }
}

output "bucket_arns" {
  value = { for key, bucket in aws_s3_bucket.data : key => bucket.arn }
}
