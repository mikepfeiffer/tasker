# Tasker Azure infrastructure

This Terraform configuration creates three resources:

- A resource group in **West US 3** (`westus3`).
- An App Service plan running **Linux**, with one **Premium v4 P1V4** instance
  (Terraform SKU spelling: `P1v4`).
- A Linux Web App on that plan, using **Python 3.12**, Always On, HTTPS, and
  TLS 1.2 or newer. FTP and basic publishing authentication are disabled.

Resource names and tags are configurable. The region, operating system, and plan
size are set in `main.tf` to match this deployment. Azure lists West US 3 among
the [Premium v4 regions](https://learn.microsoft.com/en-us/azure/app-service/app-service-configure-premium-v4-tier).
Actual provisioning also depends on your subscription's quota and available capacity.

## Prepare

Install Terraform 1.16 or newer (before 2.0) and the
[Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows).
The configuration uses AzureRM 5.6 or a compatible 5.x release; commit
`.terraform.lock.hcl` to keep the selected provider version reproducible.

From the repository root in PowerShell:

```powershell
az login
az account set --subscription "YOUR-SUBSCRIPTION-ID"
Copy-Item infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
```

Edit `infrastructure/terraform.tfvars`: set your subscription ID and choose a
globally unique `web_app_name`. The default resource group and plan names can be
overridden in the same file. Terraform creates a new resource group; using an
existing group requires importing it into state first.

The signed-in identity needs permission to create the resource group and App
Service resources, and to register `Microsoft.Web` if it is not already registered.
Credentials come from Azure CLI authentication and are not stored in the configuration.

To check Linux P1V4 availability with Azure CLI 2.73.0 or newer:

```powershell
az appservice list-locations --linux-workers-enabled --sku P1V4 --output table
```

## Review and provision

Run these commands from the repository root:

```powershell
terraform -chdir=infrastructure init
terraform -chdir=infrastructure fmt -check
terraform -chdir=infrastructure validate
terraform -chdir=infrastructure plan "-out=tasker.tfplan"
```

Review the plan, then provision its resources:

```powershell
terraform -chdir=infrastructure apply tasker.tfplan
terraform -chdir=infrastructure output
```

Applying creates billable Azure resources. This configuration uses local state;
keep the state files to manage or remove the resources later. Local state, provider
downloads, variable files, and saved plans are excluded from Git. The example
variable file and provider lock file are tracked.

## Application deployment

This configuration provisions the hosting resources. It does not upload Tasker's
source code or configure a deployment pipeline. Build-on-deploy is enabled for a
future source deployment.

Tasker's current application configuration is for local use: its allowed hosts
are loopback addresses and its SQLite database and session key live in `.instance/`
beside the application source. Before publishing Tasker, prepare an Azure startup
entry point, allowed hosts, and persistent storage for those files. The demo account
boundaries in the [project README](../README.md#demo-accounts-and-boundaries) also
apply. Those application changes are a separate step from provisioning this host.

## Remove the resources

From the repository root, preview removal before confirming:

```powershell
terraform -chdir=infrastructure plan -destroy
terraform -chdir=infrastructure destroy
```

This removes the managed resource group and its contents, including any application
or data subsequently stored in those resources.
