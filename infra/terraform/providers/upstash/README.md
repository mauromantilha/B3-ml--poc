# Upstash Blueprint

O desenho assume Upstash Redis para locks e cache leve, e QStash para cron e fan-out HTTP entre serviços stateless do Cloud Run.

## Recursos previstos
- Um banco Redis lógico para locks, cache e deduplicação curta.
- Regras de retry no QStash com backoff e número de tentativas controlado.
- Schedules independentes por fluxo assíncrono.

## Resultado esperado
- Nenhum worker depende de fila local ou filesystem persistente.
- O fan-out entre `worker-ingestion`, `worker-feature-store`, `worker-forecast`, `worker-simulation` e `worker-eod` é HTTP e observável.
