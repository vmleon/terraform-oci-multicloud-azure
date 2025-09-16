# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Terraform-based Oracle Database@Azure multi-cloud deployment repository containing modules and templates for provisioning Oracle Database services on Azure using both Azure and OCI providers.

## Development Commands

### Stack Management
- `python stack.py setup` - Interactive setup wizard for Oracle Database@Azure deployment
- `python stack.py clean` - Clean up terraform resources and workspace

### Python Environment
- `python -m venv venv` - Create virtual environment
- `source venv/bin/activate` (macOS/Linux) or `venv\Scripts\activate` (Windows) - Activate virtual environment
- `pip install -r requirements.txt` - Install Python dependencies

### Terraform Operations
Navigate to template directory first (e.g., `cd templates/azurerm-oci-exadata-quickstart`):
- `terraform init` (or `tofu init`) - Initialize workspace
- `terraform plan` (or `tofu plan`) - Validate and plan changes
- `terraform apply` (or `tofu apply`) - Apply infrastructure changes
- `terraform destroy` (or `tofu destroy`) - Remove all resources

### Authentication Setup
Source the environment file before Terraform operations:
- `source env.sh` - Load Azure and OCI authentication variables

## Architecture

### Core Structure
- **templates/**: Pre-configured deployment templates for different scenarios
- **modules/**: Reusable Terraform modules for specific services
- **stack.py**: Python CLI for template management and workspace setup

### Multi-Cloud Integration
- Uses Azure providers (azurerm, azuread, azapi) and OCI provider (oracle/oci)
- Templates handle cross-cloud authentication and resource provisioning
- Environment variables manage credentials for both cloud providers

### Template Categories
- **Exadata**: `azurerm-oci-exadata-quickstart`, `avm-oci-exadata-quickstart`, `az-oci-exa-pdb`
- **Autonomous Database**: `azurerm-oci-adbs-quickstart`, `az-oci-adbs`
- **Identity & SSO**: `az-oci-sso-federation`, `az-oci-rbac-n-sso-fed`, `az-odb-rbac`

### Module Organization
- **azure-***: Azure-specific resource modules (resource groups, networking, Exadata infrastructure)
- **oci-***: OCI-specific modules (identity, database services)
- **billing-usage-metrics-validation**: Utility module for metrics validation

### Configuration Management
- `stack.py` uses Jinja2 templates (`terraform.tfvars.j2`) to generate configuration
- Environment variables stored in `.env` file
- Template-specific variables collected through interactive CLI prompts

## Key Files
- `versions.tf`: Terraform provider version constraints
- `env.sh`: Environment variable template for authentication
- `stack.py`: Main CLI tool for managing deployments
- `requirements.txt`: Python dependencies for CLI tool