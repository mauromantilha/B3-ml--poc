variable "project_id" {
  type        = string
  description = "GCP project id"
}

variable "region" {
  type        = string
  description = "Primary GCP region for Cloud Run and GCS"
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "dev"
}

variable "project_slug" {
  type        = string
  description = "Short slug used in resource naming"
  default     = "b3quant"
}

variable "service_image_map" {
  type        = map(string)
  description = "Container image per Cloud Run service key"
  default     = {}
}

variable "gcs_curated_bucket_name" {
  type        = string
  description = "Optional override for the curated GCS bucket"
  default     = null
}

variable "bigquery_datasets" {
  type        = list(string)
  description = "Analytics datasets"
  default = [
    "raw_mirror",
    "feature_store",
    "forecasting",
    "backtests",
    "portfolio_marts",
  ]
}

variable "secret_ids" {
  type        = list(string)
  description = "Secret Manager ids to create"
  default = [
    "database-url",
    "supabase-anon-key",
    "supabase-service-role-key",
    "upstash-redis-rest-token",
    "qstash-token",
    "qstash-current-signing-key",
    "qstash-next-signing-key",
    "r2-access-key-id",
    "r2-secret-access-key",
    "edge-shared-secret",
  ]
}
