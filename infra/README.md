# Infra Foundation

Módulo de infraestrutura base da plataforma quantitativa, separado do código de aplicação e preparado para evoluir em paralelo.

## Objetivo
Provisionar a fundação lógica da arquitetura com serviços separados para API, workers e lake/analytics, respeitando Cloud Run stateless, jobs HTTP assíncronos via QStash, ausência de filesystem permanente e containers reproduzíveis.

## Árvore de diretórios
```text
infra/
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── docker-compose.yml
├── scripts/
│   ├── bootstrap-local.sh
│   ├── bootstrap-terraform.sh
│   └── check-prereqs.sh
└── terraform/
    ├── README.md
    └── providers/
        ├── cloudflare/
        │   ├── README.md
        │   └── blueprint.yaml
        ├── gcp/
        │   ├── locals.tf
        │   ├── main.tf
        │   ├── outputs.tf
        │   ├── terraform.tfvars.example
        │   ├── variables.tf
        │   └── versions.tf
        ├── supabase/
        │   ├── README.md
        │   └── blueprint.yaml
        └── upstash/
            ├── README.md
            └── blueprint.yaml
```

## Serviços Cloud Run
- `api`: FastAPI pública para operações síncronas, leitura do dashboard e entrada de webhooks internos.
- `worker-ingestion`: recebimento assíncrono de cargas EOD e persistência inicial.
- `worker-feature-store`: materialização de features e snapshots derivados.
- `worker-forecast`: execução de previsões e registro de inferências.
- `worker-simulation`: cenários, contrafactuais e stress jobs.
- `worker-eod`: reconciliação de fechamento, QA diário e fan-out pós-pregão.
- `dashboard-streamlit`: interface operacional e analítica.

Todos os serviços são dockerizáveis. `api` e workers usam o mesmo `Dockerfile.api` nesta fundação; o `dashboard-streamlit` usa `Dockerfile.dashboard`.

## Convenção de nomes
### Buckets
- R2 bronze: `${B3_PROJECT_SLUG}-${B3_ENVIRONMENT}-r2-bronze`
- R2 silver: `${B3_PROJECT_SLUG}-${B3_ENVIRONMENT}-r2-silver`
- R2 artifacts: `${B3_PROJECT_SLUG}-${B3_ENVIRONMENT}-r2-artifacts`
- GCS curated: `${B3_PROJECT_SLUG}-${B3_ENVIRONMENT}-gcs-curated`

### Datasets BigQuery
- `raw_mirror`
- `feature_store`
- `forecasting`
- `backtests`
- `portfolio_marts`

## Variáveis de ambiente padronizadas
- Identidade e ambiente: `B3_PROJECT_SLUG`, `B3_ENVIRONMENT`, `B3_STACK_ID`
- GCP: `B3_GCP_PROJECT_ID`, `B3_GCP_REGION`, `B3_GCP_ARTIFACT_REGISTRY_REPOSITORY`
- Cloud Run: `B3_CLOUD_RUN_SERVICE_*`
- R2: `B3_R2_ENDPOINT_URL`, `B3_R2_ACCESS_KEY_ID`, `B3_R2_SECRET_ACCESS_KEY`, `B3_R2_BUCKET_*`
- GCS/BigQuery: `B3_GCS_BUCKET_CURATED`, `B3_BIGQUERY_DATASET_*`
- Supabase: `B3_DATABASE_URL`, `B3_SUPABASE_DB_POOL_URL`, `B3_SUPABASE_PROJECT_REF`, `B3_SUPABASE_*_KEY`
- Upstash: `B3_UPSTASH_REDIS_REST_URL`, `B3_UPSTASH_REDIS_REST_TOKEN`, `B3_QSTASH_*`
- Observabilidade: `B3_STRUCTURED_LOG_LEVEL`, `B3_LOG_JSON`, `B3_OTEL_EXPORTER_OTLP_ENDPOINT`, `B3_GCP_TRACE_SAMPLE_RATIO`

## Estratégia de secrets
- Produção: segredos sensíveis ficam fora do Git e entram por Secret Manager no GCP, Wrangler Secrets no Worker e painéis gerenciados de Upstash e Supabase.
- Cloud Run consome segredos por referência, não por baking em imagem.
- R2 access keys, tokens QStash, tokens Upstash e chaves Supabase são tratados como runtime secrets.
- Desenvolvimento local usa `infra/.env`, derivado de `infra/.env.example`, e nunca deve ser versionado.

## Estratégia de logs e tracing
- Logs estruturados em JSON, um `request_id` por requisição e propagação de `x-request-id` entre Worker, QStash e Cloud Run.
- Trace sampling configurado por ambiente.
- Cloud Run envia logs e traces para Cloud Logging e Cloud Trace.
- Workers devem encaminhar `x-request-id` e `idempotency-key` para manter correlação ponta a ponta.

## Estratégia de retry e idempotência
- Todos os jobs são HTTP assíncronos via QStash com retries limitados e backoff exponencial.
- Locks de exclusão mútua e deduplicação curta ficam no Upstash Redis.
- Idempotência funcional é garantida no backend por `job_runs.idempotency_key` e chaves naturais nas tabelas.
- Artefatos de lake são regraváveis por partição lógica, sem anexar estado local permanente.

## Critérios de aceite
- Existe um módulo `/infra` autocontido com compose, env, scripts e IaC por provedor.
- Os sete serviços Cloud Run estão nomeados e modelados.
- Buckets e datasets seguem convenção explícita e única.
- Secrets, logs/tracing, retry e idempotência estão definidos por estratégia, não por adivinhação implícita.
- O `docker-compose` é apenas de desenvolvimento e não depende de storage persistente local para a fundação.
