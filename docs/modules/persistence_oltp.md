# Persistence OLTP

## Objetivo
Implementar a persistência transacional em Supabase PostgreSQL para sustentar usuários, estratégias, carteiras, cenários, execuções, previsões e comparações EOD.

## Escopo
- Schema OLTP com UUID, timestamps UTC, índices compostos e constraints de integridade.
- Seeds mínimos para bootstrap operacional.
- Repository layer explícito.
- Testes de integração usando SQLAlchemy sobre SQLite para validar relações, unicidade e idempotência lógica.

## Diretórios/arquivos
```text
sql/migrations/001_initial_schema.sql
sql/migrations/002_seed_portfolio_templates.sql
sql/examples/001_oltp_example_inserts.sql
src/b3_quant_platform/models/base.py
src/b3_quant_platform/models/enums.py
src/b3_quant_platform/models/entities.py
src/b3_quant_platform/repositories/
tests/test_persistence_integration.py
```

## Tabelas principais
- `users`
- `portfolio_families`
- `portfolio_strategies`
- `portfolio_constraints`
- `portfolio_instances`
- `portfolio_positions`
- `portfolio_valuations_daily`
- `market_eod_snapshots`
- `events_catalog`
- `event_scenarios`
- `simulation_runs`
- `model_registry`
- `training_runs`
- `prediction_runs`
- `eod_comparisons`
- `system_jobs`
- `job_executions`
- `audit_logs`

## Diagrama textual de relacionamento
```text
users
  -> portfolio_families.owner_user_id
  -> portfolio_strategies.created_by_user_id
  -> portfolio_instances.owner_user_id
  -> audit_logs.actor_user_id

portfolio_families
  -> portfolio_strategies.family_id
  -> portfolio_instances.portfolio_family_id

portfolio_strategies
  -> portfolio_constraints.strategy_id
  -> portfolio_instances.strategy_id
  -> model_registry.portfolio_strategy_id
  -> training_runs.portfolio_strategy_id

portfolio_instances
  -> portfolio_positions.portfolio_instance_id
  -> portfolio_valuations_daily.portfolio_instance_id
  -> simulation_runs.portfolio_instance_id
  -> prediction_runs.portfolio_instance_id
  -> eod_comparisons.portfolio_instance_id

events_catalog
  -> event_scenarios.event_id

event_scenarios
  -> simulation_runs.event_scenario_id

model_registry
  -> training_runs.model_id
  -> prediction_runs.model_id

training_runs
  -> prediction_runs.training_run_id

prediction_runs
  -> eod_comparisons.prediction_run_id

system_jobs
  -> job_executions.system_job_id
```

## Estratégia de particionamento
- Particionar por `reference_date` quando o volume justificar em `portfolio_valuations_daily`, `prediction_runs` e `eod_comparisons`.
- Particionar por `created_at` ou `occurred_at` em `audit_logs` quando o volume de trilha operacional crescer.
- Nesta fase, a implementação fica em tabelas normais com índices compostos, preservando simplicidade operacional e compatibilidade com Supabase.

## Regras de integridade
- UUID em todas as chaves primárias.
- `updated_at` mantido por trigger no PostgreSQL.
- `job_executions.idempotency_key` é único para evitar reprocessamento duplicado.
- `market_eod_snapshots(reference_date, market, ticker)` é único para manter um snapshot EOD canônico por ativo.
- `portfolio_positions(portfolio_instance_id, reference_date, ticker)` impede duplicidade de posição por data.
- `prediction_runs(model_id, portfolio_instance_id, reference_date, horizon_days)` é a natural key de previsão.
- `eod_comparisons(portfolio_instance_id, reference_date, ticker, scenario_slug)` é a natural key de reconciliação.

## Exemplos de inserts
- Arquivo SQL: `sql/examples/001_oltp_example_inserts.sql`
- Seeds mínimos: `sql/migrations/002_seed_portfolio_templates.sql`

## Repository layer
- `users.py`: usuários e lookup por email.
- `portfolio.py`: famílias, estratégias, constraints, carteiras, posições e valuation diária.
- `events.py`: catálogo de eventos, cenários e simulações.
- `ml.py`: catálogo de modelos, treino e predição.
- `jobs.py`: jobs sistêmicos, execuções e auditoria.

## Testes mínimos
- criação de usuário, família, estratégia e constraints
- criação de carteira, posição e valuation diária
- criação de evento, cenário e simulation run
- criação de system job e idempotência de job execution
- criação de model registry, training run e prediction run

## Critérios de aceite
- O schema SQL representa todas as tabelas mínimas exigidas.
- Os models ORM refletem o schema transacional sem perder compatibilidade com a superfície atual.
- Há seeds mínimos e inserts exemplificativos.
- A camada de repositório suporta as operações transacionais básicas.
- Os testes de integração validam unicidade, vínculos e idempotência lógica.
