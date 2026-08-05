# Least-privilege by construction: this role can read exactly one secret and
# write to its own log group. Nothing broader. See SECURITY.md's
# least-privilege rule -- DEPLOYMENT.md's earlier skeleton referenced these
# policy documents without defining them; this is the actual definition.

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "lambda_secrets_access" {
  statement {
    sid       = "ReadCockroachDBSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.cockroachdb_url.arn]
  }

  statement {
    sid = "WriteOwnLogs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${local.function_name}*"]
  }
}

resource "aws_iam_role" "continuum_lambda" {
  name               = local.function_name
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "continuum_lambda_secrets" {
  name   = "${local.function_name}-secrets-and-logs"
  role   = aws_iam_role.continuum_lambda.id
  policy = data.aws_iam_policy_document.lambda_secrets_access.json
}
