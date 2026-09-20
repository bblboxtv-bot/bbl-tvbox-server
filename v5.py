import os,secrets,json,hashlib,shutil
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Optional
from fastapi import FastAPI,HTTPException,Header,Form,UploadFile,File,Request
from fastapi.responses import HTMLResponse,RedirectResponse,FileResponse,Response
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
      "CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device_id TEXT NOT NULL,command TEXT NOT NULL,payload TEXT NOT NULL DEFAULT '{}',status TEXT NOT NULL DEFAULT 'pending',created_at TEXT,finished_at TEXT,result TEXT NOT NULL DEFAULT '')",
      "CREATE TABLE IF NOT EXISTS launcher_v55_profile(id TEXT PRIMARY KEY,app_ids TEXT NOT NULL DEFAULT '[]',device_ids TEXT NOT NULL DEFAULT '[]',updated_at TEXT)",
      "CREATE TABLE IF NOT EXISTS media_files(filename TEXT PRIMARY KEY,mime_type TEXT NOT NULL,size_bytes INTEGER NOT NULL,data BYTEA NOT NULL,created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS device_files(id TEXT PRIMARY KEY,device_id TEXT NOT NULL,original_name TEXT NOT NULL DEFAULT '',size_bytes INTEGER NOT NULL DEFAULT 0,sha256 TEXT NOT NULL DEFAULT '',data BYTEA NOT NULL,created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS logos(id TEXT PRIMARY KEY,name TEXT NOT NULL,filename TEXT NOT NULL,created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS launcher_updates(id TEXT PRIMARY KEY,version_name TEXT NOT NULL,version_code INTEGER NOT NULL,size_bytes INTEGER NOT NULL DEFAULT 0,sha256 TEXT NOT NULL DEFAULT '',mandatory INTEGER NOT NULL DEFAULT 1,published INTEGER NOT NULL DEFAULT 1,notes TEXT NOT NULL DEFAULT '',data BYTEA NOT NULL,created_at TEXT)"
    ]:ex(c,s)
    c.commit()
    for s in [
      "ALTER TABLE devices ADD COLUMN expires_at TEXT","ALTER TABLE devices ADD COLUMN launcher_expires_at TEXT","ALTER TABLE devices ADD COLUMN layout_id TEXT","ALTER TABLE devices ADD COLUMN manufacturer TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN model TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN android_version TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN launcher_version TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN reseller_id TEXT","ALTER TABLE devices ADD COLUMN brand_name TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN wallpaper_url TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN logo_url TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN message TEXT NOT NULL DEFAULT ''","ALTER TABLE devices ADD COLUMN block_apps_after_expiry INTEGER NOT NULL DEFAULT 1","ALTER TABLE devices ADD COLUMN wifi_locked INTEGER NOT NULL DEFAULT 0","ALTER TABLE devices ADD COLUMN bluetooth_enabled INTEGER NOT NULL DEFAULT 1","ALTER TABLE devices ADD COLUMN date_time_access INTEGER NOT NULL DEFAULT 1","ALTER TABLE devices ADD COLUMN plan_id TEXT","ALTER TABLE activation_keys ADD COLUMN reseller_id TEXT","ALTER TABLE layouts ADD COLUMN wallpaper_id TEXT","ALTER TABLE layouts ADD COLUMN banner_ids TEXT NOT NULL DEFAULT '[]'","ALTER TABLE layouts ADD COLUMN logo_url TEXT NOT NULL DEFAULT ''","ALTER TABLE layouts ADD COLUMN logo_id TEXT","ALTER TABLE launcher_v55_profile ADD COLUMN wallpaper_id TEXT","ALTER TABLE launcher_v55_profile ADD COLUMN logo_id TEXT","ALTER TABLE launcher_v55_profile ADD COLUMN banner_ids TEXT NOT NULL DEFAULT '[]',"ALTER TABLE activation_keys ADD COLUMN bound_device_id TEXT","ALTER TABLE devices ADD COLUMN hardware_key TEXT NOT NULL DEFAULT ''"
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
    manufacturer:Optional[str]=None;model:Optional[str]=None;android_version:Optional[str]=None;launcher_version:Optional[str]=None;hardware_key:Optional[str]=None
class CmdResult(BaseModel):status:str='done';result:str=''

@app.get('/health')
def health():return {'ok':True,'service':'bbl-boxtv-manager','version':'5.0.0'}
@app.post('/api/enroll')
def enroll(b:Enroll):
    key=b.activationCode or b.activation or b.activation_code or b.enrollmentKey
    if not key:raise HTTPException(400,'activation key required')
    norm=''.join(ch for ch in str(key).upper() if ch.isalnum())
    incoming_hardware=(b.hardware_key or '').strip().lower()
    c=db()
    k=None
    for candidate in rows(c,'SELECT * FROM activation_keys WHERE enabled=1'):
      cand_norm=''.join(ch for ch in str(candidate.get('key') or '').upper() if ch.isalnum())
      if cand_norm==norm:
        k=candidate
        break
    if not k:
      c.close();raise HTTPException(403,'invalid activation key')

    bound=(k.get('bound_device_id') or '').strip()
    if bound:
      d=one(c,'SELECT * FROM devices WHERE id=?',(bound,))
      if not d:
        ex(c,'UPDATE activation_keys SET bound_device_id=NULL WHERE key=?',(k['key'],));c.commit();bound=''
      else:
        saved_hw=(d.get('hardware_key') or '').strip().lower()
        if saved_hw and incoming_hardware and not secrets.compare_digest(saved_hw,incoming_hardware):
          c.close();raise HTTPException(409,'este código de ativação já pertence a outro aparelho')
        if incoming_hardware and not saved_hw:
          ex(c,'UPDATE devices SET hardware_key=? WHERE id=?',(incoming_hardware,bound))
        ex(c,'UPDATE devices SET last_seen=?,manufacturer=?,model=?,android_version=?,launcher_version=? WHERE id=?',
           (now(),b.manufacturer or d.get('manufacturer') or '',b.model or d.get('model') or '',b.android_version or d.get('android_version') or '',b.launcher_version or d.get('launcher_version') or '',bound))
        c.commit()
        token=d['token']
        c.close()
        return {'device_id':bound,'device_token':token,'deviceId':bound,'deviceToken':token,'token':token,'status':'ok','reused':True}

    did=(b.deviceId or b.device_id or '').strip() or secrets.token_hex(5).upper()
    d=one(c,'SELECT * FROM devices WHERE id=?',(did,))
    if d:
      token=d['token']
      saved_key=(d.get('activation_key') or '').strip()
      if saved_key and ''.join(ch for ch in saved_key.upper() if ch.isalnum())!=norm:
        c.close();raise HTTPException(409,'este aparelho já está vinculado a outra ativação')
      ex(c,'UPDATE devices SET activation_key=?,last_seen=?,manufacturer=?,model=?,android_version=?,launcher_version=?,hardware_key=? WHERE id=?',
         (k['key'],now(),b.manufacturer or d.get('manufacturer') or '',b.model or d.get('model') or '',b.android_version or d.get('android_version') or '',b.launcher_version or d.get('launcher_version') or '',incoming_hardware or d.get('hardware_key') or '',did))
    else:
      token=secrets.token_urlsafe(32)
      ex(c,'INSERT INTO devices(id,token,activation_key,created_at,last_seen,manufacturer,model,android_version,launcher_version,reseller_id,hardware_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
         (did,token,k['key'],now(),now(),b.manufacturer or '',b.model or '',b.android_version or '',b.launcher_version or '',k.get('reseller_id'),incoming_hardware))
      try:log(c,did,'enroll','device activated')
      except Exception:pass
    ex(c,'UPDATE activation_keys SET bound_device_id=? WHERE key=?',(did,k['key']))
    c.commit();c.close()
    return {'device_id':did,'device_token':token,'deviceId':did,'deviceToken':token,'token':token,'status':'ok','reused':False}

def payload(c,d):
    ids=[];lay=None
    v55=_load_v55()
    lv=(d.get('launcher_version') or '').strip()
    v55_devices=set(v55.get('device_ids') or []) if v55 else set()
    use_v55=bool(v55) and (d.get('id') in v55_devices or lv.startswith('2.5.5') or lv.startswith('2.5.6') or lv.startswith('5.5'))
    # Sempre carrega o layout para branding (fundo/logo/banner), mesmo quando
    # os aplicativos vêm do perfil V5.5.
    if d.get('layout_id'):
      lay=one(c,'SELECT * FROM layouts WHERE id=?',(d['layout_id'],))
    if use_v55:
      ids=list(v55.get('app_ids') or [])[:20]
    elif lay:
      ids=json.loads((lay or {}).get('app_ids') or '[]')
    if not ids:ids=json.loads(d.get('allowed_apps') or '[]')
    aa=[]
    for i in ids[:20]:
      a=one(c,'SELECT * FROM apps WHERE id=? OR package_name=?',(i,i))
      if a:
        item={k:a.get(k) for k in ('id','name','package_name','version_name','version_code','size_bytes','sha256')}|{'download_url':f"/api/apps/{a['id']}/download"}
        # Tudo Liberado usa o pacote com.rtxapps.reuse. Não forçar update por
        # comparação de versionCode: algumas builds válidas usam versionCode 21
        # e o painel pode ter metadado de outra build, causando loop "ATUALIZAR".
        if (item.get('package_name') or '').lower()=='com.rtxapps.reuse':
          item['name']='Tudo Liberado'
          item['version_code']=0
        aa.append(item)
    # A tela principal da V5.5 usa o primeiro item que contenha "unitv".
    # Prioriza explicitamente UniTV Free para não cair no UniTV Pro.
    def _v55_priority(x):
      s=((x.get('name') or '')+' '+(x.get('package_name') or '')).lower()
      # Mantém os apps essenciais sempre entre os primeiros cards,
      # enquanto launchers antigas ainda exibem só os primeiros 8.
      if 'unitv' in s and 'free' in s:return 0
      if 'tudo liberado' in s or 'rxapps.reuse' in s:return 1
      if 'stv futebol' in s or 'sport.live9' in s:return 2
      if 'unitv' in s:return 4
      return 3
    if use_v55:
      aa.sort(key=_v55_priority)
    print(f"POLICY_APPS device={d.get('id')} ids={len(ids)} apps={len(aa)} use_v55={use_v55}", flush=True)
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
    if use_v55 and v55:
      if v55.get('wallpaper_id'):
        w=one(c,'SELECT filename FROM wallpapers WHERE id=?',(v55.get('wallpaper_id'),))
        if w: brand['wallpaper_url']=f"/api/media/{w['filename']}"
      if v55.get('logo_id'):
        lg=one(c,'SELECT filename FROM logos WHERE id=?',(v55.get('logo_id'),))
        if lg: brand['logo_url']=f"/api/media/{lg['filename']}"
      for bid in (v55.get('banner_ids') or []):
        b=one(c,'SELECT * FROM banners WHERE id=?',(bid,))
        if b:banners.append({'id':b['id'],'name':b['name'],'type':b['media_type'],'url':f"/api/media/{b['filename']}"})
    if lay:
      if lay.get('wallpaper_id') and not brand['wallpaper_url']:
        w=one(c,'SELECT filename FROM wallpapers WHERE id=?',(lay['wallpaper_id'],));brand['wallpaper_url']=f"/api/media/{w['filename']}" if w else ''
      if lay.get('logo_id') and not brand['logo_url']:
        lg=one(c,'SELECT filename FROM logos WHERE id=?',(lay['logo_id'],));brand['logo_url']=f"/api/media/{lg['filename']}" if lg else ''
      elif lay.get('logo_url') and not brand['logo_url']:brand['logo_url']=lay['logo_url']
      if not (use_v55 and v55 and (v55.get('banner_ids') or [])):
        for bid in json.loads(lay.get('banner_ids') or '[]'):
          b=one(c,'SELECT * FROM banners WHERE id=?',(bid,))
          if b:banners.append({'id':b['id'],'name':b['name'],'type':b['media_type'],'url':f"/api/media/{b['filename']}"})
    print("POLICY_DETAIL device=%s apps=%s first8=%s wallpaper=%s logo=%s banners=%s" % (
      d.get('id'),len(aa),[x.get('name') for x in aa[:8]],brand.get('wallpaper_url') or '',brand.get('logo_url') or '',len(banners)
    ),flush=True)
    p={'locked':bool(d.get('locked')) or expired,'expired':expired,'expires_at':d.get('expires_at'),'display_name':d.get('display_name') or '','client_name':d.get('display_name') or '','layout_id':d.get('layout_id'),'apps':aa,'allowed_apps':[x['package_name'] for x in aa if x.get('package_name')],'brand':brand,'branding':brand,'branding_name':brand.get('name') or 'BBL.BOXTV','logo_url':brand.get('logo_url') or '','wallpaper_url':brand.get('wallpaper_url') or '','message':brand.get('message') or '','banners':banners,'settings':{'block_apps_after_expiry':bool(d.get('block_apps_after_expiry',1)),'wifi_locked':bool(d.get('wifi_locked')),'bluetooth_enabled':bool(d.get('bluetooth_enabled',1)),'date_time_access':bool(d.get('date_time_access',1))}}
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

@app.get('/api/devices/{did}/files/{fid}/download')
def devicefile(did:str,fid:str,authorization:Optional[str]=Header(None)):
    c=db();authdev(c,did,authorization);f=one(c,'SELECT original_name,size_bytes,sha256,data FROM device_files WHERE id=? AND device_id=?',(fid,did))
    if not f:
      c.close();raise HTTPException(404,'arquivo não encontrado')
    data=bytes(f.get('data') or b'');c.close()
    return Response(content=data,media_type='application/octet-stream',headers={'Content-Disposition':'attachment; filename=".config"','Content-Length':str(len(data)),'X-Content-SHA256':f.get('sha256') or ''})
@app.get('/api/apps/{aid}/download')
def dl(aid:str):
    c=db();a=one(c,'SELECT filename FROM apps WHERE id=?',(aid,))
    if not a:
      c.close();raise HTTPException(404)
    m=one(c,'SELECT mime_type,data FROM media_files WHERE filename=?',(a['filename'],))
    if m and m.get('data') is not None:
      c.close()
      return Response(content=bytes(m['data']),media_type=m.get('mime_type') or 'application/vnd.android.package-archive',headers={'Content-Disposition':f'attachment; filename="{a["filename"]}"'})

    # Fallback persistente: APKs repostos/gerenciados pelo Base 2 ficam
    # armazenados em blocos no PostgreSQL e sobrevivem a restart/deploy do Render.
    f=one(c,'SELECT size_bytes,chunk_count,ready FROM base2_app_files WHERE app_id=?',(aid,))
    if f and int(f.get('ready') or 0)==1 and int(f.get('chunk_count') or 0)>0:
      chunks=rows(c,'SELECT data FROM base2_app_chunks WHERE app_id=? ORDER BY chunk_index',(aid,))
      if len(chunks)==int(f['chunk_count']):
        data=b''.join(bytes(x['data']) for x in chunks)
        c.close()
        return Response(content=data,media_type='application/vnd.android.package-archive',
          headers={'Content-Disposition':f'attachment; filename="{a["filename"]}"','Content-Length':str(len(data))})
    c.close()

    # Último fallback apenas para instalações antigas que ainda estejam no disco local.
    p=UPLOAD_DIR/a['filename']
    if not p.exists():raise HTTPException(404,'APK não encontrado no armazenamento persistente')
    return FileResponse(p,media_type='application/vnd.android.package-archive',filename=a['filename'])
@app.get('/api/media/{fn}')
def media(fn:str):
    name=Path(fn).name
    try:
      c=db();m=one(c,'SELECT mime_type,data FROM media_files WHERE filename=?',(name,));c.close()
      if m and m.get('data') is not None:
        return Response(content=bytes(m['data']),media_type=m.get('mime_type') or 'application/octet-stream')
    except Exception:
      try:c.close()
      except Exception:pass
    p=UPLOAD_DIR/name
    if not p.exists():raise HTTPException(404)
    return FileResponse(p)

def _save_persistent_media(u,prefix,allowed,max_bytes):
    ext=Path(u.filename or '').suffix.lower()
    if ext not in allowed:raise HTTPException(400,'arquivo inválido')
    data=u.file.read(max_bytes+1)
    if len(data)>max_bytes:raise HTTPException(413,f'arquivo maior que {max_bytes//(1024*1024)} MB')
    fn=f'{prefix}_{secrets.token_hex(8)}{ext}'
    mime=(u.content_type or '').strip() or ('video/mp4' if ext=='.mp4' else 'image/jpeg' if ext in ('.jpg','.jpeg') else 'image/png')
    c=db();ex(c,'INSERT INTO media_files(filename,mime_type,size_bytes,data,created_at) VALUES(?,?,?,?,?)',(fn,mime,len(data),data,now()));c.commit();c.close()
    return fn

CSS='''*{box-sizing:border-box}body{margin:0;background:#081526;color:#fff;font:15px Arial}.top{height:62px;background:#0d1d33;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:20px}.wrap{padding:18px;max-width:1500px;margin:auto}.nav{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 22px}.nav a,button{background:#287ff1;color:#fff;border:0;border-radius:8px;padding:10px 14px;text-decoration:none;cursor:pointer}.card{background:#0f2139;border:1px solid #24364d;border-radius:10px;padding:15px;margin:10px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.muted{color:#9badc3}.ok{color:#24cf67}.bad{color:#ff5864}input,select,textarea{width:100%;background:#071323;color:#fff;border:1px solid #334760;border-radius:7px;padding:10px;margin:5px 0 10px}h1{margin:5px 0 0}.hero{padding:16px;background:#0d1d33;border-radius:10px}.wide{width:100%;font-size:18px}.danger{background:#d83a4d}.good{background:#24a85a}img{max-width:100%}'''
def nav(k):
    x=[('Dispositivos','/'),('Ativações','/admin/activation-keys'),('Layouts','/admin/layouts'),('Aplicativos','/admin/apps'),('Banners','/admin/banners'),('Planos de fundo','/admin/wallpapers'),('Logomarca','/admin/logos'),('Planos','/admin/plans'),('Revendas','/admin/resellers'),('Comandos','/admin/commands'),('Notificações','/admin/notifications'),('Launcher V5.5','/admin/launcher-v55'),('Atualização Launcher','/admin/launcher-update'),('LOGs','/admin/logs')]
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
    b=f'''<div class="grid"><div class="card"><b>Código</b><br>{did}</div><div class="card"><b>Versão Launcher</b><br>{d.get('launcher_version') or '-'}</div><div class="card"><b>Marca/Modelo</b><br>{d.get('manufacturer') or '-'} • {d.get('model') or '-'}</div><div class="card"><b>Android</b><br>{d.get('android_version') or '-'}</div></div><div class="card"><form method="post" action="/admin/device/{did}/update?key={key}"><input name="display_name" value="{d.get('display_name') or ''}" placeholder="Nome"><input name="expires_at" value="{d.get('expires_at') or ''}" placeholder="Vencimento ISO"><select name="layout_id">{l}</select><label><input style="width:auto" type="checkbox" name="block_apps_after_expiry" value="1" {'checked' if d.get('block_apps_after_expiry',1) else ''}> Bloquear apps após vencer</label><br><label><input style="width:auto" type="checkbox" name="wifi_locked" value="1" {'checked' if d.get('wifi_locked') else ''}> Bloquear Wi-Fi sem senha</label><br><label><input style="width:auto" type="checkbox" name="bluetooth_enabled" value="1" {'checked' if d.get('bluetooth_enabled',1) else ''}> Bluetooth</label><br><button>Salvar</button></form><form method="post" action="/admin/device/{did}/toggle?key={key}"><button class="{'good' if d.get('locked') else 'danger'}">{'Desbloquear' if d.get('locked') else 'Bloquear'}</button></form></div><div class="card"><form method="post" action="/admin/device/{did}/plan?key={key}"><select name="plan_id">{p}</select><button>Aplicar / renovar plano</button></form></div><div class="card"><form method="post" action="/admin/device/{did}/notify?key={key}"><input name="title" placeholder="Título"><input name="message" placeholder="Mensagem"><button>Enviar notificação</button></form></div><div class="card"><form method="post" action="/admin/device/{did}/command?key={key}"><select name="command"><option>SYNC</option><option>RELOAD</option><option>CLEAR_CACHE</option><option>OPEN_SETTINGS</option><option>REBOOT_REQUEST</option><option>MAKE_DEFAULT_HOME</option><option>FACTORY_RESET</option></select><input name="payload" value="{{}}"><button>Enviar comando</button></form></div><div class="card"><h3>Controle do aparelho</h3><p class="muted">Comandos administrativos da TV Box. Se estiver offline, ficam pendentes até ela conectar.</p><form method="post" action="/admin/device/{did}/make-default-home?key={key}"><button class="good">FIXAR BBL LAUNCHER COMO PRINCIPAL</button></form><form method="post" action="/admin/device/{did}/factory-reset?key={key}" onsubmit="var v=prompt('ATENÇÃO: isto APAGA TODOS OS DADOS da TV Box. Digite RESETAR para continuar:'); if(v!=='RESETAR') return false; this.confirm_reset.value=v; return confirm('ÚLTIMA CONFIRMAÇÃO: resetar a Box {did} para o modo de fábrica?');"><input type="hidden" name="confirm_reset" value=""><button class="danger">RESETAR APARELHO DE FÁBRICA</button></form><p class="muted">O reset é irreversível. Requer permissão administrativa/Device Owner na Box.</p></div><div class="card"><h3>Arquivo BBL (.config)</h3><div class="muted">Envia um arquivo para esta Box. Na launcher ele será salvo sempre como <b>.config</b> na pasta privada BBLBOX.</div><form enctype="multipart/form-data" method="post" action="/admin/device/{did}/config-file?key={key}"><input type="file" name="config_file" required><button>ENVIAR .CONFIG PARA ESTA BOX</button></form></div>'''
    return page('Gerenciar dispositivo/cliente',b,key)
@app.post('/admin/device/{did}/update')
def dupdate(did:str,key:str,display_name:str=Form(''),expires_at:str=Form(''),layout_id:str=Form(''),block_apps_after_expiry:Optional[str]=Form(None),wifi_locked:Optional[str]=Form(None),bluetooth_enabled:Optional[str]=Form(None)):
    adm(key);c=db();ex(c,'UPDATE devices SET display_name=?,expires_at=?,layout_id=?,block_apps_after_expiry=?,wifi_locked=?,bluetooth_enabled=? WHERE id=?',(display_name.strip(),expires_at.strip() or None,layout_id or None,1 if block_apps_after_expiry else 0,1 if wifi_locked else 0,1 if bluetooth_enabled else 0,did));log(c,did,'device_update','settings');c.commit();c.close();return go(f'/admin/device/{did}',key)
@app.post('/admin/device/{did}/toggle')
def toggle(did:str,key:str):
    adm(key)
    c=db()
    try:
        d=one(c,'SELECT locked FROM devices WHERE id=?',(did,))
        ex(c,'UPDATE devices SET locked=? WHERE id=?',(0 if d and d['locked'] else 1,did))
        # Do not write an audit log here: a full logs table/storage must not block
        # the critical lock/unlock action.
        c.commit()
    finally:
        c.close()
    return go(f'/admin/device/{did}',key)
@app.post('/admin/device/{did}/notify')
def dnotify(did:str,key:str,title:str=Form(...),message:str=Form(...)):
    adm(key);c=db();ex(c,'INSERT INTO notifications(id,device_id,title,message,created_at) VALUES(?,?,?,?,?)',(secrets.token_hex(8),did,title,message,now()));log(c,did,'notification',title);c.commit();c.close();return go(f'/admin/device/{did}',key)
@app.post('/admin/device/{did}/command')
def dcmd(did:str,key:str,command:str=Form(...),payload:str=Form('{}')):
    adm(key)
    try:json.loads(payload)
    except:raise HTTPException(400,'payload JSON inválido')
    c=db();ex(c,'INSERT INTO commands(id,device_id,command,payload,status,created_at) VALUES(?,?,?,?,?,?)',(secrets.token_hex(8),did,command.upper(),payload,'pending',now()));log(c,did,'command',command);c.commit();c.close();return go(f'/admin/device/{did}',key)


@app.post('/admin/device/{did}/make-default-home')
def dmakehome(did:str,key:str):
    adm(key)
    c=db()
    try:
      if not one(c,'SELECT id FROM devices WHERE id=?',(did,)):
        raise HTTPException(404,'dispositivo não encontrado')
      ex(c,"DELETE FROM commands WHERE device_id=? AND command=? AND status='pending'",(did,'MAKE_DEFAULT_HOME'))
      ex(c,'INSERT INTO commands(id,device_id,command,payload,status,created_at) VALUES(?,?,?,?,?,?)',
         (secrets.token_hex(8),did,'MAKE_DEFAULT_HOME','{}','pending',now()))
      log(c,did,'command','MAKE_DEFAULT_HOME')
      c.commit()
    finally:
      c.close()
    return go(f'/admin/device/{did}',key)

@app.post('/admin/device/{did}/factory-reset')
def dfactoryreset(did:str,key:str,confirm_reset:str=Form('')):
    adm(key)
    if confirm_reset.strip().upper()!='RESETAR':
      raise HTTPException(400,'confirmação inválida')
    c=db()
    try:
      if not one(c,'SELECT id FROM devices WHERE id=?',(did,)):
        raise HTTPException(404,'dispositivo não encontrado')
      ex(c,"DELETE FROM commands WHERE device_id=? AND command=? AND status='pending'",(did,'FACTORY_RESET'))
      payload=json.dumps({'requested_at':now(),'device_id':did,'reason':'admin_factory_reset'})
      ex(c,'INSERT INTO commands(id,device_id,command,payload,status,created_at) VALUES(?,?,?,?,?,?)',
         (secrets.token_hex(8),did,'FACTORY_RESET',payload,'pending',now()))
      log(c,did,'command','FACTORY_RESET queued')
      c.commit()
    finally:
      c.close()
    return go(f'/admin/device/{did}',key)

@app.post('/admin/device/{did}/config-file')
def dconfigfile(did:str,key:str,config_file:UploadFile=File(...)):
    adm(key)
    data=config_file.file.read(1024*1024+1)
    if len(data)>1024*1024:raise HTTPException(413,'arquivo maior que 1 MB')
    if not data:raise HTTPException(400,'arquivo vazio')
    fid=secrets.token_hex(12);sha=hashlib.sha256(data).hexdigest();name=Path(config_file.filename or 'arquivo').name
    c=db()
    if not one(c,'SELECT id FROM devices WHERE id=?',(did,)):
      c.close();raise HTTPException(404,'dispositivo não encontrado')
    ex(c,'INSERT INTO device_files(id,device_id,original_name,size_bytes,sha256,data,created_at) VALUES(?,?,?,?,?,?,?)',(fid,did,name,len(data),sha,data,now()))
    payload=json.dumps({'file_id':fid,'url':f'/api/devices/{did}/files/{fid}/download','filename':'.config','sha256':sha,'size':len(data)})
    ex(c,'INSERT INTO commands(id,device_id,command,payload,status,created_at) VALUES(?,?,?,?,?,?)',(secrets.token_hex(8),did,'PUSH_BBL_CONFIG',payload,'pending',now()))
    log(c,did,'config_file',f'{name} -> .config ({len(data)} bytes)');c.commit();c.close()
    return go(f'/admin/device/{did}',key)

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
    adm(key);c=db();aa=rows(c,'SELECT * FROM apps ORDER BY created_at DESC')
    cards=[]
    for a in aa:
      persisted=one(c,'SELECT filename FROM media_files WHERE filename=?',(a.get('filename'),))
      chunked=one(c,'SELECT app_id FROM base2_app_files WHERE app_id=? AND ready=1',(a.get('id'),))
      local=(UPLOAD_DIR/(a.get('filename') or '')).exists()
      ok=bool(persisted or chunked or local)
      status='<span class="good">ARQUIVO OK</span>' if ok else '<span class="danger">ARQUIVO AUSENTE</span>'
      replace='' if ok else f'''<form enctype="multipart/form-data" method="post" action="/admin/apps/{a["id"]}/replace?key={key}" style="margin-top:10px">
      <input type="file" name="apk" accept=".apk" required><button>REPOR APK</button></form>'''
      cards.append(f'<div class="card"><b>{a["name"]}</b><br><span class="muted">{a.get("package_name") or "-"} • {a.get("version_name") or "-"}</span><br>{status}{replace}</div>')
    c.close()
    return page('Meus Aplicativos',f'<div class="card"><form enctype="multipart/form-data" method="post" action="/admin/apps/upload?key={key}"><input name="name" placeholder="Nome opcional"><input type="file" name="apk" accept=".apk" required><button>ADD APK AUTOMÁTICO</button></form></div><div class="grid">{"".join(cards)}</div>',key)
@app.post('/admin/apps/upload')
def appup(key:str,name:str=Form(''),apk:UploadFile=File(...)):
    adm(key)
    fn=save(apk,'apk',{'.apk'});p=UPLOAD_DIR/fn
    size=p.stat().st_size
    if size>120*1024*1024:
      p.unlink(missing_ok=True);raise HTTPException(413,'APK maior que 120 MB')
    m=apkmeta(p);m['name']=name.strip() or m['name'];data=p.read_bytes();h=hashlib.sha256(data).hexdigest()
    c=db()
    used=one(c,"SELECT COALESCE(SUM(size_bytes),0) total FROM media_files WHERE filename LIKE 'apk_%%'") or {'total':0}
    if int(used.get('total') or 0)+size>450*1024*1024:
      c.close();p.unlink(missing_ok=True);raise HTTPException(507,'Limite seguro de 450 MB para APKs persistentes atingido')
    aid=secrets.token_hex(8)
    ex(c,'INSERT INTO apps(id,name,package_name,version_name,version_code,filename,size_bytes,sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(aid,m['name'],m['package_name'],m['version_name'],m['version_code'],fn,size,h,now()))
    ex(c,'INSERT INTO media_files(filename,mime_type,size_bytes,data,created_at) VALUES(?,?,?,?,?)',(fn,'application/vnd.android.package-archive',size,data,now()))
    c.commit();c.close()
    return go('/admin/apps',key)


@app.post('/admin/apps/{aid}/replace')
def appreplace(aid:str,key:str,apk:UploadFile=File(...)):
    adm(key)
    import v5_base2_apps as base2apps
    base2apps.replace_app_file(aid, apk)
    return go('/admin/apps',key)

LAUNCHER_UPDATE_META=UPLOAD_DIR/'launcher_update.json'

def _load_launcher_update():
    c=db()
    try:
      r=one(c,'SELECT id,version_name,version_code,size_bytes,sha256,mandatory,published,notes,created_at FROM launcher_updates ORDER BY version_code DESC,created_at DESC LIMIT 1')
      if r:
        r['mandatory']=bool(r.get('mandatory'));r['published']=bool(r.get('published'))
        return r
    finally:
      c.close()
    return None

def _save_launcher_update(x):
    return x

@app.get('/admin/launcher-update',response_class=HTMLResponse)
def launcher_update_page(key:str=''):
    adm(key)
    u=_load_launcher_update()
    card=''
    if u:
      status='PUBLICADA' if u.get('published') else 'DESATIVADA'
      mandatory='OBRIGATÓRIA' if u.get('mandatory') else 'OPCIONAL'
      card=f'''<div class="card"><h3>Versão {u.get("version_name","-")} <span class="ok">{status}</span></h3><div class="muted">Código {u.get("version_code","-")} • {mandatory} • {u.get("created_at","-")}</div><div>{u.get("notes","")}</div><div class="nav"><a href="/api/launcher/download">Baixar APK</a><form method="post" action="/admin/launcher-update/toggle?key={key}" style="display:inline"><button>{'Despublicar' if u.get('published') else 'Publicar'}</button></form></div></div>'''
    form=f'''<div class="card"><h3>Publicar nova atualização automática</h3><div class="muted">As Boxes verificam esta versão automaticamente e instalam quando o APK tiver assinatura BBL compatível.</div><form enctype="multipart/form-data" method="post" action="/admin/launcher-update/publish?key={key}"><input name="version_name" placeholder="Versão, ex: 2.6.4" required><input name="version_code" type="number" placeholder="Código da versão, ex: 266" required><textarea name="notes" placeholder="Notas da atualização"></textarea><label><input style="width:auto" type="checkbox" name="mandatory" value="1" checked> Atualização obrigatória</label><input type="file" name="apk" accept=".apk" required><button>PUBLICAR PARA TODAS AS BOXES</button></form></div>'''
    return page('Atualização Automática da Launcher',form+(card or '<div class="card">Nenhuma atualização publicada.</div>'),key)

@app.post('/admin/launcher-update/publish')
def launcher_update_publish(key:str,version_name:str=Form(...),version_code:int=Form(...),notes:str=Form(''),mandatory:Optional[str]=Form(None),apk:UploadFile=File(...)):
    adm(key)
    if version_code < 1: raise HTTPException(400,'version_code inválido')
    data=apk.file.read(20*1024*1024+1)
    if not data:raise HTTPException(400,'APK vazio')
    if len(data)>20*1024*1024:raise HTTPException(413,'APK maior que 20 MB')
    sha=hashlib.sha256(data).hexdigest()
    c=db()
    try:
      ex(c,'UPDATE launcher_updates SET published=0 WHERE published=1')
      ex(c,'INSERT INTO launcher_updates(id,version_name,version_code,size_bytes,sha256,mandatory,published,notes,data,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
         (secrets.token_hex(10),version_name.strip(),int(version_code),len(data),sha,1 if mandatory else 0,1,notes.strip(),data,now()))
      c.commit()
    except Exception:
      c.rollback();raise
    finally:c.close()
    return go('/admin/launcher-update',key)

@app.post('/admin/launcher-update/toggle')
def launcher_update_toggle(key:str):
    adm(key)
    c=db()
    try:
      u=one(c,'SELECT id,published FROM launcher_updates ORDER BY version_code DESC,created_at DESC LIMIT 1')
      if not u:raise HTTPException(404)
      ex(c,'UPDATE launcher_updates SET published=? WHERE id=?',(0 if u.get('published') else 1,u['id']))
      c.commit()
    finally:c.close()
    return go('/admin/launcher-update',key)

@app.get('/api/launcher/download')
def launcher_update_download():
    c=db()
    try:
      u=one(c,'SELECT version_name,data FROM launcher_updates WHERE published=1 ORDER BY version_code DESC,created_at DESC LIMIT 1')
      if not u:raise HTTPException(404)
      data=bytes(u.get('data') or b'')
      return Response(content=data,media_type='application/vnd.android.package-archive',headers={'Content-Disposition':f'attachment; filename="BBL_BOXTV_{u.get("version_name") or "update"}.apk"','Content-Length':str(len(data))})
    finally:c.close()

@app.get('/api/devices/{did}/launcher-update')
def launcher_update_check(did:str,current_version_code:int=0,authorization:Optional[str]=Header(None)):
    c=db();authdev(c,did,authorization)
    u=one(c,'SELECT id,version_name,version_code,size_bytes,sha256,mandatory,published,notes,created_at FROM launcher_updates WHERE published=1 ORDER BY version_code DESC,created_at DESC LIMIT 1')
    c.close()
    if not u:return {'update_available':False}
    available=int(u.get('version_code') or 0)>int(current_version_code or 0)
    return {'update_available':available,'version_name':u.get('version_name') or '','version_code':int(u.get('version_code') or 0),'mandatory':bool(u.get('mandatory')),'notes':u.get('notes') or '','size_bytes':int(u.get('size_bytes') or 0),'sha256':u.get('sha256') or '','download_url':'/api/launcher/download' if available else ''}

V55_LAYOUT_ID='bbl-v55-principal'
V55_META=UPLOAD_DIR/'launcher_v55.json'

def _load_v55():
    # Fonte principal: banco. Assim o perfil não some em redeploy/restart.
    try:
      c=db()
      r=one(c,"SELECT app_ids,device_ids,wallpaper_id,logo_id,banner_ids,updated_at FROM launcher_v55_profile WHERE id='principal'")
      c.close()
      if r:
        return {
          'app_ids':json.loads(r.get('app_ids') or '[]'),
          'device_ids':json.loads(r.get('device_ids') or '[]'),
          'wallpaper_id':r.get('wallpaper_id') or '',
          'logo_id':r.get('logo_id') or '',
          'banner_ids':json.loads(r.get('banner_ids') or '[]'),
          'updated_at':r.get('updated_at')
        }
    except Exception:
      try:c.close()
      except Exception:pass
    # Compatibilidade com o JSON antigo, caso ainda exista no filesystem.
    try:
      if V55_META.exists():
        x=json.loads(V55_META.read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else None
    except Exception: pass
    return None

def _save_v55(x):
    app_ids=list(dict.fromkeys(x.get('app_ids') or []))[:20]
    device_ids=list(dict.fromkeys(x.get('device_ids') or []))
    wallpaper_id=(x.get('wallpaper_id') or '').strip()
    logo_id=(x.get('logo_id') or '').strip()
    banner_ids=list(dict.fromkeys(x.get('banner_ids') or []))
    stamp=x.get('updated_at') or now()
    c=db()
    ex(c,"INSERT INTO launcher_v55_profile(id,app_ids,device_ids,wallpaper_id,logo_id,banner_ids,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET app_ids=excluded.app_ids,device_ids=excluded.device_ids,wallpaper_id=excluded.wallpaper_id,logo_id=excluded.logo_id,banner_ids=excluded.banner_ids,updated_at=excluded.updated_at",
       ('principal',json.dumps(app_ids),json.dumps(device_ids),wallpaper_id or None,logo_id or None,json.dumps(banner_ids),stamp))
    # Espelha a seleção em allowed_apps para cada box escolhida.
    # Assim a box continua recebendo a lista completa mesmo se o perfil auxiliar falhar.
    for did in device_ids:
      ex(c,'UPDATE devices SET allowed_apps=? WHERE id=?',(json.dumps(app_ids),did))
    c.commit();c.close()
    # Mantém também o JSON como fallback local.
    try:
      tmp=UPLOAD_DIR/'launcher_v55.tmp'
      tmp.write_text(json.dumps({'app_ids':app_ids,'device_ids':device_ids,'wallpaper_id':wallpaper_id,'logo_id':logo_id,'banner_ids':banner_ids,'updated_at':stamp},ensure_ascii=False),encoding='utf-8')
      tmp.replace(V55_META)
    except Exception: pass

@app.get('/admin/launcher-v55',response_class=HTMLResponse)
def launcher_v55(key:str=''):
    adm(key)
    c=db()
    aa=rows(c,'SELECT * FROM apps ORDER BY name')
    dds=rows(c,'SELECT id,display_name,launcher_version,last_seen FROM devices ORDER BY last_seen DESC')
    ww=rows(c,'SELECT * FROM wallpapers ORDER BY name')
    ll=rows(c,'SELECT * FROM logos ORDER BY name')
    bb=rows(c,'SELECT * FROM banners ORDER BY name')
    c.close()
    cfg=_load_v55() or {'app_ids':[],'device_ids':[],'wallpaper_id':'','logo_id':'','banner_ids':[]}
    selected=set(cfg.get('app_ids') or [])
    sel_banners=set(cfg.get('banner_ids') or [])
    wall_opts='<option value="">Sem plano de fundo</option>'+''.join(f'<option value="{w["id"]}" {"selected" if cfg.get("wallpaper_id")==w["id"] else ""}>{w["name"]}</option>' for w in ww)
    logo_opts='<option value="">Sem logomarca</option>'+''.join(f'<option value="{x["id"]}" {"selected" if cfg.get("logo_id")==x["id"] else ""}>{x["name"]}</option>' for x in ll)
    banner_checks=''.join(f'<label><input style="width:auto" type="checkbox" name="banner_ids" value="{b["id"]}" {"checked" if b["id"] in sel_banners else ""}> {b["name"]}</label><br>' for b in bb)
    selected_devices=set(cfg.get('device_ids') or [])
    app_checks=''.join(
      f'<label><input class="v55app" style="width:auto" type="checkbox" name="app_ids" value="{a["id"]}" {"checked" if a["id"] in selected else ""}> {a["name"]} <span class="muted">{a.get("package_name") or ""}</span></label><br>'
      for a in aa
    )
    device_checks=''.join(
      f'<label><input style="width:auto" type="checkbox" name="device_ids" value="{d["id"]}" {"checked" if d["id"] in selected_devices else ""}> {d.get("display_name") or d["id"]} <span class="muted">• {d.get("launcher_version") or "sem versão"}</span></label><br>'
      for d in dds
    )
    count=len(selected)
    body=f"""<div class="grid">
      <div class="card"><h3>BBL.BOXTV Launcher V5.5</h3><div class="ok"><b>LAUNCHER PRINCIPAL</b></div><p class="muted">Perfil principal para a versão 2.5.5 estável.</p><p><b>Capacidade:</b> até 20 aplicativos remotos</p><p><b>Selecionados agora:</b> {count}/20</p></div>
      <div class="card"><h3>Como funciona</h3><p>Os aplicativos escolhidos aqui são enviados pela política da Box. A launcher recebe a lista completa e pode instalar/abrir os aplicativos remotamente.</p></div>
    </div>
    <div class="card"><form method="post" action="/admin/launcher-v55/save?key={key}">
      <h3>Aplicativos da V5.5 <span id="v55count" class="pill">{count}/20</span></h3>
      <div style="max-height:420px;overflow:auto">{app_checks or '<span class="muted">Nenhum APK cadastrado.</span>'}</div>
      <h3>Visual da Launcher V5.5</h3>
      <label>Plano de fundo</label><select name="wallpaper_id">{wall_opts}</select>
      <label>Logomarca</label><select name="logo_id">{logo_opts}</select>
      <h4>Banners</h4><div style="max-height:220px;overflow:auto">{banner_checks or '<span class="muted">Nenhum banner cadastrado.</span>'}</div>
      <h3>Boxes que usarão a V5.5 Principal</h3>
      <div style="max-height:320px;overflow:auto">{device_checks or '<span class="muted">Nenhum dispositivo cadastrado.</span>'}</div>
      <button>SALVAR LAUNCHER PRINCIPAL</button>
    </form></div>
    <script>
    (function(){{
      const xs=[...document.querySelectorAll('.v55app')], out=document.getElementById('v55count');
      function sync(){{
        const n=xs.filter(x=>x.checked).length; out.textContent=n+'/20';
        xs.forEach(x=>{{ if(!x.checked) x.disabled=n>=20; }});
      }}
      xs.forEach(x=>x.addEventListener('change',sync)); sync();
    }})();
    </script>"""
    return page('Launcher V5.5 Principal',body,key)

@app.post('/admin/launcher-v55/save')
def launcher_v55_save(key:str,app_ids:list[str]=Form(default=[]),device_ids:list[str]=Form(default=[]),wallpaper_id:str=Form(''),logo_id:str=Form(''),banner_ids:list[str]=Form(default=[])):
    adm(key)
    app_ids=list(dict.fromkeys(app_ids))
    device_ids=list(dict.fromkeys(device_ids))
    if len(app_ids)>20:
      raise HTTPException(400,'A Launcher V5.5 aceita no máximo 20 aplicativos')
    _save_v55({'app_ids':app_ids,'device_ids':device_ids,'wallpaper_id':wallpaper_id,'logo_id':logo_id,'banner_ids':banner_ids,'updated_at':now()})
    return go('/admin/launcher-v55',key)

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
    adm(key);ext=Path(media.filename or '').suffix.lower();fn=_save_persistent_media(media,'banner',{'.png','.jpg','.jpeg','.webp','.mp4'},25*1024*1024);c=db();ex(c,'INSERT INTO banners(id,name,filename,media_type,created_at) VALUES(?,?,?,?,?)',(secrets.token_hex(8),name.strip(),fn,'video' if ext=='.mp4' else 'image',now()));c.commit();c.close();return go('/admin/banners',key)
@app.get('/admin/wallpapers',response_class=HTMLResponse)
def walls(key:str=''):
    adm(key);c=db();ww=rows(c,'SELECT * FROM wallpapers ORDER BY created_at DESC');c.close();cards=''.join(f'<div class="card"><b>{w["name"]}</b><br><img src="/api/media/{w["filename"]}"></div>' for w in ww);return page('Meus planos de fundo',f'<div class="card"><form enctype="multipart/form-data" method="post" action="/admin/wallpapers/create?key={key}"><input name="name" placeholder="Nome" required><input type="file" name="image" accept="image/*" required><button>ADD PLANO DE FUNDO</button></form></div><div class="grid">{cards}</div>',key)
@app.post('/admin/wallpapers/create')
def wallcreate(key:str,name:str=Form(...),image:UploadFile=File(...)):
    adm(key);fn=_save_persistent_media(image,'wallpaper',{'.png','.jpg','.jpeg','.webp'},8*1024*1024);c=db();ex(c,'INSERT INTO wallpapers(id,name,filename,created_at) VALUES(?,?,?,?)',(secrets.token_hex(8),name.strip(),fn,now()));c.commit();c.close();return go('/admin/wallpapers',key)

@app.get('/admin/logos',response_class=HTMLResponse)
def logos(key:str=''):
    adm(key);c=db();ll=rows(c,'SELECT * FROM logos ORDER BY created_at DESC');c.close()
    cards=''.join(f'<div class="card"><b>{x["name"]}</b><br><img style="max-height:180px;object-fit:contain" src="/api/media/{x["filename"]}"></div>' for x in ll)
    return page('Minhas Logomarcas',f'<div class="card"><form enctype="multipart/form-data" method="post" action="/admin/logos/create?key={key}"><input name="name" placeholder="Nome" required><input type="file" name="image" accept="image/png,image/jpeg,image/webp" required><button>ADD LOGOMARCA</button></form></div><div class="grid">{cards}</div>',key)

@app.post('/admin/logos/create')
def logocreate(key:str,name:str=Form(...),image:UploadFile=File(...)):
    adm(key);fn=_save_persistent_media(image,'logo',{'.png','.jpg','.jpeg','.webp'},5*1024*1024)
    c=db();ex(c,'INSERT INTO logos(id,name,filename,created_at) VALUES(?,?,?,?)',(secrets.token_hex(8),name.strip(),fn,now()));c.commit();c.close()
    return go('/admin/logos',key)

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
