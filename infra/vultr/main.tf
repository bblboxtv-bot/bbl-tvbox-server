terraform {
  required_providers {
    vultr = {
      source  = "vultr/vultr"
      version = "~> 2.0"
    }
  }
}

provider "vultr" {
  api_key = var.vultr_api_key
}

data "vultr_region" "sao_paulo" {
  filter {
    name   = "city"
    values = ["Sao Paulo"]
  }
}

resource "vultr_instance" "bbl_boxtv" {
  region      = data.vultr_region.sao_paulo.id
  plan        = var.plan_id
  os_id       = 2284
  label       = "bbl-boxtv-production"
  hostname    = "bbl-boxtv"
  enable_ipv6 = true
  backups     = "enabled"

  tags = ["bbl-boxtv", "production", "sao-paulo"]
}

output "server_ip" {
  value = vultr_instance.bbl_boxtv.main_ip
}

output "region" {
  value = data.vultr_region.sao_paulo.id
}
