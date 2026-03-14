# --- L9_META ---
# l9_schema: 1
# origin: infra
# engine: graph
# layer: [health, terraform]
# tags: [health, ecs, cloud-run, iac]
# owner: platform-team
# status: stub
# --- /L9_META ---
#
# HEALTH service deployment stub — ECS / Cloud Run
# Pending: actual container registry, VPC config, service mesh integration

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "image_tag" {
  description = "Container image tag for HEALTH service"
  type        = string
  default     = "latest"
}

variable "cpu" {
  description = "CPU units (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "memory" {
  description = "Memory in MiB"
  type        = number
  default     = 1024
}

variable "cost_ceiling_usd" {
  description = "Default nightly scan cost ceiling"
  type        = number
  default     = 50.0
}

# Placeholder for ECS task definition
# resource "aws_ecs_task_definition" "health_service" {
#   family                   = "ceg-health-${var.environment}"
#   requires_compatibilities = ["FARGATE"]
#   cpu                      = var.cpu
#   memory                   = var.memory
#   network_mode             = "awsvpc"
#
#   container_definitions = jsonencode([{
#     name      = "health-service"
#     image     = "ghcr.io/cryptoxdog/ceg-health:${var.image_tag}"
#     cpu       = var.cpu
#     memory    = var.memory
#     essential = true
#     portMappings = [{
#       containerPort = 8000
#       protocol      = "tcp"
#     }]
#     environment = [
#       { name = "DOMAIN_SPECS_PATH", value = "/app/domains" },
#       { name = "COST_CEILING_USD", value = tostring(var.cost_ceiling_usd) },
#     ]
#   }])
# }

output "service_name" {
  description = "HEALTH service identifier"
  value       = "ceg-health-${var.environment}"
}

output "status" {
  description = "Deployment status"
  value       = "stub — pending container registry and service mesh setup"
}
