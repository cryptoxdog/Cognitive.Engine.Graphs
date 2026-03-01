output "alb_dns_name" {
  description = "ALB public DNS name"
  value       = "http://${aws_lb.api.dns_name}"
}

output "alb_arn_suffix" {
  value = aws_lb.api.arn_suffix
}

output "target_group_arn_suffix" {
  value = aws_lb_target_group.api.arn_suffix
}

output "service_name" {
  value = aws_ecs_service.api.name
}

output "security_group_id" {
  value = aws_security_group.api.id
}
