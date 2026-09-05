# BBL TVBOX Server V2

Servidor FastAPI compatível com o APK analisado, com ativação de dispositivos, política remota, bloqueio/desbloqueio e painel administrativo.

## Rotas principais

- `POST /api/enroll`
- `GET /api/devices/{device_id}/policy`
- Painel administrativo em `/admin`

## Variáveis de ambiente

- `DATABASE_URL`
- `ADMIN_KEY`
- `ACTIVATION_KEY`

## Execução local

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Render

O projeto inclui `render.yaml` e `Dockerfile` para implantação.
