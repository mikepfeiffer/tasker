output "resource_group_name" {
  description = "Resource group containing the Tasker hosting resources."
  value       = azurerm_resource_group.tasker.name
}

output "service_plan_id" {
  description = "Resource ID of the Linux Premium v4 App Service plan."
  value       = azurerm_service_plan.tasker.id
}

output "web_app_name" {
  description = "Web App name to use when deploying application code."
  value       = azurerm_linux_web_app.tasker.name
}

output "web_app_url" {
  description = "HTTPS URL of the provisioned Web App; application code is deployed separately."
  value       = "https://${azurerm_linux_web_app.tasker.default_hostname}"
}
