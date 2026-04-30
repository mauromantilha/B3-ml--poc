# B3 Multi-Portfolio EOD Platform

Plataforma quantitativa multiportfólio para histórico da B3, simulação de cenários, baseline de ML em TensorFlow e comparação EOD contra o pregão encerrado.

## Stack obrigatória aplicada
- Cloud Run: FastAPI e Streamlit
- Cloudflare R2: lake operacional em Parquet
- Cloudflare Workers: edge e webhooks
- Upstash Redis + QStash: agendamento HTTP e fila leve
- Supabase PostgreSQL: camada transacional
- GCS + BigQuery/BigLake: mirror analítico do curado
- TensorFlow: baseline de treino e catálogo de modelos

## Estrutura
```text
src/b3_quant_platform/api         FastAPI e jobs HTTP
src/b3_quant_platform/ingestion   pipeline histórico B3 para bronze/silver no R2
src/b3_quant_platform/services    fábrica de portfólios, EOD, cenários e lake
src/b3_quant_platform/ml          baseline TensorFlow
src/b3_quant_platform/dashboard   Streamlit
sql/migrations                    esquema transacional e seed inicial
edge/worker                       Worker Cloudflare para webhooks/QStash
docs/                             arquitetura, payloads, módulos, testes e deploy
tests/                            cobertura mínima automatizada
```

## Quickstart
```bash
cp .env.example .env
python3 -m pip install -e .[dev]
make test
python3 -m uvicorn b3_quant_platform.api.main:app --host 0.0.0.0 --port 8080
```

## Comandos úteis
```bash
b3-jobs seed-templates
b3-jobs apply-migrations
b3-jobs ingest-historical --file COTAHIST_A202604.TXT --dataset-type cotahist
b3-jobs analytics-mirror --file analytics_mirror_payload.json
b3-jobs ingest-snapshots --file payload.json
b3-jobs reconcile-eod --file payload.json
b3-jobs train-model --file payload.json
```

## Documentação
- Arquitetura: `docs/architecture.md`
- Deploy: `docs/deploy.md`
- Payloads: `docs/payloads.md`
- Plano de testes: `docs/test-plan.md`
- Módulos: `docs/modules/`
