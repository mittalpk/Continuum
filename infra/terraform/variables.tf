variable "aws_region" {
  description = "AWS region to deploy the Lambda into. Doesn't need to match a CockroachDB region."
  type        = string
}

variable "database_url" {
  description = "CockroachDB connection string. Supply via -var or TF_VAR_database_url, never commit it."
  type        = string
  sensitive   = true
}

variable "embedding_model_id" {
  description = "Bedrock embedding model ID for the semantic tier."
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "lambda_package_path" {
  description = "Path to the built wheel/zip. See DEPLOYMENT.md for the build step that produces this."
  type        = string
  default     = "../build/continuum-lambda.zip"
}

variable "command_timeout_seconds" {
  description = "Per-query SQL timeout (SECURITY.md's bound on a slow/malicious query)."
  type        = number
  default     = 30
}

variable "environment_name" {
  description = "Used to namespace resource names (e.g. \"staging\", \"prod\")."
  type        = string
  default     = "staging"
}
