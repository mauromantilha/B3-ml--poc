# Plano de testes

## Escopo mínimo
- Validar healthcheck da API.
- Validar seed da fábrica multiportfólio e criação de carteira com posições.
- Validar execução de cenário stress sobre carteira existente.
- Validar escrita Parquet particionada por `date`, `market` e `ticker`.
- Validar job EOD reexecutável sem corromper dados usando chave de idempotência.
- Validar ingestão histórica bronze/silver com manifesto, deduplicação e endpoint idempotente.
- Validar espelhamento analítico incremental com watermark, lineage e consistência entre lake operacional e GCS curated.
- Validar o economic models engine com recuperação de parâmetros, previsões, valuation e integração com feature store e optimizer.

## Testes automatizados implementados
- `tests/test_health.py`
- `tests/test_portfolio_factory.py`
- `tests/test_scenario_lab.py`
- `tests/test_lake_and_reconciliation.py`
- `tests/test_historical_ingestion.py`
- `tests/test_analytics_mirror.py`
- `tests/test_economic_models_engine.py`

## Próximos testes recomendados
1. Teste de contrato HTTP para `/v1/jobs/analytics-mirror` com mocks de GCS e BigQuery.
2. Teste de integração com Supabase PostgreSQL real em ambiente efêmero.
3. Teste de carga EOD com lotes de tickers B3 representativos.
4. Teste do worker Cloudflare encaminhando payloads idempotentes para Cloud Run.
5. Teste de treino TensorFlow com dataset sintético maior e verificação de persistência do artefato.
6. Teste de integração com bucket R2 real validando `put_object` e leitura do manifesto em staging.
7. Teste estatístico ampliado de ARIMA/SARIMA e GARCH/EGARCH com séries mais longas em staging.

## Critérios de aprovação
- Todos os testes unitários passam.
- Nenhum job duplica linhas em tabelas com restrição de unicidade.
- Os artefatos locais ou remotos são gerados no layout de partição esperado.
- A API expõe corretamente templates, portfólios, cenários, snapshots e jobs EOD.
- O economic models engine persiste métricas, atualiza o feature store e gera overlay para o optimizer.
