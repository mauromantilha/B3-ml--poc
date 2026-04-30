# Historical Ingestion

## Objetivo
Ingerir séries históricas da B3, preservar o arquivo original em bronze, normalizar e enriquecer cotações em silver e registrar o manifesto de ingestão com versionamento por data de processamento.

## Escopo
- Parsing de `COTAHIST` e CSV EOD.
- Validação estrutural e de faixas de preço.
- Deduplicação reexecutável.
- Escrita de bronze/raw, silver/quotes, silver/instruments e metadata/ingestion_logs.
- Execução local via CLI e remota via endpoint HTTP compatível com Cloud Run.

## Diretórios/arquivos
```text
src/b3_quant_platform/ingestion/
src/b3_quant_platform/api/routes/jobs.py
src/b3_quant_platform/jobs/cli.py
tests/test_historical_ingestion.py
```

## Estrutura no R2
- `b3/bronze/cotahist/year=YYYY/processing_date=YYYY-MM-DD/...`
- `b3/bronze/eod/date=YYYY-MM-DD/processing_date=YYYY-MM-DD/...`
- `b3/silver/quotes/market_type=.../year=YYYY/month=MM/...`
- `b3/silver/instruments/year=YYYY/month=MM/...`
- `b3/metadata/ingestion_logs/date=YYYY-MM-DD/...`

## Regras principais
- `source_checksum`: SHA-256 do arquivo de origem.
- Deduplicação: manter o registro com maior `trade_count`, depois maior `trade_volume`, depois maior `source_line_number` para a mesma chave `reference_date + market_type + ticker + isin`.
- Enriquecimento mínimo: `ticker`, `isin`, `asset_type`, `segment`, flags `has_trades`, `is_liquid`, `is_high_liquidity`, `is_fractional`.
- Saídas silver em Parquet Snappy.

## Interfaces
- CLI: `b3-jobs ingest-historical --file ... --dataset-type cotahist`
- HTTP: `POST /v1/jobs/historical-ingestion`

## Exemplo de payload HTTP
```json
{
  "dataset_type": "eod",
  "processing_date": "2026-04-29",
  "reference_date": "2026-04-28",
  "source_name": "quotes.csv",
  "content_base64": "<base64>",
  "delimiter": ";"
}
```

## Critérios de aceite
- O arquivo original é preservado em bronze com checksum e metadados.
- O manifesto contém contagens de origem, deduplicação, partições e URIs geradas.
- Reexecuções com a mesma entrada retornam o mesmo job idempotente no endpoint HTTP.