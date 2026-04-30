output "cloud_run_services" {
  value = {
    for key, service in google_cloud_run_v2_service.services : key => {
      name = service.name
      uri  = service.uri
    }
  }
}

output "curated_bucket_name" {
  value = google_storage_bucket.curated.name
}

output "bigquery_datasets" {
  value = [for dataset in google_bigquery_dataset.datasets : dataset.dataset_id]
}

output "secret_names" {
  value = [for secret in google_secret_manager_secret.platform : secret.secret_id]
}
