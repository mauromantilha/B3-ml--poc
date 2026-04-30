CREATE TABLE IF NOT EXISTS `<project-id>.<native_dataset>.quotes` (
  reference_date DATE,
  processing_date DATE,
  ticker STRING,
  market_type STRING,
  close_price NUMERIC,
  source_checksum STRING,
  lineage_source_uri STRING,
  mirrored_at TIMESTAMP
)
PARTITION BY DATE(reference_date)
CLUSTER BY market_type, ticker;

MERGE `<project-id>.<native_dataset>.quotes` T
USING (
  SELECT
    reference_date,
    processing_date,
    ticker,
    market_type,
    close_price,
    source_checksum,
    _FILE_NAME AS lineage_source_uri,
    CURRENT_TIMESTAMP() AS mirrored_at
  FROM `<project-id>.<external_dataset>.quotes_ext`
  WHERE _FILE_NAME IN UNNEST(@mirrored_uris)
) S
ON T.reference_date = S.reference_date
AND T.market_type = S.market_type
AND T.ticker = S.ticker
AND T.source_checksum = S.source_checksum
WHEN MATCHED THEN UPDATE SET
  processing_date = S.processing_date,
  close_price = S.close_price,
  lineage_source_uri = S.lineage_source_uri,
  mirrored_at = S.mirrored_at
WHEN NOT MATCHED THEN INSERT (
  reference_date,
  processing_date,
  ticker,
  market_type,
  close_price,
  source_checksum,
  lineage_source_uri,
  mirrored_at
) VALUES (
  S.reference_date,
  S.processing_date,
  S.ticker,
  S.market_type,
  S.close_price,
  S.source_checksum,
  S.lineage_source_uri,
  S.mirrored_at
);