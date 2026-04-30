# Supabase Blueprint

Supabase permanece a camada OLTP e não é usado como lake nem como analytics store.

## Recursos previstos
- Banco PostgreSQL operacional.
- Pooler para workloads HTTP do Cloud Run.
- Chaves `anon` e `service_role` tratadas como secrets de runtime.
- Migrações forward-only a partir de `sql/migrations`.

## Resultado esperado
- Conexões stateless a partir de serviços Cloud Run.
- Estado transacional centralizado e separado do lake operacional e do analytics mirror.
