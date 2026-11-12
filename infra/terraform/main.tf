# ESBOÇO da implantação na AWS (infra/README.md). `terraform fmt` verificado; `plan` e `apply` NÃO executados.
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.0" }
    random = { source = "hashicorp/random", version = "~> 3.0" }
  }
}

provider "aws" {
  region = var.regiao
}

data "aws_caller_identity" "atual" {}

locals {
  nome = "acaso-${var.ambiente}"
  logs = { api = "/ecs/${local.nome}/api", web = "/ecs/${local.nome}/web", etl = "/ecs/${local.nome}/etl" }
}

# ---------------------------------------------------------------- rede (2 zonas; sem NAT: tarefas em sub-redes públicas, entrada só pelo ALB)
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name                         = local.nome
  cidr                         = "10.20.0.0/16"
  azs                          = ["${var.regiao}a", "${var.regiao}b"]
  public_subnets               = ["10.20.0.0/24", "10.20.1.0/24"]
  database_subnets             = ["10.20.10.0/24", "10.20.11.0/24"]
  create_database_subnet_group = true
  enable_nat_gateway           = false
}

resource "aws_security_group" "alb" {
  name   = "${local.nome}-alb"
  vpc_id = module.vpc.vpc_id
  ingress {
    description     = "so o CloudFront"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    prefix_list_ids = [data.aws_ec2_managed_prefix_list.cloudfront.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "tarefas" {
  name   = "${local.nome}-tarefas"
  vpc_id = module.vpc.vpc_id
  ingress {
    description     = "so o ALB"
    from_port       = 3000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "banco" {
  name   = "${local.nome}-banco"
  vpc_id = module.vpc.vpc_id
  ingress {
    description     = "so as tarefas"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.tarefas.id]
  }
}

# ---------------------------------------------------------------- imagens, base bruta e segredos
resource "aws_ecr_repository" "imagem" {
  for_each             = toset(["api", "web", "etl"])
  name                 = "${local.nome}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_s3_bucket" "bruto" {
  bucket = "${local.nome}-bruto-${data.aws_caller_identity.atual.account_id}"
}

resource "aws_s3_bucket_versioning" "bruto" {
  bucket = aws_s3_bucket.bruto.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "bruto" {
  bucket                  = aws_s3_bucket.bruto.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "random_password" "api_ro" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "api_ro" {
  name = "${local.nome}/api_ro_senha"
}

resource "aws_secretsmanager_secret_version" "api_ro" {
  secret_id     = aws_secretsmanager_secret.api_ro.id
  secret_string = random_password.api_ro.result
}

resource "random_password" "sessao" {
  length  = 48
  special = false
}

resource "aws_secretsmanager_secret" "sessao" {
  name = "${local.nome}/chave_de_sessao"
}

resource "aws_secretsmanager_secret_version" "sessao" {
  secret_id     = aws_secretsmanager_secret.sessao.id
  secret_string = random_password.sessao.result
}

# ---------------------------------------------------------------- base analítica (RDS PostgreSQL 16, sem acesso pela internet)
resource "aws_db_instance" "analitica" {
  identifier                  = local.nome
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = "db.t4g.small"
  allocated_storage           = 20
  storage_type                = "gp3"
  storage_encrypted           = true
  db_name                     = "retencao"
  username                    = "etl"
  manage_master_user_password = true
  db_subnet_group_name        = module.vpc.database_subnet_group_name
  vpc_security_group_ids      = [aws_security_group.banco.id]
  multi_az                    = var.banco_multi_az
  backup_retention_period     = 7
  deletion_protection         = true
  skip_final_snapshot         = false
  final_snapshot_identifier   = "${local.nome}-final"
  publicly_accessible         = false
}

# ---------------------------------------------------------------- permissões
data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execucao" {
  name               = "${local.nome}-execucao"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execucao" {
  role       = aws_iam_role.execucao.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "segredos" {
  role = aws_iam_role.execucao.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.api_ro.arn, aws_secretsmanager_secret.sessao.arn, aws_db_instance.analitica.master_user_secret[0].secret_arn]
    }]
  })
}

resource "aws_iam_role" "tarefa_etl" {
  name               = "${local.nome}-etl"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy" "etl_le_bruto" {
  role = aws_iam_role.tarefa_etl.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:ListBucket"]
      Resource = [aws_s3_bucket.bruto.arn, "${aws_s3_bucket.bruto.arn}/*"]
    }]
  })
}

# ---------------------------------------------------------------- ECS Fargate (ARM): API, web e ETL
resource "aws_ecs_cluster" "este" {
  name = local.nome
}

resource "aws_cloudwatch_log_group" "grupo" {
  for_each          = local.logs
  name              = each.value
  retention_in_days = 30
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.nome}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execucao.arn
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }
  container_definitions = jsonencode([{
    name         = "api"
    image        = "${aws_ecr_repository.imagem["api"].repository_url}:${var.imagem_tag}"
    portMappings = [{ containerPort = 8000 }]
    environment = [
      { name = "DATABASE_URL", value = "postgresql://api_ro@${aws_db_instance.analitica.address}:5432/retencao" },
      { name = "COOKIE_SECURE", value = "1" },
    ]
    secrets = [
      { name = "SESSION_SECRET", valueFrom = aws_secretsmanager_secret.sessao.arn },
      { name = "PGPASSWORD", valueFrom = aws_secretsmanager_secret.api_ro.arn },
    ]
    logConfiguration = { logDriver = "awslogs", options = { awslogs-group = local.logs.api, awslogs-region = var.regiao, awslogs-stream-prefix = "api" } }
  }])
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${local.nome}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execucao.arn
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }
  container_definitions = jsonencode([{
    name             = "web"
    image            = "${aws_ecr_repository.imagem["web"].repository_url}:${var.imagem_tag}"
    portMappings     = [{ containerPort = 3000 }]
    logConfiguration = { logDriver = "awslogs", options = { awslogs-group = local.logs.web, awslogs-region = var.regiao, awslogs-stream-prefix = "web" } }
  }])
}

resource "aws_ecs_task_definition" "etl" {
  family                   = "${local.nome}-etl"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.execucao.arn
  task_role_arn            = aws_iam_role.tarefa_etl.arn
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }
  container_definitions = jsonencode([{
    name  = "etl"
    image = "${aws_ecr_repository.imagem["etl"].repository_url}:${var.imagem_tag}"
    environment = [
      { name = "DATABASE_URL", value = "postgresql://etl@${aws_db_instance.analitica.address}:5432/retencao" },
      { name = "SEED_DIR", value = "/data/seed" }, # PENDENTE: na AWS a semente vem do S3 (aws s3 sync no início da tarefa)
      { name = "CODE_VERSION", value = var.imagem_tag },
      { name = "QA_ESTRITO", value = "1" },
    ]
    secrets          = [{ name = "PGPASSWORD", valueFrom = "${aws_db_instance.analitica.master_user_secret[0].secret_arn}:password::" }]
    logConfiguration = { logDriver = "awslogs", options = { awslogs-group = local.logs.etl, awslogs-region = var.regiao, awslogs-stream-prefix = "etl" } }
  }])
}

# ---------------------------------------------------------------- ALB: /api/* para a API, o resto para o front
resource "aws_lb" "entrada" {
  name               = local.nome
  load_balancer_type = "application"
  subnets            = module.vpc.public_subnets
  security_groups    = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "alvo" {
  for_each    = { api = 8000, web = 3000 }
  name        = "${local.nome}-${each.key}"
  port        = each.value
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = module.vpc.vpc_id
  health_check {
    path = each.key == "api" ? "/api/saude" : "/login"
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.entrada.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificado_alb_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.alvo["web"].arn
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.alvo["api"].arn
  }
  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

resource "aws_ecs_service" "servico" {
  for_each        = { api = aws_ecs_task_definition.api.arn, web = aws_ecs_task_definition.web.arn }
  name            = each.key
  cluster         = aws_ecs_cluster.este.id
  task_definition = each.value
  desired_count   = var.tarefas_por_servico
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = module.vpc.public_subnets
    security_groups  = [aws_security_group.tarefas.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.alvo[each.key].arn
    container_name   = each.key
    container_port   = each.key == "api" ? 8000 : 3000
  }
}

# ---------------------------------------------------------------- ETL: uma vez por dia (o portão de qualidade reverte a carga se algo divergir)
resource "aws_iam_role" "agenda" {
  name = "${local.nome}-agenda"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "scheduler.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "agenda" {
  role = aws_iam_role.agenda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = "ecs:RunTask", Resource = aws_ecs_task_definition.etl.arn },
      { Effect = "Allow", Action = "iam:PassRole", Resource = [aws_iam_role.execucao.arn, aws_iam_role.tarefa_etl.arn] },
    ]
  })
}

resource "aws_scheduler_schedule" "etl" {
  name                = "${local.nome}-etl-diario"
  schedule_expression = "cron(0 5 * * ? *)"
  flexible_time_window {
    mode = "OFF"
  }
  target {
    arn      = aws_ecs_cluster.este.arn
    role_arn = aws_iam_role.agenda.arn
    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.etl.arn
      launch_type         = "FARGATE"
      network_configuration {
        subnets          = module.vpc.public_subnets
        security_groups  = [aws_security_group.tarefas.id]
        assign_public_ip = true
      }
    }
  }
}

# ---------------------------------------------------------------- borda: CloudFront na frente do ALB (certificado em us-east-1)
resource "aws_cloudfront_distribution" "borda" {
  enabled = true
  aliases = [var.dominio]
  origin {
    domain_name = aws_lb.entrada.dns_name
    origin_id   = "alb"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }
  default_cache_behavior {
    target_origin_id         = "alb"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # CachingDisabled (dados dinâmicos); cachear /_next/static é uma melhoria
    origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3"
  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    acm_certificate_arn      = var.certificado_cloudfront_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# ---------------------------------------------------------------- alarmes: o time sabe antes do cliente (docs/INCIDENTE.md, item 4)
resource "aws_sns_topic" "alarmes" {
  name = "${local.nome}-alarmes"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alarmes.arn
  protocol  = "email"
  endpoint  = var.alarme_email
}

resource "aws_cloudwatch_metric_alarm" "api_p95" {
  alarm_name          = "${local.nome}-api-p95-lento"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  extended_statistic  = "p95"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0.3
  period              = 300
  evaluation_periods  = 3
  dimensions          = { LoadBalancer = aws_lb.entrada.arn_suffix, TargetGroup = aws_lb_target_group.alvo["api"].arn_suffix }
  alarm_actions       = [aws_sns_topic.alarmes.arn]
}

resource "aws_cloudwatch_metric_alarm" "erros_5xx" {
  alarm_name          = "${local.nome}-erros-5xx"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 5
  period              = 300
  evaluation_periods  = 1
  dimensions          = { LoadBalancer = aws_lb.entrada.arn_suffix }
  alarm_actions       = [aws_sns_topic.alarmes.arn]
}

resource "aws_cloudwatch_metric_alarm" "banco_cpu" {
  alarm_name          = "${local.nome}-banco-cpu"
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 80
  period              = 300
  evaluation_periods  = 3
  dimensions          = { DBInstanceIdentifier = aws_db_instance.analitica.identifier }
  alarm_actions       = [aws_sns_topic.alarmes.arn]
}

# ETL que termina com erro: nenhuma carga foi publicada e o painel segue no estado anterior; o time é avisado
resource "aws_cloudwatch_event_rule" "etl_falhou" {
  name = "${local.nome}-etl-falhou"
  event_pattern = jsonencode({
    source        = ["aws.ecs"]
    "detail-type" = ["ECS Task State Change"]
    detail        = { lastStatus = ["STOPPED"], taskDefinitionArn = [{ prefix = "arn:aws:ecs:${var.regiao}:${data.aws_caller_identity.atual.account_id}:task-definition/${local.nome}-etl" }], containers = { exitCode = [{ "anything-but" = 0 }] } }
  })
}

resource "aws_cloudwatch_event_target" "etl_falhou" {
  rule = aws_cloudwatch_event_rule.etl_falhou.name
  arn  = aws_sns_topic.alarmes.arn
}