#!/usr/bin/env bash
set -euo pipefail

required_commands=(docker terraform)
optional_commands=(gcloud wrangler jq)
missing=()

for cmd in "${required_commands[@]}"; do
  if ! command -v "$cmd" > /dev/null 2>&1; then
    missing+=("$cmd")
  fi
done

if ! docker compose version > /dev/null 2>&1; then
  missing+=("docker compose")
fi

if (( ${#missing[@]} > 0 )); then
  printf 'Missing required commands: %s\n' "${missing[*]}" >&2
  exit 1
fi

for cmd in "${optional_commands[@]}"; do
  if command -v "$cmd" > /dev/null 2>&1; then
    printf 'optional-ok: %s\n' "$cmd"
  else
    printf 'optional-missing: %s\n' "$cmd"
  fi
done

printf 'required-ok: docker terraform docker-compose\n'
