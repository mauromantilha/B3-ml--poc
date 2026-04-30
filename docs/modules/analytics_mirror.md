# Analytics Mirror

## Objetivo
Ler datasets silver no R2, validar o parquet final, espelhar em GCS curated e publicar assets analíticos em BigQuery/BigLake sem acoplamento direto do BigQuery ao R2.

## Escopo
- Listagem incremental de objetos Parquet no R2 ou no espelho local.
- Cópia incremental para GCS curated.
- Manifestos e watermarks.
- Registro de lineage mínimo por arquivo.
- Geração e publicação opcional de DDL/DML para BigLake e tabelas nativas do BigQuery.

## Diretórios/arquivos
```text
src/b3_quant_platform/services/analytics_mirror.py
src/b3_quant_platform/api/routes/jobs.py
src/b3_quant_platform/jobs/cli.py
sql/bigquery/analytics_mirror/
tests/test_analytics_mirror.py
```

## Estratégia por zona
- External/raw analytics: parquet em GCS curated exposto por BigLake external tables. Mantém granularidade de arquivo, lineage e baixo custo de ingestão.
- Native curated analytics: tabelas nativas no BigQuery para datasets com leitura recorrente, joins frequentes, SLAs de latência ou necessidade de clustering avançado.

## Partição e cluster
- `quotes`: `PARTITION BY DATE(reference_date)` e `CLUSTER BY market_type, ticker`.
- `instruments`: preferir tabela externa; se materializada, usar `PARTITION BY DATE(last_processing_date)` e `CLUSTER BY asset_type, segment, ticker`.

## Critérios de decisão
- Usar external table quando o dataset é append-only, consultado com baixa frequência, precisa preservar layout de arquivo ou serve exploração ad hoc.
- Usar native table quando há joins recorrentes, dashboards com baixa latência, filtros repetidos por data/ticker ou necessidade de evitar leitura repetida do parquet externo.
- Usar `AUTO` para materializar `quotes` e manter `instruments` apenas como external por padrão.

## Lineage mínimo
- `source_key` no R2.
- `target_uri` em GCS.
- `source_checksum` SHA-256 do parquet.
- `source_last_modified`.
- `manifest_id` e `watermark` por dataset.

## Endpoints
- `POST /v1/jobs/analytics-mirror`

## Jobs
- `b3-jobs analytics-mirror --file ...`
- QStash via `/webhooks/qstash/analytics-mirror`

## Variáveis de ambiente
- `B3_GCS_BUCKET`
- `B3_BIGQUERY_PROJECT_ID`
- `B3_BIGQUERY_EXTERNAL_DATASET`
- `B3_BIGQUERY_NATIVE_DATASET`
- `B3_BIGLAKE_CONNECTION_ID`
- `B3_ANALYTICS_STATE_DIR`

## Testes mínimos
- Detectar novos arquivos silver sem full refresh.
- Validar consistência de bytes entre origem operacional e espelho curated local.
- Validar watermark incremental.
- Validar rota idempotente do job.

## Critérios de aceite
- O mirror nunca lê diretamente do R2 para o BigQuery.
- O GCS recebe o parquet curado com layout previsível e manifests de lineage.
- O job é reexecutável sem duplicar carga lógica.
- O watermark evita reler todos os arquivos sempre que não houver novidade.
