# Migração BBL.BOXTV para VPS São Paulo

Esta branch preserva o painel e a launcher atuais. A mudança é de infraestrutura, não de visual.

## Arquitetura
- API/painel FastAPI em container próprio.
- PostgreSQL em container separado, sem armazenar APKs novos no banco.
- APKs, banners, wallpapers e logos em disco persistente em `/opt/bbl-boxtv/uploads`.
- Caddy na frente, com HTTPS automático para o domínio configurado.
- Backup diário do PostgreSQL e da pasta de uploads, retenção local de 14 dias.
- Limites de conexão/statement/lock para impedir acúmulo de sessões.

## Instalação
1. Crie uma VPS Ubuntu em São Paulo.
2. Aponte um domínio/subdomínio para o IP.
3. Copie `deploy-vps.sh` para a VPS e execute como root.
4. Na primeira execução ele cria `/opt/bbl-boxtv/.env` e para. Preencha DOMAIN, ADMIN_KEY e POSTGRES_PASSWORD.
5. Execute novamente.
6. Antes de trocar a launcher, migre os dados do banco Render para o PostgreSQL novo e copie os arquivos persistentes.
7. Valide `/health`, painel, ativação, policy, bloqueio/desbloqueio, Pix e auto-update.
8. Só depois altere a URL da launcher e mantenha o Render antigo como rollback temporário.

## Importante
A branch não inclui segredos reais. O servidor novo só deve receber credenciais diretamente na VPS.
