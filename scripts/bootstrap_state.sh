#!/usr/bin/env bash
# Cria a conta de armazenamento do state do Terraform e grava infra/backend.hcl (fora do git).
# O state fica no Azure, criptografado, com acesso só por Entra ID e sem acesso público.
set -euo pipefail
LOCATION="${1:-brazilsouth}"
RG="rg-agrofacil-tfstate"
SA="tfagrofacil$(az account show --query id -o tsv | tr -d '-' | cut -c1-8)"
cd "$(dirname "$0")/.."

az group create -n "$RG" -l "$LOCATION" -o none
az storage account create -n "$SA" -g "$RG" -l "$LOCATION" --sku Standard_LRS \
  --min-tls-version TLS1_2 --allow-blob-public-access false --allow-shared-key-access false -o none
az role assignment create --assignee "$(az ad signed-in-user show --query id -o tsv)" --role "Storage Blob Data Contributor" \
  --scope "$(az storage account show -n "$SA" -g "$RG" --query id -o tsv)" -o none
az storage container create -n tfstate --account-name "$SA" --auth-mode login -o none

cat > infra/backend.hcl <<EOF
resource_group_name  = "$RG"
storage_account_name = "$SA"
container_name       = "tfstate"
key                  = "agrofacil.tfstate"
use_azuread_auth     = true
EOF
echo "backend pronto: infra/backend.hcl"
