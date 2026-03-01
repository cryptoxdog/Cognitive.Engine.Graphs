variable "name_prefix" { type = string }
variable "image" { type = string }
variable "port" { type = number; default = 8000 }
variable "cpu" { type = number; default = 512 }
variable "memory" { type = number; default = 1024 }
variable "desired_count" { type = number; default = 2 }
variable "min_count" { type = number; default = 1 }
variable "max_count" { type = number; default = 10 }
variable "health_path" { type = string; default = "/v1/health" }
variable "env_vars" { type = map(string); default = {} }
variable "secrets" { type = map(string); default = {} }
variable "subnet_ids" { type = list(string) }
variable "public_subnets" { type = list(string) }
variable "vpc_id" { type = string }
variable "ecs_cluster_id" { type = string }
variable "log_group" { type = string }
