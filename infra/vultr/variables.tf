variable "vultr_api_key" {
  description = "Vultr API key. Prefer VULTR_API_KEY environment variable in CI/terminal."
  type        = string
  sensitive   = true
  default     = null
}

variable "plan_id" {
  description = "Vultr Cloud Compute plan available in Sao Paulo."
  type        = string
  default     = "vc2-1c-2gb"
}
