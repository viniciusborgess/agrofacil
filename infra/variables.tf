variable "subscription_id" {
  description = "Assinatura Azure"
  type        = string
}

variable "location" {
  description = "Região Azure permitida pela assinatura"
  type        = string
  default     = "brazilsouth"
}

variable "project" {
  type    = string
  default = "agrofacil"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "github_repo" {
  description = "Repositório autorizado a publicar, como aparece no token OIDC do GitHub: dono@id/nome@id"
  type        = string
}

variable "image_tag" {
  description = "Tag da primeira imagem. Vazio cria só a base, sem o aplicativo."
  type        = string
  default     = ""
}

variable "metrics_token" {
  description = "Token exigido pelo endpoint /metrics"
  type        = string
  sensitive   = true
}

variable "min_replicas" {
  type    = number
  default = 1
}

variable "max_replicas" {
  type    = number
  default = 3
}
