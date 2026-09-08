import secrets, html
from datetime import datetime, timezone, timedelta
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import v5
import v5_base2_gate as gate
import v5_base2_reseller_portal as reseller

app = v5.app

def esc(x): return html.escape(str(x or ''))
def redir(p): return RedirectResponse(p,303)
def now(): return datetime.now(timezone.utc).isoformat()

def _admin(req):
    if not gate.admin_ok(req):
        raise HTTPException(401,'Acesso administrativo inválido')

def _reseller(req):
    r=reseller.session_reseller(req)
    if not r: raise HTTPException(401,'Acesso da revenda inválido')
    return r

def _delete_client(c,cid):
    v5.ex(c,'DELETE FROM base2_tokens WHERE client_id=?',(cid,))
    v5.ex(c,'DELETE FROM base2_clients WHERE id=?',(cid,))

def _delete_reseller_tree(c,rid):
    children=v5.rows(c,'SELECT id FROM base2_resellers WHERE parent_id=?',(rid,))
    for ch in children: _delete_reseller_tree(c,ch['id'])
    clients=v5.rows(c,'SELECT id FROM base2_clients WHERE reseller_id=?',(rid,))
    for cl in clients: _delete_client(c,cl['id'])
    v5.ex(c,'DELETE FROM base2_reseller_sessions WHERE reseller_id=?',(rid,))
    v5.ex(c,'DELETE FROM base2_resellers WHERE id=?',(rid,))

def _test_form(action, reseller_select=''):
    return f'''<div class="card"><h3>Criar teste</h3><div class="muted">Teste padrão de 1 dia. Você pode escolher mais dias.</div><form method="post" action="{action}"><input name="name" placeholder="Nome do teste" required><input name="username" placeholder="Usuário" required><input name="password" type="password" placeholder="Senha" minlength="4" required>{reseller_select}<input name="days" type="number" value="1" min="1"><button class="good">CRIAR TESTE</button></form></div>'''

def _admin_page(title, body):
    nav='<div class="nav"><a href="/base2/painel">Início</a><a href="/base2/painel/revendas">Revendas</a><a href="/base2/painel/clientes">Clientes</a><a href="/base2/painel/gerenciar">Testes / Excluir</a><a href="/base2/painel/sair">Sair</a></div>'
    return HTMLResponse(f'<!doctype html><meta name="viewport" content="width=device-width"><title>{esc(title)}</title><style>{gate.style()}</style><div class="top">TUDO LIBERADO • PAINEL BASE 2</div><div class="wrap"><h1>{esc(title)}</h1>{nav}{body}</div>')

def _reseller_page(title, body):
    nav='<div class="nav"><a href="/base2/revenda">Início</a><a href="/base2/revenda/clientes">Clientes</a><a href="/base2/revenda/revendas">Sub-revendas</a><a href="/base2/revenda/gerenciar">Testes / Excluir</a><a href="/base2/revenda/sair">Sair</a></div>'
    return HTMLResponse(f'<!doctype html><meta name="viewport" content="width=device-width"><title>{esc(title)}</title><style>{reseller.style()}</style><div class="top">TUDO LIBERADO • PAINEL DE REVENDA</div><div class="wrap"><h1>{esc(title)}</h1>{nav}{body}</div>')

# Acrescenta o novo item à navegação das páginas antigas sem reescrever os módulos existentes.
_old_admin_page=gate.page
def _patched_admin_page(title,body,nav=True):
    r=_old_admin_page(title,body,nav)
    if nav and isinstance(r,HTMLResponse):
        txt=r.body.decode('utf-8').replace('<a href="/base2/painel/sair">Sair</a>','<a href="/base2/painel/gerenciar">Testes / Excluir</a><a href="/base2/painel/sair">Sair</a>')
        return HTMLResponse(txt,status_code=r.status_code)
    return r
gate.page=_patched_admin_page

_old_reseller_page=reseller.page
def _patched_reseller_page(title,body,nav=True):
    r=_old_reseller_page(title,body,nav)
    if nav and isinstance(r,HTMLResponse):
        txt=r.body.decode('utf-8').replace('<a href="/base2/revenda/sair">Sair</a>','<a href="/base2/revenda/gerenciar">Testes / Excluir</a><a href="/base2/revenda/sair">Sair</a>')
        return HTMLResponse(txt,status_code=r.status_code)
    return r
reseller.page=_patched_reseller_page

@app.get('/base2/painel/gerenciar')
def admin_manage(req:Request):
    if not gate.admin_ok(req): return redir('/base2/painel/login')
    c=v5.db(); rs=v5.rows(c,'SELECT * FROM base2_resellers ORDER BY created_at DESC'); cs=v5.rows(c,'SELECT c.*,r.name reseller_name FROM base2_clients c LEFT JOIN base2_resellers r ON r.id=c.reseller_id ORDER BY c.created_at DESC'); c.close()
    opts='<select name="reseller_id"><option value="">ADMIN</option>'+''.join(f'<option value="{x["id"]}">{esc(x["name"])}</option>' for x in rs)+'</select>'
    body=_test_form('/base2/painel/testes/criar',opts)
    body+='<h2>Clientes e testes</h2><div class="grid">'
    for x in cs:
        label='TESTE' if str(x['name']).startswith('TESTE - ') else 'CLIENTE'
        body+=f'<div class="card"><b>{label}: {esc(x["name"])}</b><br>{esc(x["username"])}<br><span class="muted">Revenda: {esc(x.get("reseller_name") or "ADMIN")} • Vence: {esc(x["expires_at"])}</span><form method="post" action="/base2/painel/clientes/{x["id"]}/excluir" onsubmit="return confirm(\'Excluir definitivamente este cliente/teste?\')"><button class="danger">EXCLUIR</button></form></div>'
    body+='</div><h2>Revendas</h2><div class="grid">'
    for x in rs:
        body+=f'<div class="card"><b>{esc(x["name"])}</b> • {esc(x["username"])}<form method="post" action="/base2/painel/revendas/{x["id"]}/excluir" onsubmit="return confirm(\'Excluir esta revenda e também todos os clientes e sub-revendas dela?\')"><button class="danger">EXCLUIR REVENDA</button></form></div>'
    body+='</div>'
    return _admin_page('Testes e exclusões',body)

@app.post('/base2/painel/testes/criar')
def admin_create_test(req:Request,name:str=Form(...),username:str=Form(...),password:str=Form(...),reseller_id:str=Form(''),days:int=Form(1)):
    _admin(req); c=v5.db(); exp=(datetime.now(timezone.utc)+timedelta(days=max(1,days))).isoformat()
    try:
        v5.ex(c,'INSERT INTO base2_clients(id,reseller_id,name,username,password_hash,enabled,expires_at,device_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(secrets.token_hex(8),reseller_id or None,'TESTE - '+name.strip(),username.strip(),gate.phash(password),1,exp,'',now())); c.commit()
    except Exception:
        c.rollback(); c.close(); raise HTTPException(409,'Usuário já existe')
    c.close(); return redir('/base2/painel/gerenciar')

@app.post('/base2/painel/clientes/{cid}/excluir')
def admin_delete_client(req:Request,cid:str):
    _admin(req); c=v5.db(); _delete_client(c,cid); c.commit(); c.close(); return redir('/base2/painel/gerenciar')

@app.post('/base2/painel/revendas/{rid}/excluir')
def admin_delete_reseller(req:Request,rid:str):
    _admin(req); c=v5.db(); _delete_reseller_tree(c,rid); c.commit(); c.close(); return redir('/base2/painel/gerenciar')

@app.get('/base2/revenda/gerenciar')
def reseller_manage(req:Request):
    r=reseller.session_reseller(req)
    if not r: return redir('/base2/revenda/login')
    c=v5.db(); cs=v5.rows(c,'SELECT * FROM base2_clients WHERE reseller_id=? ORDER BY created_at DESC',(r['id'],)); subs=v5.rows(c,'SELECT * FROM base2_resellers WHERE parent_id=? ORDER BY created_at DESC',(r['id'],)); c.close()
    body=_test_form('/base2/revenda/testes/criar')
    body+='<h2>Clientes e testes</h2><div class="grid">'
    for x in cs:
        label='TESTE' if str(x['name']).startswith('TESTE - ') else 'CLIENTE'
        body+=f'<div class="card"><b>{label}: {esc(x["name"])}</b><br>{esc(x["username"])}<br><span class="muted">Vence: {esc(x["expires_at"])}</span><form method="post" action="/base2/revenda/clientes/{x["id"]}/excluir" onsubmit="return confirm(\'Excluir definitivamente este cliente/teste?\')"><button class="danger">EXCLUIR</button></form></div>'
    body+='</div><h2>Sub-revendas</h2><div class="grid">'
    for x in subs:
        body+=f'<div class="card"><b>{esc(x["name"])}</b> • {esc(x["username"])}<form method="post" action="/base2/revenda/revendas/{x["id"]}/excluir" onsubmit="return confirm(\'Excluir esta sub-revenda e todos os dados dela?\')"><button class="danger">EXCLUIR SUB-REVENDA</button></form></div>'
    body+='</div>'
    return _reseller_page('Testes e exclusões',body)

@app.post('/base2/revenda/testes/criar')
def reseller_create_test(req:Request,name:str=Form(...),username:str=Form(...),password:str=Form(...),days:int=Form(1)):
    r=_reseller(req); c=v5.db(); count=v5.one(c,'SELECT COUNT(*) n FROM base2_clients WHERE reseller_id=?',(r['id'],))['n']
    if count>=int(r['max_clients']): c.close(); raise HTTPException(403,'Limite de clientes atingido')
    exp=(datetime.now(timezone.utc)+timedelta(days=max(1,days))).isoformat()
    try:
        v5.ex(c,'INSERT INTO base2_clients(id,reseller_id,name,username,password_hash,enabled,expires_at,device_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(secrets.token_hex(8),r['id'],'TESTE - '+name.strip(),username.strip(),reseller.phash(password),1,exp,'',now())); c.commit()
    except Exception:
        c.rollback(); c.close(); raise HTTPException(409,'Usuário já existe')
    c.close(); return redir('/base2/revenda/gerenciar')

@app.post('/base2/revenda/clientes/{cid}/excluir')
def reseller_delete_client(req:Request,cid:str):
    r=_reseller(req); c=v5.db(); x=v5.one(c,'SELECT id FROM base2_clients WHERE id=? AND reseller_id=?',(cid,r['id']))
    if not x: c.close(); raise HTTPException(404)
    _delete_client(c,cid); c.commit(); c.close(); return redir('/base2/revenda/gerenciar')

@app.post('/base2/revenda/revendas/{rid}/excluir')
def reseller_delete_sub(req:Request,rid:str):
    r=_reseller(req); c=v5.db(); x=v5.one(c,'SELECT id FROM base2_resellers WHERE id=? AND parent_id=?',(rid,r['id']))
    if not x: c.close(); raise HTTPException(404)
    _delete_reseller_tree(c,rid); c.commit(); c.close(); return redir('/base2/revenda/gerenciar')
