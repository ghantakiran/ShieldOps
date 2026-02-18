###############################################################################
# ShieldOps — ECS Fargate Cluster, Task Definition & Service
###############################################################################

# ---------------------------------------------------------------------------
# ECS Cluster
# ---------------------------------------------------------------------------

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-cluster"
  }
}

# ---------------------------------------------------------------------------
# ECS Task Definition
# ---------------------------------------------------------------------------

resource "aws_ecs_task_definition" "main" {
  family                   = "${var.project_name}-${var.environment}-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.app_cpu
  memory                   = var.app_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "shieldops-app"
      image     = var.container_image
      essential = true

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "DATABASE_HOST"
          value = aws_db_instance.main.address
        },
        {
          name  = "DATABASE_PORT"
          value = tostring(aws_db_instance.main.port)
        },
        {
          name  = "DATABASE_NAME"
          value = "shieldops"
        },
        {
          name  = "DATABASE_USER"
          value = "shieldops_admin"
        },
        {
          name  = "REDIS_HOST"
          value = aws_elasticache_replication_group.main.primary_endpoint_address
        },
        {
          name  = "REDIS_PORT"
          value = tostring(aws_elasticache_replication_group.main.port)
        },
        {
          name  = "REDIS_TLS"
          value = "true"
        },
        {
          name  = "OPA_ENDPOINT"
          value = "http://localhost:8181"
        },
        {
          name  = "APP_PORT"
          value = "8000"
        }
      ]

      secrets = [
        {
          name      = "DATABASE_PASSWORD"
          valueFrom = aws_secretsmanager_secret.rds_password.arn
        },
        {
          name      = "ANTHROPIC_API_KEY"
          valueFrom = "${var.secrets_arn}:ANTHROPIC_API_KEY::"
        },
        {
          name      = "JWT_SECRET"
          valueFrom = "${var.secrets_arn}:JWT_SECRET::"
        },
        {
          name      = "OPENAI_API_KEY"
          valueFrom = "${var.secrets_arn}:OPENAI_API_KEY::"
        },
        {
          name      = "LANGSMITH_API_KEY"
          valueFrom = "${var.secrets_arn}:LANGSMITH_API_KEY::"
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
    },
    {
      name      = "opa-sidecar"
      image     = "openpolicyagent/opa:latest"
      essential = false

      command = ["run", "--server", "--addr", "0.0.0.0:8181"]

      portMappings = [
        {
          containerPort = 8181
          hostPort      = 8181
          protocol      = "tcp"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.opa.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-${var.environment}-task"
  }
}

# ---------------------------------------------------------------------------
# ECS Service
# ---------------------------------------------------------------------------

resource "aws_ecs_service" "main" {
  name            = "${var.project_name}-${var.environment}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.main.arn
  desired_count   = var.app_desired_count
  launch_type     = "FARGATE"

  force_new_deployment = true

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.main.arn
    container_name   = "shieldops-app"
    container_port   = 8000
  }

  depends_on = [
    aws_lb_listener.https,
    aws_lb_listener.http,
  ]

  tags = {
    Name = "${var.project_name}-${var.environment}-service"
  }
}
