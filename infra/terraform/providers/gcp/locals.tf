locals {
  service_keys = [
    "api",
    "worker-ingestion",
    "worker-feature-store",
    "worker-forecast",
    "worker-simulation",
    "worker-eod",
    "dashboard-streamlit",
  ]

  resource_prefix = "${var.project_slug}-${var.environment}"

  cloud_run_service_names = {
    for service in local.service_keys : service => "${local.resource_prefix}-${service}"
  }

  curated_bucket_name = coalesce(var.gcs_curated_bucket_name, "${local.resource_prefix}-gcs-curated")

  common_roles = [
    "roles/logging.logWriter",
    "roles/secretmanager.secretAccessor",
    "roles/cloudtrace.agent",
    "roles/storage.objectAdmin",
    "roles/bigquery.dataEditor",
  ]

  project_iam_pairs = {
    for pair in setproduct(local.service_keys, local.common_roles) :
    "${pair[0]}::${pair[1]}" => {
      service = pair[0]
      role    = pair[1]
    }
  }

  secret_env_bindings = {
    B3_DATABASE_URL               = "database-url"
    B3_SUPABASE_ANON_KEY          = "supabase-anon-key"
    B3_SUPABASE_SERVICE_ROLE_KEY  = "supabase-service-role-key"
    B3_UPSTASH_REDIS_REST_TOKEN   = "upstash-redis-rest-token"
    B3_QSTASH_TOKEN               = "qstash-token"
    B3_QSTASH_CURRENT_SIGNING_KEY = "qstash-current-signing-key"
    B3_QSTASH_NEXT_SIGNING_KEY    = "qstash-next-signing-key"
    B3_R2_ACCESS_KEY_ID           = "r2-access-key-id"
    B3_R2_SECRET_ACCESS_KEY       = "r2-secret-access-key"
    B3_EDGE_SHARED_SECRET         = "edge-shared-secret"
  }

  static_env = {
    B3_ENVIRONMENT                      = var.environment
    B3_PROJECT_SLUG                     = var.project_slug
    B3_GCP_PROJECT_ID                   = var.project_id
    B3_GCP_REGION                       = var.region
    B3_GCS_BUCKET_CURATED               = local.curated_bucket_name
    B3_BIGQUERY_DATASET_RAW_MIRROR      = "raw_mirror"
    B3_BIGQUERY_DATASET_FEATURE_STORE   = "feature_store"
    B3_BIGQUERY_DATASET_FORECASTING     = "forecasting"
    B3_BIGQUERY_DATASET_BACKTESTS       = "backtests"
    B3_BIGQUERY_DATASET_PORTFOLIO_MARTS = "portfolio_marts"
  }
}
