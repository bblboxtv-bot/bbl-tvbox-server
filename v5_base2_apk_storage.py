from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import v5
import v5_base2_apps as base2apps

app = v5.app


def _resolve_app(c, requested_id: str):
    a=v5.one(c,'SELECT * FROM apps WHERE id=?',(requested_id,))
    if a:return a
    q=v5.one(c,'SELECT app_id FROM base2_remote_apps WHERE id=?',(requested_id,))
    if q:return v5.one(c,'SELECT * FROM apps WHERE id=?',(q['app_id'],))
    return None


def _find_ready_equivalent(c,a):
    f=v5.one(c,'SELECT * FROM base2_app_files WHERE app_id=? AND ready=1',(a['id'],))
    if f:return a,f
    pkg=a.get('package_name') or ''
    if pkg:
        x=v5.one(c,'''SELECT a.*,f.size_bytes stored_size,f.sha256 stored_sha,f.chunk_count stored_chunks
            FROM apps a JOIN base2_app_files f ON f.app_id=a.id
            WHERE a.package_name=? AND f.ready=1 ORDER BY a.created_at DESC LIMIT 1''',(pkg,))
        if x:
            return x,{'size_bytes':x['stored_size'],'sha256':x['stored_sha'],'chunk_count':x['stored_chunks']}
    return None,None


def _chunk_stream(app_id, chunk_count):
    for idx in range(int(chunk_count)):
        c=v5.db(); row=v5.one(c,'SELECT data FROM base2_app_chunks WHERE app_id=? AND chunk_index=?',(app_id,idx)); c.close()
        if not row:
            raise RuntimeError(f'chunk {idx} ausente')
        yield bytes(row['data'])


@app.get('/base2/api/apps/{requested_id}/download')
def base2_download_apk(requested_id:str):
    c=v5.db(); a=_resolve_app(c,requested_id)
    if not a:
        c.close(); raise HTTPException(404,'Aplicativo não encontrado')
    stored,meta=_find_ready_equivalent(c,a); c.close()
    if stored and meta:
        filename=stored.get('filename') or ((stored.get('name') or 'aplicativo')+'.apk')
        headers={'Content-Length':str(meta['size_bytes']),'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'}
        return StreamingResponse(_chunk_stream(stored['id'],meta['chunk_count']),media_type='application/vnd.android.package-archive',headers=headers)
    p=v5.UPLOAD_DIR/a['filename']
    if p.exists():
        return v5.FileResponse(p,media_type='application/vnd.android.package-archive',filename=a['filename'])
    raise HTTPException(404,'Arquivo APK não disponível. Reenvie este APK no painel.')


@app.post('/base2/api/apps/list')
async def base2_apps_list(req:Request):
    try:d=await req.json()
    except Exception:return JSONResponse({'ok':False,'error':'invalid_json'},400)
    token=str(d.get('token') or '').strip();device=str(d.get('device_id') or '').strip();c=v5.db();auth=base2apps._auth_client_by_token(c,token,device)
    if not auth:c.close();return JSONResponse({'ok':False,'error':'unauthorized'},401)
    rows=v5.rows(c,"SELECT q.id queue_id,q.app_id,q.status,q.created_at,a.* FROM base2_remote_apps q JOIN apps a ON a.id=q.app_id JOIN base2_app_files f ON f.app_id=a.id WHERE q.client_id=? AND f.ready=1 ORDER BY q.created_at DESC",(auth['client_id'],));c.close()
    seen=set();out=[]
    for x in rows:
        aid=x['app_id']
        if aid in seen:continue
        seen.add(aid);out.append({'queue_id':x['queue_id'],'id':aid,'name':x['name'],'package_name':x.get('package_name') or '','version_name':x.get('version_name') or '','version_code':x.get('version_code') or '','status':x.get('status') or 'pending','download_url':f'https://bbl-tvbox-manager-v2.onrender.com/base2/api/apps/{aid}/download','sha256':x.get('sha256') or ''})
    return {'ok':True,'apps':out}
