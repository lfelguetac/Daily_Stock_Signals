terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  tickers = jsonencode([
    # Semiconductores
    "NVDA", "AMD", "AVGO", "QCOM", "MU", "ON", "MPWR", "ALAB",
    # Energia
    "XOM", "OXY", "SLB", "VTLE", "NOG", "ARIS", "PUMP",
    # Nuclear / Uranio
    "CCJ", "UUUU", "DNN", "LEU", "OKLO", "LTBR",
    # Tech Emergentes / AI
    "PLTR", "RKLB", "IONQ", "SOUN", "RGTI", "ASTS", "HIMS",
    # Mega Cap Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA",
    # Finanzas
    "JPM", "V", "GS", "MS", "BAC", "BLK", "SPGI",
    # Salud / Farma
    "JNJ", "UNH", "LLY", "ABBV", "PFE", "MRK", "AMGN",
    # Consumo
    "WMT", "PG", "HD", "DIS", "NFLX", "MCD", "COST",
    # Industrial / Defensa
    "CAT", "DE", "LMT", "RTX", "BA",
  ])
}

# S3 Bucket for signals data
resource "aws_s3_bucket" "signals" {
  bucket = "daily-signals-data-${random_id.suffix.hex}"
}

# DynamoDB table for historical scores
resource "aws_dynamodb_table" "signals" {
  name         = "daily-signals-${random_id.suffix.hex}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ticker"
  range_key    = "date"

  attribute {
    name = "ticker"
    type = "S"
  }

  attribute {
    name = "date"
    type = "S"
  }
}

# SNS Topic for email notifications
resource "aws_sns_topic" "alerts" {
  name = "daily-signals-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.email
}

# IAM Role for Lambda functions
resource "aws_iam_role" "lambda_role" {
  name = "daily-signals-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_permissions" {
  name = "daily-signals-lambda-permissions"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:Query",
          "dynamodb:BatchWriteItem"
        ]
        Resource = aws_dynamodb_table.signals.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.signals.arn}/*"
      },
      {
        Effect = "Allow"
        Action = "sns:Publish"
        Resource = aws_sns_topic.alerts.arn
      },
      {
        Effect = "Allow"
        Action = "ses:SendRawEmail"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = "states:StartExecution"
        Resource = aws_sfn_state_machine.pipeline.arn
      }
    ]
  })
}

# IAM Role for Step Functions
resource "aws_iam_role" "sfn_role" {
  name = "daily-signals-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "sfn_permissions" {
  name = "daily-signals-sfn-permissions"
  role = aws_iam_role.sfn_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.extract.arn,
          aws_lambda_function.transform.arn,
          aws_lambda_function.analyze.arn,
          aws_lambda_function.load.arn,
          aws_lambda_function.notify.arn,
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda packaging
data "archive_file" "extract" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/extract"
  output_path = "${path.module}/../functions/extract.zip"
  excludes    = ["__pycache__", "*.pyc"]
}

data "archive_file" "transform" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/transform"
  output_path = "${path.module}/../functions/transform.zip"
}

data "archive_file" "analyze" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/analyze"
  output_path = "${path.module}/../functions/analyze.zip"
}

data "archive_file" "load" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/load"
  output_path = "${path.module}/../functions/load.zip"
}

data "archive_file" "notify" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/notify"
  output_path = "${path.module}/../functions/notify.zip"
}

# Lambda: Extract (uses S3 due to large package size)
resource "aws_lambda_function" "extract" {
  s3_bucket      = aws_s3_bucket.signals.bucket
  s3_key         = "lambdas/extract.zip"
  function_name    = "daily-signals-extract"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 1024

  environment {
    variables = {
      FINNHUB_API_KEY = var.finnhub_api_key
    }
  }
}

# Lambda: Transform
resource "aws_lambda_function" "transform" {
  filename         = "${path.module}/../functions/transform.zip"
  function_name    = "daily-signals-transform"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 256
  source_code_hash = data.archive_file.transform.output_base64sha256
}

# Lambda: Analyze
resource "aws_lambda_function" "analyze" {
  filename         = "${path.module}/../functions/analyze.zip"
  function_name    = "daily-signals-analyze"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 256
  source_code_hash = data.archive_file.analyze.output_base64sha256
}

# Lambda: Load
resource "aws_lambda_function" "load" {
  filename         = "${path.module}/../functions/load.zip"
  function_name    = "daily-signals-load"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 256
  source_code_hash = data.archive_file.load.output_base64sha256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.signals.name
      BUCKET     = aws_s3_bucket.signals.bucket
    }
  }
}

# Lambda: Notify (SES for HTML email)
resource "aws_lambda_function" "notify" {
  filename         = "${path.module}/../functions/notify.zip"
  function_name    = "daily-signals-notify"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 256
  source_code_hash = data.archive_file.notify.output_base64sha256

  environment {
    variables = {
      SENDER_EMAIL    = var.email
      RECIPIENT_EMAIL = var.email
      GITHUB_PAT      = var.github_pat
    }
  }
}

# Step Functions State Machine
resource "aws_sfn_state_machine" "pipeline" {
  name     = "daily-signals-pipeline"
  role_arn = aws_iam_role.sfn_role.arn

  definition = jsonencode({
    Comment = "Daily Stock Signals ETL Pipeline"
    StartAt = "Extract"
    States = {
      Extract = {
        Type     = "Task"
        Resource = aws_lambda_function.extract.arn
        Parameters = {
          tickers = jsondecode(local.tickers)
        }
        ResultPath = "$.extract_result"
        Next     = "Transform"
        Retry = [{
          ErrorEquals      = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
          IntervalSeconds  = 5
          MaxAttempts      = 2
          BackoffRate      = 2
        }]
      }
      Transform = {
        Type     = "Task"
        Resource = aws_lambda_function.transform.arn
        InputPath = "$.extract_result"
        ResultPath = "$.transform_result"
        Next     = "Analyze"
        Retry = [{
          ErrorEquals      = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
          IntervalSeconds  = 2
          MaxAttempts      = 2
          BackoffRate      = 2
        }]
      }
      Analyze = {
        Type     = "Task"
        Resource = aws_lambda_function.analyze.arn
        InputPath = "$.transform_result"
        ResultPath = "$.analyze_result"
        Next     = "Load"
        Retry = [{
          ErrorEquals      = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
          IntervalSeconds  = 2
          MaxAttempts      = 2
          BackoffRate      = 2
        }]
      }
      Load = {
        Type     = "Task"
        Resource = aws_lambda_function.load.arn
        InputPath = "$.analyze_result"
        ResultPath = "$.load_result"
        Next     = "Notify"
        Retry = [{
          ErrorEquals      = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
          IntervalSeconds  = 2
          MaxAttempts      = 2
          BackoffRate      = 2
        }]
      }
      Notify = {
        Type     = "Task"
        Resource = aws_lambda_function.notify.arn
        InputPath = "$.analyze_result"
        End      = true
        Retry = [{
          ErrorEquals      = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
          IntervalSeconds  = 2
          MaxAttempts      = 2
          BackoffRate      = 2
        }]
      }
    }
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }
}

resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/states/daily-signals-pipeline"
  retention_in_days = 30
}

# EventBridge rule - Mon-Fri at 9:00 AM Chile (UTC-4) = 13:00 UTC
resource "aws_cloudwatch_event_rule" "daily_trigger" {
  name                = "daily-signals-trigger"
  description         = "Trigger daily stock signals pipeline at 9 AM Chile time, Mon-Fri"
  schedule_expression = "cron(0 13 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_target" "pipeline" {
  rule      = aws_cloudwatch_event_rule.daily_trigger.name
  target_id = "daily-signals-pipeline"
  arn       = aws_sfn_state_machine.pipeline.arn
  role_arn  = aws_iam_role.eventbridge_role.arn
}

resource "aws_iam_role" "eventbridge_role" {
  name = "daily-signals-eventbridge-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_permissions" {
  name = "daily-signals-eventbridge-permissions"
  role = aws_iam_role.eventbridge_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "states:StartExecution"
      Resource = aws_sfn_state_machine.pipeline.arn
    }]
  })
}

# Outputs
output "s3_bucket" {
  value = aws_s3_bucket.signals.bucket
}

output "dynamodb_table" {
  value = aws_dynamodb_table.signals.name
}

output "sns_topic" {
  value = aws_sns_topic.alerts.arn
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.pipeline.arn
}
