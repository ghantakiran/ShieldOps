#!/usr/bin/env bash
# Generate TypeScript types from OpenAPI spec.
#
# Usage:
#   ./scripts/generate_types.sh              # default: http://localhost:8000
#   ./scripts/generate_types.sh http://host  # custom API URL
set -euo pipefail

API_URL="${1:-http://localhost:8000}"
OUTPUT_DIR="dashboard-ui/src/types/api"

mkdir -p "$OUTPUT_DIR"

echo "Fetching OpenAPI spec from ${API_URL}..."
curl -sf "${API_URL}/api/v1/openapi.json" -o /tmp/shieldops-openapi.json

echo "Generating TypeScript types..."
npx openapi-typescript /tmp/shieldops-openapi.json \
    -o "${OUTPUT_DIR}/generated.ts"

echo "Types generated at ${OUTPUT_DIR}/generated.ts"
