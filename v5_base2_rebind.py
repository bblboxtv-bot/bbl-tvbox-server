from datetime import datetime, timezone
from fastapi import Request
from fastapi.responses import JSONResponse
import v5
import v5_base2_gate as gate

app = v5.app

@app.post('/base2/api/rebind')
async def api_rebind(req: Request):
    try:
        d = await req.json()
    except Exception:
        return JSONResponse({'ok': False, 'error': 'invalid_json'}, 400)

    username = str(d.get('username') or '').strip()
    password = str(d.get('password') or '')
    device = str(d.get('device_id') or '').strip()
    if not username or not password or not device:
        return JSONResponse({'ok': False, 'error': 'missing_fields'}, 400)

    c = v5.db()
    x = v5.one(c, '''
        SELECT c.*, r.enabled reseller_enabled
        FROM base2_clients c
        LEFT JOIN base2_resellers r ON r.id = c.reseller_id
        WHERE lower(c.username) = lower(?)
    ''', (username,))

    if not x or not gate.pcheck(password, x['password_hash']):
        c.close()
        return JSONResponse({'ok': False, 'error': 'invalid_credentials'}, 401)
    if not x['enabled'] or (x.get('reseller_id') and x.get('reseller_enabled') == 0):
        c.close()
        return JSONResponse({'ok': False, 'error': 'blocked'}, 403)
    try:
        if x['expires_at'] and datetime.fromisoformat(x['expires_at'].replace('Z', '+00:00')) < datetime.now(timezone.utc):
            c.close()
            return JSONResponse({'ok': False, 'error': 'expired'}, 403)
    except Exception:
        pass

    v5.ex(c, 'UPDATE base2_clients SET device_id=? WHERE id=?', (device, x['id']))
    v5.ex(c, 'DELETE FROM base2_tokens WHERE client_id=?', (x['id'],))
    c.commit()
    c.close()
    return {'ok': True, 'device_id': device}
