# EOD Pipeline

## Objetivo
Ingerir fechamento do pregão, persistir snapshots EOD, gerar artefatos raw no R2 e comparar expectativa versus realizado ao final do dia.

## Escopo
- Ingestão EOD sem intraday.
- Escrita raw em Parquet particionado.
- Reconcilição EOD idempotente.

## Diretórios/arquivos
```text
src/b3_quant_platform/services/market_data.py
src/b3_quant_platform/services/eod_reconciliation.py
src/b3_quant_platform/services/lake_writer.py
src/b3_quant_platform/api/routes/eod.py
src/b3_quant_platform/api/routes/jobs.py
sql/migrations/001_initial_schema.sql
tests/test_lake_and_reconciliation.py
```

## Modelos de dados
- `market_eod_snapshots`
- `eod_comparisons`
- `job_runs`

## Endpoints
- `POST /v1/market-snapshots`
- `GET /v1/eod/comparisons`
- `POST /v1/jobs/eod-reconcile`

## Jobs
- `b3-jobs ingest-snapshots --file ...`
- `b3-jobs reconcile-eod --file ...`
- QStash via `/webhooks/qstash/eod`

## Variáveis de ambiente
- `B3_DATABASE_URL`
- `B3_R2_ENDPOINT_URL`
- `B3_R2_ACCESS_KEY_ID`
- `B3_R2_SECRET_ACCESS_KEY`
- `B3_R2_BUCKET`
- `B3_LOCAL_PARQUET_DIR`

## Testes mínimos
- Escrita de partição `date/market/ticker`.
- Reconciliação EOD reexecutada sem criar novo job run.

## Critérios de aceite
- Snapshots EOD gravados no transacional e no lake raw.
- Job EOD reexecutável via `idempotency_key`.
- Comparações curadas escritas sem corromper histórico.
