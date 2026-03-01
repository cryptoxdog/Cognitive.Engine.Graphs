# ============================================================================
# NEO4J MODULE — Enterprise on ECS with GDS Plugin + EFS persistence
# ============================================================================

# --- Security Group ---
resource "aws_security_group" "neo4j" {
  name_prefix = "${var.name_prefix}-neo4j-"
  vpc_id      = var.vpc_id

  ingress {
    description = "Bolt protocol"
    from_port   = 7687
    to_port     = 7687
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.selected.cidr_block]
  }

  ingress {
    description = "HTTP (browser)"
    from_port   = 7474
    to_port     = 7474
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.selected.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle { create_before_destroy = true }
}

data "aws_vpc" "selected" {
  id = var.vpc_id
}

# --- EFS for Neo4j Data Persistence ---
resource "aws_efs_file_system" "neo4j" {
  creation_token = "${var.name_prefix}-neo4j-data"
  encrypted      = true

  tags = { Name = "${var.name_prefix}-neo4j-efs" }
}

resource "aws_efs_mount_target" "neo4j" {
  count           = length(var.subnet_ids)
  file_system_id  = aws_efs_file_system.neo4j.id
  subnet_id       = var.subnet_ids[count.index]
  security_groups = [aws_security_group.neo4j.id]
}

# --- IAM Role ---
resource "aws_iam_role" "neo4j_task" {
  name_prefix = "${var.name_prefix}-neo4j-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "neo4j_exec" {
  role       = aws_iam_role.neo4j_task.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "neo4j_ssm" {
  name_prefix = "ssm-"
  role        = aws_iam_role.neo4j_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter", "ssm:GetParameters"]
      Resource = "arn:aws:ssm:*:*:parameter/l9/*"
    }]
  })
}

# --- Task Definition ---
resource "aws_ecs_task_definition" "neo4j" {
  family                   = "${var.name_prefix}-neo4j"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.neo4j_task.arn
  task_role_arn            = aws_iam_role.neo4j_task.arn

  volume {
    name = "neo4j-data"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.neo4j.id
      root_directory = "/"
    }
  }

  container_definitions = jsonencode([{
    name  = "neo4j"
    image = var.image
    essential = true

    portMappings = [
      { containerPort = 7687, protocol = "tcp" },
      { containerPort = 7474, protocol = "tcp" }
    ]

    environment = [
      { name = "NEO4J_AUTH",                          value = "neo4j/changeme" },
      { name = "NEO4J_ACCEPT_LICENSE_AGREEMENT",      value = "yes" },
      { name = "NEO4J_PLUGINS",                       value = var.gds_enabled ? "["graph-data-science"]" : "[]" },
      { name = "NEO4J_dbms_memory_heap_initial__size", value = "${floor(var.memory * 0.4)}m" },
      { name = "NEO4J_dbms_memory_heap_max__size",     value = "${floor(var.memory * 0.4)}m" },
      { name = "NEO4J_dbms_memory_pagecache_size",     value = "${floor(var.memory * 0.3)}m" },
      { name = "NEO4J_dbms_security_procedures_unrestricted", value = "gds.*" },
    ]

    secrets = [
      {
        name      = "NEO4J_AUTH"
        valueFrom = var.ssm_password_arn
      }
    ]

    mountPoints = [{
      sourceVolume  = "neo4j-data"
      containerPath = "/data"
      readOnly      = false
    }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/${var.name_prefix}-neo4j"
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "neo4j"
      }
    }
  }])
}

data "aws_region" "current" {}

# --- Service ---
resource "aws_ecs_service" "neo4j" {
  name            = "${var.name_prefix}-neo4j"
  cluster         = var.ecs_cluster_id
  task_definition = aws_ecs_task_definition.neo4j.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.neo4j.id]
    assign_public_ip = false
  }

  # Neo4j is stateful — don't redeploy on every apply
  lifecycle { ignore_changes = [task_definition] }
}

# --- CloudWatch Log Group ---
resource "aws_cloudwatch_log_group" "neo4j" {
  name              = "/ecs/${var.name_prefix}-neo4j"
  retention_in_days = 30
}

# --- Service Discovery ---
resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.name_prefix}.local"
  vpc  = var.vpc_id
}

resource "aws_service_discovery_service" "neo4j" {
  name = "neo4j"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
}
