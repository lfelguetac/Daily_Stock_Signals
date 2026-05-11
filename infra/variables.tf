variable "aws_region" {
  default = "us-east-1"
}

variable "finnhub_api_key" {
  description = "Finnhub API key for news sentiment"
  type        = string
  sensitive   = true
}

variable "email" {
  description = "Email for SNS notifications"
  default     = "lf.elgueta@gmail.com"
}

variable "github_pat" {
  description = "GitHub Personal Access Token for README updates"
  type        = string
  sensitive   = true
}
