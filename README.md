# BBL.BOXTV Server V3

Backend FastAPI para gerenciamento autorizado de launchers Android/TV Box.

## Recursos
- Ativação por chave e ID de dispositivo
- Painel para gerar, ativar e desativar códigos de ativação
- Bloqueio/desbloqueio e vencimento
- Layout por dispositivo
- Upload automático de APK com extração de nome/pacote/versão
- Catálogo e download de APK
- Notificações e logs
- Informações de fabricante/modelo/Android/versão da launcher
- SQLite local ou PostgreSQL no Render

## Rodar local
```bash
pip install -r requirements.txt
set ADMIN_KEY=uma-chave-forte
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
No Linux/macOS use `export ADMIN_KEY=...`.

Abra `http://localhost:8000` e informe a ADMIN_KEY.

## Variáveis
Veja `.env.example`. Em produção, use uma ADMIN_KEY forte e PostgreSQL persistente.

## Launcher
1. `POST /api/enroll` com chave de ativação e dados do aparelho.
2. Guardar `device_id` e `device_token` retornados.
3. Consultar `GET /api/devices/{device_id}/policy` com `Authorization: Bearer <device_token>`.
4. A resposta contém bloqueio, vencimento, layout e apps autorizados.
5. `GET /api/devices/{device_id}/notifications` retorna notificações pendentes.

A instalação/atualização de APK deve respeitar as permissões e políticas do Android do aparelho.

## Novidades da V3 atualizada
- Nome do serviço Render corrigido para `bbl-tvbox-manager-v3`.
- Nova aba **Ativações** no painel.
- Geração automática de códigos no formato `BBL-XXXX-XXXX`.
- Possibilidade de criar código personalizado e ativar/desativar códigos existentes.
