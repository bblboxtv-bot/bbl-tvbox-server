import hashlib
from fastapi import Request
from fastapi.responses import JSONResponse
import v5

app = v5.app


def _auth_client(c, token: str, device_id: str):
    th = hashlib.sha256((token or '').encode()).hexdigest()
    row = v5.one(c, 'SELECT t.client_id,t.device_id,c.enabled,c.expires_at FROM base2_tokens t JOIN base2_clients c ON c.id=t.client_id WHERE t.token_hash=?', (th,))
    if not row or not row.get('enabled') or row.get('device_id') != device_id:
        return None
    return row


@app.post('/base2/api/apps/list')
async def api_apps_list(req: Request):
    try:
        d = await req.json()
    except Exception:
        return JSONResponse({'ok': False, 'error': 'invalid_json'}, 400)
    token = str(d.get('token') or '').strip()
    device = str(d.get('device_id') or '').strip()
    c = v5.db()
    auth = _auth_client(c, token, device)
    if not auth:
        c.close()
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, 401)
    rows = v5.rows(c, '''
        SELECT q.id queue_id,q.status queue_status,q.created_at queue_created,a.*
        FROM base2_remote_apps q
        JOIN apps a ON a.id=q.app_id
        WHERE q.client_id=?
        ORDER BY CASE WHEN q.status='pending' THEN 0 ELSE 1 END, q.created_at DESC
    ''', (auth['client_id'],))
    c.close()
    seen = set()
    out = []
    for x in rows:
        aid = x.get('id')
        if aid in seen:
            continue
        seen.add(aid)
        out.append({
            'queue_id': x.get('queue_id') or '',
            'id': aid,
            'name': x.get('name') or 'Aplicativo',
            'package_name': x.get('package_name') or '',
            'version_name': x.get('version_name') or '',
            'version_code': x.get('version_code') or '',
            'status': x.get('queue_status') or 'pending',
            'download_url': f"/api/apps/{aid}/download",
            'sha256': x.get('sha256') or ''
        })
    return {'ok': True, 'apps': out}
