# Provisionamento Vultr - BBL.BOXTV

Esta pasta cria somente a VPS. O aplicativo é instalado depois por `deploy-vps.sh`.

## Recomendação
- Região: São Paulo, detectada pelo provider.
- Sistema: Ubuntu 24.04 LTS (OS id 2284).
- Plano padrão: 1 vCPU / 2 GB. Pode alterar `plan_id` para um plano maior disponível na região.
- Backups da própria VPS habilitados.

## Segurança
Não grave API key no GitHub. Use variável de ambiente:

```bash
export VULTR_API_KEY='...'
terraform init
terraform apply
```

Depois use o IP retornado para apontar o DNS e executar `deploy-vps.sh`.
