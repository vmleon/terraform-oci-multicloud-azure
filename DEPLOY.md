# Quick Deploy Guide

## Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run setup wizard
python stack.py setup
# Select template, provide credentials and configuration
```

## Deploy
```bash
# Navigate to selected template directory
cd templates/<your-selected-template>

# Initialize Terraform
terraform init

# Review plan
terraform plan

# Deploy infrastructure
terraform apply
```

## Clean Up
```bash
# Destroy infrastructure
terraform destroy

# Clean generated files
cd ../..
python stack.py clean
```

## Environment Variables
The `.env` file stores:
- Azure credentials (ARM_*)
- OCI credentials (TF_VAR_oci_*)
- Selected template and configuration