provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "cloudbuild.googleapis.com",
    "logging.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "sqladmin.googleapis.com",
    "cloudtrace.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "curated" {
  name                        = local.curated_bucket_name
  location                    = var.region
  project                     = var.project_id
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.required]
}

resource "google_bigquery_dataset" "datasets" {
  for_each = toset(var.bigquery_datasets)

  dataset_id                 = each.value
  project                    = var.project_id
  location                   = var.region
  delete_contents_on_destroy = false

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "platform" {
  for_each = toset(var.secret_ids)

  project   = var.project_id
  secret_id = "${local.resource_prefix}-${each.value}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_service_account" "cloud_run" {
  for_each = toset(local.service_keys)

  project      = var.project_id
  account_id   = substr("svc-${var.environment}-${each.value}", 0, 30)
  display_name = "Cloud Run ${each.value}"
}

resource "google_project_iam_member" "cloud_run_common_roles" {
  for_each = local.project_iam_pairs

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.cloud_run[each.value.service].email}"
}

resource "google_cloud_run_v2_service" "services" {
  for_each = local.cloud_run_service_names

  name                = each.value
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.cloud_run[each.key].email
    timeout                          = each.key == "dashboard-streamlit" ? "900s" : "300s"
    max_instance_request_concurrency = each.key == "dashboard-streamlit" ? 20 : 80

    scaling {
      min_instance_count = 0
      max_instance_count = contains(["api", "dashboard-streamlit"], each.key) ? 10 : 4
    }

    containers {
      image = lookup(var.service_image_map, each.key, "us-docker.pkg.dev/cloudrun/container/hello")

      dynamic "env" {
        for_each = local.static_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.secret_env_bindings
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.platform[env.value].secret_id
              version = "latest"
            }
          }
        }
      }

      resources {
        limits = {
          cpu    = each.key == "dashboard-streamlit" ? "2" : "1"
          memory = each.key == "dashboard-streamlit" ? "2Gi" : "1Gi"
        }
      }
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  depends_on = [
    google_project_service.required,
    google_project_iam_member.cloud_run_common_roles,
  ]
}
