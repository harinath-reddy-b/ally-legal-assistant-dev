param (
    [string]$RG,
    [string]$ACR_NAME
)

# Ensure current working directory is parent of "deployment" folder
$deploymentPath = (Get-Location).Path
if ($deploymentPath -contains "deployment") {
    Write-Host "Please run this script from the parent directory of the 'deployment' folder" -ForegroundColor Red
    exit
}

$BUILD_ID = Get-Date -Format "yyyyMMddHHmmss"
$TAG = "build-$BUILD_ID"

# If $ACR_NAME is not provided, query the resource group for the ACR name not containing 'ml'
if (-not $ACR_NAME) {
    $ACR_NAME = az acr list --resource-group $RG --query "[? contains(name, 'ally')].name" -o tsv
}

Write-Host "Using Azure Container Registry: $ACR_NAME"

function DeployContainerApp($dockerImageName, $dockerFile, $sourceFolder, $tag, $containerAppName) {
    # Confirmation
    $confirmation = Read-Host -Prompt "Do you want to proceed with the build and deployment of $dockerImageName ? (Y/N)"
    
    if ($confirmation.ToLower() -eq "y") {
        Write-Host "Building the $containerAppName Docker image using Azure Container Registry with tag = $tag..." -ForegroundColor Green
        az acr build --registry $ACR_NAME --resource-group $RG --image "${dockerImageName}:$tag" --image "${dockerImageName}:latest" --file $dockerFile $sourceFolder

        # Update the container app to pull the latest image and restart
        Write-Host "Updating the Azure Container App ($containerAppName) to pull the latest image..." -ForegroundColor Yellow
        az containerapp update --name $containerAppName --resource-group $RG --image "${dockerImageName}:$tag"

        Write-Host "$dockerImageName build completed and deployed to Azure Container App $containerAppName" -ForegroundColor Green
    }
    else {
        Write-Host "$dockerImageName build cancelled by user." -ForegroundColor Green
    }
}

$containerAppNames = az containerapp list --resource-group $RG --query "[].name" -o tsv

$MAIN_DOCKER_IMAGE_NAME = "$ACR_NAME.azurecr.io/ally-legal-assistant"
$MAIN_DOCKERFILE_PATH = "backend/Docker/legal-main-flow-container/Dockerfile"
$MAIN_SOURCE_FOLDER = "backend/Docker/legal-main-flow-container"

$EMBEDDING_DOCKER_IMAGE_NAME = "$ACR_NAME.azurecr.io/ally-doc-embedding"
$EMBEDDING_DOCKERFILE_PATH = "backend/Docker/doc-embedding/Dockerfile"
$EMBEDDING_SOURCE_FOLDER = "backend/Docker/doc-embedding"

$MAIN_CONTAINER_APP_NAME = $containerAppNames | Where-Object { $_ -like "*-ally-legal-assistant*" }
$EMBEDDING_CONTAINER_APP_NAME = $containerAppNames | Where-Object { $_ -like "*ally-doc-embedding*" }

Write-Host "Container app name is $MAIN_CONTAINER_APP_NAME, $EMBEDDING_CONTAINER_APP_NAME"

DeployContainerApp $MAIN_DOCKER_IMAGE_NAME $MAIN_DOCKERFILE_PATH $MAIN_SOURCE_FOLDER $TAG $MAIN_CONTAINER_APP_NAME
DeployContainerApp $EMBEDDING_DOCKER_IMAGE_NAME $EMBEDDING_DOCKERFILE_PATH $EMBEDDING_SOURCE_FOLDER $TAG $EMBEDDING_CONTAINER_APP_NAME