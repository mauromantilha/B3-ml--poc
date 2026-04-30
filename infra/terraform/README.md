# Terraform and Provider Blueprints

Este diretório mistura dois níveis de materialização:
- `providers/gcp`: Terraform executável para a fundação em GCP.
- `providers/cloudflare`, `providers/upstash`, `providers/supabase`: blueprints pseudo-IaC, organizados por provedor, para guiar provisionamento e integração sem acoplar este repositório a credenciais ou providers ainda não fixados.

## Ordem sugerida
1. Provisionar GCP foundation.
2. Provisionar buckets e worker de borda em Cloudflare.
3. Configurar Redis e QStash no Upstash.
4. Conectar Supabase como camada OLTP.

## Observação operacional
A fundação já assume que BigQuery nunca lê diretamente do R2. O fluxo correto é R2 bronze/silver/artifacts -> GCS curated -> BigQuery/BigLake.
