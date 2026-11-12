variable "regiao" {
  description = "Região da AWS. São Paulo mantém o dado no Brasil (LGPD)."
  type        = string
  default     = "sa-east-1"
}

variable "ambiente" {
  description = "dev, staging ou prod"
  type        = string
  default     = "prod"
}

variable "dominio" {
  description = "Domínio do painel, por exemplo painel.exemplo.com.br"
  type        = string
}

variable "alarme_email" {
  description = "E-mail do time de dados que recebe os alarmes"
  type        = string
}

variable "imagem_tag" {
  description = "Etiqueta (commit) das imagens no ECR"
  type        = string
  default     = "latest"
}

variable "tarefas_por_servico" {
  description = "Tarefas da API e do front (1 = mínimo; 2 = recomendado)"
  type        = number
  default     = 2
}

variable "banco_multi_az" {
  description = "Multi-AZ no RDS (dobra o custo do banco)"
  type        = bool
  default     = false
}

variable "certificado_alb_arn" {
  description = "Certificado ACM na região do ALB"
  type        = string
}

variable "certificado_cloudfront_arn" {
  description = "Certificado ACM em us-east-1 (exigência do CloudFront)"
  type        = string
}