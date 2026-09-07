import os, secrets, hashlib, hmac, html, time
from datetime import datetime, timezone, timedelta
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import v5

app = v5.app
ADMIN_USER = os.getenv('BASE2_ADMIN_USER','').strip()
ADMIN_PASS = os.getenv('BASE2_ADMIN_PASSWORD','')
ADMIN_SECRET = os.getenv('BASE2_ADMIN_SECRET','base2-change-me')
BASE2_PACKAGE = 'com.rtxapps.reuse'

def now(): return datetime.now(timezone.utc).isoformat()
def esc(x): return html.escape(str(x or ''))
def phash(p,s=None):
    s=s or secrets.token_hex(16)
    d=hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(s),180000)
    return f'pbkdf2_sha256$180000${s}${d.hex()}'
def pcheck(p,e):
    try:
        a,r,s,d=e.split('$',3)
        x=hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(s),int(r)).hex()
        return a=='pbkdf2_sha256' and hmac.compare_digest(x,d)
    except: return False

def init():
    c=v5.db()
    for s in [
      "CREATE TABLE IF NOT EXISTS base2_resellers(id TEXT PRIMARY KEY,parent_id TEXT,name TEXT NOT NULL,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,max_clients INTEGER NOT NULL DEFAULT 50,max_resellers INTEGER NOT NULL DEFAULT 5,created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS base2_clients(id TEXT PRIMARY KEY,reseller_id TEXT,name TEXT NOT NULL,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,expires_at TEXT,device_id TEXT NOT NULL DEFAULT '',created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS base2_tokens(token_hash TEXT PRIMARY KEY,client_id TEXT NOT NULL,device_id TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL)",
      "CREATE TABLE IF NOT EXISTS base2_reseller_sessions(token_hash TEXT PRIMARY KEY,reseller_id TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL)"
    ]: v5.ex(c,s)
    c.commit(); c.close()
init()

def sign_admin():
    ts=str(int(time.time()))
    sig=hmac.new(ADMIN_SECRET.encode(),f'{ADMIN_USER}:{ts}'.encode(),hashlib.sha256).hexdigest()
    return ts+'.'+sig
def admin_ok(req):
    t=req.cookies.get('base2_admin','')
    try:
        ts,sig=t.split('.',1)
        if time.time()-int(ts)>43200:return False
        exp=hmac.new(ADMIN_SECRET.encode(),f'{ADMIN_USER}:{ts}'.encode(),hashlib.sha256).hexdigest()
        return bool(ADMIN_USER and ADMIN_PASS and hmac.compare_digest(sig,exp))
    except:return False

def style():
    return '''body{margin:0;background:#07111f;color:#fff;font-family:Arial,sans-serif}.top{background:#0b2037;padding:18px 28px;font-weight:800;font-size:22px}.wrap{max-width:1200px;margin:auto;padding:24px}.card{background:#10253d;border:1px solid #24496e;border-radius:16px;padding:18px;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.muted{color:#9db1c7}input,select{width:100%;box-sizing:border-box;padding:13px;margin:7px 0;border-radius:10px;border:1px solid #315a80;background:#081a2c;color:white}button,.btn{display:inline-block;background:#1677ff;color:#fff;border:0;border-radius:10px;padding:11px 15px;margin:4px;text-decoration:none;font-weight:700}.danger{background:#d43838}.good{background:#16875b}.nav a{color:#fff;margin-right:16px;text-decoration:none}.tag{padding:4px 9px;border-radius:12px;background:#173e67}.login{max-width:480px;margin:70px auto}.stat{font-size:30px;font-weight:800}'''
def page(title,body,nav=True):
    n='<div class="nav"><a href="/base2/painel">Início</a><a href="/base2/painel/revendas">Revendas</a><a href="/base2/painel/clientes">Clientes</a><a href="/base2/painel/sair">Sair</a></div>' if nav else ''
    return HTMLResponse(f'<!doctype html><meta name="viewport" content="width=device-width"><title>{esc(title)}</title><style>{style()}</style><div class="top">TUDO LIBERADO • PAINEL BASE 2</div><div class="wrap"><h1>{esc(title)}</h1>{n}{body}</div>')
def redir(p): return RedirectResponse(p,303)

@app.get('/base2/painel/login')
def admin_login_page(erro:str=''):
    e=f'<div class="card">{esc(erro)}</div>' if erro else ''
    return page('Acesso administrativo',f'<div class="login card">{e}<form method="post"><input name="username" placeholder="Usuário" required><input name="password" type="password" placeholder="Senha" required><button>ENTRAR</button></form></div>',False)
@app.post('/base2/painel/login')
def admin_login(username:str=Form(...),password:str=Form(...)):
    if not ADMIN_USER or not ADMIN_PASS or not secrets.compare_digest(username.strip(),ADMIN_USER) or not secrets.compare_digest(password,ADMIN_PASS):return redir('/base2/painel/login?erro=Acesso+inválido')
    r=redir('/base2/painel');r.set_cookie('base2_admin',sign_admin(),httponly=True,secure=True,samesite='lax',max_age=43200);return r
@app.get('/base2/painel/sair')
def admin_logout():
    r=redir('/base2/painel/login');r.delete_cookie('base2_admin');return r

def adm(req):
    if not admin_ok(req): raise HTTPException(401,'Acesso administrativo inválido')

@app.get('/base2/painel')
def dashboard(req:Request):
    if not admin_ok(req):return redir('/base2/painel/login')
    c=v5.db();r=v5.one(c,'SELECT COUNT(*) n FROM base2_resellers')['n'];cl=v5.one(c,'SELECT COUNT(*) n FROM base2_clients')['n'];ac=v5.one(c,'SELECT COUNT(*) n FROM base2_clients WHERE enabled=1')['n'];c.close()
    b=f'<div class="grid"><div class="card"><div class="stat">{r}</div>Revendas</div><div class="card"><div class="stat">{cl}</div>Clientes</div><div class="card"><div class="stat">{ac}</div>Clientes ativos</div></div><div class="card"><b>Aplicativo controlado:</b> Base 2 / Tudo Liberado<br><span class="muted">Pacote Android: {BASE2_PACKAGE}. Cada cliente fica vinculado ao primeiro aparelho que fizer login.</span></div>'
    return page('Painel Base 2',b)

@app.get('/base2/painel/revendas')
def resellers(req:Request):
    if not admin_ok(req):return redir('/base2/painel/login')
    c=v5.db();rr=v5.rows(c,'SELECT * FROM base2_resellers ORDER BY created_at DESC');c.close();cards=''
    for x in rr:
        cards+=f'<div class="card"><b>{esc(x["name"])}</b> • {esc(x["username"])} <span class="tag">{"ATIVA" if x["enabled"] else "BLOQUEADA"}</span><br><span class="muted">Clientes: {x["max_clients"]} • Sub-revendas: {x["max_resellers"]}</span><br><form method="post" action="/base2/painel/revendas/{x["id"]}/toggle"><button>{"Bloquear" if x["enabled"] else "Desbloquear"}</button></form></div>'
    b='<div class="card"><h3>Criar revenda</h3><form method="post" action="/base2/painel/revendas/criar"><input name="name" placeholder="Nome" required><input name="username" placeholder="Usuário" required><input name="password" type="password" placeholder="Senha" minlength="4" required><input name="max_clients" type="number" value="50" min="1"><input name="max_resellers" type="number" value="5" min="0"><button>CRIAR REVENDA</button></form></div><div class="grid">'+(cards or '<div class="card muted">Nenhuma revenda.</div>')+'</div>'
    return page('Revendas Base 2',b)
@app.post('/base2/painel/revendas/criar')
def reseller_create(req:Request,name:str=Form(...),username:str=Form(...),password:str=Form(...),max_clients:int=Form(50),max_resellers:int=Form(5)):
    adm(req);c=v5.db()
    try:v5.ex(c,'INSERT INTO base2_resellers(id,parent_id,name,username,password_hash,enabled,max_clients,max_resellers,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(secrets.token_hex(8),None,name.strip(),username.strip(),phash(password),1,max(1,max_clients),max(0,max_resellers),now()));c.commit()
    except Exception:c.rollback();c.close();raise HTTPException(409,'Usuário já existe')
    c.close();return redir('/base2/painel/revendas')
@app.post('/base2/painel/revendas/{rid}/toggle')
def reseller_toggle(req:Request,rid:str):
    adm(req);c=v5.db();x=v5.one(c,'SELECT * FROM base2_resellers WHERE id=?',(rid,));
    if not x:c.close();raise HTTPException(404)
    en=0 if x['enabled'] else 1;v5.ex(c,'UPDATE base2_resellers SET enabled=? WHERE id=?',(en,rid));c.commit();c.close();return redir('/base2/painel/revendas')

@app.get('/base2/painel/clientes')
def clients(req:Request):
    if not admin_ok(req):return redir('/base2/painel/login')
    c=v5.db();cc=v5.rows(c,'SELECT c.*,r.name reseller_name FROM base2_clients c LEFT JOIN base2_resellers r ON r.id=c.reseller_id ORDER BY c.created_at DESC');rr=v5.rows(c,'SELECT * FROM base2_resellers WHERE enabled=1 ORDER BY name');c.close();opts='<option value="">ADMIN</option>'+''.join(f'<option value="{x["id"]}">{esc(x["name"])}</option>' for x in rr);cards=''
    for x in cc:
        cards+=f'<div class="card"><b>{esc(x["name"])}</b> • {esc(x["username"])} <span class="tag">{"ATIVO" if x["enabled"] else "BLOQUEADO"}</span><br><span class="muted">Revenda: {esc(x.get("reseller_name") or "ADMIN")} • Vence: {esc(x["expires_at"] or "sem vencimento")} • Aparelho: {esc(x["device_id"] or "não vinculado")}</span><br><form method="post" action="/base2/painel/clientes/{x["id"]}/toggle" style="display:inline"><button>{"Bloquear" if x["enabled"] else "Desbloquear"}</button></form><form method="post" action="/base2/painel/clientes/{x["id"]}/reset-device" style="display:inline"><button>Trocar aparelho</button></form><form method="post" action="/base2/painel/clientes/{x["id"]}/renovar" style="display:inline"><input type="hidden" name="days" value="30"><button class="good">+30 dias</button></form></div>'
    b=f'<div class="card"><h3>Criar cliente final</h3><form method="post" action="/base2/painel/clientes/criar"><input name="name" placeholder="Nome" required><input name="username" placeholder="Usuário" required><input name="password" type="password" placeholder="Senha" minlength="4" required><select name="reseller_id">{opts}</select><input name="days" type="number" value="30" min="1"><button>CRIAR CLIENTE</button></form></div><div class="grid">{cards or "<div class=\"card muted\">Nenhum cliente.</div>"}</div>'
    return page('Clientes Base 2',b)
@app.post('/base2/painel/clientes/criar')
def client_create(req:Request,name:str=Form(...),username:str=Form(...),password:str=Form(...),reseller_id:str=Form(''),days:int=Form(30)):
    adm(req);exp=(datetime.now(timezone.utc)+timedelta(days=max(1,days))).isoformat();c=v5.db()
    try:v5.ex(c,'INSERT INTO base2_clients(id,reseller_id,name,username,password_hash,enabled,expires_at,device_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(secrets.token_hex(8),reseller_id or None,name.strip(),username.strip(),phash(password),1,exp,'',now()));c.commit()
    except Exception:c.rollback();c.close();raise HTTPException(409,'Usuário já existe')
    c.close();return redir('/base2/painel/clientes')
@app.post('/base2/painel/clientes/{cid}/toggle')
def client_toggle(req:Request,cid:str):
    adm(req);c=v5.db();x=v5.one(c,'SELECT * FROM base2_clients WHERE id=?',(cid,));
    if not x:c.close();raise HTTPException(404)
    en=0 if x['enabled'] else 1;v5.ex(c,'UPDATE base2_clients SET enabled=? WHERE id=?',(en,cid));v5.ex(c,'DELETE FROM base2_tokens WHERE client_id=?',(cid,));c.commit();c.close();return redir('/base2/painel/clientes')
@app.post('/base2/painel/clientes/{cid}/reset-device')
def reset_device(req:Request,cid:str):
    adm(req);c=v5.db();v5.ex(c,'UPDATE base2_clients SET device_id=? WHERE id=?',('',cid));v5.ex(c,'DELETE FROM base2_tokens WHERE client_id=?',(cid,));c.commit();c.close();return redir('/base2/painel/clientes')
@app.post('/base2/painel/clientes/{cid}/renovar')
def renew(req:Request,cid:str,days:int=Form(30)):
    adm(req);c=v5.db();x=v5.one(c,'SELECT * FROM base2_clients WHERE id=?',(cid,));
    if not x:c.close();raise HTTPException(404)
    base=datetime.now(timezone.utc)
    try:
        old=datetime.fromisoformat((x['expires_at'] or '').replace('Z','+00:00'))
        if old>base:base=old
    except:pass
    exp=(base+timedelta(days=max(1,days))).isoformat();v5.ex(c,'UPDATE base2_clients SET enabled=1,expires_at=? WHERE id=?',(exp,cid));c.commit();c.close();return redir('/base2/painel/clientes')

@app.post('/base2/api/login')
async def api_login(req:Request):
    try:d=await req.json()
    except:return JSONResponse({'ok':False,'error':'invalid_json'},400)
    u=str(d.get('username') or '').strip();p=str(d.get('password') or '');device=str(d.get('device_id') or '').strip()
    if not u or not p or not device:return JSONResponse({'ok':False,'error':'missing_fields'},400)
    c=v5.db();x=v5.one(c,'SELECT c.*,r.enabled reseller_enabled FROM base2_clients c LEFT JOIN base2_resellers r ON r.id=c.reseller_id WHERE lower(c.username)=lower(?)',(u,))
    if not x or not pcheck(p,x['password_hash']):c.close();return JSONResponse({'ok':False,'error':'invalid_credentials'},401)
    if not x['enabled'] or (x.get('reseller_id') and x.get('reseller_enabled')==0):c.close();return JSONResponse({'ok':False,'error':'blocked'},403)
    try:
        if x['expires_at'] and datetime.fromisoformat(x['expires_at'].replace('Z','+00:00'))<datetime.now(timezone.utc):c.close();return JSONResponse({'ok':False,'error':'expired'},403)
    except:pass
    if x['device_id'] and x['device_id']!=device:c.close();return JSONResponse({'ok':False,'error':'device_in_use'},403)
    if not x['device_id']:v5.ex(c,'UPDATE base2_clients SET device_id=? WHERE id=?',(device,x['id']))
    token=secrets.token_urlsafe(40);th=hashlib.sha256(token.encode()).hexdigest();exp=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat();v5.ex(c,'DELETE FROM base2_tokens WHERE client_id=?',(x['id'],));v5.ex(c,'INSERT INTO base2_tokens(token_hash,client_id,device_id,expires_at,created_at) VALUES(?,?,?,?,?)',(th,x['id'],device,exp,now()));c.commit();c.close()
    return {'ok':True,'token':token,'package_name':BASE2_PACKAGE,'app_name':'Tudo Liberado','expires_at':x['expires_at']}
@app.post('/base2/api/check')
async def api_check(req:Request):
    try:d=await req.json()
    except:return JSONResponse({'ok':False},400)
    token=str(d.get('token') or '');device=str(d.get('device_id') or '');th=hashlib.sha256(token.encode()).hexdigest();c=v5.db();s=v5.one(c,'SELECT t.*,c.enabled,c.expires_at,c.device_id FROM base2_tokens t JOIN base2_clients c ON c.id=t.client_id WHERE t.token_hash=?',(th,))
    if not s or s['device_id']!=device or not s['enabled']:c.close();return JSONResponse({'ok':False},401)
    try:
        if datetime.fromisoformat(s['expires_at'].replace('Z','+00:00'))<datetime.now(timezone.utc):c.close();return JSONResponse({'ok':False,'error':'expired'},403)
        if datetime.fromisoformat(s['expires_at'].replace('Z','+00:00'))<datetime.now(timezone.utc):c.close();return JSONResponse({'ok':False},401)
    except:pass
    c.close();return {'ok':True,'package_name':BASE2_PACKAGE}
