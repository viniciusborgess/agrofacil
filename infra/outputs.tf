output "app_url" {
  value = length(azurerm_container_app.api) > 0 ? "https://${azurerm_container_app.api[0].ingress[0].fqdn}" : null
}

output "app_name" {
  value = length(azurerm_container_app.api) > 0 ? azurerm_container_app.api[0].name : null
}

output "resource_group" {
  value = azurerm_resource_group.main.name
}

output "acr_name" {
  value = azurerm_container_registry.main.name
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "github_client_id" {
  description = "Vai para o secret AZURE_CLIENT_ID do GitHub"
  value       = azurerm_user_assigned_identity.github.client_id
}

output "tenant_id" {
  value = azurerm_user_assigned_identity.github.tenant_id
}
