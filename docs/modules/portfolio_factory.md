# Portfolio Factory

## Objetivo
Criar múltiplas carteiras com objetivos distintos, evitando um desenho monolítico de carteira única.

## Escopo
- Templates de mandato.
- Instâncias de portfólio por data de referência.
- Posições alvo e sinais por ticker.

## Diretórios/arquivos
```text
src/b3_quant_platform/services/portfolio_factory.py
src/b3_quant_platform/api/routes/portfolios.py
sql/migrations/001_initial_schema.sql
sql/migrations/002_seed_portfolio_templates.sql
tests/test_portfolio_factory.py
```

## Modelos de dados
- `portfolio_templates`
- `portfolio_instances`
- `portfolio_positions`

## Endpoints
- `POST /v1/templates/seed`
- `GET /v1/templates`
- `POST /v1/templates`
- `GET /v1/portfolios`
- `POST /v1/portfolios`

## Jobs
- `b3-jobs seed-templates`

## Variáveis de ambiente
- `B3_DATABASE_URL`
- `B3_DEFAULT_MARKET`

## Testes mínimos
- Seed de templates padrão.
- Criação de instância com duas posições.

## Critérios de aceite
- Pelo menos quatro templates padrão disponíveis.
- Criação de carteira sem duplicar `(template_id, name, reference_date)`.
- Posições persistidas por ticker e data.
