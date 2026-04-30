# Arquitetura

## Topologia obrigatória implementada
- Compute e API: FastAPI preparado para Cloud Run em `Dockerfile.api`.
- Lake operacional: escrita em Parquet particionado para Cloudflare R2 via `LakeWriterService`.
- Edge e webhooks: Worker em `edge/worker` para encaminhar QStash e webhooks a Cloud Run.
- Cache, fila leve e agendamento HTTP: integração prevista por `QStash` e `Upstash` nas variáveis de ambiente.
- Banco transacional: modelo e migrações em `sql/migrations` para Supabase PostgreSQL.
- Analytics e lakehouse: espelho em GCS e registro de tabela externa BigQuery/BigLake em `AnalyticsMirrorService`.
- ML principal: baseline TensorFlow em `src/b3_quant_platform/ml/tensorflow_baseline.py`.
- Dashboard: Streamlit em `src/b3_quant_platform/dashboard/app.py`.

## Separação de camadas
- Transacional Supabase: cadastros, posições, snapshots EOD, cenários, comparações, jobs e catálogo de modelos.
- Lake operacional R2: artefatos Parquet reprocessáveis, particionados por `date`, `market` e `ticker` quando aplicável.
- Analytics lakehouse GCS + BigQuery/BigLake: mirror explícito do dado curado; não há acoplamento direto BigQuery → R2.

## Árvore principal
```text
.
├── Dockerfile.api
├── Dockerfile.dashboard
├── Makefile
├── edge/
│   └── worker/
├── docs/
│   ├── architecture.md
│   ├── deploy.md
│   ├── modules/
│   ├── payloads.md
│   └── test-plan.md
├── sql/
│   └── migrations/
├── src/
│   └── b3_quant_platform/
│       ├── api/
│       ├── core/
│       ├── dashboard/
│       ├── jobs/
│       ├── ml/
│       ├── models/
│       ├── schemas/
│       └── services/
└── tests/
```

## Fluxo EOD
1. Ingestão EOD recebe snapshots do pregão encerrado e persiste em Supabase.
2. Os mesmos snapshots são gravados em R2 como artefatos `raw` reexecutáveis.
3. O laboratório de cenários produz projeções contrafactuais e stress por portfólio.
4. O job EOD compara expectativa versus fechamento real e grava `eod_comparisons`.
5. O dado curado pode ser espelhado para GCS e registrado como tabela externa no BigQuery/BigLake.
6. O dashboard consome apenas a API e não acessa diretamente banco ou storage.
