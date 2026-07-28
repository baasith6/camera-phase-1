#!/usr/bin/env bash
# ONEVO MVP — provision Azure resource group, ACR, and GPU VM (run from your workstation).
# Requires: az login, sufficient GPU quota in the target region.
#
# Usage:
#   export AZURE_RESOURCE_GROUP=onevo-mvp-rg
#   export AZURE_LOCATION=eastus
#   export AZURE_ACR_NAME=onevoacr   # globally unique, alphanumeric only
#   export AZURE_VM_NAME=onevo-mvp-vm
#   export AZURE_ADMIN_USER=azureuser
#   ./infra/mvp/provision-azure.sh
set -euo pipefail

AZURE_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-onevo-mvp-rg}"
AZURE_LOCATION="${AZURE_LOCATION:-eastus}"
AZURE_ACR_NAME="${AZURE_ACR_NAME:-onevoacr}"
AZURE_VM_NAME="${AZURE_VM_NAME:-onevo-mvp-vm}"
AZURE_ADMIN_USER="${AZURE_ADMIN_USER:-azureuser}"
# NC4as_T4_v3 — adjust if quota unavailable in your subscription/region
AZURE_VM_SIZE="${AZURE_VM_SIZE:-Standard_NC4as_T4_v3}"

echo "==> Resource group $AZURE_RESOURCE_GROUP ($AZURE_LOCATION)"
az group create --name "$AZURE_RESOURCE_GROUP" --location "$AZURE_LOCATION" --output none

echo "==> Container Registry $AZURE_ACR_NAME"
az acr create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_ACR_NAME" \
  --sku Basic \
  --admin-enabled true \
  --output none

ACR_LOGIN_SERVER=$(az acr show --name "$AZURE_ACR_NAME" --query loginServer -o tsv)
echo "    ACR login server: $ACR_LOGIN_SERVER"

echo "==> GPU VM $AZURE_VM_NAME ($AZURE_VM_SIZE)"
az vm create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_VM_NAME" \
  --image Ubuntu2204 \
  --size "$AZURE_VM_SIZE" \
  --admin-username "$AZURE_ADMIN_USER" \
  --generate-ssh-keys \
  --public-ip-sku Standard \
  --output none

VM_IP=$(az vm show -d --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_VM_NAME" --query publicIps -o tsv)
echo "    VM public IP: $VM_IP"

echo "==> NSG rules (SSH, HTTP, HTTPS)"
az network nsg rule create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --nsg-name "${AZURE_VM_NAME}NSG" \
  --name allow-http \
  --priority 1001 \
  --destination-port-ranges 80 \
  --access Allow \
  --protocol Tcp \
  --output none 2>/dev/null || true

az network nsg rule create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --nsg-name "${AZURE_VM_NAME}NSG" \
  --name allow-https \
  --priority 1002 \
  --destination-port-ranges 443 \
  --access Allow \
  --protocol Tcp \
  --output none 2>/dev/null || true

echo ""
echo "==> Provisioned. Next steps:"
echo "    1. SSH: ssh $AZURE_ADMIN_USER@$VM_IP"
echo "    2. Clone repo to /opt/onevo and run: sudo ACR_LOGIN_SERVER=$ACR_LOGIN_SERVER ./infra/mvp/vm-setup.sh"
echo "    3. Create GitHub service principal + secrets (see docs/AZURE_MVP_DEPLOY.md)"
echo "    4. Push to main to trigger deploy workflow"
