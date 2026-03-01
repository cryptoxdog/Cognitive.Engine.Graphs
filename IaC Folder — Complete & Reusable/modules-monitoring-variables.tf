variable "name_prefix" { type = string }
variable "alarm_email" { type = string; default = "" }
variable "log_retention_days" { type = number; default = 30 }
variable "ecs_cluster_name" { type = string }
variable "ecs_service_name" { type = string }
variable "alb_arn_suffix" { type = string }
variable "target_group_arn" { type = string }
