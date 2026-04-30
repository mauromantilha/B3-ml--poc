# ML Baseline

## Objetivo
Entregar um baseline operacional em TensorFlow para previsão EOD e registro de modelos por portfólio.

## Escopo
- Treino supervisionado tabular.
- Persistência local do artefato `.keras`.
- Registro do catálogo e do run de modelo.

## Diretórios/arquivos
```text
src/b3_quant_platform/ml/tensorflow_baseline.py
src/b3_quant_platform/api/routes/jobs.py
src/b3_quant_platform/jobs/cli.py
sql/migrations/001_initial_schema.sql
```

## Modelos de dados
- `model_registry`
- `model_runs`
- `portfolio_instances`

## Endpoints
- `POST /v1/jobs/train-model`

## Jobs
- `b3-jobs train-model --file ...`
- QStash via `/webhooks/qstash/train-model`

## Variáveis de ambiente
- `B3_TF_ARTIFACT_DIR`
- `B3_DATABASE_URL`

## Testes mínimos
- Validação futura com dataset sintético e checagem do artefato salvo.

## Critérios de aceite
- Modelo salvo em artefato versionado por data.
- Catálogo de modelos atualizado sem duplicar `(model_name, version)`.
- Run de treino idempotente por `(model_id, portfolio_id, reference_date, horizon_days)`.
