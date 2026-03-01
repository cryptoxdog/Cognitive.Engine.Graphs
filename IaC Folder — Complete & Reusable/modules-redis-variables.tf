variable "name_prefix" { type = string }
variable "node_type" { type = string; default = "cache.t3.micro" }
variable "num_nodes" { type = number; default = 1 }
variable "engine_version" { type = string; default = "7.0" }
variable "subnet_ids" { type = list(string) }
variable "vpc_id" { type = string }
variable "allowed_sg_ids" { type = list(string) }
