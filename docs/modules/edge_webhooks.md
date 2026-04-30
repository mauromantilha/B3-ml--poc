# Edge Webhooks

## Objetivo
Receber webhooks e requisições agendadas na borda, normalizar headers e encaminhar jobs HTTP para Cloud Run.

## Escopo
- Rotas de webhook para EOD, mirror e treino.
- Propagação de `x-request-id`.
- Reuso do identificador do QStash como chave de idempotência de borda.

## Diretórios/arquivos
```text
edge/worker/package.json
edge/worker/wrangler.toml
edge/worker/src/index.ts
```

## Modelos de dados
- Não persiste estado próprio.
- Trabalha com envelope HTTP e headers.

## Endpoints
- `POST /webhooks/qstash/eod`
- `POST /webhooks/qstash/analytics-mirror`
- `POST /webhooks/qstash/train-model`

## Jobs
- Encaminhamento para jobs HTTP do Cloud Run.

## Variáveis de ambiente
- `CLOUD_RUN_BASE_URL`
- `EDGE_SHARED_SECRET`
- `B3_QSTASH_TOKEN`

## Testes mínimos
- Teste futuro de forwarding com payload e header `Upstash-Message-Id`.

## Critérios de aceite
- Somente rotas mapeadas são aceitas.
- Toda chamada encaminhada recebe `x-request-id` e `idempotency-key`.
- Segredo compartilhado é propagado ao backend.
