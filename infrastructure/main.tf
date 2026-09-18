resource "azurerm_resource_group" "tasker" {
  name     = var.resource_group_name
  location = "westus3"
  tags     = var.tags
}

resource "azurerm_service_plan" "tasker" {
  name                = var.service_plan_name
  resource_group_name = azurerm_resource_group.tasker.name
  location            = azurerm_resource_group.tasker.location
  os_type             = "Linux"
  sku_name            = "P1v4"
  worker_count        = 1
  tags                = var.tags
}

resource "azurerm_linux_web_app" "tasker" {
  name                = var.web_app_name
  resource_group_name = azurerm_resource_group.tasker.name
  location            = azurerm_service_plan.tasker.location
  service_plan_id     = azurerm_service_plan.tasker.id
  https_only          = true
  tags                = var.tags

  ftp_publish_basic_authentication_enabled       = false
  webdeploy_publish_basic_authentication_enabled = false

  site_config {
    always_on               = true
    ftps_state              = "Disabled"
    minimum_tls_version     = "1.2"
    scm_minimum_tls_version = "1.2"

    application_stack {
      python_version = "3.12"
    }
  }

  app_settings = {
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
  }
}
