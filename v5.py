import os,secrets,json,hashlib,shutil
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Optional
from fastapi import FastAPI,HTTPException,Header,Form,UploadFile,File,Request
from fastapi.responses import HTMLResponse,RedirectResponse,FileResponse
from pydantic import BaseModel

DATABASE_URL=os.getenv('DATABASE_URL','sqlite:///./tvbox.db')
ADMIN_KEY=os.getenv('ADMIN_KEY','troque-esta-chave')
ACTIVATION_KEY=os.getenv('ACTIVATION_KEY','BBL-2026')
UPLOAD_DIR=Path(os.getenv('UPLOAD_DIR','./uploads'));UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='BBL.BOXTV Manager API',version='5.0.0')

def now():return datetime.now(timezone.utc).isoformat()
def pg():return DATABASE_URL.startswith(('postgres://','postgresql://'))
def db():
    if pg():
        import psycopg
        return psycopg.connect(DATABASE_URL.replace('postgres://','postgresql://',1),autocommit=False)
    import sqlite3
    p=DATABASE_URL.replace('sqlite:///','',1) if DATABASE_URL.startswith('sqlite:///') else DATABASE_URL
    c=sqlite3.connect(p);c.row_factory=sqlite3.Row;return c
def ex(c,s,p=()):
    if pg():s=s.replace('?','%s')
    q=c.cursor();q.execute(s,p);return q
def rd(r,q=None):
    if r is None:return None
    try:return dict(r)
    except Exception:return dict(zip([getattr(x,'name',x[0]) for x in q.description],r))
def col(c,s):
    try:ex(c,s);c.commit()
    except Exception:c.rollback()
def rows(c,s,p=()):
    q=ex(c,s,p);return [rd(x,q) for x in q.fetchall()]
def one(c,s,p=()):
    q=ex(c,s,p);return rd(q.fetchone(),q)
def log(c,d,e,x=''):ex(c,'INSERT INTO logs(id,device_id,event,detail,created_at) VALUES(?,?,?,?,?)',(secrets.token_hex(8),d,e,x,now()))

def init():
    c=db()
    for s in [
      "CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,token TEXT UNIQUE NOT NULL,activation_key TEXT,locked INTEGER NOT NULL DEFAULT 0,allowed_apps TEXT NOT NULL DEFAULT '[]',managed_apps TEXT NOT NULL DEFAULT '[]',display_name TEXT NOT NULL DEFAULT '',notes TEXT NOT NULL DEFAULT '',created_at TEXT,last_seen TEXT)",
      "CREATE TABLE IF NOT EXISTS activation_keys(key TEXT PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 1,label TEXT NOT NULL DEFAULT '',created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS apps(id TEXT PRIMARY KEY,name TEXT NOT NULL,package_name TEXT NOT NULL DEFAULT '',version_name TEXT NOT NULL DEFAULT '',version_code TEXT NOT NULL DEFAULT '',filename TEXT NOT NULL,size_bytes INTEGER NOT NULL DEFAULT 0,sha256 TEXT NOT NULL DEFAULT '',created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS layouts(id TEXT PRIMARY KEY,name TEXT NOT NULL,app_ids TEXT NOT NULL DEFAULT '[]',created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,device_id TEXT,title TEXT,message TEXT,created_at TEXT,read_at TEXT)",
      "CREATE TABLE IF NOT EXISTS logs(id TEXT PRIMARY KEY,device_id TEXT,event TEXT,detail TEXT,created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS resellers(id TEXT PRIMARY KEY,name TEXT NOT NULL,access_key TEXT UNIQUE NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,max_devices INTEGER NOT NULL DEFAULT 50,brand_name TEXT NOT NULL DEFAULT 'BBL.BOXTV',wallpaper_url TEXT NOT NULL DEFAULT '',logo_url TEXT NOT NULL DEFAULT '',message TEXT NOT NULL DEFAULT '',created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS banners(id TEXT PRIMARY KEY,name TEXT NOT NULL,filename TEXT NOT NULL,media_type TEXT NOT NULL DEFAULT 'image',created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS wallpapers(id TEXT PRIMARY KEY,name TEXT NOT NULL,filename TEXT NOT NULL,created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY,name TEXT NOT NULL,days INTEGER NOT NULL DEFAULT 30,price_cents INTEGER NOT NULL DEFAULT 0,layout_id TEXT,created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device_id TEXT NOT NULL,command TEXT NOT NULL,payload TEXT NOT NULL DEFAULT '{}',status TEXT NOT NULL DEFAULT 'pending',created_at TEXT,finished_at TEXT,result TEXT NOT NULL DEFAULT '')"
    ]:ex(c,s)
    c.commit()
    for s in [
      "ALTER TABLE devices ADD COLUMN expires_at TEXT","ALTER TABLE devices ADD COLUMN launcher_expires_at TEXT","ALTER TABLE devices ADD COLUMN layout_id TEXT","ALTER TABLE devices ADD COLUMN manufacturer TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN model TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN android_version TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN launcher_version TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN reseller_id TEXT","ALTER TABLE devices ADD COLUMN brand_name TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN wallpaper_url TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN logo_url TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN message TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN block_apps_after_expiry INTEGER NOT NULL DEFAULT 1","ALTER TABLE devices ADD COLUMN wifi_locked INTEGER NOT NULL DEFAULT 0","ALTER TABLE devices ADD COLUMN bluetooth_enabled INTEGER NOT NULL DEFAULT 1","ALTER TABLE devices ADD COLUMN date_time_access INTEGER NOT NULL DEFAULT 1","ALTER TABLE devices ADD COLUMN plan_id TEXT","ALTER TABLE activation_keys ADD COLUMN reseller_id TEXT","ALTER TABLE layouts ADD COLUMN wallpaper_id TEXT","ALTER TABLE layouts ADD COLUMN banner_ids TEXT NOT NULL DEFAULT '[]'","ALTER TABLE layouts ADD COLUMN logo_url TEXT NOT NULL DEFAULT ''"
    ]:col(c,s)
    try:ex(c,'INSERT INTO activation_keys(key,enabled,label,created_at) VALUES(?,?,?,?)',(ACTIVATION_KEY,1,'Chave padrão',now()));c.commit()
    except Exception:c.rollback()
    c.close()
@app.on_event('startup')
def startup():init()

def bearer(a):return a.split(' ',1)[1].strip() if a and a.lower().startswith('bearer ') else None
def adm(k):
    if not k or not secrets.compare_digest(k,ADMIN_KEY):raise HTTPException(401,'ADMIN_KEY inválida')
def authdev(c,did,a):
    d=one(c,'SELECT * FROM devices WHERE id=?',(did,));t=bearer(a)
    if not d or not t or not secrets.compare_digest(t,d['token']):raise HTTPException(401,'unauthorized')
    return d

def save(u,prefix,allowed):
    ext=Path(u.filename or '').suffix.lower()
    if ext not in allowed:raise HTTPException(400,'tipo de arquivo não permitido')
    fn=f'{prefix}_{secrets.token_hex(8)}{ext}';path=UPLOAD_DIR/fn
    with path.open('wb') as f:shutil.copyfileobj(u.file,f)
    return fn

def apkmeta(p):
    m={'name':p.stem,'package_name':'','version_name':'','version_code':''}
    try:
      from androguard.core.apk import APK
      a=APK(str(p));m={'name':a.get_app_name() or p.stem,'package_name':a.get_package() or '','version_name':a.get_androidversion_name() or '','version_code':str(a.get_androidversion_code() or '')}
    except Exception:pass
    return m

class Enroll(BaseModel):
    activationCode:Optional[str]=None;activation:Optional[str]=None;activation_code:Optional[str]=None;enrollmentKey:Optional[str]=None;deviceId:Optional[str]=None;device_id:Optional[str]=None
    manufacturer:Optional[str]=None;model:Optional[str]=None;android_version:Optional[str]=None;launcher_version:Optional[str]=None
class CmdResult(BaseModel):status:str='done';result:str=''

@app.get('/health')
def health():return {'ok':True,'service':'bbl-boxtv-manager','version':'5.0.0'}
@app.post('/api/enroll')
def enroll(b:Enroll):
    key=b.activationCode or b.activation or b.activation_code or b.enrollmentKey
    if not key:raise HTTPException(400,'activation key required')
    c=db();k=one(c,'SELECT * FROM activation_keys WHERE key=? AND enabled=1',(key,))
    if not k:c.close();raise HTTPException(403,'invalid activation key')
    did=b.deviceId or b.device_id or secrets.token_hex(5).upper();d=one(c,'SELECT * FROM devices WHERE id=?',(did,))
    if d:token=d['token'];ex(c,'UPDATE devices SET last_seen=? WHERE id=?',(now(),did))
    else:
      token=secrets.token_urlsafe(32);ex(c,'INSERT INTO devices(id,token,activation_key,created_at,last_seen,manufacturer,model,android_version,launcher_version,reseller_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(did,token,key,now(),now(),b.manufacturer or '',b.model or '',b.android_version or '',b.launcher_version or '',k.get('reseller_id')));log(c,did,'enroll','device activated')
    c.commit();c.close();return {'device_id':did,'device_token':token,'deviceId':did,'deviceToken':token,'token':token,'status':'ok'}

def payload(c,d):
    ids=[];lay=None
    if d.get('layout_id'):
      lay=one(c,'SELECT * FROM layouts WHERE id=?',(d['layout_id'],));ids=json.loads((lay or {}).get('app_ids') or '[]')
    if not ids:ids=json.loads(d.get('allowed_apps') or '[]')
    aa=[]
    for i in ids:
      a=one(c,'SELECT * FROM apps WHERE id=? OR package_name=?',(i,i))
      if a:aa.append({k:a.get(k) for k in ('id','name','package_name','version_name','version_code','size_bytes','sha256')}|{'download_url':f"/api/apps/{a['id']}/download"})
    expired=False
    if d.get('expires_at'):
      try:expired=datetime.fromisoformat(d['expires_at'].replace('Z','+00:00'))<datetime.now(timezone.utc)
      except:pass
    brand={'name':d.get('brand_name') or 'BBL.BOXTV','wallpaper_url':d.get('wallpaper_url') or '','logo_url':d.get('logo_url') or '','message':d.get('message') or ''}
    if d.get('reseller_id'):
      r=one(c,'SELECT * FROM resellers WHERE id=?',(d['reseller_id'],))
      if r:
        brand['name']=d.get('brand_name') or r.get('brand_name') or brand['name'];brand['wallpaper_url']=d.get('wallpaper_url') or r.get('wallpaper_url') or '';brand['logo_url']=d.get('logo_url') or r.get('logo_url') or '';brand['message']=d.get('message') or r.get('message') or ''
    banners=[]
    if lay:
      if lay.get('wallpaper_id') and not brand['wallpaper_url']:
        w=one(c,'SELECT filename FROM wallpapers WHERE id=?',(lay['wallpaper_id'],));brand['wallpaper_url']=f"/api/media/{w['filename']}" if w else ''
      if lay.get('logo_url') and not brand['logo_url']:brand['logo_url']=lay['logo_url']
      for bid in json.loads(lay.get('banner_ids') or '[]'):
        b=one(c,'SELECT * FROM banners WHERE id=?',(bid,))
        if b:banners.append({'id':b['id'],'name':b['name'],'type':b['media_type'],'url':f"/api/media/{b['filename']}"})
    p={'locked':bool(d.get('locked')) or expired,'expired':expired,'expires_at':d.get('expires_at'),'layout_id':d.get('layout_id'),'apps':aa,'allowed_apps':[x['package_name'] for x in aa if x.get('package_name')],'brand':brand,'banners':banners,'settings':{'block_apps_after_expiry':bool(d.get('block_apps_after_expiry',1)),'wifi_locked':bool(d.get('wifi_locked')),'bluetooth_enabled':bool(d.get('bluetooth_enabled',1)),'date_time_access':bool(d.get('date_time_access',1))}}
    return {**p,'policy':p}
@app.api_route('/api/devices/{did}/policy',methods=['GET','POST'])
def policy(did:str,authorization:Optional[str]=Header(None)):
    c=db();d=authdev(c,did,authorization);ex(c,'UPDATE devices SET last_seen=? WHERE id=?',(now(),did));c.commit();o=payload(c,d);c.close();return o
@app.get('/api/devices/{did}/notifications')
def notif(did:str,authorization:Optional[str]=Header(None)):
    c=db();authdev(c,did,authorization);o=rows(c,'SELECT id,title,message,created_at FROM notifications WHERE device_id=? AND read_at IS NULL ORDER BY created_at DESC',(did,));c.close();return o
@app.get('/api/devices/{did}/commands')
def commands(did:str,authorization:Optional[str]=Header(None)):
    c=db();authdev(c,did,authorization);o=rows(c,"SELECT id,command,payload,created_at FROM commands WHERE device_id=? AND status='pending' ORDER BY created_at",(did,));c.close()
    for r in o:
      try:r['payload']=json.loads(r.get('payload') or '{}')
      except:r['payload']={}
    return o
@app.post('/api/devices/{did}/commands/{cid}/result')
def cmdresult(did:str,cid:str,b:CmdResult,authorization:Optional[str]=Header(None)):
    c=db();authdev(c,did,authorization);ex(c,'UPDATE commands SET status=?,result=?,finished_at=? WHERE id=? AND device_id=?',(b.status,b.result,now(),cid,did));log(c,did,'command_result',f'{cid}:{b.status}:{b.result[:180]}');c.commit();c.close();return {'ok':True}
@app.get('/api/apps/{aid}/download')
def dl(aid:str):
    c=db();a=one(c,'SELECT filename FROM apps WHERE id=?',(aid,));c.close()
    if not a or not (UPLOAD_DIR/a['filename']).exists():raise HTTPException(404)
    return FileResponse(UPLOAD_DIR/a['filename'],media_type='application/vnd.android.package-archive',filename=a['filename'])
@app.get('/api/media/{fn}')
def media(fn:str):
    p=UPLOAD_DIR/Path(fn).name
    if not p.exists():raise HTTPException(404)
    return FileResponse(p)

CSS='''*{box-sizing:border-box}body{margin:0;background:#081526;color:#fff;font:15px Arial}.top{height:62px;background:#0d1d33;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:20px}.wrap{padding:18px;max-width:1500px;margin:auto}.nav{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 22px}.nav a,button{background:#287ff1;color:#fff;border:0;border-radius:8px;padding:10px 14px;text-decoration:none;cursor:pointer}.card{background:#0f2139;border:1px solid #24364d;border-radius:10px;padding:15px;margin:10px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.muted{color:#9badc3}.ok{color:#24cf67}.bad{color:#ff5864}input,select,textarea{width:100%;background:#071323;color:#fff;border:1px solid #334760;border-radius:7px;padding:10px;margin:5px 0 10px}h1{margin:5px 0 0}.hero{padding:16px;background:#0d1d33;border-radius:10px}.wide{width:100%;font-size:18px}.danger{background:#d83a4d}.good{background:#24a85a}img{max-width:100%}'''
def nav(k):
    x=[('Dispositivos','/'),('Ativações','/admin/activation-keys'),('Layouts','/admin/layouts'),('Aplicativos','/admin/apps'),('Banners','/admin/banners'),('Planos de fundo','/admin/wallpapers'),('Planos','/admin/plans'),('Revendas','/admin/resellers'),('Comandos','/admin/commands'),('Notificações','/admin/notifications'),('LOGs','/admin/logs')]
    return '<div class="nav">'+''.join(f'<a href="{u}?key={k}">{n}</a>' for n,u in x)+'</div>'
def page(t,b,k=''):return HTMLResponse(f'<!doctype html><meta name="viewport" content="width=device-width"><title>{t}</title><style>{CSS}</style><div class="top">BBL.BOXTV</div><div class="wrap"><h1>{t}</h1>{nav(k) if k else ""}{b}</div>')
def go(u,k):return RedirectResponse(f'{u}?key={k}',303)

@app.get('/',response_class=HTMLResponse)
def home(key:str=''):
    if not key or not secrets.compare_digest(key,ADMIN_KEY):return page('Painel','<div class="card"><form><input name="key" type="password" placeholder="ADMIN_KEY"><button>Entrar</button></form></div>')
    c=db();ds=rows(c,'SELECT * FROM devices ORDER BY created_at DESC');c.close();cards=''
    for d in ds:
      st='BLOQUEADO' if d.get('locked') else 'ATIVO';cl='bad' if d.get('locked') else 'ok';cards+=f'<div class="card"><h3>{d.get("display_name") or "Sem nome"} <span class="{cl}">{st}</span></h3><div class="muted">ID {d["id"]} • último contato {d.get("last_seen") or "-"}</div><a href="/admin/device/{d["id"]}?key={key}">Gerenciar cliente</a></div>'
    return page('Bem vindo(a) BBL.boxtv',f'<div class="hero">Gerencie clientes, aplicativos, banners, temas, planos, revendas e comandos remotos.</div><h2>Dispositivos ({len(ds)})</h2><div class="grid">{cards or "<div class=card>Nenhum dispositivo.</div>"}</div>',key)

@app.get('/admin/device/{did}',response_class=HTMLResponse)
def device(did:str,key:str=''):
    adm(key);c=db();d=one(c,'SELECT * FROM devices WHERE id=?',(did,));ls=rows(c,'SELECT * FROM layouts ORDER BY name');ps=rows(c,'SELECT * FROM plans ORDER BY name');c.close()
    if not d:raise HTTPException(404)
    l='<option value="">Sem layout</option>'+''.join(f'<option value="{x["id"]}" {"selected" if d.get("layout_id")==x["id"] else ""}>{x["name"]}</option>' for x in ls);p=''.join(f'<option value="{x["id"]}">{x["name"]}</option>' for x in ps)
    b=f'''<div class="grid"><div class="card"><b>Código</b><br>{did}</div><div class="card"><b>Versão Launcher</b><br>{d.get('launcher_version') or '-'}</div><div class="card"><b>Marca/Modelo</b><br>{d.get('manufacturer') or '-'} • {d.get('model') or '-'}</div><div class="card"><b>Android</b><br>{d.get('android_version') or '-'}</div></div><div class="card"><form method="post" action="/admin/device/{did}/update?key={key}"><input name="display_name" value="{d.get('display_name') or ''}" placeholder="Nome"><input name="expires_at" value="{d.get('expires_at') or ''}" placeholder="Vencimento ISO"><select name="layout_id">{l}</select><label><input style="width:auto" type="checkbox" name="block_apps_after_expiry" value="1" {'checked' if d.get('block_apps_after_expiry',1) else ''}> Bloquear apps após vencer</label><br><label><input style="width:auto" type="checkbox" name="wifi_locked" value="1" {'checked' if d.get('wifi_locked') else ''}> Bloquear Wi-Fi sem senha</label><br><label><input style="width:auto" type="checkbox" name="bluetooth_enabled" value="1" {'checked' if d.get('bluetooth_enabled',1) else ''}> Bluetooth</label><br><button>Salvar</button></form><form method="post" action="/admin/device/{did}/toggle?key={key}"><button class="{'good' if d.get('locked') else 'danger'}">{'Desbloquear' if d.get('locked') else 'Bloquear'}</button></form></div><div class="card"><form method="post" action="/admin/device/{did}/plan?key={key}"><select name="plan_id">{p}</select><button>Aplicar / renovar plano</button></form></div><div class="card"><form method="post" action="/admin/device/{did}/notify?key={key}"><input name="title" placeholder="Título"><input name="message" placeholder="Mensagem"><button>Enviar notificação</button></form></div><div class="card"><form method="post" action="/admin/device/{did}/command?key={key}"><select name="command"><option>SYNC</option><option>RELOAD</option><option>CLEAR_CACHE</option><option>OPEN_SETTINGS</option><option>REBOOT_REQUEST</option></select><input name="payload" value="{{}}"><button>Enviar comando</button></form></div>'''
    return page('Gerenciar dispositivo/cliente',b,key)
@app.post('/admin/device/{did}/update')
def dupdate(did:str,key:str,display_name:str=Form(''),expires_at:str=Form(''),layout_id:str=Form(''),block_apps_after_expiry:Optional[str]=Form(None),wifi_locked:Optional[str]=Form(None),bluetooth_enabled:Optional[str]=Form(None)):
    adm(key);c=db();ex(c,'UPDATE devices SET display_name=?,expires_at=?,layout_id=?,block_apps_after_expiry=?,wifi_locked=?,bluetooth_enabled=? WHERE id=?',(display_name.strip(),expires_at.strip() or None,layout_id or None,1 if block_apps_after_expiry else 0,1 if wifi_locked else 0,1 if bluetooth_enabled else 0,did));log(c,did,'device_update','settings');c.commit();c.close();return go(f'/admin/device/{did}',key)
@app.post('/admin/device/{did}/toggle')
def toggle(did:str,key:str):
    adm(key);c=db();d=one(c,'SELECT locked FROM devices WHERE id=?',(did,));ex(c,'UPDATE devices SET locked=? WHERE id=?',(0 if d and d['locked'] else 1,did));log(c,did,'lock','toggle');c.commit();c.close();return go(f'/admin/device/{did}',key)
@app.post('/admin/device/{did}/notify')
def dnotify(did:str,key:str,title:str=Form(...),message:str=Form(...)):
    adm(key);c=db();ex(c,'INSERT INTO notifications(id,device_id,title,message,created_at) VALUES(?,?,?,?,?)',(secrets.token_hex(8),did,title,message,now()));log(c,did,'notification',title);c.commit();c.close();return go(f'/admin/device/{did}',key)
@app.post('/admin/device/{did}/command')
def dcmd(did:str,key:str,command:str=Form(...),payload:str=Form('{}')):
    adm(key)
    try:json.loads(payload)
    except:raise HTTPException(400,'payload JSON inválido')
    c=db();ex(c,'INSERT INTO commands(id,device_id,command,payload,status,created_at) VALUES(?,?,?,?,?,?)',(secrets.token_hex(8),did,command.upper(),payload,'pending',now()));log(c,did,'command',command);c.commit();c.close();return go(f'/admin/device/{did}',key)

@app.get('/admin/activation-keys',response_class=HTMLResponse)
def keys(key:str=''):
    adm(key);c=db();ks=rows(c,'SELECT * FROM activation_keys ORDER BY created_at DESC');rs=rows(c,'SELECT id,name FROM resellers WHERE enabled=1 ORDER BY name');c.close();opts='<option value="">Administrador</option>'+''.join(f'<option value="{r["id"]}">{r["name"]}</option>' for r in rs);cards=''.join(f'<div class="card"><b>{x["label"] or x["key"]}</b><br>{x["key"]} • {"ATIVA" if x["enabled"] else "DESATIVADA"}</div>' for x in ks);return page('Ativações',f'<div class="card"><form method="post" action="/admin/activation-keys/create?key={key}"><input name="label" placeholder="Descrição"><input name="activation_key" placeholder="Código"><select name="reseller_id">{opts}</select><button>Criar ativação</button></form></div>{cards}',key)
@app.post('/admin/activation-keys/create')
def keycreate(key:str,label:str=Form(''),activation_key:str=Form(''),reseller_id:str=Form('')):
    adm(key);k=activation_key.strip() or secrets.token_hex(4).upper();c=db()
    try:ex(c,'INSERT INTO activation_keys(key,enabled,label,created_at,reseller_id) VALUES(?,?,?,?,?)',(k,1,label.strip(),now(),reseller_id or None));c.commit()
    except Exception:c.rollback();c.close();raise HTTPException(409,'código já existe')
    c.close();return go('/admin/activation-keys',key)

@app.get('/admin/apps',response_class=HTMLResponse)
def apps(key:str=''):
    adm(key);c=db();aa=rows(c,'SELECT * FROM apps ORDER BY created_at DESC');c.close();cards=''.join(f'<div class="card"><b>{a["name"]}</b><br><span class="muted">{a.get("package_name") or "-"} • {a.get("version_name") or "-"}</span></div>' for a in aa);return page('Meus Aplicativos',f'<div class="card"><form enctype="multipart/form-data" method="post" action="/admin/apps/upload?key={key}"><input name="name" placeholder="Nome opcional"><input type="file" name="apk" accept=".apk" required><button>ADD APK AUTOMÁTICO</button></form></div><div class="grid">{cards}</div>',key)
@app.post('/admin/apps/upload')
def appup(key:str,name:str=Form(''),apk:UploadFile=File(...)):
    adm(key);fn=save(apk,'apk',{'.apk'});p=UPLOAD_DIR/fn;m=apkmeta(p);m['name']=name.strip() or m['name'];h=hashlib.sha256(p.read_bytes()).hexdigest();c=db();ex(c,'INSERT INTO apps(id,name,package_name,version_name,version_code,filename,size_bytes,sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(secrets.token_hex(8),m['name'],m['package_name'],m['version_name'],m['version_code'],fn,p.stat().st_size,h,now()));c.commit();c.close();return go('/admin/apps',key)

@app.get('/admin/layouts',response_class=HTMLResponse)
def layouts(key:str=''):
    adm(key);c=db();ls=rows(c,'SELECT * FROM layouts ORDER BY created_at DESC');aa=rows(c,'SELECT * FROM apps ORDER BY name');ww=rows(c,'SELECT * FROM wallpapers ORDER BY name');bb=rows(c,'SELECT * FROM banners ORDER BY name');c.close();apps=''.join(f'<label><input style="width:auto" type="checkbox" name="app_ids" value="{a["id"]}"> {a["name"]}</label><br>' for a in aa);walls='<option value="">Sem fundo</option>'+''.join(f'<option value="{w["id"]}">{w["name"]}</option>' for w in ww);bans=''.join(f'<label><input style="width:auto" type="checkbox" name="banner_ids" value="{b["id"]}"> {b["name"]}</label><br>' for b in bb);cards=''.join(f'<div class="card"><b>{l["name"]}</b><br><span class="muted">Apps {len(json.loads(l.get("app_ids") or "[]"))}</span></div>' for l in ls);return page('Meus Layouts',f'<div class="card"><form method="post" action="/admin/layouts/create?key={key}"><input name="name" placeholder="Nome do layout" required><select name="wallpaper_id">{walls}</select><input name="logo_url" placeholder="URL da logo"><h4>Aplicativos</h4>{apps}<h4>Banners</h4>{bans}<button>ADD LAYOUT</button></form></div><div class="grid">{cards}</div>',key)
@app.post('/admin/layouts/create')
def layoutcreate(key:str,name:str=Form(...),wallpaper_id:str=Form(''),logo_url:str=Form(''),app_ids:list[str]=Form(default=[]),banner_ids:list[str]=Form(default=[])):
    adm(key);c=db();ex(c,'INSERT INTO layouts(id,name,app_ids,created_at,wallpaper_id,banner_ids,logo_url) VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(8),name.strip(),json.dumps(app_ids),now(),wallpaper_id or None,json.dumps(banner_ids),logo_url.strip()));c.commit();c.close();return go('/admin/layouts',key)

@app.get('/admin/banners',response_class=HTMLResponse)
def banners(key:str=''):
    adm(key);c=db();bb=rows(c,'SELECT * FROM banners ORDER BY created_at DESC');c.close();cards=''.join(f'<div class="card"><b>{b["name"]}</b><br><span class="muted">{b["media_type"]}</span><br>{"<video controls style=max-width:100% src=/api/media/"+b["filename"]+"></video>" if b["media_type"]=="video" else "<img src=/api/media/"+b["filename"]+">"}</div>' for b in bb);return page('Meus Banners',f'<div class="card"><form enctype="multipart/form-data" method="post" action="/admin/banners/create?key={key}"><input name="name" placeholder="Nome" required><input type="file" name="media" accept="image/*,video/mp4" required><button>ADD BANNER</button></form></div><div class="grid">{cards}</div>',key)
@app.post('/admin/banners/create')
def bannercreate(key:str,name:str=Form(...),media:UploadFile=File(...)):
    adm(key);ext=Path(media.filename or '').suffix.lower();fn=save(media,'banner',{'.png','.jpg','.jpeg','.webp','.mp4'});c=db();ex(c,'INSERT INTO banners(id,name,filename,media_type,created_at) VALUES(?,?,?,?,?)',(secrets.token_hex(8),name.strip(),fn,'video' if ext=='.mp4' else 'image',now()));c.commit();c.close();return go('/admin/banners',key)
@app.get('/admin/wallpapers',response_class=HTMLResponse)
def walls(key:str=''):
    adm(key);c=db();ww=rows(c,'SELECT * FROM wallpapers ORDER BY created_at DESC');c.close();cards=''.join(f'<div class="card"><b>{w["name"]}</b><br><img src="/api/media/{w["filename"]}"></div>' for w in ww);return page('Meus planos de fundo',f'<div class="card"><form enctype="multipart/form-data" method="post" action="/admin/wallpapers/create?key={key}"><input name="name" placeholder="Nome" required><input type="file" name="image" accept="image/*" required><button>ADD PLANO DE FUNDO</button></form></div><div class="grid">{cards}</div>',key)
@app.post('/admin/wallpapers/create')
def wallcreate(key:str,name:str=Form(...),image:UploadFile=File(...)):
    adm(key);fn=save(image,'wallpaper',{'.png','.jpg','.jpeg','.webp'});c=db();ex(c,'INSERT INTO wallpapers(id,name,filename,created_at) VALUES(?,?,?,?)',(secrets.token_hex(8),name.strip(),fn,now()));c.commit();c.close();return go('/admin/wallpapers',key)

@app.get('/admin/plans',response_class=HTMLResponse)
def plans(key:str=''):
    adm(key);c=db();pp=rows(c,'SELECT * FROM plans ORDER BY created_at DESC');ls=rows(c,'SELECT id,name FROM layouts ORDER BY name');c.close();opts='<option value="">Sem layout</option>'+''.join(f'<option value="{x["id"]}">{x["name"]}</option>' for x in ls);cards=''.join(f'<div class="card"><b>{p["name"]}</b><br>{p["days"]} dias • R$ {p["price_cents"]/100:.2f}</div>' for p in pp);return page('Meus Planos',f'<div class="card"><form method="post" action="/admin/plans/create?key={key}"><input name="name" required placeholder="Nome"><input name="days" type="number" value="30"><input name="price" type="number" step="0.01" value="35.00"><select name="layout_id">{opts}</select><button>ADD PLANO</button></form></div>{cards}',key)
@app.post('/admin/plans/create')
def plancreate(key:str,name:str=Form(...),days:int=Form(30),price:float=Form(35),layout_id:str=Form('')):
    adm(key);c=db();ex(c,'INSERT INTO plans(id,name,days,price_cents,layout_id,created_at) VALUES(?,?,?,?,?,?)',(secrets.token_hex(8),name.strip(),max(1,days),max(0,int(round(price*100))),layout_id or None,now()));c.commit();c.close();return go('/admin/plans',key)
@app.post('/admin/device/{did}/plan')
def applyplan(did:str,key:str,plan_id:str=Form(...)):
    adm(key);c=db();p=one(c,'SELECT * FROM plans WHERE id=?',(plan_id,));
    if not p:c.close();raise HTTPException(404)
    exp=(datetime.now(timezone.utc)+timedelta(days=int(p['days']))).isoformat();ex(c,'UPDATE devices SET plan_id=?,expires_at=?,layout_id=COALESCE(?,layout_id),locked=0 WHERE id=?',(plan_id,exp,p.get('layout_id'),did));log(c,did,'plan',p['name']);c.commit();c.close();return go(f'/admin/device/{did}',key)

@app.get('/admin/resellers',response_class=HTMLResponse)
def resellers(key:str=''):
    adm(key);c=db();rr=rows(c,'SELECT * FROM resellers ORDER BY created_at DESC');c.close();cards=''.join(f'<div class="card"><b>{r["name"]}</b><br>Chave {r["access_key"]}<br><span class="muted">Limite {r["max_devices"]} • {r["brand_name"]}</span></div>' for r in rr);return page('Gerenciar revendas',f'<div class="card"><form method="post" action="/admin/resellers/create?key={key}"><input name="name" placeholder="Nome" required><input name="access_key" placeholder="Senha/chave"><input name="max_devices" type="number" value="50"><input name="brand_name" value="BBL.BOXTV"><input name="wallpaper_url" placeholder="URL fundo"><input name="logo_url" placeholder="URL logo"><input name="message" placeholder="Mensagem"><button>ADD REVENDEDOR</button></form></div>{cards}',key)
@app.post('/admin/resellers/create')
def resellercreate(key:str,name:str=Form(...),access_key:str=Form(''),max_devices:int=Form(50),brand_name:str=Form('BBL.BOXTV'),wallpaper_url:str=Form(''),logo_url:str=Form(''),message:str=Form('')):
    adm(key);c=db();ex(c,'INSERT INTO resellers(id,name,access_key,enabled,max_devices,brand_name,wallpaper_url,logo_url,message,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(secrets.token_hex(8),name.strip(),access_key.strip() or secrets.token_urlsafe(8),1,max(1,max_devices),brand_name.strip() or 'BBL.BOXTV',wallpaper_url.strip(),logo_url.strip(),message.strip(),now()));c.commit();c.close();return go('/admin/resellers',key)

@app.get('/admin/commands',response_class=HTMLResponse)
def cmdpage(key:str=''):
    adm(key);c=db();cc=rows(c,'SELECT * FROM commands ORDER BY created_at DESC');c.close();return page('Logs de comandos',''.join(f'<div class="card"><b>{x["command"]}</b> • {x["device_id"]}<br><span class="muted">{x["status"]} • {x["created_at"]} • {x.get("result") or ""}</span></div>' for x in cc[:300]),key)
@app.get('/admin/notifications',response_class=HTMLResponse)
def notpage(key:str=''):
    adm(key);c=db();nn=rows(c,'SELECT * FROM notifications ORDER BY created_at DESC');c.close();return page('Notificações',''.join(f'<div class="card"><b>{x["title"]}</b><br>{x["message"]}<br><span class="muted">{x["device_id"]} • {x["created_at"]}</span></div>' for x in nn[:300]),key)
@app.get('/admin/logs',response_class=HTMLResponse)
def logpage(key:str=''):
    adm(key);c=db();ll=rows(c,'SELECT * FROM logs ORDER BY created_at DESC');c.close();return page('LOGs',''.join(f'<div class="card"><b>{x["event"]}</b> • {x.get("device_id") or "-"}<br><span class="muted">{x.get("detail") or ""} • {x["created_at"]}</span></div>' for x in ll[:500]),key)
