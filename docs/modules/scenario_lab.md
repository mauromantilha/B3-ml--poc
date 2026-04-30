# Scenario Lab

## Objetivo
Manter um laboratório de cenários exógenos, contrafactuais e stress sobre múltiplos portfólios.

## Escopo
- Cadastro de cenários.
- Execução de choque por portfólio e data.
- Sumário de PnL projetado por posição.
- Derivação de cenários a partir de eventos reais ou sintéticos.
- Runs contrafactuais persistidos em `counterfactual_runs`.

## Diretórios/arquivos
```text
src/b3_quant_platform/services/scenario_lab.py
src/b3_quant_platform/services/event_catalog.py
src/b3_quant_platform/api/routes/events.py
src/b3_quant_platform/api/routes/scenarios.py
sql/migrations/001_initial_schema.sql
sql/migrations/003_event_catalog_module.sql
tests/test_scenario_lab.py
tests/test_event_catalog.py
```

## Modelos de dados
- `scenario_definitions`
- `scenario_runs`
- `events_catalog`
- `counterfactual_runs`
- `portfolio_instances`
- `portfolio_positions`

## Endpoints
- `POST /v1/scenarios`
- `POST /v1/scenarios/run`
- `POST /v1/scenarios/from-event`
- `POST /v1/scenarios/counterfactual-run`

## Jobs
- Execução HTTP síncrona pela API.
- Pode ser agendado externamente via QStash se necessário.

## Variáveis de ambiente
- `B3_DATABASE_URL`

## Testes mínimos
- Criação de cenário stress.
- Execução de cenário contra portfólio com projeção de NAV.
- Conversão de evento em vetor de choque com escopo explícito.
- Run contrafactual com persistência do resultado.

## Critérios de aceite
- Cenário persistido com slug único.
- Reexecução do mesmo cenário e mesma data reutiliza o registro existente.
- Resultado inclui impactos por ticker e NAV projetado.
