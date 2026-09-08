import json, secrets, hashlib
from fastapi import Request, Form, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import v5
import v5_base2_gate as admin
import v5_base2_reseller_portal as reseller

app = v5.app


def init_remote_apps():
    c = v5.db()
    v5.ex(c, "CREATE TABLE IF NOT EXISTS base2_remote_apps(id TEXT PRIMARY KEY,client_id TEXT NOT NULL,app_id TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL,finished_at TEXT,result TEXT NOT NULL DEFAULT '')")
    blob_type = 'BYTEA' if v5.pg() else 'BLOB'
    v5.ex(c, f"CREATE TABLE IF NOT EXISTS base2_app_blobs(app_id TEXT PRIMARY KEY, data {blob_type} NOT NULL, size_bytes INTEGER NOT NULL DEFAULT 0, sha256 TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)")
    c.commit(); c.close()

init_remote_apps()


def usable_apps(c):
    return v5.rows(c, '''
        SELECT a.* FROM apps a
        JOIN base2_app_blobs b ON b.app_id=a.id
        WHERE b.size_bytes > 0
        ORDER BY a.name, a.created_at DESC
    ''')


def resolve_persisted_app(c, app_id: str):
    a = v5.one(c, 'SELECT * FROM apps WHERE id=?', (app_id,))
    if not a:
        return None
    b = v5.one(c, 'SELECT app_id FROM base2_app_blobs WHERE app_id=? AND size_bytes>0', (app_id,))
    if b:
        return a
    pkg = a.get('package_name') or ''
    if pkg:
        return v5.one(c, '''
            SELECT a.* FROM apps a
            JOIN base2_app_blobs b ON b.app_id=a.id
            WHERE a.package_name=? AND b.size_bytes>0
            ORDER BY a.created_at DESC LIMIT 1
        ''', (pkg,))
    return None


def queue_install(c, client_id: str, app_id: str):
    cl = v5.one(c, 'SELECT * FROM base2_clients WHERE id=?', (client_id,))
    if not cl:
        raise HTTPException(404, 'Cliente não encontrado')
    a = resolve_persisted_app(c, app_id)
    if not a:
        raise HTTPException(409, 'APK não está salvo no servidor. Reenvie esse aplicativo no painel Base 2.')
    app_id = a['id']
    existing = v5.one(c, "SELECT * FROM base2_remote_apps WHERE client_id=? AND app_id=? AND status='pending'", (client_id, app_id))
    if not existing:
        v5.ex(c, 'INSERT INTO base2_remote_apps(id,client_id,app_id,status,created_at,result) VALUES(?,?,?,?,?,?)',
              (secrets.token_hex(8), client_id, app_id, 'pending', v5.now(), ''))
    return cl, a


def save_app(apk, name):
    fn = v5.save(apk, 'apk', {'.apk'})
    p = v5.UPLOAD_DIR / fn
    data = p.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    m = v5.apkmeta(p)
    m['name'] = name.strip() or m['name']
    aid = secrets.token_hex(8)
    c = v5.db()
    try:
        old_ids = []
        if m.get('package_name'):
            old_ids = [x['id'] for x in v5.rows(c, 'SELECT id FROM apps WHERE package_name=?', (m['package_name'],))]
        v5.ex(c, 'INSERT INTO apps(id,name,package_name,version_name,version_code,filename,size_bytes,sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
              (aid, m['name'], m['package_name'], m['version_name'], m['version_code'], fn, len(data), h, v5.now()))
        v5.ex(c, 'INSERT INTO base2_app_blobs(app_id,data,size_bytes,sha256,created_at) VALUES(?,?,?,?,?)',
              (aid, data, len(data), h, v5.now()))
        for old_id in old_ids:
            v5.ex(c, 'UPDATE base2_remote_apps SET app_id=? WHERE app_id=?', (aid, old_id))
        c.commit()
    except Exception:
        c.rollback(); c.close(); raise
    c.close()
    return aid


def app_cards(rows):
    return ''.join(
        f'<div class="card"><b>{admin.esc(a["name"])}</b><br><span class="muted">{admin.esc(a.get("package_name") or "-")} • versão {admin.esc(a.get("version_name") or "-")} • APK SALVO</span></div>'
        for a in rows
    ) or '<div class="card muted">Nenhum APK salvo. Use “Adicionar APK” para enviar os aplicativos novamente.</div>'


@app.get('/base2/painel/aplicativos')
def admin_apps(req: Request, ok: str=''):
    if not admin.admin_ok(req):
        return admin.redir('/base2/painel/login')
    c = v5.db()
    apps = usable_apps(c)
    clients = v5.rows(c, 'SELECT c.*,r.name reseller_name FROM base2_clients c LEFT JOIN base2_resellers r ON r.id=c.reseller_id ORDER BY c.name')
    c.close()
    aopts = ''.join(f'<option value="{a["id"]}">{admin.esc(a["name"])} • {admin.esc(a.get("package_name") or "")}</option>' for a in apps)
    copts = ''.join(f'<option value="{x["id"]}">{admin.esc(x["name"])} • {admin.esc(x["username"])} • {admin.esc(x.get("reseller_name") or "ADMIN")}</option>' for x in clients)
    msg = f'<div class="card good">{admin.esc(ok)}</div>' if ok else ''
    body = msg + f'''<div class="card"><h3>Adicionar APK</h3><div class="muted">Os APKs enviados aqui ficam salvos de forma persistente no banco do servidor.</div><form enctype="multipart/form-data" method="post" action="/base2/painel/aplicativos/upload"><input name="name" placeholder="Nome opcional"><input type="file" name="apk" accept=".apk" required><button>ADICIONAR APK</button></form></div>
    <div class="card"><h3>Instalar remotamente</h3><form method="post" action="/base2/painel/aplicativos/instalar"><select name="client_id" required><option value="">Escolha o cliente</option>{copts}</select><select name="app_id" required><option value="">Escolha o aplicativo</option>{aopts}</select><button>INSTALAR NO CLIENTE</button></form></div>
    <h3>Aplicativos disponíveis</h3><div class="grid">{app_cards(apps)}</div>'''
    return admin.page('Aplicativos / Instalação remota', body)


@app.post('/base2/painel/aplicativos/upload')
def admin_app_upload(req: Request, name: str=Form(''), apk: UploadFile=File(...)):
    admin.adm(req)
    save_app(apk, name)
    return admin.redir('/base2/painel/aplicativos?ok=APK+adicionado+e+salvo+com+sucesso')


@app.post('/base2/painel/aplicativos/instalar')
def admin_install(req: Request, client_id: str=Form(...), app_id: str=Form(...)):
    admin.adm(req)
    c = v5.db(); cl, a = queue_install(c, client_id, app_id); c.commit(); c.close()
    return admin.redir('/base2/painel/aplicativos?ok=Instalação+enviada')


@app.get('/base2/revenda/aplicativos')
def reseller_apps(req: Request, ok: str=''):
    r = reseller.session_reseller(req)
    if not r:
        return reseller.redir('/base2/revenda/login')
    c = v5.db()
    apps = usable_apps(c)
    clients = v5.rows(c, 'SELECT * FROM base2_clients WHERE reseller_id=? ORDER BY name', (r['id'],))
    c.close()
    aopts = ''.join(f'<option value="{a["id"]}">{reseller.esc(a["name"])} • {reseller.esc(a.get("package_name") or "")}</option>' for a in apps)
    copts = ''.join(f'<option value="{x["id"]}">{reseller.esc(x["name"])} • {reseller.esc(x["username"])}</option>' for x in clients)
    msg = f'<div class="card good">{reseller.esc(ok)}</div>' if ok else ''
    body = msg + f'''<div class="card"><h3>Adicionar APK</h3><form enctype="multipart/form-data" method="post" action="/base2/revenda/aplicativos/upload"><input name="name" placeholder="Nome opcional"><input type="file" name="apk" accept=".apk" required><button>ADICIONAR APK</button></form></div>
    <div class="card"><h3>Instalar remotamente em cliente</h3><form method="post" action="/base2/revenda/aplicativos/instalar"><select name="client_id" required><option value="">Escolha o cliente</option>{copts}</select><select name="app_id" required><option value="">Escolha o aplicativo</option>{aopts}</select><button>INSTALAR NO CLIENTE</button></form></div><div class="grid">{app_cards(apps)}</div>'''
    return reseller.page('Aplicativos / Instalação remota', body)


@app.post('/base2/revenda/aplicativos/upload')
def reseller_app_upload(req: Request, name: str=Form(''), apk: UploadFile=File(...)):
    reseller.require_reseller(req)
    save_app(apk, name)
    return reseller.redir('/base2/revenda/aplicativos?ok=APK+adicionado+e+salvo+com+sucesso')


@app.post('/base2/revenda/aplicativos/instalar')
def reseller_install(req: Request, client_id: str=Form(...), app_id: str=Form(...)):
    r = reseller.require_reseller(req)
    c = v5.db()
    cl = v5.one(c, 'SELECT * FROM base2_clients WHERE id=? AND reseller_id=?', (client_id, r['id']))
    if not cl:
        c.close(); raise HTTPException(404, 'Cliente não encontrado')
    queue_install(c, client_id, app_id); c.commit(); c.close()
    return reseller.redir('/base2/revenda/aplicativos?ok=Instalação+enviada')


def _auth_client_by_token(c, token: str, device_id: str):
    th = hashlib.sha256((token or '').encode()).hexdigest()
    row = v5.one(c, 'SELECT t.client_id,t.device_id,c.enabled,c.expires_at FROM base2_tokens t JOIN base2_clients c ON c.id=t.client_id WHERE t.token_hash=?', (th,))
    if not row or not row.get('enabled') or row.get('device_id') != device_id:
        return None
    return row


@app.post('/base2/api/apps/pending')
async def api_pending_apps(req: Request):
    try: d = await req.json()
    except Exception: return JSONResponse({'ok':False,'error':'invalid_json'}, 400)
    token = str(d.get('token') or '').strip(); device = str(d.get('device_id') or '').strip()
    c = v5.db(); auth = _auth_client_by_token(c, token, device)
    if not auth:
        c.close(); return JSONResponse({'ok':False,'error':'unauthorized'}, 401)
    x = v5.one(c, "SELECT q.id queue_id,q.app_id,a.* FROM base2_remote_apps q JOIN apps a ON a.id=q.app_id JOIN base2_app_blobs b ON b.app_id=a.id WHERE q.client_id=? AND q.status='pending' AND b.size_bytes>0 ORDER BY q.created_at LIMIT 1", (auth['client_id'],))
    c.close()
    if not x: return {'ok':True,'app':None}
    aid = x['app_id']
    return {'ok':True,'app':{'queue_id':x['queue_id'],'id':aid,'name':x['name'],'package_name':x.get('package_name') or '', 'version_name':x.get('version_name') or '', 'version_code':x.get('version_code') or '', 'download_url':f"https://bbl-tvbox-manager-v2.onrender.com/base2/api/apps/{aid}/download", 'sha256':x.get('sha256') or ''}}


@app.post('/base2/api/apps/result')
async def api_remote_app_result(req: Request):
    try: d = await req.json()
    except Exception: return JSONResponse({'ok':False,'error':'invalid_json'}, 400)
    token = str(d.get('token') or '').strip(); device = str(d.get('device_id') or '').strip(); qid = str(d.get('queue_id') or '').strip(); status = str(d.get('status') or 'done').strip()[:20]; result = str(d.get('result') or '')[:500]
    c = v5.db(); auth = _auth_client_by_token(c, token, device)
    if not auth:
        c.close(); return JSONResponse({'ok':False,'error':'unauthorized'}, 401)
    q = v5.one(c, 'SELECT * FROM base2_remote_apps WHERE id=? AND client_id=?', (qid, auth['client_id']))
    if not q:
        c.close(); return JSONResponse({'ok':False,'error':'not_found'}, 404)
    v5.ex(c, 'UPDATE base2_remote_apps SET status=?,finished_at=?,result=? WHERE id=?', (status, v5.now(), result, qid)); c.commit(); c.close()
    return {'ok':True}
