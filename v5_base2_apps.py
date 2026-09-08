import json, secrets, hashlib
from pathlib import Path
from fastapi import Request, Form, UploadFile, File, HTTPException
import v5
import v5_base2_gate as admin
import v5_base2_reseller_portal as reseller

app = v5.app

# Make per-device app assignments work even when the Launcher device already has a layout.
_original_payload = v5.payload

def _payload_with_device_apps(c, d):
    out = _original_payload(c, d)
    existing = {x.get('id') for x in out.get('apps', [])} | {x.get('package_name') for x in out.get('apps', [])}
    try:
        extra_ids = json.loads(d.get('allowed_apps') or '[]')
    except Exception:
        extra_ids = []
    for app_id in extra_ids:
        a = v5.one(c, 'SELECT * FROM apps WHERE id=? OR package_name=?', (app_id, app_id))
        if not a or a.get('id') in existing or a.get('package_name') in existing:
            continue
        item = {k: a.get(k) for k in ('id','name','package_name','version_name','version_code','size_bytes','sha256')}
        item['download_url'] = f"/api/apps/{a['id']}/download"
        out.setdefault('apps', []).append(item)
        existing.add(a.get('id')); existing.add(a.get('package_name'))
    out['allowed_apps'] = [x.get('package_name') for x in out.get('apps', []) if x.get('package_name')]
    if isinstance(out.get('policy'), dict):
        out['policy']['apps'] = out.get('apps', [])
        out['policy']['allowed_apps'] = out.get('allowed_apps', [])
    return out

v5.payload = _payload_with_device_apps


def launcher_id(base2_device_id: str) -> str:
    raw = (base2_device_id or '').strip()
    if not raw:
        return ''
    if raw.upper().startswith('BOX-'):
        return raw.upper()
    return 'BOX-' + raw[-8:].upper()


def queue_install(c, base2_device_id: str, app_id: str):
    did = launcher_id(base2_device_id)
    if not did:
        raise HTTPException(400, 'Cliente ainda não vinculou um aparelho')
    dev = v5.one(c, 'SELECT * FROM devices WHERE id=?', (did,))
    if not dev:
        raise HTTPException(404, f'Launcher do aparelho {did} ainda não apareceu no painel BBL.BOXTV')
    a = v5.one(c, 'SELECT * FROM apps WHERE id=?', (app_id,))
    if not a:
        raise HTTPException(404, 'Aplicativo não encontrado')
    try:
        ids = json.loads(dev.get('allowed_apps') or '[]')
    except Exception:
        ids = []
    if app_id not in ids and a.get('package_name') not in ids:
        ids.append(app_id)
        v5.ex(c, 'UPDATE devices SET allowed_apps=? WHERE id=?', (json.dumps(ids), did))
    v5.ex(c, 'INSERT INTO commands(id,device_id,command,payload,status,created_at) VALUES(?,?,?,?,?,?)',
          (secrets.token_hex(8), did, 'SYNC', '{}', 'pending', v5.now()))
    v5.log(c, did, 'base2_remote_install', a.get('name') or app_id)
    return did, a


def app_cards(rows):
    return ''.join(
        f'<div class="card"><b>{admin.esc(a["name"])}</b><br><span class="muted">{admin.esc(a.get("package_name") or "-")} • versão {admin.esc(a.get("version_name") or "-")}</span></div>'
        for a in rows
    ) or '<div class="card muted">Nenhum aplicativo cadastrado.</div>'


def admin_nav_page(body):
    return admin.page('Aplicativos / Instalação remota', body)

@app.get('/base2/painel/aplicativos')
def admin_apps(req: Request, ok: str=''):
    if not admin.admin_ok(req):
        return admin.redir('/base2/painel/login')
    c = v5.db()
    apps = v5.rows(c, 'SELECT * FROM apps ORDER BY name')
    clients = v5.rows(c, 'SELECT c.*,r.name reseller_name FROM base2_clients c LEFT JOIN base2_resellers r ON r.id=c.reseller_id ORDER BY c.name')
    c.close()
    aopts = ''.join(f'<option value="{a["id"]}">{admin.esc(a["name"])} • {admin.esc(a.get("package_name") or "")}</option>' for a in apps)
    copts = ''.join(f'<option value="{x["id"]}">{admin.esc(x["name"])} • {admin.esc(x["username"])} • {admin.esc(x.get("reseller_name") or "ADMIN")}</option>' for x in clients)
    msg = f'<div class="card good">{admin.esc(ok)}</div>' if ok else ''
    body = msg + f'''<div class="card"><h3>Adicionar APK</h3><form enctype="multipart/form-data" method="post" action="/base2/painel/aplicativos/upload"><input name="name" placeholder="Nome opcional"><input type="file" name="apk" accept=".apk" required><button>ADICIONAR APK</button></form></div>
    <div class="card"><h3>Instalar remotamente</h3><div class="muted">O cliente precisa estar com a Launcher BBL.BOXTV instalada e ativada. A Launcher sincroniza e inicia a instalação automaticamente.</div><form method="post" action="/base2/painel/aplicativos/instalar"><select name="client_id" required><option value="">Escolha o cliente</option>{copts}</select><select name="app_id" required><option value="">Escolha o aplicativo</option>{aopts}</select><button>INSTALAR NO CLIENTE</button></form></div>
    <h3>Aplicativos disponíveis</h3><div class="grid">{app_cards(apps)}</div>'''
    return admin_nav_page(body)

@app.post('/base2/painel/aplicativos/upload')
def admin_app_upload(req: Request, name: str=Form(''), apk: UploadFile=File(...)):
    admin.adm(req)
    fn = v5.save(apk, 'apk', {'.apk'})
    p = v5.UPLOAD_DIR / fn
    m = v5.apkmeta(p); m['name'] = name.strip() or m['name']
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    c = v5.db()
    v5.ex(c, 'INSERT INTO apps(id,name,package_name,version_name,version_code,filename,size_bytes,sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
          (secrets.token_hex(8), m['name'], m['package_name'], m['version_name'], m['version_code'], fn, p.stat().st_size, h, v5.now()))
    c.commit(); c.close()
    return admin.redir('/base2/painel/aplicativos?ok=APK+adicionado')

@app.post('/base2/painel/aplicativos/instalar')
def admin_install(req: Request, client_id: str=Form(...), app_id: str=Form(...)):
    admin.adm(req)
    c = v5.db()
    cl = v5.one(c, 'SELECT * FROM base2_clients WHERE id=?', (client_id,))
    if not cl:
        c.close(); raise HTTPException(404, 'Cliente não encontrado')
    did, a = queue_install(c, cl.get('device_id') or '', app_id)
    c.commit(); c.close()
    return admin.redir(f'/base2/painel/aplicativos?ok=Instalação+enviada+para+{did}')

@app.get('/base2/revenda/aplicativos')
def reseller_apps(req: Request, ok: str=''):
    r = reseller.session_reseller(req)
    if not r:
        return reseller.redir('/base2/revenda/login')
    c = v5.db()
    apps = v5.rows(c, 'SELECT * FROM apps ORDER BY name')
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
    fn = v5.save(apk, 'apk', {'.apk'})
    p = v5.UPLOAD_DIR / fn
    m = v5.apkmeta(p); m['name'] = name.strip() or m['name']
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    c = v5.db()
    v5.ex(c, 'INSERT INTO apps(id,name,package_name,version_name,version_code,filename,size_bytes,sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
          (secrets.token_hex(8), m['name'], m['package_name'], m['version_name'], m['version_code'], fn, p.stat().st_size, h, v5.now()))
    c.commit(); c.close()
    return reseller.redir('/base2/revenda/aplicativos?ok=APK+adicionado')

@app.post('/base2/revenda/aplicativos/instalar')
def reseller_install(req: Request, client_id: str=Form(...), app_id: str=Form(...)):
    r = reseller.require_reseller(req)
    c = v5.db()
    cl = v5.one(c, 'SELECT * FROM base2_clients WHERE id=? AND reseller_id=?', (client_id, r['id']))
    if not cl:
        c.close(); raise HTTPException(404, 'Cliente não encontrado')
    did, a = queue_install(c, cl.get('device_id') or '', app_id)
    c.commit(); c.close()
    return reseller.redir(f'/base2/revenda/aplicativos?ok=Instalação+enviada+para+{did}')
