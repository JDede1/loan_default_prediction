variable "project_id" {
  type        = string
  description = "The GCP project ID"
  default     = "loan-default-mlops"
}

variable "region" {
  description = "Default GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "bucket_name" {
  description = "Name of the GCS bucket for ML artifacts"
  type        = string
}
