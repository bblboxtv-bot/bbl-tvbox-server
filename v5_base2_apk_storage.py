import hashlib
from io import BytesIO

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

import v5
import v5_base2_apps as base2apps

app = v5.app


def _init_blob_table():
    c = v5.db()
    blob_type = 'BYTEA' if v5.pg() else 'BLOB'
    v5.ex(c, f"CREATE TABLE IF NOT EXISTS base2_app_blobs(app_id TEXT PRIMARY KEY, data {blob_type} NOT NULL, size_bytes INTEGER NOT NULL DEFAULT 0, sha256 TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)")
    c.commit(); c.close()


def _persist_app_file(app_id: str):
    c = v5.db()
    a = v5.one(c, 'SELECT * FROM apps WHERE id=?', (app_id,))
    if not a:
        c.close(); return False
    p = v5.UPLOAD_DIR / a['filename']
    if not p.exists():
        c.close(); return False
    data = p.read_bytes(); sha = hashlib.sha256(data).hexdigest()
    v5.ex(c, 'INSERT INTO base2_app_blobs(app_id,data,size_bytes,sha256,created_at) VALUES(?,?,?,?,?) ON CONFLICT(app_id) DO UPDATE SET data=excluded.data,size_bytes=excluded.size_bytes,sha256=excluded.sha256,created_at=excluded.created_at', (app_id, data, len(data), sha, v5.now()))
    c.commit(); c.close(); return True


def _resolve_app(c, requested_id: str):
    # New clients send an app id. Older clients/queues may still send queue ids.
    a = v5.one(c, 'SELECT * FROM apps WHERE id=?', (requested_id,))
    if a:
        return a
    q = v5.one(c, 'SELECT app_id FROM base2_remote_apps WHERE id=?', (requested_id,))
    if q:
        return v5.one(c, 'SELECT * FROM apps WHERE id=?', (q['app_id'],))
    return None


def _blob_for_app_or_equivalent(c, a):
    b = v5.one(c, 'SELECT data,size_bytes FROM base2_app_blobs WHERE app_id=?', (a['id'],))
    if b:
        return b
    # If this is an old/stale app record, reuse the bytes from the latest re-upload
    # of the same Android package/version.
    pkg = a.get('package_name') or ''
    ver = a.get('version_name') or ''
    if pkg:
        rows = v5.rows(c, 'SELECT id FROM apps WHERE package_name=? ORDER BY created_at DESC', (pkg,))
        for r in rows:
            bb = v5.one(c, 'SELECT data,size_bytes FROM base2_app_blobs WHERE app_id=?', (r['id'],))
            if bb:
                return bb
    if ver:
        rows = v5.rows(c, 'SELECT id FROM apps WHERE version_name=? ORDER BY created_at DESC', (ver,))
        for r in rows:
            bb = v5.one(c, 'SELECT data,size_bytes FROM base2_app_blobs WHERE app_id=?', (r['id'],))
            if bb:
                return bb
    return None


_init_blob_table()

@app.middleware('http')
async def persist_base2_apk_uploads(request: Request, call_next):
    response = await call_next(request)
    if request.method == 'POST' and request.url.path in {'/base2/painel/aplicativos/upload','/base2/revenda/aplicativos/upload'} and response.status_code < 400:
        try:
            c=v5.db(); a=v5.one(c,'SELECT id FROM apps ORDER BY created_at DESC LIMIT 1'); c.close()
            if a: _persist_app_file(a['id'])
        except Exception:
            pass
    return response


@app.get('/base2/api/apps/{requested_id}/download')
def base2_download_apk(requested_id: str):
    c = v5.db()
    a = _resolve_app(c, requested_id)
    if not a:
        c.close(); raise HTTPException(404, 'Aplicativo não encontrado')
    b = _blob_for_app_or_equivalent(c, a)
    if b:
        data = bytes(b['data']); c.close()
        filename = a.get('filename') or (a.get('name') or 'aplicativo') + '.apk'
        headers = {'Content-Length': str(len(data)), 'Content-Disposition': f'attachment; filename="{filename}"', 'Cache-Control':'no-store'}
        return StreamingResponse(BytesIO(data), media_type='application/vnd.android.package-archive', headers=headers)
    p = v5.UPLOAD_DIR / a['filename']
    c.close()
    if p.exists():
        try: _persist_app_file(a['id'])
        except Exception: pass
        return v5.FileResponse(p, media_type='application/vnd.android.package-archive', filename=a['filename'])
    raise HTTPException(404, 'Arquivo APK não disponível. Reenvie este APK no painel.')


@app.post('/base2/api/apps/list')
async def base2_apps_list(req: Request):
    try: d = await req.json()
    except Exception: return JSONResponse({'ok':False,'error':'invalid_json'},400)
    token=str(d.get('token') or '').strip(); device=str(d.get('device_id') or '').strip()
    c=v5.db(); auth=base2apps._auth_client_by_token(c,token,device)
    if not auth:
        c.close(); return JSONResponse({'ok':False,'error':'unauthorized'},401)
    rows=v5.rows(c,"SELECT q.id queue_id,q.app_id,q.status,q.created_at,a.* FROM base2_remote_apps q JOIN apps a ON a.id=q.app_id WHERE q.client_id=? ORDER BY q.created_at DESC",(auth['client_id'],)); c.close()
    seen=set(); out=[]
    for x in rows:
        app_id=x['app_id']
        if app_id in seen: continue
        seen.add(app_id)
        out.append({'queue_id':x['queue_id'],'id':app_id,'name':x['name'],'package_name':x.get('package_name') or '','version_name':x.get('version_name') or '','version_code':x.get('version_code') or '','status':x.get('status') or 'pending','download_url':f'/base2/api/apps/{app_id}/download','sha256':x.get('sha256') or ''})
    return {'ok':True,'apps':out}
