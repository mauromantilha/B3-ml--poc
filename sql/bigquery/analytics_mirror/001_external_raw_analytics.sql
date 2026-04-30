CREATE OR REPLACE EXTERNAL TABLE `<project-id>.<external_dataset>.quotes_ext`
WITH CONNECTION `<biglake-connection-id>`
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://<gcs-curated-bucket>/curated/external_raw_analytics/quotes/*'],
  hive_partition_uri_prefix = 'gs://<gcs-curated-bucket>/curated/external_raw_analytics/quotes/',
  require_hive_partition_filter = FALSE
);

CREATE OR REPLACE EXTERNAL TABLE `<project-id>.<external_dataset>.instruments_ext`
WITH CONNECTION `<biglake-connection-id>`
OPTIONS (
  format = 'PARQUET',
  uris = ['gs://<gcs-curated-bucket>/curated/external_raw_analytics/instruments/*'],
  hive_partition_uri_prefix = 'gs://<gcs-curated-bucket>/curated/external_raw_analytics/instruments/',
  require_hive_partition_filter = FALSE
);