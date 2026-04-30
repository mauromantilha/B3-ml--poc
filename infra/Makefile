COMPOSE_FILE := $(CURDIR)/docker-compose.yml
ENV_FILE := $(CURDIR)/.env
TERRAFORM_DIRS := terraform/providers/gcp terraform/providers/cloudflare

.PHONY: bootstrap-local check-prereqs compose-config compose-up compose-down compose-logs compose-ps terraform-fmt terraform-init show-services

bootstrap-local:
	./scripts/bootstrap-local.sh

check-prereqs:
	./scripts/check-prereqs.sh

compose-config:
	B3_INFRA_ENV_FILE=$(ENV_FILE) docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE) config > /dev/null

compose-up:
	B3_INFRA_ENV_FILE=$(ENV_FILE) docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE) up --build -d

compose-down:
	B3_INFRA_ENV_FILE=$(ENV_FILE) docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE) down --remove-orphans

compose-logs:
	B3_INFRA_ENV_FILE=$(ENV_FILE) docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE) logs -f

compose-ps:
	B3_INFRA_ENV_FILE=$(ENV_FILE) docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE) ps

terraform-fmt:
	terraform fmt -recursive terraform

terraform-init:
	./scripts/bootstrap-terraform.sh

show-services:
	@printf '%s\n' \
	  api \
	  worker-ingestion \
	  worker-feature-store \
	  worker-forecast \
	  worker-simulation \
	  worker-eod \
	  dashboard-streamlit
