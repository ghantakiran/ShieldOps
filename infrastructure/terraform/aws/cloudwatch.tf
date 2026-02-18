###############################################################################
# ShieldOps — CloudWatch Log Groups & Alarms
###############################################################################

# ---------------------------------------------------------------------------
# Log Groups
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project_name}-${var.environment}-app"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-${var.environment}-app-logs"
  }
}

resource "aws_cloudwatch_log_group" "opa" {
  name              = "/ecs/${var.project_name}-${var.environment}-opa"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-${var.environment}-opa-logs"
  }
}

# ---------------------------------------------------------------------------
# SNS Topic for Alarms
# ---------------------------------------------------------------------------

resource "aws_sns_topic" "alarms" {
  name = "${var.project_name}-${var.environment}-alarms"

  tags = {
    Name = "${var.project_name}-${var.environment}-alarms"
  }
}

# ---------------------------------------------------------------------------
# CloudWatch Alarms
# ---------------------------------------------------------------------------

# High CPU Utilization (>80% for 5 minutes)
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${var.project_name}-${var.environment}-high-cpu"
  alarm_description   = "ECS service CPU utilization exceeds 80% for 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.main.name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-high-cpu-alarm"
  }
}

# High Memory Utilization (>80% for 5 minutes)
resource "aws_cloudwatch_metric_alarm" "high_memory" {
  alarm_name          = "${var.project_name}-${var.environment}-high-memory"
  alarm_description   = "ECS service memory utilization exceeds 80% for 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.main.name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-high-memory-alarm"
  }
}

# Unhealthy Host Count (>0 for 2 minutes)
resource "aws_cloudwatch_metric_alarm" "unhealthy_hosts" {
  alarm_name          = "${var.project_name}-${var.environment}-unhealthy-hosts"
  alarm_description   = "ALB target group has unhealthy hosts for 2 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    TargetGroup  = aws_lb_target_group.main.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-unhealthy-hosts-alarm"
  }
}

# 5xx Errors (>10 for 5 minutes)
resource "aws_cloudwatch_metric_alarm" "http_5xx" {
  alarm_name          = "${var.project_name}-${var.environment}-5xx-errors"
  alarm_description   = "ALB is returning more than 10 5xx errors per minute for 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  dimensions = {
    TargetGroup  = aws_lb_target_group.main.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-5xx-errors-alarm"
  }
}

# ---------------------------------------------------------------------------
# SNS Email Subscription (conditional)
# ---------------------------------------------------------------------------

resource "aws_sns_topic_subscription" "alarm_email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# ---------------------------------------------------------------------------
# RDS Alarms
# ---------------------------------------------------------------------------

# RDS CPU > 80% (5 minutes)
resource "aws_cloudwatch_metric_alarm" "rds_high_cpu" {
  alarm_name          = "${var.project_name}-${var.environment}-rds-high-cpu"
  alarm_description   = "RDS CPU utilization exceeds 80% for 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-high-cpu-alarm"
  }
}

# RDS Free Storage < 5GB
resource "aws_cloudwatch_metric_alarm" "rds_low_storage" {
  alarm_name          = "${var.project_name}-${var.environment}-rds-low-storage"
  alarm_description   = "RDS free storage space is below 5GB"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5368709120
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-low-storage-alarm"
  }
}

# RDS Connections > 120 (80% of ~150 max)
resource "aws_cloudwatch_metric_alarm" "rds_high_connections" {
  alarm_name          = "${var.project_name}-${var.environment}-rds-high-connections"
  alarm_description   = "RDS database connections exceed 80% of max (~120 of 150)"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 120
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-high-connections-alarm"
  }
}

# ---------------------------------------------------------------------------
# ElastiCache Alarms
# ---------------------------------------------------------------------------

# ElastiCache CPU > 80%
resource "aws_cloudwatch_metric_alarm" "redis_high_cpu" {
  alarm_name          = "${var.project_name}-${var.environment}-redis-high-cpu"
  alarm_description   = "ElastiCache Redis CPU utilization exceeds 80%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.main.id
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-redis-high-cpu-alarm"
  }
}

# ElastiCache Evictions > 100 per 5 minutes
resource "aws_cloudwatch_metric_alarm" "redis_evictions" {
  alarm_name          = "${var.project_name}-${var.environment}-redis-evictions"
  alarm_description   = "ElastiCache Redis evictions exceed 100 per 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Sum"
  threshold           = 100
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.main.id
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-redis-evictions-alarm"
  }
}

# ElastiCache Connections > 400 (80% of ~500 max)
resource "aws_cloudwatch_metric_alarm" "redis_high_connections" {
  alarm_name          = "${var.project_name}-${var.environment}-redis-high-connections"
  alarm_description   = "ElastiCache Redis connections exceed 80% of max (~400 of 500)"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CurrConnections"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Average"
  threshold           = 400
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.main.id
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-redis-high-connections-alarm"
  }
}

# ---------------------------------------------------------------------------
# ALB Alarms
# ---------------------------------------------------------------------------

# ALB Target Response Time > 2 seconds
resource "aws_cloudwatch_metric_alarm" "alb_high_response_time" {
  alarm_name          = "${var.project_name}-${var.environment}-alb-high-response-time"
  alarm_description   = "ALB target response time exceeds 2 seconds for 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 2
  treat_missing_data  = "notBreaching"

  dimensions = {
    TargetGroup  = aws_lb_target_group.main.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-alb-high-response-time-alarm"
  }
}

# ---------------------------------------------------------------------------
# ECS Task Count Alarm
# ---------------------------------------------------------------------------

# ECS Running Tasks < Desired Count (3 minutes)
resource "aws_cloudwatch_metric_alarm" "ecs_running_tasks" {
  alarm_name          = "${var.project_name}-${var.environment}-ecs-low-running-tasks"
  alarm_description   = "ECS running tasks count is below desired count for 3 minutes"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  threshold           = var.app_desired_count
  treat_missing_data  = "breaching"

  metric_name = "RunningTaskCount"
  namespace   = "ECS/ContainerInsights"
  period      = 60
  statistic   = "Average"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.main.name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${var.project_name}-${var.environment}-ecs-low-running-tasks-alarm"
  }
}

# ---------------------------------------------------------------------------
# CloudWatch Dashboard
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}-overview"

  dashboard_body = jsonencode({
    widgets = [
      # Row 1: ECS metrics
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ECS CPU & Memory Utilization"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.main.name],
            ["AWS/ECS", "MemoryUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.main.name]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ECS Running Task Count"
          region = data.aws_region.current.name
          metrics = [
            ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.main.name]
          ]
          period = 60
          stat   = "Average"
        }
      },
      # Row 2: RDS metrics
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "RDS CPU & Connections"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.main.identifier],
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", aws_db_instance.main.identifier]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "RDS Free Storage (bytes)"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", aws_db_instance.main.identifier]
          ]
          period = 300
          stat   = "Average"
        }
      },
      # Row 3: Redis metrics
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "Redis CPU & Connections"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", "ReplicationGroupId", aws_elasticache_replication_group.main.id],
            ["AWS/ElastiCache", "CurrConnections", "ReplicationGroupId", aws_elasticache_replication_group.main.id]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "Redis Evictions"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ElastiCache", "Evictions", "ReplicationGroupId", aws_elasticache_replication_group.main.id]
          ]
          period = 300
          stat   = "Sum"
        }
      },
      # Row 4: ALB metrics
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 12
        height = 6
        properties = {
          title  = "ALB Response Time & Request Count"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "TargetGroup", aws_lb_target_group.main.arn_suffix, "LoadBalancer", aws_lb.main.arn_suffix],
            ["AWS/ApplicationELB", "RequestCount", "TargetGroup", aws_lb_target_group.main.arn_suffix, "LoadBalancer", aws_lb.main.arn_suffix]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 18
        width  = 12
        height = 6
        properties = {
          title  = "ALB 5xx & 4xx Errors"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "TargetGroup", aws_lb_target_group.main.arn_suffix, "LoadBalancer", aws_lb.main.arn_suffix],
            ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", "TargetGroup", aws_lb_target_group.main.arn_suffix, "LoadBalancer", aws_lb.main.arn_suffix]
          ]
          period = 300
          stat   = "Sum"
        }
      }
    ]
  })
}
