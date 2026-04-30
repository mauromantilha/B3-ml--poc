# Dashboard

## Objetivo
Operar a plataforma por uma interface Streamlit simples, voltada a observabilidade e acionamento dos fluxos principais.

## Escopo
- Visualização de templates e portfólios.
- Acionamento de comparação EOD.
- Criação e execução de cenários.

## Diretórios/arquivos
```text
src/b3_quant_platform/dashboard/app.py
Dockerfile.dashboard
```

## Modelos de dados
- Consome somente respostas da API.
- Não persiste estado transacional próprio.

## Endpoints
- `GET /v1/templates`
- `GET /v1/portfolios`
- `POST /v1/templates/seed`
- `POST /v1/jobs/eod-reconcile`
- `GET /v1/eod/comparisons`
- `POST /v1/scenarios`
- `POST /v1/scenarios/run`

## Jobs
- Disparo manual de jobs EOD e cenários via API.

## Variáveis de ambiente
- `B3_CLOUD_RUN_BASE_URL`
- `B3_API_PREFIX`

## Testes mínimos
- Smoke test manual carregando overview, cenário e reconciliação.

## Critérios de aceite
- Dashboard sobe em Cloud Run com Streamlit.
- Nenhuma regra de negócio crítica fica apenas na UI.
- Toda operação visível no dashboard corresponde a um endpoint do backend.
