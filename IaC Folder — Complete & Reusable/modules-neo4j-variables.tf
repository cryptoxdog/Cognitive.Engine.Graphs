variable "name_prefix" { type = string }
variable "image" { type = string; default = "neo4j:5.15-enterprise" }
variable "cpu" { type = number; default = 2048 }
variable "memory" { type = number; default = 8192 }
variable "volume_size" { type = number; default = 100 }
variable "gds_enabled" { type = bool; default = true }
variable "subnet_ids" { type = list(string) }
variable "vpc_id" { type = string }
variable "ecs_cluster_id" { type = string }
variable "ssm_password_arn" { type = string }
