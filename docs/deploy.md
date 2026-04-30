# Deploy

## Pré-requisitos
- Python 3.12 para desenvolvimento local.
- Projeto GCP com Cloud Run, GCS e BigQuery habilitados.
- Conta Cloudflare com R2 e Workers.
- Upstash Redis + QStash.
- Projeto Supabase PostgreSQL.

## 1. Configuração local
```bash
cp .env.example .env
python3 -m pip install -e .[dev]
```

## 2. Migrações no Supabase PostgreSQL
Aplicar, nesta ordem:
1. `sql/migrations/001_initial_schema.sql`
2. `sql/migrations/002_seed_portfolio_templates.sql`
3. `sql/migrations/003_event_catalog_module.sql`
4. `sql/migrations/004_seed_historical_events.sql`
5. `sql/migrations/005_economic_models_engine.sql`

Opcionalmente, pelo próprio CLI do projeto:
```bash
b3-jobs apply-migrations
```

## 3. Deploy da API FastAPI no Cloud Run
```bash
gcloud builds submit --tag gcr.io/<project-id>/b3-api -f Dockerfile.api
gcloud run deploy b3-api \
  --image gcr.io/<project-id>/b3-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars-file .env
```

## 4. Deploy do dashboard Streamlit no Cloud Run
```bash
gcloud builds submit --tag gcr.io/<project-id>/b3-dashboard -f Dockerfile.dashboard
gcloud run deploy b3-dashboard \
  --image gcr.io/<project-id>/b3-dashboard \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars B3_CLOUD_RUN_BASE_URL=https://<api-service-url>
```

## 5. Deploy do Worker Cloudflare
```bash
cd edge/worker
npm install
npx wrangler deploy
```

## 6. Agendamento HTTP com QStash
- `/webhooks/qstash/eod` para reconciliar no fechamento.
- `/webhooks/qstash/analytics-mirror` para espelhar o curado em GCS/BigQuery.
- `/webhooks/qstash/train-model` para treino de baseline TensorFlow.
- `POST /v1/jobs/historical-ingestion` para disparar ingestão histórica no worker de ingestão em Cloud Run.
- `POST /v1/jobs/economic-models` para calcular modelos econômicos, popular o feature store e alimentar o optimizer.

## 7. Smoke test mínimo
```bash
make test
python3 -m uvicorn b3_quant_platform.api.main:app --host 0.0.0.0 --port 8080
curl http://localhost:8080/healthz
```
