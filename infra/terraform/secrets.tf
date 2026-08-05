resource "aws_secretsmanager_secret" "cockroachdb_url" {
  name = "continuum/${var.environment_name}/database-url"
}

resource "aws_secretsmanager_secret_version" "cockroachdb_url" {
  secret_id     = aws_secretsmanager_secret.cockroachdb_url.id
  secret_string = var.database_url
}
