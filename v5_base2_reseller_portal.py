import secrets, hashlib, html
from datetime import datetime, timezone, timedelta
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import v5

app = v5.app

def now():
    return datetime.now(timezone.utc).isoformat()

def esc(x):
    return html.escape(str(x or ''))

def pcheck(password, encoded):
    try:
        algo, rounds, salt, digest = encoded.split('$', 3)
        calc = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return algo == 'pbkdf2_sha256' and secrets.compare_digest(calc, digest)
    except Exception:
        return False

def phash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 180000).hex()
    return f'pbkdf2_sha256$180000${salt}${digest}'

def redir(path):
    return RedirectResponse(path, 303)

def style():
    return '''body{margin:0;background:#07111f;color:#fff;font-family:Arial,sans-serif}.top{background:#0b2037;padding:18px 28px;font-weight:800;font-size:22px}.wrap{max-width:1200px;margin:auto;padding:24px}.card{background:#10253d;border:1px solid #24496e;border-radius:16px;padding:18px;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.muted{color:#9db1c7}input,select{width:100%;box-sizing:border-box;padding:13px;margin:7px 0;border-radius:10px;border:1px solid #315a80;background:#081a2c;color:white}button,.btn{display:inline-block;background:#1677ff;color:#fff;border:0;border-radius:10px;padding:11px 15px;margin:4px;text-decoration:none;font-weight:700}.danger{background:#d43838}.good{background:#16875b}.nav a{color:#fff;margin-right:16px;text-decoration:none}.tag{padding:4px 9px;border-radius:12px;background:#173e67}.login{max-width:480px;margin:70px auto}.stat{font-size:30px;font-weight:800}'''

def page(title, body, nav=True):
    nav_html = ''
    if nav:
        nav_html = '<div class="nav"><a href="/base2/revenda">Início</a><a href="/base2/revenda/clientes">Clientes</a><a href="/base2/revenda/revendas">Sub-revendas</a><a href="/base2/revenda/sair">Sair</a></div>'
    return HTMLResponse(f'<!doctype html><meta name="viewport" content="width=device-width"><title>{esc(title)}</title><style>{style()}</style><div class="top">TUDO LIBERADO • PAINEL DE REVENDA</div><div class="wrap"><h1>{esc(title)}</h1>{nav_html}{body}</div>')

def session_reseller(req):
    token = (req.cookies.get('base2_reseller') or '').strip()
    if not token:
        return None
    th = hashlib.sha256(token.encode()).hexdigest()
    c = v5.db()
    s = v5.one(c, 'SELECT s.*,r.* FROM base2_reseller_sessions s JOIN base2_resellers r ON r.id=s.reseller_id WHERE s.token_hash=?', (th,))
    if not s:
        c.close(); return None
    try:
        if datetime.fromisoformat(s['expires_at'].replace('Z','+00:00')) < datetime.now(timezone.utc):
            v5.ex(c, 'DELETE FROM base2_reseller_sessions WHERE token_hash=?', (th,)); c.commit(); c.close(); return None
    except Exception:
        pass
    if not s['enabled']:
        c.close(); return None
    c.close()
    return s

def require_reseller(req):
    r = session_reseller(req)
    if not r:
        raise HTTPException(401, 'Acesso da revenda inválido')
    return r

@app.get('/base2/revenda/login')
def reseller_login_page(erro: str=''):
    e = f'<div class="card">{esc(erro)}</div>' if erro else ''
    return page('Acesso da revenda', f'<div class="login card">{e}<form method="post"><input name="username" placeholder="Usuário" required><input name="password" type="password" placeholder="Senha" required><button>ENTRAR</button></form></div>', False)

@app.post('/base2/revenda/login')
def reseller_login(username: str=Form(...), password: str=Form(...)):
    c = v5.db()
    r = v5.one(c, 'SELECT * FROM base2_resellers WHERE lower(username)=lower(?)', (username.strip(),))
    if not r or not r['enabled'] or not pcheck(password, r['password_hash']):
        c.close(); return redir('/base2/revenda/login?erro=Acesso+inválido')
    token = secrets.token_urlsafe(40)
    th = hashlib.sha256(token.encode()).hexdigest()
    exp = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    v5.ex(c, 'DELETE FROM base2_reseller_sessions WHERE reseller_id=?', (r['id'],))
    v5.ex(c, 'INSERT INTO base2_reseller_sessions(token_hash,reseller_id,expires_at,created_at) VALUES(?,?,?,?)', (th,r['id'],exp,now()))
    c.commit(); c.close()
    resp = redir('/base2/revenda')
    resp.set_cookie('base2_reseller', token, httponly=True, secure=True, samesite='lax', max_age=2592000)
    return resp

@app.get('/base2/revenda/sair')
def reseller_logout(req: Request):
    token = (req.cookies.get('base2_reseller') or '').strip()
    if token:
        c=v5.db(); v5.ex(c,'DELETE FROM base2_reseller_sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)); c.commit(); c.close()
    r = redir('/base2/revenda/login'); r.delete_cookie('base2_reseller'); return r

@app.get('/base2/revenda')
def reseller_dashboard(req: Request):
    r = session_reseller(req)
    if not r: return redir('/base2/revenda/login')
    c=v5.db()
    clients=v5.one(c,'SELECT COUNT(*) n FROM base2_clients WHERE reseller_id=?',(r['id'],))['n']
    active=v5.one(c,'SELECT COUNT(*) n FROM base2_clients WHERE reseller_id=? AND enabled=1',(r['id'],))['n']
    subs=v5.one(c,'SELECT COUNT(*) n FROM base2_resellers WHERE parent_id=?',(r['id'],))['n']
    c.close()
    b=f'<div class="card"><b>Revenda:</b> {esc(r["name"])} • {esc(r["username"])} <span class="tag">ATIVA</span></div><div class="grid"><div class="card"><div class="stat">{clients}</div>Clientes / limite {r["max_clients"]}</div><div class="card"><div class="stat">{active}</div>Clientes ativos</div><div class="card"><div class="stat">{subs}</div>Sub-revendas / limite {r["max_resellers"]}</div></div>'
    return page('Painel da Revenda', b)

@app.get('/base2/revenda/clientes')
def reseller_clients(req: Request):
    r=session_reseller(req)
    if not r:return redir('/base2/revenda/login')
    c=v5.db(); rows=v5.rows(c,'SELECT * FROM base2_clients WHERE reseller_id=? ORDER BY created_at DESC',(r['id'],)); count=len(rows); c.close()
    cards=''
    for x in rows:
        cards += f'<div class="card"><b>{esc(x["name"])}</b> • {esc(x["username"])} <span class="tag">{"ATIVO" if x["enabled"] else "BLOQUEADO"}</span><br><span class="muted">Vence: {esc(x["expires_at"] or "sem vencimento")} • Aparelho: {esc(x["device_id"] or "não vinculado")}</span><br><form method="post" action="/base2/revenda/clientes/{x["id"]}/toggle" style="display:inline"><button>{"Bloquear" if x["enabled"] else "Desbloquear"}</button></form><form method="post" action="/base2/revenda/clientes/{x["id"]}/reset-device" style="display:inline"><button>Trocar aparelho</button></form><form method="post" action="/base2/revenda/clientes/{x["id"]}/renovar" style="display:inline"><input type="hidden" name="days" value="30"><button class="good">+30 dias</button></form></div>'
    disabled = 'disabled' if count >= int(r['max_clients']) else ''
    b=f'<div class="card"><h3>Criar cliente final</h3><div class="muted">Usados: {count} de {r["max_clients"]}</div><form method="post" action="/base2/revenda/clientes/criar"><input name="name" placeholder="Nome" required><input name="username" placeholder="Usuário" required><input name="password" type="password" placeholder="Senha" minlength="4" required><input name="days" type="number" value="30" min="1"><button {disabled}>CRIAR CLIENTE</button></form></div><div class="grid">{cards or "<div class=\"card muted\">Nenhum cliente.</div>"}</div>'
    return page('Clientes da Revenda', b)

@app.post('/base2/revenda/clientes/criar')
def reseller_client_create(req:Request,name:str=Form(...),username:str=Form(...),password:str=Form(...),days:int=Form(30)):
    r=require_reseller(req); c=v5.db()
    count=v5.one(c,'SELECT COUNT(*) n FROM base2_clients WHERE reseller_id=?',(r['id'],))['n']
    if count >= int(r['max_clients']): c.close(); raise HTTPException(403,'Limite de clientes atingido')
    exp=(datetime.now(timezone.utc)+timedelta(days=max(1,days))).isoformat()
    try:
        v5.ex(c,'INSERT INTO base2_clients(id,reseller_id,name,username,password_hash,enabled,expires_at,device_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(secrets.token_hex(8),r['id'],name.strip(),username.strip(),phash(password),1,exp,'',now())); c.commit()
    except Exception:
        c.rollback(); c.close(); raise HTTPException(409,'Usuário já existe')
    c.close(); return redir('/base2/revenda/clientes')

def owned_client(c, rid, cid):
    return v5.one(c,'SELECT * FROM base2_clients WHERE id=? AND reseller_id=?',(cid,rid))

@app.post('/base2/revenda/clientes/{cid}/toggle')
def reseller_client_toggle(req:Request,cid:str):
    r=require_reseller(req); c=v5.db(); x=owned_client(c,r['id'],cid)
    if not x:c.close();raise HTTPException(404)
    en=0 if x['enabled'] else 1; v5.ex(c,'UPDATE base2_clients SET enabled=? WHERE id=?',(en,cid)); v5.ex(c,'DELETE FROM base2_tokens WHERE client_id=?',(cid,)); c.commit(); c.close(); return redir('/base2/revenda/clientes')

@app.post('/base2/revenda/clientes/{cid}/reset-device')
def reseller_client_reset(req:Request,cid:str):
    r=require_reseller(req); c=v5.db(); x=owned_client(c,r['id'],cid)
    if not x:c.close();raise HTTPException(404)
    v5.ex(c,'UPDATE base2_clients SET device_id=? WHERE id=?',('',cid)); v5.ex(c,'DELETE FROM base2_tokens WHERE client_id=?',(cid,)); c.commit(); c.close(); return redir('/base2/revenda/clientes')

@app.post('/base2/revenda/clientes/{cid}/renovar')
def reseller_client_renew(req:Request,cid:str,days:int=Form(30)):
    r=require_reseller(req); c=v5.db(); x=owned_client(c,r['id'],cid)
    if not x:c.close();raise HTTPException(404)
    base=datetime.now(timezone.utc)
    try:
        old=datetime.fromisoformat((x['expires_at'] or '').replace('Z','+00:00'))
        if old>base:base=old
    except Exception: pass
    exp=(base+timedelta(days=max(1,days))).isoformat(); v5.ex(c,'UPDATE base2_clients SET enabled=1,expires_at=? WHERE id=?',(exp,cid)); c.commit(); c.close(); return redir('/base2/revenda/clientes')

@app.get('/base2/revenda/revendas')
def reseller_subs(req:Request):
    r=session_reseller(req)
    if not r:return redir('/base2/revenda/login')
    c=v5.db(); rows=v5.rows(c,'SELECT * FROM base2_resellers WHERE parent_id=? ORDER BY created_at DESC',(r['id'],)); count=len(rows); c.close(); cards=''
    for x in rows:
        cards+=f'<div class="card"><b>{esc(x["name"])}</b> • {esc(x["username"])} <span class="tag">{"ATIVA" if x["enabled"] else "BLOQUEADA"}</span><br><span class="muted">Clientes: {x["max_clients"]} • Sub-revendas: {x["max_resellers"]}</span><br><form method="post" action="/base2/revenda/revendas/{x["id"]}/toggle"><button>{"Bloquear" if x["enabled"] else "Desbloquear"}</button></form></div>'
    disabled='disabled' if count>=int(r['max_resellers']) else ''
    b=f'<div class="card"><h3>Criar sub-revenda</h3><div class="muted">Usadas: {count} de {r["max_resellers"]}</div><form method="post" action="/base2/revenda/revendas/criar"><input name="name" placeholder="Nome" required><input name="username" placeholder="Usuário" required><input name="password" type="password" placeholder="Senha" minlength="4" required><input name="max_clients" type="number" value="20" min="1"><input name="max_resellers" type="number" value="0" min="0"><button {disabled}>CRIAR SUB-REVENDA</button></form></div><div class="grid">{cards or "<div class=\"card muted\">Nenhuma sub-revenda.</div>"}</div>'
    return page('Sub-revendas',b)

@app.post('/base2/revenda/revendas/criar')
def reseller_sub_create(req:Request,name:str=Form(...),username:str=Form(...),password:str=Form(...),max_clients:int=Form(20),max_resellers:int=Form(0)):
    r=require_reseller(req); c=v5.db(); count=v5.one(c,'SELECT COUNT(*) n FROM base2_resellers WHERE parent_id=?',(r['id'],))['n']
    if count>=int(r['max_resellers']):c.close();raise HTTPException(403,'Limite de sub-revendas atingido')
    try:
        v5.ex(c,'INSERT INTO base2_resellers(id,parent_id,name,username,password_hash,enabled,max_clients,max_resellers,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(secrets.token_hex(8),r['id'],name.strip(),username.strip(),phash(password),1,max(1,max_clients),max(0,max_resellers),now())); c.commit()
    except Exception:
        c.rollback(); c.close(); raise HTTPException(409,'Usuário já existe')
    c.close(); return redir('/base2/revenda/revendas')

@app.post('/base2/revenda/revendas/{rid}/toggle')
def reseller_sub_toggle(req:Request,rid:str):
    r=require_reseller(req); c=v5.db(); x=v5.one(c,'SELECT * FROM base2_resellers WHERE id=? AND parent_id=?',(rid,r['id']))
    if not x:c.close();raise HTTPException(404)
    en=0 if x['enabled'] else 1; v5.ex(c,'UPDATE base2_resellers SET enabled=? WHERE id=?',(en,rid)); v5.ex(c,'DELETE FROM base2_reseller_sessions WHERE reseller_id=?',(rid,)); c.commit(); c.close(); return redir('/base2/revenda/revendas')
