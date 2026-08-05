resource "aws_lambda_function" "continuum_mcp_server" {
  function_name    = local.function_name
  role             = aws_iam_role.continuum_lambda.arn
  handler          = "continuum.server.handler"
  runtime          = "python3.12"
  timeout          = 30
  filename         = var.lambda_package_path
  source_code_hash = filebase64sha256(var.lambda_package_path)

  environment {
    variables = {
      COCKROACHDB_SECRET_ARN                = aws_secretsmanager_secret.cockroachdb_url.arn
      MCP_CONTINUUM_EMBEDDING_MODEL         = var.embedding_model_id
      MCP_CONTINUUM_COMMAND_TIMEOUT_SECONDS = tostring(var.command_timeout_seconds)
    }
  }
}

# Streamable HTTP needs an HTTP-reachable endpoint; a Function URL is the
# simplest one Mangum's API Gateway v2 event format already supports, without
# adding a separate API Gateway resource. auth_type = NONE is a demo-scope
# choice (SRS §13) -- see SECURITY.md before reusing this beyond the demo.
resource "aws_lambda_function_url" "continuum_mcp_server" {
  function_name      = aws_lambda_function.continuum_mcp_server.function_name
  authorization_type = "NONE"
}
