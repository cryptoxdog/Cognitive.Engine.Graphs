# ============================================================================
# ROOT OUTPUTS — Everything you need post-deploy
# ============================================================================

output "api_url" {
  description = "API load balancer URL"
  value       = module.api.alb_dns_name
}

output "neo4j_host" {
  description = "Neo4j internal hostname"
  value       = module.neo4j.host
}

output "neo4j_bolt_uri" {
  description = "Neo4j Bolt URI"
  value       = "bolt://${module.neo4j.host}:7687"
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = module.redis.endpoint
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.networking.ecs_cluster_name
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = module.monitoring.dashboard_url
}

output "env_vars_summary" {
  description = "Environment variables configured for API containers"
  value = {
    NEO4J_URI    = "bolt://${module.neo4j.host}:7687"
    REDIS_URL    = "redis://${module.redis.endpoint}:6379/0"
    API_PORT     = var.api_port
    LOG_LEVEL    = var.log_level
    DOMAINS_ROOT = var.domains_root
  }
}
