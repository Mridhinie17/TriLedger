#!/usr/bin/env bash
# ==============================================================================
# TriLedger: Azure Container Apps Zero-Cost Deployment Script
# Provisions serverless single-container hosting (scale-to-zero) on Azure
# ==============================================================================

set -euo pipefail

# Configuration variables
RESOURCE_GROUP="rg-triledger-prod"
LOCATION="eastus"
ACR_NAME="acrtriledger$RANDOM"
ENVIRONMENT_NAME="cae-triledger"
APP_NAME="triledger-app"
IMAGE_TAG="v1.0.0"

echo "================================================================================"
echo "TriLedger: Deploying to Azure Container Apps"
echo "================================================================================"

# 1. Check Azure CLI
if ! command -v az &> /dev/null; then
    echo "Error: Azure CLI ('az') is not installed. Please install it first."
    exit 1
fi

echo "Step 1: Creating Resource Group '$RESOURCE_GROUP' in '$LOCATION'..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output table

echo "Step 2: Creating Azure Container Registry '$ACR_NAME'..."
az acr create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACR_NAME" \
    --sku Basic \
    --admin-enabled true \
    --output table

echo "Step 3: Building and Pushing Docker Image to ACR using ACR Tasks..."
az acr build \
    --registry "$ACR_NAME" \
    --image "${APP_NAME}:${IMAGE_TAG}" \
    .

ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query "loginServer" --output tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" --output tsv)

echo "Step 4: Creating Azure Container Apps Environment '$ENVIRONMENT_NAME'..."
az containerapp env create \
    --name "$ENVIRONMENT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output table

echo "Step 5: Deploying Container App '$APP_NAME' with scale-to-zero support..."
az containerapp create \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$ENVIRONMENT_NAME" \
    --image "${ACR_LOGIN_SERVER}/${APP_NAME}:${IMAGE_TAG}" \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_NAME" \
    --registry-password "$ACR_PASSWORD" \
    --target-port 8000 \
    --ingress external \
    --cpu 0.5 \
    --memory 1.0Gi \
    --min-replicas 0 \
    --max-replicas 3 \
    --env-vars TRILEDGER_ENV=production PORT=8000 \
    --output table

APP_FQDN=$(az containerapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" --output tsv)

echo "================================================================================"
echo "Deployment Succeeded!"
echo "TriLedger Google Stitch Application is live at:"
echo "https://${APP_FQDN}"
echo "================================================================================"
