output "host" {
  description = "Neo4j service discovery hostname"
  value       = "${aws_service_discovery_service.neo4j.name}.${aws_service_discovery_private_dns_namespace.main.name}"
}

output "security_group_id" {
  value = aws_security_group.neo4j.id
}

output "efs_id" {
  value = aws_efs_file_system.neo4j.id
}
