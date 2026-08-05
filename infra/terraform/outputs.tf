output "function_url" {
  description = "HTTP endpoint for the MCP server -- point Bedrock Agents or any MCP client here."
  value       = aws_lambda_function_url.continuum_mcp_server.function_url
}

output "lambda_function_arn" {
  value = aws_lambda_function.continuum_mcp_server.arn
}

output "cockroachdb_secret_arn" {
  value = aws_secretsmanager_secret.cockroachdb_url.arn
}
