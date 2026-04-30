#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_EXAMPLE="$ROOT_DIR/.env.example"
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Created $ENV_FILE from template"
else
  echo "Using existing $ENV_FILE"
fi

"$ROOT_DIR/scripts/check-prereqs.sh"
B3_INFRA_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/docker-compose.yml" config > /dev/null

echo "Infrastructure local bootstrap ready"
echo "Next steps:"
echo "  cd $ROOT_DIR"
echo "  make compose-up"
