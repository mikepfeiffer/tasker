variable "subscription_id" {
  description = "Azure subscription ID in which to create the Tasker resources."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.subscription_id))
    error_message = "Use an Azure subscription ID in UUID format."
  }
}

variable "resource_group_name" {
  description = "Name of the new resource group in West US 3."
  type        = string
  default     = "rg-tasker-westus3"
  nullable    = false
}

variable "service_plan_name" {
  description = "Name of the Linux Premium v4 P1v4 App Service plan."
  type        = string
  default     = "asp-tasker-westus3"
  nullable    = false
}

variable "web_app_name" {
  description = "Globally unique Web App name, used in its default azurewebsites.net hostname."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,58}[a-z0-9]$", var.web_app_name))
    error_message = "Use 2-60 lowercase letters, numbers, or hyphens, starting and ending with a letter or number."
  }
}

variable "tags" {
  description = "Tags applied to all Tasker Azure resources."
  type        = map(string)
  default = {
    Application = "Tasker"
    Environment = "Demo"
    ManagedBy   = "Terraform"
  }
  nullable = false
}
