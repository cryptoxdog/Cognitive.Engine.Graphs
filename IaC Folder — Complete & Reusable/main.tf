# ============================================================================
# ROOT MODULE — Wires all infrastructure together
# ============================================================================

locals {
  name_prefix = "${var.project}-${var.env}"

  # Standard env vars passed to ALL L9 containers
  # This block is the single source of truth for app config
  app_env = {
    L9_PROJECT     = var.project
    L9_ENV         = var.env
    NEO4J_URI      = "bolt://${module.neo4j.host}:7687"
    NEO4J_USERNAME = "neo4j"
    NEO4J_DATABASE = "neo4j"
    REDIS_URL      = "redis://${module.redis.endpoint}:6379/0"
    DOMAINS_ROOT   = var.domains_root
    LOG_LEVEL      = var.log_level
    API_PORT       = tostring(var.api_port)
    API_WORKERS    = tostring(var.api_workers)
    GDS_ENABLED    = tostring(var.neo4j_gds_enabled)
    CORS_ORIGINS   = var.cors_origins
  }

  # Secrets fetched from SSM at runtime (not baked into task def)
  app_secrets = {
    NEO4J_PASSWORD = "/l9/${var.env}/neo4j/password"
    REDIS_AUTH     = "/l9/${var.env}/redis/auth_token"
    API_SECRET_KEY = "/l9/${var.env}/api/secret_key"
  }
}

# --- Networking ---
module "networking" {
  source = "./modules/networking"

  name_prefix        = local.name_prefix
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  extra_tags         = var.extra_tags
}

# --- Neo4j ---
module "neo4j" {
  source = "./modules/neo4j"

  name_prefix   = local.name_prefix
  image         = var.neo4j_image
  cpu           = var.neo4j_cpu
  memory        = var.neo4j_memory
  volume_size   = var.neo4j_volume_size
  gds_enabled   = var.neo4j_gds_enabled
  subnet_ids    = module.networking.private_subnet_ids
  vpc_id        = module.networking.vpc_id
  ecs_cluster_id = module.networking.ecs_cluster_id
  ssm_password_arn = local.app_secrets["NEO4J_PASSWORD"]
}

# --- Redis ---
module "redis" {
  source = "./modules/redis"

  name_prefix    = local.name_prefix
  node_type      = var.redis_node_type
  num_nodes      = var.redis_num_nodes
  engine_version = var.redis_engine_version
  subnet_ids     = module.networking.private_subnet_ids
  vpc_id         = module.networking.vpc_id
  allowed_sg_ids = [module.api.security_group_id]
}

# --- API Service ---
module "api" {
  source = "./modules/api"

  name_prefix    = local.name_prefix
  image          = var.api_image
  port           = var.api_port
  cpu            = var.api_cpu
  memory         = var.api_memory
  desired_count  = var.api_desired_count
  min_count      = var.api_min_count
  max_count      = var.api_max_count
  health_path    = var.api_health_path
  env_vars       = local.app_env
  secrets        = local.app_secrets
  subnet_ids     = module.networking.private_subnet_ids
  public_subnets = module.networking.public_subnet_ids
  vpc_id         = module.networking.vpc_id
  ecs_cluster_id = module.networking.ecs_cluster_id
  log_group      = module.monitoring.log_group_name
}

# --- Monitoring ---
module "monitoring" {
  source = "./modules/monitoring"

  name_prefix        = local.name_prefix
  alarm_email        = var.alarm_email
  log_retention_days = var.log_retention_days
  ecs_cluster_name   = module.networking.ecs_cluster_name
  ecs_service_name   = module.api.service_name
  alb_arn_suffix     = module.api.alb_arn_suffix
  target_group_arn   = module.api.target_group_arn_suffix
}
