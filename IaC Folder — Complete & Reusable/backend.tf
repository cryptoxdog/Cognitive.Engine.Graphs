# ============================================================================
# TERRAFORM BACKEND - S3 State Storage
# ============================================================================
# Override bucket/key per repo via -backend-config or backend.hcl
#
# Usage:
#   terraform init -backend-config=backend.hcl
#
# backend.hcl example:
#   bucket  = "l9-terraform-state"
#   key     = "plasticos/terraform.tfstate"
#   region  = "us-east-1"
#   encrypt = true
# ============================================================================

terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    bucket         = "l9-terraform-state"
    key            = "l9-engine/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "l9-terraform-locks"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.env
      ManagedBy   = "terraform"
      Repo        = var.project
    }
  }
}
