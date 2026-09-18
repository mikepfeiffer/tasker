terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.6"
    }
  }
}

provider "azurerm" {
  features {}

  subscription_id                 = var.subscription_id
  resource_provider_registrations = "none"
  resource_providers_to_register  = ["Microsoft.Web"]
}
