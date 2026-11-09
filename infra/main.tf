terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.14" }
    random  = { source = "hashicorp/random", version = "~> 3.6" }
  }
  # State remoto no Azure Storage, fora do repositório. Configure com: terraform init -backend-config=backend.hcl
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

locals {
  name = "${var.project}-${var.environment}"
  tags = { projeto = var.project, ambiente = var.environment, gerenciado_por = "terraform" }
}

resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${local.name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.5 # teto de custo: a ingestão para ao atingir o limite diário
  tags                = local.tags
}

resource "azurerm_container_registry" "main" {
  name                = "acr${var.project}${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Basic"
  admin_enabled       = false # sem usuário e senha: pull e push só por identidade gerenciada
  tags                = local.tags
}

# Identidade da aplicação: só consegue baixar imagens do registro.
resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${local.name}-app"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_role_assignment" "app_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# Identidade do GitHub Actions, autenticada por OIDC: nenhuma senha de nuvem fica no GitHub.
resource "azurerm_user_assigned_identity" "github" {
  name                = "id-${local.name}-github"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_federated_identity_credential" "github_production" {
  name                = "github-production"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.github.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${var.github_repo}:environment:production"
}

resource "azurerm_role_assignment" "github_push" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPush"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
}

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${local.name}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = local.tags
}

# Criado só depois que existe uma imagem no registro (ver README da pasta infra).
resource "azurerm_container_app" "api" {
  count                        = var.image_tag == "" ? 0 : 1
  name                         = "ca-${local.name}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  secret {
    name  = "metrics-token"
    value = var.metrics_token
  }

  # Só HTTPS, terminado pela plataforma. Não existe porta de administração (SSH, RDP) exposta.
  ingress {
    external_enabled           = true
    target_port                = 8000
    transport                  = "auto"
    allow_insecure_connections = false
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = "api"
      image  = "${azurerm_container_registry.main.login_server}/agrofacil-visao:${var.image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "METRICS_TOKEN"
        secret_name = "metrics-token"
      }
      env {
        name  = "MAX_CONCURRENT"
        value = "4"
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health"
      }
      readiness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/health"
      }
    }

    http_scale_rule {
      name                = "http"
      concurrent_requests = "10"
    }
  }

  # O pipeline publica novas imagens; o Terraform não deve revertê-las.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.app_pull]
}

# O GitHub só pode atualizar este aplicativo, nada mais na assinatura.
resource "azurerm_role_assignment" "github_deploy" {
  count                = length(azurerm_container_app.api)
  scope                = azurerm_container_app.api[0].id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
}

resource "azurerm_role_assignment" "github_read" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
}
