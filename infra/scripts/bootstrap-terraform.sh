#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIRS=(
  "$ROOT_DIR/terraform/providers/gcp"
  "$ROOT_DIR/terraform/providers/cloudflare"
)

if ! command -v terraform > /dev/null 2>&1; then
  echo "terraform is required" >&2
  exit 1
fi

for dir in "${TF_DIRS[@]}"; do
  if [[ -f "$dir/main.tf" ]]; then
    echo "Initializing $dir"
    terraform -chdir="$dir" init -backend=false
  fi
done

echo "Terraform bootstrap complete"
