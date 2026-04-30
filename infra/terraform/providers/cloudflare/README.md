# Cloudflare Blueprint

Este provider está modelado como pseudo-IaC para manter a fundação organizada sem congelar cedo demais detalhes de credenciais e do pipeline Wrangler.

## Recursos previstos
- Worker de borda para webhooks, callbacks e fan-out controlado.
- Buckets R2 `bronze`, `silver` e `artifacts`.
- Segredos injetados via `wrangler secret put` ou pipeline equivalente.

## Resultado esperado
- O Worker encaminha chamadas QStash para Cloud Run com `x-request-id` e `idempotency-key`.
- O lake operacional fica segmentado em três buckets distintos por responsabilidade.
- Nenhum analytics consumer acessa o R2 diretamente.
