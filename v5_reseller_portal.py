import hashlib,hmac,html,secrets
from datetime import datetime,timezone,timedelta
from typing import Optional
from fastapi import Form,Request,HTTPException
from fastapi.responses import HTMLResponse,RedirectResponse
import v5_layout_roles as base
import v5

app=base.app

def now(): return datetime.now(timezone.utc).isoformat()
def esc(x): return html.escape(str(x or ''))
def redir(p): return RedirectResponse(p,303)

def phash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    dk=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),180000)
    return f'pbkdf2_sha256$180000${salt}${dk.hex()}'
def pcheck(password,encoded):
    try:
        algo,rounds,salt,digest=encoded.split('$',3)
        dk=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(rounds))
        return algo=='pbkdf2_sha256' and hmac.compare_digest(dk.hex(),digest)
    except: return False

def init_tables():
    c=v5.db()
    for s in [
      "CREATE TABLE IF NOT EXISTS reseller_accounts(id TEXT PRIMARY KEY,parent_id TEXT,name TEXT NOT NULL,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,can_create_resellers INTEGER NOT NULL DEFAULT 1,max_clients INTEGER NOT NULL DEFAULT 50,max_resellers INTEGER NOT NULL DEFAULT 10,created_at TEXT)",
      "CREATE TABLE IF NOT EXISTS reseller_sessions(id TEXT PRIMARY KEY,reseller_id TEXT NOT NULL,token_hash TEXT UNIQUE NOT NULL,created_at TEXT,last_seen TEXT,expires_at TEXT,ip TEXT NOT NULL DEFAULT '',user_agent TEXT NOT NULL DEFAULT '')",
      "CREATE TABLE IF NOT EXISTS reseller_clients(id TEXT PRIMARY KEY,reseller_id TEXT NOT NULL,name TEXT NOT NULL,activation_key TEXT UNIQUE NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,days INTEGER NOT NULL DEFAULT 30,expires_at TEXT,notes TEXT NOT NULL DEFAULT '',created_at TEXT)"
    ]: v5.ex(c,s)
    c.commit();c.close()
init_tables()

_old_nav=v5.nav
def nav(k):
    return _old_nav(k).replace('</div>',f'<a href="/admin/reseller-accounts?key={k}">Painel Revenda</a></div>',1)
v5.nav=nav

def token_from(req): return req.cookies.get('bbl_reseller_session','')
def account(req):
    t=token_from(req)
    if not t:return None
    th=hashlib.sha256(t.encode()).hexdigest();c=v5.db()
    s=v5.one(c,'SELECT * FROM reseller_sessions WHERE token_hash=?',(th,))
    if not s:c.close();return None
    try: expired=datetime.fromisoformat((s.get('expires_at') or '').replace('Z','+00:00'))<datetime.now(timezone.utc)
    except: expired=False
    if expired:
        v5.ex(c,'DELETE FROM reseller_sessions WHERE id=?',(s['id'],));c.commit();c.close();return None
    a=v5.one(c,'SELECT * FROM reseller_accounts WHERE id=? AND enabled=1',(s['reseller_id'],))
    if not a:c.close();return None
    v5.ex(c,'UPDATE reseller_sessions SET last_seen=? WHERE id=?',(now(),s['id']));c.commit();c.close();return a
def require(req):
    a=account(req)
    if not a:raise HTTPException(401,'Sessão inválida')
    return a

def page(title,body,a=None):
    n=''
    if a:n='<div class="nav"><a href="/revenda">Início</a><a href="/revenda/clientes">Clientes finais</a><a href="/revenda/revendas">Revendas</a><a href="/revenda/sair">Sair</a></div>'
    css=v5.CSS+'.login{max-width:520px;margin:70px auto}.tag{display:inline-block;padding:5px 9px;border-radius:14px;background:#183a64}.stat{font-size:30px;font-weight:700}'
    return HTMLResponse(f'<!doctype html><meta name="viewport" content="width=device-width"><title>{esc(title)}</title><style>{css}</style><div class="top">BBL.BOXTV • REVENDA</div><div class="wrap"><h1>{esc(title)}</h1>{n}{body}</div>')

@app.get('/revenda/login',response_class=HTMLResponse)
def login_page(erro:str=''):
    e=f'<div class="card bad">{esc(erro)}</div>' if erro else ''
    b=f'<div class="login card"><h2>Acesso da revenda</h2>{e}<form method="post" action="/revenda/login"><input name="username" placeholder="Usuário" required><input type="password" name="password" placeholder="Senha" required><button class="wide">ENTRAR</button></form></div>'
    return page('Painel de Revenda',b)

@app.post('/revenda/login')
def login(req:Request,username:str=Form(...),password:str=Form(...)):
    c=v5.db();a=v5.one(c,'SELECT * FROM reseller_accounts WHERE lower(username)=lower(?) AND enabled=1',(username.strip(),))
    if not a or not pcheck(password,a['password_hash']):c.close();return redir('/revenda/login?erro=Usuário+ou+senha+inválidos')
    s=v5.one(c,'SELECT * FROM reseller_sessions WHERE reseller_id=? ORDER BY created_at DESC',(a['id'],))
    if s:
        try: expired=datetime.fromisoformat((s.get('expires_at') or '').replace('Z','+00:00'))<datetime.now(timezone.utc)
        except: expired=False
        if not expired:c.close();return redir('/revenda/login?erro=Este+acesso+já+está+em+uso')
        v5.ex(c,'DELETE FROM reseller_sessions WHERE reseller_id=?',(a['id'],))
    t=secrets.token_urlsafe(40);th=hashlib.sha256(t.encode()).hexdigest();exp=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()
    ip=req.client.host if req.client else '';ua=req.headers.get('user-agent','')[:250]
    v5.ex(c,'INSERT INTO reseller_sessions(id,reseller_id,token_hash,created_at,last_seen,expires_at,ip,user_agent) VALUES(?,?,?,?,?,?,?,?)',(secrets.token_hex(12),a['id'],th,now(),now(),exp,ip,ua));c.commit();c.close()
    r=redir('/revenda');r.set_cookie('bbl_reseller_session',t,httponly=True,secure=True,samesite='lax',max_age=43200);return r

@app.get('/revenda/sair')
def logout(req:Request):
    t=token_from(req)
    if t:
        c=v5.db();v5.ex(c,'DELETE FROM reseller_sessions WHERE token_hash=?',(hashlib.sha256(t.encode()).hexdigest(),));c.commit();c.close()
    r=redir('/revenda/login');r.delete_cookie('bbl_reseller_session');return r

@app.get('/revenda',response_class=HTMLResponse)
def home(req:Request):
    a=account(req)
    if not a:return redir('/revenda/login')
    c=v5.db();nc=v5.one(c,'SELECT COUNT(*) n FROM reseller_clients WHERE reseller_id=?',(a['id'],))['n'];na=v5.one(c,'SELECT COUNT(*) n FROM reseller_clients WHERE reseller_id=? AND enabled=1',(a['id'],))['n'];nr=v5.one(c,'SELECT COUNT(*) n FROM reseller_accounts WHERE parent_id=?',(a['id'],))['n'];c.close()
    b=f'<div class="hero"><b>{esc(a["name"])}</b><p class="muted">Uma sessão ativa por senha.</p></div><div class="grid"><div class="card"><div class="stat">{nc}</div>Clientes finais<br><span class="muted">Limite {a["max_clients"]}</span></div><div class="card"><div class="stat">{na}</div>Clientes ativos</div><div class="card"><div class="stat">{nr}</div>Revendas<br><span class="muted">Limite {a["max_resellers"]}</span></div></div>'
    return page('Início',b,a)

@app.get('/revenda/clientes',response_class=HTMLResponse)
def clients(req:Request):
    a=account(req)
    if not a:return redir('/revenda/login')
    c=v5.db();cc=v5.rows(c,'SELECT * FROM reseller_clients WHERE reseller_id=? ORDER BY created_at DESC',(a['id'],));c.close()
    cards=''
    for x in cc:
        state='ATIVO' if x['enabled'] else 'BLOQUEADO';action='Bloquear' if x['enabled'] else 'Desbloquear'
        cards+=f'<div class="card"><b>{esc(x["name"])}</b> <span class="tag">{state}</span><br><span class="muted">Código: {esc(x["activation_key"])} • {x["days"]} dias</span><br><br><form method="post" action="/revenda/clientes/{x["id"]}/toggle" style="display:inline"><button>{action}</button></form> <form method="post" action="/revenda/clientes/{x["id"]}/renovar" style="display:inline"><button class="good">Renovar</button></form></div>'
    if not cards:cards='<div class="card muted">Nenhum cliente final.</div>'
    b=f'<div class="card"><h3>Criar cliente final</h3><form method="post" action="/revenda/clientes/criar"><input name="name" placeholder="Nome do cliente" required><input name="days" type="number" min="1" value="30"><input name="notes" placeholder="Observação"><button>CRIAR CLIENTE</button></form></div><div class="grid">{cards}</div>'
    return page('Clientes finais',b,a)

@app.post('/revenda/clientes/criar')
def client_create(req:Request,name:str=Form(...),days:int=Form(30),notes:str=Form('')):
    a=require(req);c=v5.db();n=v5.one(c,'SELECT COUNT(*) n FROM reseller_clients WHERE reseller_id=?',(a['id'],))['n']
    if n>=int(a['max_clients']):c.close();raise HTTPException(403,'Limite de clientes atingido')
    code='BBL-'+secrets.token_hex(4).upper();cid=secrets.token_hex(8);days=max(1,min(int(days),3650));exp=(datetime.now(timezone.utc)+timedelta(days=days)).isoformat()
    v5.ex(c,'INSERT INTO reseller_clients(id,reseller_id,name,activation_key,enabled,days,expires_at,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(cid,a['id'],name.strip(),code,1,days,exp,notes.strip(),now()))
    v5.ex(c,'INSERT INTO activation_keys(key,enabled,label,created_at) VALUES(?,?,?,?)',(code,1,'Cliente '+name.strip()+' • Revenda '+a['name'],now()));c.commit();c.close();return redir('/revenda/clientes')

@app.post('/revenda/clientes/{cid}/toggle')
def client_toggle(req:Request,cid:str):
    a=require(req);c=v5.db();x=v5.one(c,'SELECT * FROM reseller_clients WHERE id=? AND reseller_id=?',(cid,a['id']))
    if not x:c.close();raise HTTPException(404)
    en=0 if x['enabled'] else 1;v5.ex(c,'UPDATE reseller_clients SET enabled=? WHERE id=?',(en,cid));v5.ex(c,'UPDATE activation_keys SET enabled=? WHERE key=?',(en,x['activation_key']));v5.ex(c,'UPDATE devices SET locked=? WHERE activation_key=?',(0 if en else 1,x['activation_key']));c.commit();c.close();return redir('/revenda/clientes')

@app.post('/revenda/clientes/{cid}/renovar')
def client_renew(req:Request,cid:str):
    a=require(req);c=v5.db();x=v5.one(c,'SELECT * FROM reseller_clients WHERE id=? AND reseller_id=?',(cid,a['id']))
    if not x:c.close();raise HTTPException(404)
    exp=(datetime.now(timezone.utc)+timedelta(days=int(x['days']))).isoformat();v5.ex(c,'UPDATE reseller_clients SET enabled=1,expires_at=? WHERE id=?',(exp,cid));v5.ex(c,'UPDATE activation_keys SET enabled=1 WHERE key=?',(x['activation_key'],));v5.ex(c,'UPDATE devices SET locked=0,expires_at=? WHERE activation_key=?',(exp,x['activation_key']));c.commit();c.close();return redir('/revenda/clientes')

@app.get('/revenda/revendas',response_class=HTMLResponse)
def children(req:Request):
    a=account(req)
    if not a:return redir('/revenda/login')
    c=v5.db();rr=v5.rows(c,'SELECT * FROM reseller_accounts WHERE parent_id=? ORDER BY created_at DESC',(a['id'],));c.close()
    cards=''
    for x in rr:
        state='ATIVA' if x['enabled'] else 'BLOQUEADA';action='Bloquear' if x['enabled'] else 'Desbloquear'
        cards+=f'<div class="card"><b>{esc(x["name"])}</b> <span class="tag">{state}</span><br><span class="muted">Usuário: {esc(x["username"])} • Clientes {x["max_clients"]} • Revendas {x["max_resellers"]}</span><br><br><form method="post" action="/revenda/revendas/{x["id"]}/toggle"><button>{action}</button></form></div>'
    if not cards:cards='<div class="card muted">Nenhuma revenda.</div>'
    create=''
    if a['can_create_resellers']:create='<div class="card"><h3>Criar revenda</h3><form method="post" action="/revenda/revendas/criar"><input name="name" placeholder="Nome" required><input name="username" placeholder="Usuário" required><input type="password" name="password" placeholder="Senha" minlength="4" required><input type="number" name="max_clients" value="30" min="1"><input type="number" name="max_resellers" value="5" min="0"><button>CRIAR REVENDA</button></form></div>'
    return page('Revendas',create+'<div class="grid">'+cards+'</div>',a)

@app.post('/revenda/revendas/criar')
def child_create(req:Request,name:str=Form(...),username:str=Form(...),password:str=Form(...),max_clients:int=Form(30),max_resellers:int=Form(5)):
    a=require(req)
    if not a['can_create_resellers']:raise HTTPException(403,'Sem permissão')
    c=v5.db();n=v5.one(c,'SELECT COUNT(*) n FROM reseller_accounts WHERE parent_id=?',(a['id'],))['n']
    if n>=int(a['max_resellers']):c.close();raise HTTPException(403,'Limite de revendas atingido')
    try:v5.ex(c,'INSERT INTO reseller_accounts(id,parent_id,name,username,password_hash,enabled,can_create_resellers,max_clients,max_resellers,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(secrets.token_hex(8),a['id'],name.strip(),username.strip(),phash(password),1,1,max(1,max_clients),max(0,max_resellers),now()));c.commit()
    except Exception:c.rollback();c.close();raise HTTPException(409,'Usuário já existe')
    c.close();return redir('/revenda/revendas')

@app.post('/revenda/revendas/{rid}/toggle')
def child_toggle(req:Request,rid:str):
    a=require(req);c=v5.db();x=v5.one(c,'SELECT * FROM reseller_accounts WHERE id=? AND parent_id=?',(rid,a['id']))
    if not x:c.close();raise HTTPException(404)
    en=0 if x['enabled'] else 1;v5.ex(c,'UPDATE reseller_accounts SET enabled=? WHERE id=?',(en,rid))
    if not en:v5.ex(c,'DELETE FROM reseller_sessions WHERE reseller_id=?',(rid,))
    c.commit();c.close();return redir('/revenda/revendas')

@app.get('/admin/reseller-accounts',response_class=HTMLResponse)
def admin_accounts(key:str=''):
    v5.adm(key);c=v5.db();rr=v5.rows(c,'SELECT * FROM reseller_accounts WHERE parent_id IS NULL ORDER BY created_at DESC');c.close();cards=''
    for x in rr:
        state='ATIVA' if x['enabled'] else 'BLOQUEADA';action='Bloquear' if x['enabled'] else 'Desbloquear'
        cards+=f'<div class="card"><b>{esc(x["name"])}</b> • {esc(x["username"])}<br><span class="muted">{state} • clientes {x["max_clients"]} • sub-revendas {x["max_resellers"]}</span><br><br><form method="post" action="/admin/reseller-accounts/{x["id"]}/toggle?key={key}" style="display:inline"><button>{action}</button></form> <form method="post" action="/admin/reseller-accounts/{x["id"]}/logout?key={key}" style="display:inline"><button class="danger">Encerrar acesso</button></form></div>'
    if not cards:cards='<div class="card muted">Nenhuma revenda principal.</div>'
    b=f'<div class="hero"><b>Painel de revenda</b><p class="muted">Cada usuário/senha libera somente uma sessão ativa por vez.</p></div><div class="card"><h3>Criar revenda principal</h3><form method="post" action="/admin/reseller-accounts/create?key={key}"><input name="name" placeholder="Nome da revenda" required><input name="username" placeholder="Usuário" required><input type="password" name="password" placeholder="Senha" minlength="4" required><input name="max_clients" type="number" value="50" min="1"><input name="max_resellers" type="number" value="10" min="0"><button>CRIAR REVENDA</button></form></div><div class="grid">{cards}</div><div class="card"><b>Login das revendas:</b> /revenda/login</div>'
    return v5.page('Painel Revenda',b,key)

@app.post('/admin/reseller-accounts/create')
def admin_create(key:str,name:str=Form(...),username:str=Form(...),password:str=Form(...),max_clients:int=Form(50),max_resellers:int=Form(10)):
    v5.adm(key);c=v5.db()
    try:v5.ex(c,'INSERT INTO reseller_accounts(id,parent_id,name,username,password_hash,enabled,can_create_resellers,max_clients,max_resellers,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(secrets.token_hex(8),None,name.strip(),username.strip(),phash(password),1,1,max(1,max_clients),max(0,max_resellers),now()));c.commit()
    except Exception:c.rollback();c.close();raise HTTPException(409,'Usuário já existe')
    c.close();return v5.go('/admin/reseller-accounts',key)

@app.post('/admin/reseller-accounts/{rid}/toggle')
def admin_toggle(rid:str,key:str):
    v5.adm(key);c=v5.db();x=v5.one(c,'SELECT * FROM reseller_accounts WHERE id=?',(rid,))
    if not x:c.close();raise HTTPException(404)
    en=0 if x['enabled'] else 1;v5.ex(c,'UPDATE reseller_accounts SET enabled=? WHERE id=?',(en,rid))
    if not en:v5.ex(c,'DELETE FROM reseller_sessions WHERE reseller_id=?',(rid,))
    c.commit();c.close();return v5.go('/admin/reseller-accounts',key)

@app.post('/admin/reseller-accounts/{rid}/logout')
def admin_logout(rid:str,key:str):
    v5.adm(key);c=v5.db();v5.ex(c,'DELETE FROM reseller_sessions WHERE reseller_id=?',(rid,));c.commit();c.close();return v5.go('/admin/reseller-accounts',key)
