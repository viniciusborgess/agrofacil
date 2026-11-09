#!/usr/bin/env bash
# Prepara os segredos da stack local e o alvo do Azure para o Prometheus. Nada disso vai para o git.
# Uso: scripts/monitoring_setup.sh [token]   (passe o mesmo token usado no terraform.tfvars)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p monitoring/secrets monitoring/prometheus/targets
TOKEN="${1:-$(grep -E '^metrics_token' infra/terraform.tfvars 2>/dev/null | cut -d'"' -f2 || true)}"
TOKEN="${TOKEN:-$(openssl rand -hex 32)}"

printf '%s' "$TOKEN" > monitoring/secrets/metrics_token
printf 'METRICS_TOKEN=%s\n' "$TOKEN" > monitoring/secrets/api.env
[ -f monitoring/secrets/grafana_admin ] || openssl rand -hex 16 | tr -d '\n' > monitoring/secrets/grafana_admin
chmod 600 monitoring/secrets/*

URL="$(terraform -chdir=infra output -raw app_url 2>/dev/null || true)"
if [ -n "$URL" ] && [ "$URL" != "null" ]; then
  printf '[{"targets": ["%s"], "labels": {"ambiente": "azure"}}]\n' "${URL#https://}" > monitoring/prometheus/targets/azure.json
  echo "alvo do Azure: $URL"
else
  echo '[]' > monitoring/prometheus/targets/azure.json
  echo "sem app no Azure ainda; só o alvo local será monitorado"
fi
