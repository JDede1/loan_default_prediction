output "bucket_name" {
  description = "The name of the GCS bucket"
  value       = google_storage_bucket.artifacts.name
}

output "bucket_url" {
  description = "The GCS URL of the bucket"
  value       = "gs://${google_storage_bucket.artifacts.name}"
}
