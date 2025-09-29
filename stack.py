#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stack management CLI for Oracle Database @ Azure multi-cloud deployments.
Manages template selection and configuration generation.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List

import click
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv, set_key

# Template metadata with descriptions
TEMPLATE_PROFILES = {
    "avm-oci-exadata-quickstart": {
        "name": "Exadata with Azure Verified Modules",
        "description": "Quickstart OracleDB@Azure (Exadata) with AVM (AzAPI) and OCI LZ Modules",
        "requires_passwords": ["db_admin_password"],
        "requires_ssh_keys": ["vm_cluster_ssh_public_keys"]
    },
    "azurerm-oci-exadata-quickstart": {
        "name": "Exadata with AzureRM Provider",
        "description": "Quickstart OracleDB@Azure (Exadata) with AzureRM and OCI Terraform provider",
        "requires_passwords": ["db_admin_password"],
        "requires_ssh_keys": ["vm_cluster_ssh_public_keys"]
    },
    "azurerm-oci-adbs-quickstart": {
        "name": "Autonomous Database Quickstart",
        "description": "Quickstart OracleDB@Azure (Autonomous Database) with AzureRM and OCI provider",
        "requires_passwords": ["admin_password"],
        "requires_ssh_keys": []
    },
    "az-oci-adbs": {
        "name": "Autonomous Database with AzAPI",
        "description": "Quickstart OracleDB@Azure (Autonomous Database) with AzAPI provider",
        "requires_passwords": ["db_admin_password"],
        "requires_ssh_keys": []
    },
    "az-oci-exa-pdb": {
        "name": "Exadata PDB Validation",
        "description": "Terraform Template for Provisioning Exa on Azure and Validation",
        "requires_passwords": ["db_admin_password"],
        "requires_ssh_keys": ["vm_cluster_ssh_public_key"]
    },
    "az-oci-sso-federation": {
        "name": "SSO Federation Setup",
        "description": "Setup SSO Federation between OCI & Azure",
        "requires_passwords": [],
        "requires_ssh_keys": []
    },
    "az-oci-rbac-n-sso-fed": {
        "name": "RBAC and SSO Federation",
        "description": "Setup RBAC and SSO Federation between OCI & Azure",
        "requires_passwords": [],
        "requires_ssh_keys": []
    }
}

ENV_FILE = ".env"


def load_env_config() -> Dict[str, str]:
    """Load configuration from .env file."""
    if Path(ENV_FILE).exists():
        load_dotenv(ENV_FILE)
    return dict(os.environ)


def save_env_var(key: str, value: str):
    """Save a variable to the .env file."""
    set_key(ENV_FILE, key, value)


def validate_uuid(value: str) -> bool:
    """Validate UUID format for Azure IDs."""
    import re
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(uuid_pattern, value, re.IGNORECASE))


def validate_ocid(value: str) -> bool:
    """Validate OCID format for OCI resources."""
    return value.startswith('ocid1.') and len(value) > 20


def validate_file_path(path: str) -> bool:
    """Check if file exists."""
    return Path(path).expanduser().exists()


def get_ssh_keys_input() -> List[str]:
    """Get SSH public keys from user input."""
    click.echo("\nSSH Public Keys (required for VM cluster access):")
    click.echo("You can provide:")
    click.echo("1. Path to public key file (e.g., ~/.ssh/id_rsa.pub)")
    click.echo("2. Direct key content (ssh-rsa AAAAB3...)")

    keys = []
    while True:
        key_input = click.prompt(f"SSH public key #{len(keys) + 1} (press Enter to finish)",
                               default="", show_default=False)
        if not key_input:
            break

        # Check if it's a file path
        if key_input.startswith('~/') or key_input.startswith('/'):
            key_path = Path(key_input).expanduser()
            if key_path.exists():
                try:
                    with open(key_path, 'r') as f:
                        key_content = f.read().strip()
                    keys.append(key_content)
                    click.echo(f"✓ Added key from {key_input}")
                except Exception as e:
                    click.echo(f"✗ Error reading {key_input}: {e}")
            else:
                click.echo(f"✗ File not found: {key_input}")
        else:
            # Assume it's direct key content
            if key_input.startswith('ssh-'):
                keys.append(key_input)
                click.echo("✓ Added direct key content")
            else:
                click.echo("✗ Invalid key format. Should start with 'ssh-'")

    if not keys:
        click.echo("⚠ No SSH keys provided. You'll need to add them manually.")
        keys = ["ssh-rsa REPLACE_WITH_YOUR_PUBLIC_KEY"]

    return keys


def collect_template_variables(template_name: str) -> Dict[str, Any]:
    """Collect template-specific variables from user."""
    profile = TEMPLATE_PROFILES[template_name]
    variables = {}

    click.echo(f"\n=== {profile['name']} Configuration ===")

    # Common variables for most templates
    if template_name != "az-oci-sso-federation" and template_name != "az-oci-rbac-n-sso-fed":
        variables["az_region"] = click.prompt("Azure Region", default="useast")

        if "resource_group" in ["avm-oci-exadata-quickstart", "azurerm-oci-exadata-quickstart", "az-oci-adbs"]:
            variables["resource_group"] = click.prompt("Resource Group Name", default="oradb")

    # Template-specific variables
    if template_name in ["az-oci-sso-federation", "az-oci-rbac-n-sso-fed"]:
        variables["config_file_profile"] = click.prompt("OCI Config File Profile")
        variables["compartment_ocid"] = click.prompt("OCI Compartment OCID")
        variables["region"] = click.prompt("OCI Region", default="us-ashburn-1")

    elif template_name == "azurerm-oci-adbs-quickstart":
        variables["name"] = click.prompt("Database Name", default="adbsdemo")

    elif template_name == "az-oci-adbs":
        variables["db_name"] = click.prompt("Database Name", default="demodb")
        variables["db_ecpu_count"] = click.prompt("Database ECPU Count", default=2, type=int)
        variables["db_storage_in_gb"] = click.prompt("Database Storage (GB)", default=20, type=int)

    # VM Cluster configuration for Exadata templates
    if "exadata" in template_name:
        variables["vm_cluster_name"] = click.prompt("VM Cluster Name", default="vmc")
        variables["exadata_infrastructure_name"] = click.prompt("Exadata Infrastructure Name", default="exainfra")

    # Collect passwords
    for password_field in profile["requires_passwords"]:
        password = click.prompt(f"Database Admin Password", hide_input=True, confirmation_prompt=True)
        variables[password_field] = password

    # Collect SSH keys
    for ssh_field in profile["requires_ssh_keys"]:
        if ssh_field in ["vm_cluster_ssh_public_keys"]:
            variables[ssh_field] = get_ssh_keys_input()
        else:
            # Single SSH key
            ssh_key = click.prompt("SSH Public Key (file path or key content)")
            if ssh_key.startswith('~/') or ssh_key.startswith('/'):
                key_path = Path(ssh_key).expanduser()
                if key_path.exists():
                    with open(key_path, 'r') as f:
                        variables[ssh_field] = f.read().strip()
                else:
                    click.echo(f"⚠ SSH key file not found: {ssh_key}")
                    variables[ssh_field] = ssh_key
            else:
                variables[ssh_field] = ssh_key

    return variables


@click.group()
def cli():
    """Oracle Database @ Azure Stack Management CLI"""
    pass


@cli.command()
def setup():
    """Interactive setup wizard for Oracle Database @ Azure deployment."""
    click.echo("=🚀 Oracle Database @ Azure Stack Setup")
    click.echo("=" * 50)

    # Load existing configuration
    env_config = load_env_config()
    current_template = env_config.get("SELECTED_TEMPLATE")

    if current_template:
        click.echo(f"Current template: {current_template}")
        if not click.confirm("Change template?", default=False):
            selected_template = current_template
        else:
            selected_template = None
    else:
        selected_template = None

    # Template selection
    if not selected_template:
        click.echo("\n=📦 Available Deployment Templates:")
        template_choices = []
        for i, (key, profile) in enumerate(TEMPLATE_PROFILES.items(), 1):
            click.echo(f"{i:2d}. {profile['name']}")
            click.echo(f"    {profile['description']}")
            template_choices.append(key)

        while True:
            try:
                choice = click.prompt("\nSelect template number", type=int)
                if 1 <= choice <= len(template_choices):
                    selected_template = template_choices[choice - 1]
                    break
                else:
                    click.echo(f"Please enter a number between 1 and {len(template_choices)}")
            except (ValueError, click.Abort):
                click.echo("Please enter a valid number")

    click.echo(f"\n✓ Selected: {TEMPLATE_PROFILES[selected_template]['name']}")
    save_env_var("SELECTED_TEMPLATE", selected_template)

    # Get template path
    template_path = Path("templates") / selected_template
    if not template_path.exists():
        click.echo(f"✗ Template directory not found: {template_path}")
        sys.exit(1)

    click.echo(f"✓ Using template at {template_path}")

    # Collect Azure credentials
    click.echo("\n=🔐 Azure Credentials")
    current_client_id = env_config.get("ARM_CLIENT_ID")
    if current_client_id and click.confirm(f"Use existing Azure Client ID ({current_client_id[:8]}...)?", default=True):
        arm_client_id = current_client_id
    else:
        while True:
            arm_client_id = click.prompt("Azure Client ID (Service Principal App ID)")
            if validate_uuid(arm_client_id):
                break
            click.echo("✗ Invalid UUID format")

    arm_client_secret = click.prompt("Azure Client Secret", hide_input=True)

    while True:
        arm_tenant_id = click.prompt("Azure Tenant ID", default=env_config.get("ARM_TENANT_ID", ""))
        if validate_uuid(arm_tenant_id):
            break
        click.echo(" Invalid UUID format")

    while True:
        arm_subscription_id = click.prompt("Azure Subscription ID", default=env_config.get("ARM_SUBSCRIPTION_ID", ""))
        if validate_uuid(arm_subscription_id):
            break
        click.echo(" Invalid UUID format")

    # Save Azure credentials
    save_env_var("ARM_CLIENT_ID", arm_client_id)
    save_env_var("ARM_CLIENT_SECRET", arm_client_secret)
    save_env_var("ARM_TENANT_ID", arm_tenant_id)
    save_env_var("ARM_SUBSCRIPTION_ID", arm_subscription_id)

    # Collect OCI credentials (skip for SSO templates that might not need them)
    if selected_template not in ["az-oci-sso-federation", "az-oci-rbac-n-sso-fed"]:
        click.echo("\n=🔐 OCI Credentials")

        while True:
            oci_tenancy_ocid = click.prompt("OCI Tenancy OCID", default=env_config.get("TF_VAR_oci_tenancy_ocid", ""))
            if validate_ocid(oci_tenancy_ocid):
                break
            click.echo("✗ Invalid OCID format")

        while True:
            oci_user_ocid = click.prompt("OCI User OCID", default=env_config.get("TF_VAR_oci_user_ocid", ""))
            if validate_ocid(oci_user_ocid):
                break
            click.echo("✗ Invalid OCID format")

        while True:
            oci_private_key_path = click.prompt("OCI Private Key Path", default=env_config.get("TF_VAR_oci_private_key_path", ""))
            expanded_path = str(Path(oci_private_key_path).expanduser())
            if validate_file_path(expanded_path):
                oci_private_key_path = expanded_path
                break
            click.echo(f"✗ File not found: {expanded_path}")

        oci_fingerprint = click.prompt("OCI Key Fingerprint", default=env_config.get("TF_VAR_oci_fingerprint", ""))

        # Save OCI credentials
        save_env_var("TF_VAR_oci_tenancy_ocid", oci_tenancy_ocid)
        save_env_var("TF_VAR_oci_user_ocid", oci_user_ocid)
        save_env_var("TF_VAR_oci_private_key_path", oci_private_key_path)
        save_env_var("TF_VAR_oci_fingerprint", oci_fingerprint)

    # Collect template-specific variables
    template_vars = collect_template_variables(selected_template)

    # Save template variables
    for key, value in template_vars.items():
        if isinstance(value, list):
            save_env_var(key.upper(), json.dumps(value))
        else:
            save_env_var(key.upper(), str(value))

    # Generate terraform.tfvars using Jinja2
    template_j2_path = template_path / "terraform.tfvars.j2"
    if template_j2_path.exists():
        # Prepare template context
        context = {
            # Azure credentials
            "arm_client_id": arm_client_id,
            "arm_client_secret": arm_client_secret,
            "arm_tenant_id": arm_tenant_id,
            "arm_subscription_id": arm_subscription_id,
        }

        # OCI credentials
        if selected_template not in ["az-oci-sso-federation", "az-oci-rbac-n-sso-fed"]:
            context.update({
                "oci_tenancy_ocid": oci_tenancy_ocid,
                "oci_user_ocid": oci_user_ocid,
                "oci_private_key_path": oci_private_key_path,
                "oci_fingerprint": oci_fingerprint,
                "use_env_vars": True,  # We use environment variables
            })

        # Template variables
        context.update(template_vars)

        # Render template
        env = Environment(loader=FileSystemLoader(template_path))
        template = env.get_template("terraform.tfvars.j2")
        rendered = template.render(**context)

        # Write terraform.tfvars in the template directory
        tfvars_path = template_path / "terraform.tfvars"
        with open(tfvars_path, 'w') as f:
            f.write(rendered)

        click.echo(f"✓ Generated {tfvars_path}")
    else:
        click.echo(f"⚠ No Jinja2 template found at {template_j2_path}")

    # Display next steps
    click.echo("\n✨ Setup Complete!")
    click.echo("Next steps:")
    click.echo(f"1. cd {template_path}")
    click.echo("2. terraform init")
    click.echo("3. terraform plan")
    click.echo("4. terraform apply")
    click.echo(f"\nTo clean up later: python stack.py clean")


@cli.command()
def clean():
    """Clean up terraform resources and generated files."""
    click.echo("🧹 Cleaning up Oracle Database @ Azure Stack")
    click.echo("=" * 50)

    # Load configuration
    env_config = load_env_config()
    selected_template = env_config.get("SELECTED_TEMPLATE")

    if not selected_template:
        click.echo("✓ No template selected, checking for .env file to clean")
    else:
        template_path = Path("templates") / selected_template

        if template_path.exists():
            # Check terraform state
            tfstate_path = template_path / "terraform.tfstate"

            if tfstate_path.exists():
                try:
                    # Check if there are resources in state
                    result = subprocess.run(
                        ["terraform", "state", "list"],
                        cwd=template_path,
                        capture_output=True,
                        text=True,
                        check=False
                    )

                    if result.returncode == 0 and result.stdout.strip():
                        resources = result.stdout.strip().split('\n')
                        click.echo(f"⚠ Found {len(resources)} resources in terraform state:")
                        for resource in resources[:10]:  # Show first 10
                            click.echo(f"  - {resource}")
                        if len(resources) > 10:
                            click.echo(f"  ... and {len(resources) - 10} more")

                        click.echo(f"\n⚠ Run 'cd {template_path} && terraform destroy' first")

                        if not click.confirm("Continue cleanup anyway?", default=False):
                            click.echo("Cleanup cancelled")
                            return
                except subprocess.SubprocessError:
                    click.echo("Could not check terraform state (terraform not available)")

            # Clean up terraform files in the template directory
            tfvars_path = template_path / "terraform.tfvars"
            if tfvars_path.exists():
                if click.confirm(f"Delete generated terraform.tfvars in {template_path}?", default=True):
                    tfvars_path.unlink()
                    click.echo(f"✓ Removed {tfvars_path}")

            # Clean up .terraform directory
            terraform_dir = template_path / ".terraform"
            if terraform_dir.exists():
                if click.confirm(f"Delete .terraform directory in {template_path}?", default=True):
                    shutil.rmtree(terraform_dir)
                    click.echo(f"✓ Removed {terraform_dir}")

            # Clean up terraform lock file
            lock_file = template_path / ".terraform.lock.hcl"
            if lock_file.exists():
                if click.confirm(f"Delete terraform lock file in {template_path}?", default=True):
                    lock_file.unlink()
                    click.echo(f"✓ Removed {lock_file}")

            # Clean up state files
            for state_file in template_path.glob("*.tfstate*"):
                if click.confirm(f"Delete state file {state_file.name}?", default=True):
                    state_file.unlink()
                    click.echo(f"✓ Removed {state_file}")

            # Clean up tfplan files
            for plan_file in template_path.glob("tfplan*"):
                if click.confirm(f"Delete plan file {plan_file.name}?", default=True):
                    plan_file.unlink()
                    click.echo(f"✓ Removed {plan_file}")

    # Optionally remove .env
    if Path(ENV_FILE).exists():
        if click.confirm(f"Delete configuration file '{ENV_FILE}'?", default=False):
            Path(ENV_FILE).unlink()
            click.echo(f"✓ Removed {ENV_FILE}")

    click.echo("✨ Cleanup complete!")


if __name__ == "__main__":
    cli()