# ============================================================================
# ROOT VARIABLES — Consistent across all L9 repos
# ============================================================================
# Override via terraform.tfvars, env vars (TF_VAR_*), or -var flags.
# Naming convention: L9_* env vars map to these variables.
# ============================================================================

# --- Project Identity ---
variable "project" {
  description = "Project name (maps to L9_PROJECT)"
  type        = string
  default     = "l9-engine"
}

variable "env" {
  description = "Environment: dev, staging, prod (maps to L9_ENV)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be dev, staging, or prod."
  }
}

variable "region" {
  description = "AWS region (maps to L9_REGION)"
  type        = string
  default     = "us-east-1"
}

# --- Networking ---
variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "AZs for multi-AZ deployment"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# --- API Service ---
variable "api_image" {
  description = "Docker image URI for API service"
  type        = string
}

variable "api_port" {
  description = "API container port (maps to API_PORT)"
  type        = number
  default     = 8000
}

variable "api_cpu" {
  description = "API task CPU units (256 = 0.25 vCPU)"
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "API task memory (MiB)"
  type        = number
  default     = 1024
}

variable "api_desired_count" {
  description = "Desired API task count"
  type        = number
  default     = 2
}

variable "api_min_count" {
  description = "Minimum API tasks (autoscaling)"
  type        = number
  default     = 1
}

variable "api_max_count" {
  description = "Maximum API tasks (autoscaling)"
  type        = number
  default     = 10
}

variable "api_workers" {
  description = "Uvicorn workers per container (maps to API_WORKERS)"
  type        = number
  default     = 4
}

variable "api_health_path" {
  description = "Health check endpoint"
  type        = string
  default     = "/v1/health"
}

# --- Neo4j ---
variable "neo4j_image" {
  description = "Neo4j Docker image"
  type        = string
  default     = "neo4j:5.15-enterprise"
}

variable "neo4j_cpu" {
  description = "Neo4j task CPU units"
  type        = number
  default     = 2048
}

variable "neo4j_memory" {
  description = "Neo4j task memory (MiB)"
  type        = number
  default     = 8192
}

variable "neo4j_volume_size" {
  description = "Neo4j EBS volume size (GB)"
  type        = number
  default     = 100
}

variable "neo4j_gds_enabled" {
  description = "Enable GDS plugin (maps to GDS_ENABLED)"
  type        = bool
  default     = true
}

# --- Redis ---
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_nodes" {
  description = "Number of Redis cache nodes"
  type        = number
  default     = 1
}

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

# --- Monitoring ---
variable "alarm_email" {
  description = "Email for CloudWatch alarm notifications"
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch log retention (days)"
  type        = number
  default     = 30
}

# --- Application Config (passed as env vars to containers) ---
variable "log_level" {
  description = "Application log level (maps to LOG_LEVEL)"
  type        = string
  default     = "INFO"
}

variable "domains_root" {
  description = "Path to domain specs inside container (maps to DOMAINS_ROOT)"
  type        = string
  default     = "/app/domains"
}

variable "cors_origins" {
  description = "Allowed CORS origins (maps to CORS_ORIGINS)"
  type        = string
  default     = "*"
}

# --- Tags ---
variable "extra_tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
