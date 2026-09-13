import secrets
from datetime import datetime, timezone, timedelta
from fastapi import Request, Form, HTTPException
from fastapi.responses import RedirectResponse
import v5
import v5_base2_gate as gate


def _add_priority_route(path, endpoint, methods):
    v5.app.add_api_route(path, endpoint, methods=methods)
    route = v5.app.router.routes.pop()
    v5.app.router.routes.insert(0, route)


def _esc(x):
    import html
    return html.escape(str(x or ''))


def activation_page(request: Request, key: str, ok: str = '', erro: str = ''):
    v5.adm(key)
    c = v5.db()
    clients = v5.rows(c, 'SELECT id,name,username,enabled,expires_at,device_id,created_at FROM base2_clients ORDER BY created_at DESC LIMIT 100')
    activations = v5.rows(c, 'SELECT key,label,enabled,created_at FROM activation_keys ORDER BY created_at DESC LIMIT 100')
    c.close()
    msg = ''
    if ok:
        msg = f'<div class="card"><span class="ok">{_esc(ok)}</span></div>'
    if erro:
        msg = f'<div class="card"><span class="bad">{_esc(erro)}</span></div>'
    rows = ''.join(
        f'<div class="card"><b>{_esc(x["name"])}</b><br>'
        f'Usuário: <b>{_esc(x["username"])}</b><br>'
        f'Status: {"ATIVO" if x["enabled"] else "BLOQUEADO"}<br>'
        f'Vence: {_esc(x.get("expires_at") or "sem vencimento")}<br>'
        f'Aparelho: {_esc(x.get("device_id") or "não vinculado")}</div>'
        for x in clients
    ) or '<div class="card">Nenhum usuário criado ainda.</div>'
    old = ''.join(
        f'<div class="card"><b>{_esc(x["label"] or "Cliente")}</b><br>Código: <b>{_esc(x["key"])}</b><br>Status: {"ATIVO" if x["enabled"] else "BLOQUEADO"}</div>'
        for x in activations[:20]
    )
    body = msg + f'''
    <div class="card">
      <h3>Criar cliente com usuário e senha</h3>
      <form method="post" action="/admin/activation-keys/create-base2?key={_esc(key)}">
        <input name="name" placeholder="Nome do cliente" required>
        <input name="username" placeholder="Usuário (ex.: BBL0000)" required>
        <input name="password" type="password" placeholder="Senha" minlength="4" required>
        <input name="custom_code" placeholder="Código personalizado (opcional)">
        <input name="days" type="number" value="30" min="1" placeholder="Dias de acesso">
        <button class="good">CRIAR USUÁRIO + SENHA</button>
      </form>
      <div class="muted">Se o código personalizado ficar vazio, o painel gera um código automaticamente. O mesmo cadastro já fica pronto para login no BBL Container.</div>
    </div>
    <h3>Usuários Base 2</h3>
    <div class="grid">{rows}</div>
    <h3>Códigos de ativação</h3>
    <div class="grid">{old}</div>
    '''
    return v5.page('Ativações / Usuários e Senhas', body, key)


def create_base2_user(
    request: Request,
    key: str,
    name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    custom_code: str = Form(''),
    days: int = Form(30),
):
    v5.adm(key)
    name = name.strip()
    username = username.strip()
    password = password.strip()
    if not name or not username or len(password) < 4:
        return RedirectResponse(f'/admin/activation-keys?key={key}&erro=Preencha+nome,+usuário+e+senha', 303)
    code = custom_code.strip().upper() or ('BBL-' + secrets.token_hex(3).upper())
    exp = (datetime.now(timezone.utc) + timedelta(days=max(1, days))).isoformat()
    c = v5.db()
    try:
        if v5.one(c, 'SELECT id FROM base2_clients WHERE lower(username)=lower(?)', (username,)):
            raise HTTPException(409, 'Usuário já existe')
        if v5.one(c, 'SELECT key FROM activation_keys WHERE key=?', (code,)):
            raise HTTPException(409, 'Código de ativação já existe')
        v5.ex(c, 'INSERT INTO base2_clients(id,reseller_id,name,username,password_hash,enabled,expires_at,device_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
              (secrets.token_hex(8), None, name, username, gate.phash(password), 1, exp, '', gate.now()))
        v5.ex(c, 'INSERT INTO activation_keys(key,enabled,label,created_at) VALUES(?,?,?,?)',
              (code, 1, name, v5.now()))
        c.commit()
    except HTTPException:
        c.rollback(); c.close(); raise
    except Exception as e:
        c.rollback(); c.close();
        return RedirectResponse(f'/admin/activation-keys?key={key}&erro=Falha+ao+criar+usuário', 303)
    c.close()
    return RedirectResponse(f'/admin/activation-keys?key={key}&ok=Usuário+{username}+criado+com+sucesso', 303)


_add_priority_route('/admin/activation-keys', activation_page, ['GET'])
_add_priority_route('/admin/activation-keys/create-base2', create_base2_user, ['POST'])
